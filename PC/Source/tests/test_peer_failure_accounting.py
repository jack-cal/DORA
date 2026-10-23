"""Real socket failures must schedule exactly one learned-peer retry."""
import asyncio
from pathlib import Path
import tempfile
import unittest

from sumuww.peer import PeerNode


class LearnedFailureTests(unittest.IsolatedAsyncioTestCase):
    async def test_one_silent_handshake_counts_one_failure(self):
        with tempfile.TemporaryDirectory() as root:
            writers = []
            def silent(reader, writer):
                writers.append(writer)
            server = await asyncio.start_server(silent, '127.0.0.1', 0)
            target = server.sockets[0].getsockname()[:2]
            node = PeerNode(Path(root)/'client.sqlite', timeout=.1,
                            discover_peers=False, dht_enabled=False,
                            discovery_scope='loopback')
            try:
                await node.start()
                node._addresses.verified(target)
                await node._discovered_connection(target)
                self.assertEqual(1, node._stats['reconnect_attempts'])
                entry = node._addresses._entries[target]
                self.assertEqual(1, entry.failures)
                self.assertAlmostEqual(10, entry.retry_at-entry.attempted_at)
                self.assertFalse(node.synchronization_info()['mining_ready'])
                self.assertIn(target, node._addresses.known())
            finally:
                await node.stop()
                for writer in writers:
                    writer.close()
                    await writer.wait_closed()
                server.close()
                await server.wait_closed()

    async def test_expired_verified_session_does_not_become_successful_retry(self):
        with tempfile.TemporaryDirectory() as root:
            options = dict(timeout=1, poll_interval=.03, discover_peers=False,
                           dht_enabled=False, discovery_scope='loopback')
            client = PeerNode(Path(root)/'client.sqlite', **options)
            remote = PeerNode(Path(root)/'remote.sqlite', **options)
            task = None
            try:
                await client.start()
                await remote.start()
                task = asyncio.create_task(client._discovered_connection(remote.address))
                async with asyncio.timeout(4):
                    while not client.synchronization_info()['mining_ready']:
                        await asyncio.sleep(.01)
                session = next(iter(client._sessions.values()))
                self.assertTrue(session.cached)
                session.header_requested = True
                session.header_requested_at = asyncio.get_running_loop().time()-60
                # Exercise the same block-response expiry as an unresponsive
                # public peer, without changing consensus or production timers.
                await client._poll_session(session, client.chain.tip_hash, (),
                                           asyncio.get_running_loop().time())
                await asyncio.wait_for(task, 2)
                self.assertEqual('block_response_timeout', session.local_close_reason)
                self.assertEqual(1, client._addresses._entries[remote.address].failures)
                self.assertFalse(client.synchronization_info()['mining_ready'])
            finally:
                if task is not None and not task.done():
                    task.cancel()
                    await asyncio.gather(task, return_exceptions=True)
                await client.stop()
                await remote.stop()
