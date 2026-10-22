"""Discovery through a full hub must not depend on spare slots at the hub."""
import asyncio
from pathlib import Path
import tempfile
import unittest

from sumuww.peer import PeerNode


class FullHubContactTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.nodes = []

    async def asyncTearDown(self):
        await asyncio.gather(*(node.stop() for node in self.nodes))
        self.directory.cleanup()

    def node(self, name, **options):
        node = PeerNode(Path(self.directory.name) / (name + '.sqlite'),
                        poll_interval=.03, timeout=1, discovery_interval=1,
                        discovery_scope='loopback', **options)
        self.nodes.append(node)
        return node

    async def wait(self, predicate, seconds=4):
        deadline = asyncio.get_running_loop().time() + seconds
        while not predicate():
            if asyncio.get_running_loop().time() >= deadline:
                self.fail('Contact did not propagate through the full hub')
            await asyncio.sleep(.02)

    async def test_incoming_listener_reaches_other_peer_without_hub_reverse_dial(self):
        hub = self.node('hub', max_peers=2)
        # Prevent the hub from dialing, as happens when all slots are occupied.
        async def no_dials():
            while hub.running:
                await asyncio.sleep(.05)
        hub._discover = no_dials
        await hub.start()
        hub._next_exploration = float('inf')
        a = self.node('a', peers=[hub.address])
        b = self.node('b', peers=[hub.address])
        await a.start()
        await b.start()
        await self.wait(lambda: len(hub._healthy_sessions()) == 2 and
                        all(s.remote_listener for s in hub._healthy_sessions()))
        self.assertTrue(all(s.outgoing is None for s in hub._sessions.values()))
        self.assertNotIn(b.address, hub._addresses.known())
        await self.wait(lambda: b.address in a._addresses.known())
        self.assertTrue(a.synchronization_info()['mining_ready'])
        self.assertEqual(a.chain.tip_hash, b.chain.tip_hash)
        # Forwarding a claim does not certify it or persist it at the hub.
        self.assertNotIn(b.address, hub._addresses.known())


if __name__ == '__main__':
    unittest.main()
