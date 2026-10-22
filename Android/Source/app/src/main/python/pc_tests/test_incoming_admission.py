"""Real TCP saturation fixtures; no public network or user chain access."""
import asyncio
from pathlib import Path
import tempfile
import unittest

from sumuww.peer import PeerNode
from sumuww.wire import read_frame


class IncomingAdmissionTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.nodes = []
        self.writers = []

    async def asyncTearDown(self):
        for writer in self.writers:
            writer.close()
        await asyncio.gather(*(writer.wait_closed() for writer in self.writers),
                             return_exceptions=True)
        for node in reversed(self.nodes):
            await node.stop()
            self.assertIsNone(node._incoming_probe)
            self.assertFalse(node._incoming_probe_sources)
        self.directory.cleanup()

    async def node(self, name, **options):
        node = PeerNode(Path(self.directory.name) / (name + '.sqlite'),
                        network='regtest', poll_interval=.02, timeout=.5,
                        discovery_scope='loopback', discovery_interval=1,
                        dht_enabled=False, **options)
        self.nodes.append(node)
        await node.start()
        return node

    async def wait(self, predicate, timeout=5):
        deadline = asyncio.get_running_loop().time() + timeout
        while not predicate():
            self.assertLess(asyncio.get_running_loop().time(), deadline)
            await asyncio.sleep(.01)

    async def saturated(self, size=2):
        server = await self.node('listener', max_peers=size, allow_internet=True)
        anchors = []
        for i in range(size - 1):
            anchors.append(await self.node('anchor-' + str(i),
                                           peers=[server.address], discover_peers=False))
        await self.wait(lambda: len(server._healthy_sessions()) == size - 1)
        return server, anchors

    async def test_full_listener_accepts_validated_newcomer_before_replacing_path(self):
        server, anchors = await self.saturated()
        old = {s.nonce for s in server._healthy_sessions()}
        newcomer = await self.node('newcomer', peers=[server.address])
        deadline = asyncio.get_running_loop().time() + 5
        while server._stats['incoming_replacements'] == 0:
            self.assertTrue(server.synchronization_info()['mining_ready'])
            self.assertLessEqual(len(server._sessions), server.max_peers + 1)
            self.assertLess(asyncio.get_running_loop().time(), deadline)
            await asyncio.sleep(.005)
        await self.wait(lambda: newcomer.synchronization_info()['mining_ready'])
        await self.wait(lambda: len(server._sessions) == 1)
        self.assertEqual({newcomer.nonce}, {s.nonce for s in server._healthy_sessions()})
        self.assertNotEqual(old, {s.nonce for s in server._healthy_sessions()})
        self.assertEqual(1, server._stats['incoming_probes'])

    async def test_idle_new_socket_does_not_evict_anchor_and_probe_is_bounded(self):
        server, anchors = await self.saturated()
        old = {s.nonce for s in server._healthy_sessions()}
        reader, writer = await asyncio.open_connection(*server.address)
        self.writers.append(writer)
        frame = await read_frame(reader, timeout=1, magic=server.network.message_magic)
        self.assertEqual('version', frame.command)
        self.assertIsNotNone(server._incoming_probe)
        # A second simultaneous newcomer cannot allocate another probe.
        reader2, writer2 = await asyncio.open_connection(*server.address)
        self.writers.append(writer2)
        self.assertEqual(b'', await asyncio.wait_for(reader2.read(1), 1))
        self.assertEqual(2, len(server._sessions))
        self.assertEqual(old, {s.nonce for s in server._healthy_sessions()})
        await self.wait(lambda: server._incoming_probe is None)
        self.assertEqual(old, {s.nonce for s in server._healthy_sessions()})
        self.assertEqual(0, server._stats['incoming_replacements'])

    async def test_duplicate_identity_cannot_replace_existing_anchor(self):
        server, anchors = await self.saturated()
        old = {s.nonce for s in server._healthy_sessions()}
        newcomer = await self.node('duplicate')
        newcomer.nonce = anchors[0].nonce
        await newcomer.add_peer(*server.address)
        await self.wait(lambda: server._stats['duplicate_connection_rejections'] > 0)
        self.assertEqual(old, {s.nonce for s in server._healthy_sessions()})
        self.assertEqual(0, server._stats['incoming_replacements'])

    async def test_wrong_network_does_not_replace_anchor(self):
        server, anchors = await self.saturated()
        old = {s.nonce for s in server._healthy_sessions()}
        newcomer = await self.node('wrong-network')
        newcomer.genesis = b'\xff' * 32
        await newcomer.add_peer(*server.address)
        await self.wait(lambda: server._stats['protocol_errors'] > 0)
        self.assertEqual(old, {s.nonce for s in server._healthy_sessions()})
        self.assertEqual(0, server._stats['incoming_replacements'])

    async def test_seven_incoming_anchors_allow_new_process_within_nine_socket_bound(self):
        server, anchors = await self.saturated(8)
        newcomer = await self.node('eighth-newcomer', peers=[server.address])
        await self.wait(lambda: server._stats['incoming_replacements'] == 1)
        await self.wait(lambda: newcomer.nonce in {s.nonce for s in server._healthy_sessions()})
        await self.wait(lambda: len(server._sessions) <= 7)
        self.assertTrue(server.synchronization_info()['mining_ready'])
        self.assertEqual(7, server.info()['peers'])
        self.assertEqual(7, len({r['peer_id'] for r in server.info()['peer_connections']}))

    async def test_replacement_cooldown_preserves_current_anchors(self):
        server, anchors = await self.saturated()
        other = await self.node('handoff-backup', discover_peers=False)
        server._addresses.add_hint(other.address)
        await self.wait(lambda: other.nonce in {s.nonce for s in server._healthy_sessions()})
        old = {s.nonce for s in server._healthy_sessions()}
        server._next_incoming_rotation = server._peer_clock() + 60
        newcomer = await self.node('waiting-newcomer', peers=[server.address])
        await self.wait(lambda: server._stats['incoming_handoffs'] == 1)
        await self.wait(lambda: server._incoming_probe is None)
        self.assertEqual(0, server._stats['incoming_replacements'])
        self.assertEqual(old, {s.nonce for s in server._healthy_sessions()})
        self.assertGreaterEqual(newcomer._stats['address_hints_received'], 1)
        await self.wait(lambda: other.nonce in {s.nonce for s in newcomer._healthy_sessions()})

    async def test_unverified_probe_expires_without_retiring_any_anchor(self):
        server, anchors = await self.saturated()
        old = {s.nonce for s in server._healthy_sessions()}
        reader, writer = await asyncio.open_connection(*server.address)
        self.writers.append(writer)
        await read_frame(reader, timeout=1, magic=server.network.message_magic)
        server._incoming_probe_deadline = 0
        await self.wait(lambda: server._stats['incoming_probe_expirations'] == 1)
        self.assertEqual(old, {s.nonce for s in server._healthy_sessions()})
        self.assertEqual(0, server._stats['incoming_replacements'])

    async def test_new_outgoing_connection_still_uses_reserved_slot(self):
        server, anchors = await self.saturated()
        other = await self.node('outbound-backup', discover_peers=False)
        server._addresses.add_hint(other.address)
        await self.wait(lambda: other.nonce in {s.nonce for s in server._healthy_sessions()})
        self.assertEqual(2, server.info()['peers'])
        self.assertEqual(0, server._stats['incoming_replacements'])

    async def test_one_source_retry_does_not_lock_out_another_source(self):
        server, anchors = await self.saturated()
        reader, writer = await asyncio.open_connection(*server.address)
        self.writers.append(writer)
        await read_frame(reader, timeout=1, magic=server.network.message_magic)
        writer.close()
        await self.wait(lambda: server._incoming_probe is None)
        await asyncio.sleep(.3)
        same_reader, same_writer = await asyncio.open_connection(*server.address)
        self.writers.append(same_writer)
        self.assertEqual(b'', await asyncio.wait_for(same_reader.read(1), 1))
        other_reader, other_writer = await asyncio.open_connection(
            *server.address, local_addr=('127.0.0.2', 0))
        self.writers.append(other_writer)
        frame = await read_frame(other_reader, timeout=1, magic=server.network.message_magic)
        self.assertEqual('version', frame.command)
        self.assertEqual(0, server._stats['incoming_replacements'])

    async def test_public_budget_keeps_ten_distinct_clients_without_rotation(self):
        server = await self.node('public-budget', max_peers=32, outgoing_target=8,
                                 allow_internet=True)
        clients = [await self.node('budget-client-' + str(i),
                                   peers=[server.address], discover_peers=False)
                   for i in range(10)]
        await self.wait(lambda: len(server._healthy_sessions()) == 10)
        await asyncio.sleep(.3)
        self.assertEqual(24, server.info()['incoming_capacity'])
        self.assertEqual(10, server.info()['peers'])
        self.assertEqual({c.nonce for c in clients}, {s.nonce for s in server._healthy_sessions()})
        self.assertEqual(0, server._stats['incoming_probes'])
        self.assertEqual(0, server._stats['incoming_evictions'])

    async def test_pending_incoming_probe_does_not_block_outgoing_backup(self):
        server, anchors = await self.saturated()
        reader, writer = await asyncio.open_connection(*server.address)
        self.writers.append(writer)
        await read_frame(reader, timeout=1, magic=server.network.message_magic)
        other = await self.node('backup-during-probe', discover_peers=False)
        server._addresses.add_hint(other.address)
        await self.wait(lambda: other.nonce in {s.nonce for s in server._healthy_sessions()})
        self.assertLessEqual(len(server._sessions), server.max_peers + 1)
        self.assertEqual(0, server._stats['incoming_replacements'])

    async def test_connection_burst_keeps_one_probe_and_existing_anchors(self):
        server, anchors = await self.saturated(8)
        identities = {s.nonce for s in server._healthy_sessions()}
        burst = asyncio.gather(*(asyncio.open_connection(*server.address)
                                 for _ in range(32)))
        deadline = asyncio.get_running_loop().time() + 20
        while not burst.done():
            self.assertLessEqual(len(server._sessions), server.max_peers + 1)
            self.assertEqual(identities, {s.nonce for s in server._healthy_sessions()})
            self.assertLess(asyncio.get_running_loop().time(), deadline)
            await asyncio.sleep(.01)
        clients = await burst
        self.writers.extend(writer for _, writer in clients)
        await asyncio.sleep(.05)
        self.assertGreaterEqual(server._stats['incoming_probes'], 1)
        self.assertLessEqual(len(server._sessions), server.max_peers + 1)
        self.assertEqual(identities, {s.nonce for s in server._healthy_sessions()})
        self.assertEqual(0, server._stats['incoming_replacements'])
        self.assertGreaterEqual(server._stats['peer_limit_rejections'],
                                32 - server._stats['incoming_probes'])
