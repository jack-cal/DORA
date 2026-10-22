"""Replay a full listener's address handoff, using actual owned TCP only."""
import asyncio
import socket
import struct
import sys
from pathlib import Path
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock

from sumuww.peer import PeerNode


class ShortSyncedReconnectTests(unittest.IsolatedAsyncioTestCase):
    async def test_only_recent_validated_remote_close_marks_bounded_grace(self):
        with tempfile.TemporaryDirectory() as folder:
            node = PeerNode(Path(folder)/'policy.sqlite', dht_enabled=False)
            node._peer_clock = lambda: 100
            def session(**overrides):
                fields = dict(outgoing=('127.0.0.1', 21000), ready=True,
                              verified_once=True, synchronized=True,
                              writer=SimpleNamespace(is_closing=lambda: False),
                              local_close_reason=None,
                              initial_discovery_deferred=False,
                              last_address_reply_at=99.9, diagnostic_started_at=90)
                fields.update(overrides)
                return SimpleNamespace(**fields)
            try:
                for invalid in (dict(ready=False), dict(verified_once=False),
                                dict(synchronized=False), dict(outgoing=None),
                                dict(last_address_reply_at=None),
                                dict(last_address_reply_at=90),
                                dict(diagnostic_started_at=60),
                                dict(local_close_reason='poll_send_failed'),
                                dict(writer=SimpleNamespace(is_closing=lambda: True))):
                    with self.subTest(invalid=invalid):
                        node._short_session_grace.clear()
                        node._remember_short_synced_close(session(**invalid))
                        self.assertFalse(node._short_session_grace)
                closing = SimpleNamespace(is_closing=lambda: True)
                for error in (None, BrokenPipeError(), OSError()):
                    node._remember_short_synced_close(session(writer=closing), transport_error=error)
                    self.assertFalse(node._short_session_grace)
                for invalid in (dict(verified_once=False), dict(synchronized=False),
                                dict(local_close_reason='poll_send_failed'),
                                dict(last_address_reply_at=90)):
                    node._remember_short_synced_close(session(writer=closing, **invalid),
                                                       transport_error=ConnectionResetError(104, 'peer reset'))
                    self.assertFalse(node._short_session_grace)
                node._remember_short_synced_close(session(writer=closing),
                                                   transport_error=ConnectionResetError(104, 'peer reset'))
                self.assertIn(('127.0.0.1', 21000), node._short_session_grace)
                for port in range(21000, 21140):
                    node._remember_short_synced_close(session(outgoing=('127.0.0.1', port)))
                self.assertEqual(128, len(node._short_session_grace))
                node._peer_clock = lambda: 191
                node._remember_short_synced_close(session(last_address_reply_at=190.9,
                                                          diagnostic_started_at=185))
                self.assertEqual(128, len(node._short_session_grace))
                self.assertEqual(191, node._short_session_grace[('127.0.0.1', 21000)])
            finally:
                await node.stop()

    async def test_cold_contacts_other_targets_and_block_sync_are_not_delayed(self):
        with tempfile.TemporaryDirectory() as folder:
            node = PeerNode(Path(folder)/'scope.sqlite', dht_enabled=False)
            node._peer_clock = lambda: 100
            node._send = AsyncMock()
            def session(target):
                return SimpleNamespace(outgoing=target, protocol=3,
                    address_response_count=0, diagnostic_started_at=99,
                    initial_discovery_deferred=False, discovery_requested=False,
                    last_discovery_request=0, ready=True, header_requested=False,
                    headers=(), hint_requested=None, hint_blocks=(), branch_tip=None,
                    unknown_blocks=set())
            target=('127.0.0.1',21000)
            try:
                cold=session(target)
                await node._request_addresses(cold)
                self.assertEqual('getaddr', node._send.await_args.args[1])
                node._short_session_grace[target]=190
                deferred=session(target)
                node._send.reset_mock()
                await node._request_addresses(deferred)
                node._send.assert_not_awaited()
                # An old marker survives admission waits; it is not a claim
                # that the peer is live and does not delay another endpoint.
                node._short_session_grace[target] = 99
                await node._request_addresses(deferred)
                node._send.assert_not_awaited()
                admitted_new = session(target)
                await node._request_addresses(admitted_new)
                self.assertTrue(admitted_new.initial_discovery_deferred)
                node._send.assert_not_awaited()
                node._send.reset_mock()
                await node._request_addresses(deferred)
                node._send.assert_not_awaited()
                await node._request_headers(deferred)
                self.assertEqual('getheaders',node._send.await_args.args[1])
                other=session(('127.0.0.1',21001))
                await node._request_addresses(other)
                self.assertEqual('getaddr',node._send.await_args.args[1])
                deferred.diagnostic_started_at=69
                await node._request_addresses(deferred)
                self.assertEqual('getaddr',node._send.await_args.args[1])
                self.assertNotIn(target,node._short_session_grace)
            finally:
                await node.stop()

    async def test_address_handoff_retry_keeps_data_sync_until_rotation_opens(self):
        await self._exercise_handoff(reset=False)

    async def test_reset_handoff_retry_keeps_data_sync_until_rotation_opens(self):
        await self._exercise_handoff(reset=True)

    async def test_admission_wait_does_not_expire_pending_recovery(self):
        await self._exercise_handoff(reset=False, admission_wait=122)

    async def test_repeated_handoff_after_quiet_window_can_retry_again(self):
        await self._exercise_handoff(reset=False, extra_handoff=True)

    async def _exercise_handoff(self, *, reset, admission_wait=0, extra_handoff=False):
        nodes = []
        second = None
        with tempfile.TemporaryDirectory() as folder:
            async def make(name, **overrides):
                options = dict(network='regtest', allow_internet=True,
                               discovery_scope='loopback', dht_enabled=False,
                               auto_address=False, poll_interval=.02, timeout=5)
                options.update(overrides)
                node = PeerNode(Path(folder)/(name+'.sqlite'), **options)
                async def no_background_dials():
                    while node.running:
                        await asyncio.sleep(.05)
                node._discover = no_background_dials
                nodes.append(node)
                await node.start()
                return node

            async def until(predicate, seconds=3):
                async with asyncio.timeout(seconds):
                    while not predicate():
                        await asyncio.sleep(.01)

            try:
                server = await make('full-listener', max_peers=2, outgoing_target=1)
                anchor = await make('old-anchor', peers=[server.address], discover_peers=False)
                await until(lambda: len(server._healthy_sessions()) == 1)
                self.assertEqual(1, server._incoming_capacity())
                server._next_incoming_rotation = server._peer_clock() + 60
                client = None
                maintain = server._maintain_incoming_probe
                def controlled_handoff():
                    candidate = server._incoming_probe
                    if (candidate is not None and candidate.address_reply_sent
                            and candidate.synchronized
                            and server._peer_clock() < server._next_incoming_rotation):
                        # Isolate a close AFTER the client's validated addr.
                        # TCP scheduling must not turn this into a different
                        # before-addr test on a slow physical phone.
                        if client is None or not any(s.synchronized and s.last_address_reply_at is not None
                                                     for s in client._sessions.values()):
                            return
                        if reset:
                            def abort():
                                sock = candidate.writer.get_extra_info('socket')
                                sock.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER,
                                    struct.pack('hh' if sys.platform == 'win32' else 'ii', 1, 0))
                                candidate.writer.transport.abort()
                            candidate.writer.close = abort
                    maintain()
                server._maintain_incoming_probe = controlled_handoff
                client = await make('mobile-retry')
                target = server.address
                client._addresses.add_hint(target)
                # Real source behavior: a synchronized v3 newcomer learns
                # addresses, then loses the provisional slot during cooldown.
                await client._discovered_connection(target)
                self.assertEqual(1, server._stats['incoming_handoffs'])
                self.assertGreater(client._stats['address_responses_sent'], 0)
                self.assertEqual(0, client.info()['peers'])
                self.assertIn(target, client._short_session_grace)
                if reset and sys.platform != 'win32':
                    self.assertTrue(any('ConnectionResetError' in row.get('error', '')
                                        for row in client._recent_peer_attempts),
                                    list(client._recent_peer_attempts))
                # Admission timing is a separate fixture variable: let this
                # second attempt enter, preserving the rotation cooldown.
                server._next_incoming_probe = 0
                server._incoming_probe_sources.clear()
                if admission_wait:
                    clock = client._peer_clock
                    client._peer_clock = lambda: clock() + admission_wait
                second = asyncio.create_task(client._discovered_connection(target))
                await until(lambda: client.info()['synchronized_peers'] == 1)
                session = next(iter(client._healthy_sessions()))
                self.assertEqual(3, session.protocol)
                self.assertFalse(second.done())
                self.assertEqual(1, server._stats['incoming_handoffs'])
                self.assertTrue(session.initial_discovery_deferred)
                await asyncio.sleep(.1)
                self.assertFalse(second.done())
                if extra_handoff:
                    session.diagnostic_started_at -= 31
                    await until(second.done)
                    self.assertIn(target, client._short_session_grace)
                    server._next_incoming_probe = 0
                    server._incoming_probe_sources.clear()
                    second = asyncio.create_task(client._discovered_connection(target))
                    await until(lambda: client.info()['synchronized_peers'] == 1)
                    session = next(iter(client._healthy_sessions()))
                    self.assertTrue(session.initial_discovery_deferred)
                # Open the fixture's rotation gate explicitly, avoiding a
                # wall-clock race with CPU-heavy APK compilation or CI load.
                server._next_incoming_rotation = 0
                await until(lambda: server._stats['incoming_replacements'] == 1)
                # Expire only this fixture's local grace age. Address exchange
                # must resume on the same validated TCP connection afterward.
                previous = session.address_response_count
                session.diagnostic_started_at -= 31
                await until(lambda: session.address_response_count > previous)
                self.assertIs(session, next(iter(client._healthy_sessions())))
                self.assertFalse(second.done())
                self.assertEqual(0, client._stats['legacy_fallbacks'])
            finally:
                if second:
                    second.cancel()
                    await asyncio.gather(second, return_exceptions=True)
                for node in reversed(nodes):
                    await node.stop()
