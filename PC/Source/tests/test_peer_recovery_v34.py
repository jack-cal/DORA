"""Bounded retries and listener recovery on owned regtest/loopback fixtures.

Windows tests inject one failure into the real Proactor accept callback. No
public endpoint, user wallet, user database, or configured port is inspected.
"""
import asyncio
import errno
from pathlib import Path
import socket
import tempfile
import unittest
from unittest.mock import patch

from sumuww import peer
from sumuww.peer_discovery import PeerAddressBook
from sumuww.wallet import RegtestKey


async def eventually(predicate, timeout=3):
    deadline = asyncio.get_running_loop().time() + timeout
    while not predicate():
        if asyncio.get_running_loop().time() >= deadline:
            raise AssertionError('Owned listener recovery deadline')
        await asyncio.sleep(.005)


class RetryCapTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='sumuww-owned-retry-cap-')
        self.addCleanup(self.temporary.cleanup)
        self.now = 1000.
        self.book = PeerAddressBook(Path(self.temporary.name) / 'peers.json',
                                    'owned-fixture', bytes(32), scope='loopback',
                                    retry_clock=lambda: self.now)
        self.endpoint = ('127.0.0.1', 23456)
        self.book.add_hint(self.endpoint)

    def test_disconnected_cap_preserves_full_connected_backoff(self):
        self.book.attempted(self.endpoint)
        self.assertNotIn(self.endpoint,self.book._entries)
        self.assertIsNone(self.book.candidate())
        self.assertIsNone(self.book.candidate(retry_cap=15))
        self.now+=61;self.book.prune()
        self.assertTrue(self.book.add_hint(self.endpoint))
        self.assertEqual(self.endpoint,self.book.candidate())

    def test_repeated_hints_cannot_reset_disconnected_backoff(self):
        self.book.attempted(self.endpoint)
        for second in range(60):
            self.now=1000.+second
            self.assertFalse(self.book.add_hint(self.endpoint))
            self.assertIsNone(self.book.candidate(retry_cap=15))
        self.now=1061.;self.book.prune()
        self.assertTrue(self.book.add_hint(self.endpoint))
        self.assertEqual(self.endpoint,self.book.candidate())

    def test_short_initial_failure_and_success_delays_still_apply(self):
        self.book.attempted(self.endpoint)
        self.assertNotIn(self.endpoint,self.book._entries)
        self.book.verified(self.endpoint)
        self.now+=9;self.assertIsNone(self.book.candidate())
        self.now+=1;self.assertEqual(self.endpoint,self.book.candidate())
        self.book.attempted(self.endpoint,success=True)
        self.now+=4;self.assertIsNone(self.book.candidate())
        self.now+=1;self.assertEqual(self.endpoint,self.book.candidate())


class PeerRecoveryTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='sumuww-owned-listener-recovery-')
        self.folder = Path(self.temporary.name)
        self.nodes = []
        self.raw_sockets = []

    async def asyncTearDown(self):
        for sock in self.raw_sockets:
            sock.close()
        await asyncio.gather(*(node.stop() for node in self.nodes), return_exceptions=True)
        self.temporary.cleanup()

    def node(self, name, **extra):
        options = {'network': 'regtest', 'host': '127.0.0.1', 'port': 0,
                   'timeout': 1, 'poll_interval': .03, 'discover_peers': False,
                   'dht_enabled': False}
        options.update(extra)
        node = peer.PeerNode(self.folder / (name + '.sqlite'), **options)
        self.nodes.append(node)
        return node

    async def test_closed_listener_rebinds_same_port_and_preserves_bidirectional_sessions(self):
        source, other, newcomer = (self.node(name) for name in ('source', 'other', 'newcomer'))
        await source.start()
        await other.start()
        await source.connect(*other.address)
        await other.connect(*source.address)
        await eventually(lambda: source.synchronization_info()['mining_ready'] and
                         other.synchronization_info()['mining_ready'] and len(source._sessions) == 1)
        address = source.address
        original = source._server
        sessions = set(source._sessions)
        original.close()
        self.assertFalse(source.info()['listener_active'])
        self.assertEqual('TCP listener unavailable', source.info()['listener_error'])
        self.assertTrue(source.synchronization_info()['mining_ready'])
        await eventually(lambda: source.info()['listener_restarts'] == 1 and source._listener_active())
        self.assertEqual(address, source.address)
        self.assertIsNot(original, source._server)
        self.assertEqual(sessions, set(source._sessions))
        self.assertIsNone(source.info()['listener_error'])
        await newcomer.start()
        await newcomer.connect(*address)
        await eventually(lambda: newcomer.synchronization_info()['mining_ready'] and
                         source.synchronization_info()['mining_ready'])
        source.chain.mine(RegtestKey.from_int(3401).script_pubkey, 1)
        await eventually(lambda: other.chain.tip_hash == source.chain.tip_hash and
                         newcomer.chain.tip_hash == source.chain.tip_hash)
        self.assertEqual(1, newcomer.chain.info()['height'])

    async def test_last_ready_peer_loss_uses_capped_tcp_retry_for_existing_candidate(self):
        standby, replacement = self.node('standby'), self.node('replacement')
        client = self.node('client', discover_peers=True, discovery_scope='loopback')
        await standby.start()
        await replacement.start()
        now = [1000.]
        client._addresses.retry_clock = lambda: now[0]
        target = replacement.address
        client._addresses.add_hint(target)
        for _ in range(3):
            client._addresses.attempted(target)
        await client.start()
        await client.connect(*standby.address)
        await eventually(lambda: client.synchronization_info()['mining_ready'])
        now[0] += 15
        await asyncio.sleep(.15)
        self.assertFalse(any(session.outgoing == target for session in client._sessions.values()))
        self.assertNotIn(target,client._addresses._entries)
        await standby.stop()
        # Deletion ends automatic retries until a fresh, unsuppressed hint arrives.
        now[0]+=46
        self.assertTrue(client._addresses.add_hint(target))
        await eventually(lambda: client.synchronization_info()['mining_ready'] and
                         any(session.ready and session.outgoing == target for session in client._sessions.values()))
        self.assertEqual(0, client._addresses._entries[target].failures)

    async def _proactor_failure(self, cancelled):
        loop = asyncio.get_running_loop()
        if not hasattr(loop, '_proactor'):
            self.skipTest('Windows Proactor accept callback required')
        source, newcomer = self.node('source'), self.node('newcomer')
        gate = asyncio.Event()
        original_guard = source._maintain_listener

        async def guarded():
            await gate.wait()
            await original_guard()

        source._maintain_listener = guarded
        original_accept = loop._proactor.accept
        failed = []
        contexts = []
        previous_handler = loop.get_exception_handler()

        def handler(event_loop, context):
            if context.get('message') == 'Accept failed on a socket':
                contexts.append(context)
            elif previous_handler is not None:
                previous_handler(event_loop, context)
            else:
                event_loop.default_exception_handler(context)

        def fail_once(sock):
            if not failed and sock.getsockname()[0] == '127.0.0.1':
                failed.append(sock)
                future = loop.create_future()
                if cancelled:
                    future.cancel()
                else:
                    future.set_exception(OSError(errno.ECONNABORTED, 'owned accept fault'))
                return future
            return original_accept(sock)

        loop.set_exception_handler(handler)
        try:
            with patch.object(loop._proactor, 'accept', side_effect=fail_once):
                await source.start()
                address = source.address
                await eventually(lambda: bool(failed) and failed[0].fileno() == -1)
                self.assertTrue(source._server.is_serving(), 'Reproduce stale Server serving flag')
                self.assertFalse(source.info()['listener_active'])
                if not cancelled:
                    self.assertEqual(1, len(contexts))
                gate.set()
                await eventually(lambda: source._listener_restarts == 1 and source._listener_active())
                self.assertEqual(address, source.address)
                await newcomer.start()
                await newcomer.connect(*address)
                await eventually(lambda: newcomer.synchronization_info()['mining_ready'] and
                                 source.synchronization_info()['mining_ready'])
        finally:
            gate.set()
            loop.set_exception_handler(previous_handler)

    async def test_windows_proactor_oserror_closed_socket_recovers(self):
        await self._proactor_failure(cancelled=False)

    async def test_windows_proactor_cancelled_accept_closed_socket_recovers(self):
        await self._proactor_failure(cancelled=True)

    async def test_occupied_recovery_port_retains_address_and_bounds_retry(self):
        node = self.node('occupied')
        await node.start()
        address = node.address
        node._server.close()
        blocker = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.raw_sockets.append(blocker)
        if hasattr(socket, 'SO_EXCLUSIVEADDRUSE'):
            blocker.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        blocker.bind(address)
        blocker.listen(1)
        original_start = asyncio.start_server
        attempts = []

        async def record(callback, *endpoint, **options):
            attempts.append(endpoint)
            return await original_start(callback, *endpoint, **options)

        with patch('sumuww.peer.LISTENER_RETRY_INTERVAL', .2), \
                patch('sumuww.peer.LISTENER_POLL_INTERVAL', .01), \
                patch('sumuww.peer.asyncio.start_server', side_effect=record):
            await node._recover_listener()
            self.assertEqual(address, node.address)
            self.assertFalse(node.info()['listener_active'])
            self.assertTrue(node.info()['listener_error'].startswith('OSError:'))
            self.assertFalse(node.synchronization_info()['mining_ready'])
            for _ in range(5):
                await node._recover_listener()
            self.assertEqual([address], attempts)
            blocker.close()
            await eventually(lambda: node._listener_active() and node._listener_restarts == 1)
            self.assertEqual([address, address], attempts)
            self.assertEqual(1, node.info()['listener_restarts'])

    async def test_stop_during_bound_listener_activation_closes_candidate(self):
        node = self.node('stop-race')
        await node.start()
        address = node.address
        node._server.close()
        entered = asyncio.Event()
        release = asyncio.Event()
        candidates = []
        original_start = asyncio.base_events.Server.start_serving

        async def delayed(server):
            candidates.append(server)
            await original_start(server)
            entered.set()
            await release.wait()

        with patch.object(asyncio.base_events.Server, 'start_serving', delayed):
            recovery = node._spawn(node._recover_listener(), 'owned-recovery-stop-race')
            await asyncio.wait_for(entered.wait(), 1)
            await asyncio.wait_for(node.stop(), 1)
            release.set()
            await asyncio.gather(recovery, return_exceptions=True)
        self.assertEqual(1, len(candidates))
        self.assertFalse(candidates[0].is_serving())
        self.assertFalse(candidates[0].sockets)
        self.assertIsNone(node._server)
        self.assertFalse(node.running)
        self.assertEqual(0, node._listener_restarts)
        await node._recover_listener()
        self.assertIsNone(node._server)
        with self.assertRaises(OSError):
            await asyncio.wait_for(asyncio.open_connection(*address), .5)


if __name__ == '__main__':
    unittest.main()
