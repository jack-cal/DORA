"""Real local fixtures; no live public peers, user profile or wallet data."""

import asyncio
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from sumuww.peer import PeerNode
from sumuww.peer_discovery import PeerAddressBook, discovery_endpoint
from sumuww.wallet import RegtestKey
from sumuww.__main__ import create_payment
from sumuww.node_manager import probe_peer
from sumuww.primitives import COIN
from sumuww.wire import (DISCOVERY_PROTOCOL_VERSION, PeerAddress, ProtocolError, Version,
                       decode_addresses, decode_version, encode_addresses, encode_headers,
                       encode_version, read_frame, write_frame)


WORK = Path(os.environ.get('SUMUWW_TEST_WORKDIR', tempfile.gettempdir()))


async def eventually(predicate, timeout=15):
    end = asyncio.get_running_loop().time() + timeout
    while not predicate():
        if asyncio.get_running_loop().time() >= end:
            raise AssertionError('Discovery fixture did not reach its expected state')
        await asyncio.sleep(.04)


class AddressValidationTests(unittest.TestCase):
    def setUp(self):
        WORK.mkdir(parents=True, exist_ok=True)
        self.directory = tempfile.TemporaryDirectory(prefix='discovery-book-', dir=WORK)
        self.path = Path(self.directory.name) / 'fixture.peers.json'

    def tearDown(self):
        self.directory.cleanup()

    def book(self, **options):
        return PeerAddressBook(self.path, 'fixture', bytes(32), **options)

    def test_public_scope_rejects_private_reserved_loopback_and_dns_hints(self):
        for host in ('127.0.0.1', '10.0.0.1', '192.168.1.1', '172.16.1.1',
                     '169.254.1.1', '192.0.2.1', '198.18.0.1', '100.64.0.1',
                     '0.0.0.0', '224.0.0.1', '255.255.255.255', 'example.org'):
            with self.subTest(host=host), self.assertRaises(ValueError):
                discovery_endpoint(host, 18444)
        self.assertEqual(('8.8.8.8', 18444), discovery_endpoint('8.8.8.8', 18444))

    def test_only_successfully_synced_endpoints_persist_and_foreign_cache_is_discarded(self):
        book = self.book(scope='loopback')
        book.add_hint(('127.0.0.1', 10001))
        self.assertFalse(self.path.exists())
        book.verified(('127.0.0.1', 10002))
        stored = json.loads(self.path.read_text(encoding='utf-8'))
        self.assertEqual([10002], [item['port'] for item in stored['peers']])
        reloaded = self.book(scope='loopback')
        self.assertEqual((('127.0.0.1', 10002),), reloaded.known())
        stored['genesis'] = 'ff' * 32
        self.path.write_text(json.dumps(stored), encoding='utf-8')
        rejected = self.book(scope='loopback')
        self.assertEqual((), rejected.known())
        self.assertIsNotNone(rejected.load_error)

    def test_new_candidates_have_no_count_cap_and_do_not_evict_verified_peer(self):
        book = self.book(scope='loopback')
        book.verified(('127.0.0.1', 10000))
        for port in range(10001, 10300):
            book.add_hint(('127.0.0.1', port))
        self.assertEqual(300,book.info()['candidates'])
        self.assertIsNone(book.info()['maximum'])
        self.assertIn(('127.0.0.1', 10000), book.known())
        self.assertEqual(1, len(json.loads(self.path.read_text(encoding='utf-8'))['peers']))

    def test_malformed_and_oversized_cache_is_rejected_without_using_hints(self):
        for content in ('[1,2,3]', '{', 'x' * (64 * 1024 + 1)):
            self.path.write_text(content, encoding='utf-8')
            book = self.book()
            self.assertEqual(0, book.info()['candidates'])
            self.assertIsNotNone(book.load_error)

    def test_wire_addresses_enforce_per_message_bound_duplicate_and_trailing_bytes(self):
        listener = PeerAddress('127.0.0.1', 10001)
        peers = tuple(PeerAddress('127.0.0.1', 11000 + index) for index in range(31))
        self.assertEqual((listener, peers), decode_addresses(encode_addresses(listener, peers)))
        for args in ((listener, peers + (PeerAddress('127.0.0.1', 12000),)),
                     (listener, (listener,))):
            with self.assertRaises(ProtocolError):
                encode_addresses(*args)
        raw = encode_addresses(listener, peers)
        for data in (raw[:-1], raw + b'\0', b'\x02\0', b'\0\x21'):
            with self.assertRaises(ProtocolError):
                decode_addresses(data)


class PeerDiscoverySocketTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        WORK.mkdir(parents=True, exist_ok=True)
        self.directory = tempfile.TemporaryDirectory(prefix='discovery-sockets-', dir=WORK)
        self.nodes = []
        self.writers = []

    async def asyncTearDown(self):
        for writer in self.writers:
            writer.close()
        await asyncio.gather(*(node.stop() for node in self.nodes), return_exceptions=True)
        self.directory.cleanup()

    def node(self, name, **options):
        options.setdefault('discovery_scope', 'loopback')
        node = PeerNode(Path(self.directory.name) / (name + '.sqlite'),
                        poll_interval=.05, timeout=2, discovery_interval=1, **options)
        self.nodes.append(node)
        return node

    async def test_incoming_occupancy_cannot_starve_later_automatic_outgoing_sync(self):
        # Two total slots are enough to reproduce the old failure: two incoming
        # peers previously blocked all dialing of a subsequently learned hint.
        alice,bob=RegtestKey.from_int(1),RegtestKey.from_int(2)
        honest=self.node('honest-later-hint',discover_peers=False)
        honest.chain.mine(alice.script_pubkey,100)
        await honest.start()
        victim=self.node('automatic-capacity',allow_internet=True,max_peers=2)
        await victim.start()
        incoming=self.node('ordinary-incoming',discover_peers=False)
        await incoming.start();await incoming.connect(*victim.address)
        await eventually(lambda:victim.synchronization_info()['mining_ready'])
        reader,writer=await asyncio.open_connection(*victim.address)
        self.writers.append(writer)
        # Full listeners now admit one bounded newcomer without consuming
        # the opportunity to establish an outgoing backup.
        frame = await read_frame(reader, timeout=2, magic=victim.network.message_magic)
        self.assertEqual('version', frame.command)
        self.assertEqual(1,victim.info()['incoming_capacity'])
        self.assertEqual(2,len(victim._sessions))
        self.assertFalse(victim._configured)
        self.assertTrue(victim._addresses.add_hint(honest.address))
        await eventually(lambda:victim.chain.info()['height']==100 and
                         victim.synchronization_info()['mining_ready'])
        await eventually(lambda:victim._incoming_probe is None)
        self.assertEqual(1,sum(session.outgoing is not None for session in victim._sessions.values()))
        self.assertEqual(1,sum(session.outgoing is None for session in victim._sessions.values()))
        transaction=create_payment(victim.chain,alice,bob.script_pubkey,COIN,1000)
        victim.chain.submit_transaction(transaction)
        await eventually(lambda:any(tx.txid()==transaction.txid() for tx in honest.chain.mempool_transactions()))
        honest.chain.mine(alice.script_pubkey,1)
        await eventually(lambda:victim.chain.info()['height']==101)
        self.assertEqual(COIN,victim.chain.balance(bob.script_pubkey))
        self.assertEqual(victim.chain.tip_hash,honest.chain.tip_hash)

    async def test_automatic_outgoing_and_monitor_queries_keep_existing_peers_ready(self):
        ordinary=self.node('ordinary-monitor-companion',discover_peers=False)
        await ordinary.start()
        automatic=self.node('automatic-monitor-target',allow_internet=True)
        await automatic.start()
        self.assertTrue(automatic._addresses.add_hint(ordinary.address))
        await eventually(lambda:automatic.synchronization_info()['mining_ready'])
        before=tuple(id(session) for session in automatic._sessions.values() if session.ready)
        original_send=PeerNode._send
        async def delayed_ack(node,session,command,payload=b''):
            if node is automatic and command=='verack' and session.outgoing is None:
                await asyncio.sleep(.15)
            return await original_send(node,session,command,payload)
        endpoint=f'{automatic.address[0]}:{automatic.address[1]}'
        with patch.object(PeerNode,'_send',delayed_ack):
            queries=asyncio.gather(*(probe_peer(endpoint,network='regtest',timeout=2) for _ in range(3)))
            while not queries.done():
                self.assertTrue(automatic.synchronization_info()['mining_ready'])
                await asyncio.sleep(.01)
            self.assertEqual(['reachable']*3,[item['status'] for item in await queries])
        await eventually(lambda:len(automatic._sessions)==len(before))
        self.assertEqual(before,tuple(id(session) for session in automatic._sessions.values() if session.ready))
        self.assertTrue(automatic.synchronization_info()['mining_ready'])

    async def test_three_nodes_learn_peers_survive_seed_retirement_and_restart_from_cache(self):
        seed = self.node('seed')
        await seed.start()
        b, c = self.node('b', peers=(seed.address,)), self.node('c', peers=(seed.address,))
        await b.start()
        await c.start()
        await eventually(lambda: c.address in b._addresses.known() and b.address in c._addresses.known())
        self.assertEqual(1, b.info()['configured_peers'])
        await seed.stop()
        await eventually(lambda: b.synchronization_info()['mining_ready'] and
                         c.synchronization_info()['mining_ready'])
        b.chain.mine(RegtestKey.from_int(19).script_pubkey, 1)
        await eventually(lambda: b.chain.tip_hash == c.chain.tip_hash)
        self.assertEqual(1, c.chain.info()['height'])
        bdb = b.database
        await b.stop()
        restarted = PeerNode(
            bdb, poll_interval=.05, timeout=2, discovery_interval=1, discovery_scope='loopback')
        self.nodes.append(restarted)
        await restarted.start()
        await eventually(lambda: restarted.synchronization_info()['mining_ready'])
        self.assertEqual(0, restarted.info()['configured_peers'])
        self.assertIn(c.address, restarted._addresses.known())
        newcomer = self.node('newcomer', peers=(c.address,))
        await newcomer.start()
        await eventually(lambda: newcomer.synchronization_info()['mining_ready'])
        await eventually(lambda: restarted.address in newcomer._addresses.known())
        self.assertEqual(c.chain.tip_hash, newcomer.chain.tip_hash)
        self.assertGreater(restarted.info()['peers'], 0)

    async def test_default_public_scope_never_dials_advertised_loopback_and_stays_bounded(self):
        server, client = self.node('server'), self.node('client', discovery_scope='public')
        await server.start()
        await client.start()
        await client.connect(*server.address)
        await eventually(lambda: client.info()['stats']['address_hints_rejected'] > 0)
        self.assertEqual(0, client.info()['peer_discovery']['candidates'])
        self.assertFalse(client._addresses.path.exists())

    async def v2_raw(self, node):
        reader, writer = await asyncio.open_connection(*node.address)
        self.writers.append(writer)
        frame = await read_frame(reader, 2)
        version = decode_version(frame.payload)
        await write_frame(writer, 'version', encode_version(Version(
            DISCOVERY_PROTOCOL_VERSION, node.genesis, version.nonce ^ 42,
            node.network.profile_id, node.chain.tip_hash)), 2)
        self.assertEqual('verack', (await read_frame(reader, 2)).command)
        await write_frame(writer, 'verack', b'', 2)
        return reader, writer

    async def test_duplicate_address_reply_does_not_add_hints_or_disconnect(self):
        node = self.node('target')
        await node.start()
        reader, writer = await self.v2_raw(node)
        # Complete its first solicited response, then ignore an immediate
        # duplicate before adding hints, preserving the established transport.
        for _ in range(6):
            frame = await read_frame(reader, 2)
            if frame.command == 'getaddr':
                break
        await write_frame(writer, 'addr', encode_addresses(None), 2)
        await write_frame(writer, 'addr', encode_addresses(PeerAddress('127.0.0.1', 23456)), 2)
        await eventually(lambda: node.info()['stats']['address_rate_rejections'] > 0)
        self.assertEqual(0, node._addresses.info()['verified'])
        self.assertEqual(0, node._addresses.info()['candidates'])
        self.assertEqual(1, node.info()['peers'])
        self.assertFalse(node._addresses.path.exists())

    async def test_address_frame_without_any_earlier_request_is_still_rejected(self):
        node=self.node('never-requested',discover_peers=False)
        await node.start()
        reader,writer=await self.v2_raw(node)
        await write_frame(writer,'addr',encode_addresses(PeerAddress('127.0.0.1',23456)),2)
        await eventually(lambda:node.info()['stats']['protocol_errors']>0)
        self.assertEqual(0,node._addresses.info()['candidates'])
        self.assertFalse(node._addresses.path.exists())

    async def test_actual_legacy_listener_gets_one_bounded_v2_fallback_and_no_extension(self):
        client = self.node('legacy-client')
        attempts = []
        commands = []

        async def legacy(reader, writer):
            self.writers.append(writer)
            try:
                remote = decode_version((await read_frame(reader, 2)).payload)
                attempts.append(remote.protocol)
                own = Version(1, client.genesis, client.nonce ^ 100,
                              client.network.profile_id, client.chain.tip_hash)
                await write_frame(writer, 'version', encode_version(own), 2)
                if remote.protocol != 1:
                    return
                await write_frame(writer, 'verack', b'', 2)
                await read_frame(reader, 2)
                while True:
                    frame = await read_frame(reader, 2)
                    commands.append(frame.command)
                    if frame.command == 'getheaders':
                        await write_frame(writer, 'headers', encode_headers(()), 2)
            except (ProtocolError, OSError):
                pass
            finally:
                writer.close()

        server = await asyncio.start_server(legacy, '127.0.0.1', 0)
        endpoint = server.sockets[0].getsockname()[:2]
        try:
            await client.start()
            await client.connect(*endpoint)
            await eventually(lambda: client.synchronization_info()['mining_ready'])
            self.assertEqual([3, 2, 1], attempts)
            self.assertEqual(2, client.info()['stats']['legacy_fallbacks'])
            self.assertNotIn('getaddr', commands)
            self.assertNotIn('addr', commands)
        finally:
            await client.stop()
            server.close()
            await server.wait_closed()

    async def test_foreign_genesis_does_not_trigger_protocol_downgrade_or_cache(self):
        client = self.node('foreign-client')

        async def foreign(reader, writer):
            self.writers.append(writer)
            try:
                await read_frame(reader, 2)
                await write_frame(writer, 'version', encode_version(Version(
                    1, b'\xff' * 32, 900, client.network.profile_id, client.chain.tip_hash)), 2)
            finally:
                writer.close()

        server = await asyncio.start_server(foreign, '127.0.0.1', 0)
        endpoint = server.sockets[0].getsockname()[:2]
        try:
            await client.start()
            await client.add_peer(*endpoint)
            await eventually(lambda: client.info()['stats']['protocol_errors'] >= 1)
            self.assertEqual(0, client.info()['stats']['legacy_fallbacks'])
            self.assertNotIn(endpoint, client._legacy_targets)
            self.assertFalse(client._addresses.path.exists())
            self.assertFalse(client.synchronization_info()['mining_ready'])
        finally:
            server.close()
            await server.wait_closed()


if __name__ == '__main__':
    unittest.main()
