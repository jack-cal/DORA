import asyncio
import tempfile
import unittest
from pathlib import Path

from sumuww.peer import PeerNode


class ExplorationTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.nodes = []

    async def asyncTearDown(self):
        await asyncio.gather(*(n.stop() for n in self.nodes))
        self.directory.cleanup()

    def node(self, name, **options):
        n = PeerNode(Path(self.directory.name)/(name+'.sqlite'), poll_interval=.05,
                     timeout=1, discovery_scope='loopback', discovery_interval=1, **options)
        self.nodes.append(n)
        return n

    async def wait(self, predicate, timeout=8):
        end = asyncio.get_running_loop().time()+timeout
        while not predicate():
            if asyncio.get_running_loop().time() >= end:
                self.fail('Peer exploration did not converge')
            await asyncio.sleep(.02)

    async def full_client(self):
        a, b = self.node('a', discover_peers=False), self.node('b', discover_peers=False)
        await a.start(); await b.start()
        client = self.node('client', max_peers=2)
        client._addresses.add_hint(a.address); client._addresses.add_hint(b.address)
        await client.start()
        await self.wait(lambda: len(client._healthy_sessions()) == 2)
        return client

    async def test_full_healthy_node_verifies_replacement_before_retiring_old_path(self):
        client = await self.full_client()
        before = set(client._connected_endpoints())
        other = self.node('new', discover_peers=False)
        await other.start()
        client._addresses.add_hint(other.address)
        client._next_exploration = 0
        end = asyncio.get_running_loop().time()+8
        while other.address not in {s.outgoing for s in client._healthy_sessions()} or len(client._sessions)>2:
            self.assertTrue(client.synchronization_info()['mining_ready'])
            self.assertLessEqual(len(client._sessions), 3)
            self.assertLess(asyncio.get_running_loop().time(), end)
            await asyncio.sleep(.02)
        self.assertEqual(2, len(client._healthy_sessions()))
        self.assertTrue(before - client._connected_endpoints())

    async def test_failed_probe_preserves_existing_anchors(self):
        client = await self.full_client()
        before = {s.nonce for s in client._healthy_sessions()}
        server = await asyncio.start_server(lambda r,w:w.close(), '127.0.0.1', 0)
        try:
            client._addresses.add_hint(server.sockets[0].getsockname()[:2])
            client._next_exploration = 0
            await self.wait(lambda: client._next_exploration > 0)
            await self.wait(lambda: client._exploration_target is None)
            self.assertEqual(before, {s.nonce for s in client._healthy_sessions()})
        finally:
            server.close(); await server.wait_closed()

    async def test_manual_only_full_node_explores_without_erasing_preferences(self):
        a, b = self.node('manual-a', discover_peers=False), self.node('manual-b', discover_peers=False)
        await a.start(); await b.start()
        client = self.node('manual-client', max_peers=2, peers=[a.address, b.address])
        await client.start()
        await self.wait(lambda: len(client._healthy_sessions()) == 2)
        preferences = set(client._configured)
        other = self.node('manual-new', discover_peers=False)
        await other.start()
        client._addresses.add_hint(other.address)
        client._next_exploration = 0
        await self.wait(lambda: other.address in {s.outgoing for s in client._healthy_sessions()}
                        and len(client._sessions) == 2)
        self.assertEqual(preferences, set(client._configured))
        self.assertTrue(client.synchronization_info()['mining_ready'])

    async def test_incoming_only_full_node_also_explores(self):
        client = self.node('incoming-client', max_peers=2)
        await client.start()
        a = self.node('incoming-a', peers=[client.address], discover_peers=False)
        b = self.node('incoming-b', peers=[client.address], discover_peers=False)
        await a.start(); await b.start()
        await self.wait(lambda: len(client._healthy_sessions()) == 2)
        self.assertTrue(all(s.outgoing is None for s in client._healthy_sessions()))
        other = self.node('incoming-new', discover_peers=False)
        await other.start()
        client._addresses.add_hint(other.address)
        client._next_exploration = 0
        await self.wait(lambda: other.address in {s.outgoing for s in client._healthy_sessions()}
                        and len(client._sessions) == 2)
        self.assertTrue(client.synchronization_info()['mining_ready'])
