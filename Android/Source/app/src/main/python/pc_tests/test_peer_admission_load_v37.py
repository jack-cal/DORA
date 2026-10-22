"""Bounded native admission, framing and send-backpressure fixtures."""
import asyncio
from collections import Counter
import hashlib
import os
from pathlib import Path
import socket
import tempfile
import time
import unittest
from unittest.mock import patch

WORK = Path(os.environ.get('SUMUWW_TEST_WORKDIR', tempfile.gettempdir()))
from sumuww.peer import PeerNode
from sumuww.primitives import sha256d
from sumuww.wire import (FRAME_HEADER_SIZE, INV_BLOCK, Inventory, PeerDisconnected,
                       ProtocolError, Version, _decode_frame_header, decode_version,
                       encode_frame, encode_headers, encode_inventory, encode_version,
                       read_frame)

METRICS = {}


async def eventually(predicate, timeout=3):
    deadline = asyncio.get_running_loop().time() + timeout
    while not predicate():
        if asyncio.get_running_loop().time() >= deadline:
            raise AssertionError('Owned load fixture deadline')
        await asyncio.sleep(.005)


class Sampler:
    def __init__(self, node):
        self.node = node
        self.task = None
        self.delays = []
        self.values = {'sessions_peak': 0, 'registered_peer_tasks_peak': 0,
                       'server_active_transports_peak': 0, 'ready_sessions_peak': 0,
                       'closing_sessions_peak': 0, 'receive_buffer_total_bytes_peak': 0,
                       'send_buffer_total_bytes_peak': 0, 'all_fixture_and_actor_tasks_peak': 0}

    def sample(self):
        node = self.node
        sessions = tuple(node._sessions.values())
        current = {'sessions_peak': len(sessions), 'registered_peer_tasks_peak': len(node._tasks),
                   'ready_sessions_peak': sum(item.ready for item in sessions),
                   'closing_sessions_peak': sum(item.writer.is_closing() for item in sessions),
                   'receive_buffer_total_bytes_peak': sum(len(item.reader._buffer) for item in sessions),
                   'send_buffer_total_bytes_peak': sum(item.writer.transport.get_write_buffer_size() for item in sessions),
                   'server_active_transports_peak': node._server._active_count if node._server else 0,
                   'all_fixture_and_actor_tasks_peak': len(asyncio.all_tasks())}
        for key, value in current.items():
            self.values[key] = max(self.values[key], value)

    async def run(self):
        loop = asyncio.get_running_loop()
        previous = loop.time()
        while True:
            self.sample()
            await asyncio.sleep(.005)
            current = loop.time()
            self.delays.append(max(0, current - previous - .005))
            previous = current

    def start(self):
        self.task = asyncio.create_task(self.run())
        return self

    async def finish(self):
        self.sample()
        self.task.cancel()
        await asyncio.gather(self.task, return_exceptions=True)
        ordered = sorted(self.delays)
        return {**self.values,
                'event_loop_lag_max_ms': round(max(ordered, default=0) * 1000, 3),
                'event_loop_lag_p95_ms': round(ordered[int((len(ordered) - 1) * .95)] * 1000, 3) if ordered else 0,
                'samples': len(ordered)}


class AdmissionLoadTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        WORK.mkdir(parents=True, exist_ok=True)
        self.temporary = tempfile.TemporaryDirectory(prefix='owned-admission-', dir=WORK)
        self.folder = Path(self.temporary.name).resolve()
        assert self.folder.is_relative_to(WORK.resolve())
        self.nodes = []
        self.writers = []
        self.sockets = []
        self.old_servers = []
        self.samplers = []
        self.fixture_tasks = []
        self.records = []
        METRICS[self._testMethodName] = self.records

    async def asyncTearDown(self):
        for writer in self.writers:
            writer.transport.abort()
        for sock in self.sockets:
            sock.close()
        for task in self.fixture_tasks:
            if not task.done():
                task.cancel()
        if self.fixture_tasks:
            await asyncio.gather(*self.fixture_tasks, return_exceptions=True)
        for node in self.nodes:
            await asyncio.wait_for(node.stop(), 4)
        for server in self.old_servers:
            server.close()
            await asyncio.wait_for(server.wait_closed(), 1)
        for sampler in self.samplers:
            if sampler.task is not None and not sampler.task.done():
                await sampler.finish()
        self.temporary.cleanup()

    async def node(self, **options):
        options.setdefault('max_peers',8)  # Explicit operator-budget fixture; production default is unlimited.
        options.setdefault('poll_interval', .05)
        options.setdefault('timeout', .5)
        node = PeerNode(self.folder / f'fixture-{len(self.nodes)}.sqlite', network='regtest',
                        discover_peers=False, dht_enabled=False, **options)
        self.nodes.append(node)
        await node.start()
        return node

    def sample(self, node):
        sampler = Sampler(node).start()
        self.samplers.append(sampler)
        return sampler

    async def spike(self, node, count, *, partial=False):
        async def attempt(index):
            writer = None
            try:
                reader, writer = await asyncio.wait_for(asyncio.open_connection(*node.address), 2)
                self.writers.append(writer)
                try:
                    frame = await read_frame(reader, timeout=1, magic=node.network.message_magic)
                except PeerDisconnected:
                    return 'capacity_closed'
                require_version = frame.command == 'version'
                self.assertTrue(require_version)
                if partial:
                    version = decode_version(frame.payload)
                    packet = encode_frame('version', encode_version(Version(
                        1, node.genesis, version.nonce ^ (index + 1), node.network.profile_id,
                        node.genesis)), node.network.message_magic)
                    writer.write(packet[:7])
                    await writer.drain()
                return 'admitted_partial' if partial else 'admitted_idle'
            except (OSError, TimeoutError, ProtocolError):
                return 'transport_or_frame_deadline'

        began = time.monotonic()
        outcomes = await asyncio.gather(*(attempt(index) for index in range(count)))
        return {'attempts': count, 'outcomes': dict(Counter(outcomes)),
                'burst_completion_seconds': round(time.monotonic() - began, 3)}

    async def raw_read(self, sock, node):
        loop = asyncio.get_running_loop()
        async def exact(count):
            raw = bytearray()
            while len(raw) < count:
                chunk = await loop.sock_recv(sock, count - len(raw))
                if not chunk:
                    raise EOFError('Owned native client EOF')
                raw.extend(chunk)
            return bytes(raw)
        header = await asyncio.wait_for(exact(FRAME_HEADER_SIZE), 1)
        command, size, checksum = _decode_frame_header(header, node.network.message_magic)
        payload = await asyncio.wait_for(exact(size), 1)
        self.assertEqual(sha256d(payload)[:4], checksum)
        return command, payload

    async def raw_ready(self, node, index):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 1024)
        sock.setblocking(False)
        self.sockets.append(sock)
        loop = asyncio.get_running_loop()
        await asyncio.wait_for(loop.sock_connect(sock, node.address), 1)
        command, payload = await self.raw_read(sock, node)
        self.assertEqual('version', command)
        version = decode_version(payload)
        response = Version(1, node.genesis, version.nonce ^ (index + 1), node.network.profile_id, node.genesis)
        await loop.sock_sendall(sock, encode_frame('version', encode_version(response), node.network.message_magic))
        command, payload = await self.raw_read(sock, node)
        self.assertEqual(('verack', b''), (command, payload))
        await loop.sock_sendall(sock, encode_frame('verack', b'', node.network.message_magic))
        for _ in range(5):
            command, payload = await self.raw_read(sock, node)
            if command == 'getheaders':
                await loop.sock_sendall(sock, encode_frame('headers', encode_headers(()), node.network.message_magic))
                break
        else:
            self.fail('Owned initial header request not received')
        return sock

    async def closed_cleanly(self, node, server, sampler, label, *, limit=2):
        began = time.monotonic()
        await asyncio.wait_for(node.stop(), limit)
        record = {'phase': label, **await sampler.finish(),
                  'stop_seconds': round(time.monotonic() - began, 3),
                  'sessions_after_stop': len(node._sessions), 'peer_tasks_after_stop': len(node._tasks),
                  'server_active_transports_after_stop': server._active_count,
                  'server_sockets_after_stop': len(server.sockets),
                  'internal_errors': node._stats['internal_errors']}
        self.records.append(record)
        self.assertFalse(node._sessions)
        self.assertFalse(node._tasks)
        self.assertFalse(server.sockets)
        self.assertEqual(0, server._active_count)
        self.assertEqual(0, node._stats['internal_errors'])
        self.assertLessEqual(record['sessions_peak'], 8)
        return record

    async def test_01_tcp_spikes_32_64_128_keep_eight_session_cap(self):
        for count in (32, 64, 128):
            node = await self.node()
            server = node._server
            sampler = self.sample(node)
            burst = await self.spike(node, count)
            await eventually(lambda: not node._sessions, 3)
            record = await self.closed_cleanly(node, server, sampler, f'idle_{count}')
            record.update(burst)
            record['peer_limit_rejections'] = node._stats['peer_limit_rejections']
            self.assertGreater(record['sessions_peak'], 0)
            self.assertGreater(node._stats['peer_limit_rejections'], 0)
            self.assertFalse(node._invalid_peers)

    async def test_02_partial_handshake_spikes_expire_without_peer_cooldown(self):
        for count in (32, 64, 128):
            node = await self.node()
            server = node._server
            sampler = self.sample(node)
            burst = await self.spike(node, count, partial=True)
            await eventually(lambda: not node._sessions, 3)
            record = await self.closed_cleanly(node, server, sampler, f'partial_{count}')
            record.update(burst)
            record['invalid_peer_incidents'] = node._stats['invalid_peer_incidents']
            self.assertEqual(0, node._stats['invalid_peer_incidents'])
            self.assertFalse(node._invalid_peers)

    async def test_03_ready_partial_frames_use_whole_frame_deadline(self):
        node = await self.node()
        server = node._server
        sampler = self.sample(node)
        clients = [await self.raw_ready(node, index) for index in range(8)]
        await eventually(lambda: sum(session.ready for session in node._sessions.values()) == 8)
        began = time.monotonic()
        for client in clients:
            await asyncio.get_running_loop().sock_sendall(client, node.network.message_magic[:1])
        await eventually(lambda: not node._sessions, 2)
        elapsed = time.monotonic() - began
        record = await self.closed_cleanly(node, server, sampler, 'ready_partial_eight')
        record['partial_frame_cleanup_seconds'] = round(elapsed, 3)
        self.assertLess(elapsed, 2)
        self.assertFalse(node.synchronization_info()['mining_ready'])

    async def test_04_honest_ready_peer_survives_128_partial_connections(self):
        node = await self.node(allow_internet=True)
        server = node._server
        honest = await self.node(peers=(node.address,))
        await eventually(lambda: node.synchronization_info()['mining_ready'])
        original = tuple(id(session) for session in node._sessions.values() if session.ready)
        sampler = self.sample(node)
        burst = await self.spike(node, 128, partial=True)
        await eventually(lambda: len(node._sessions) == 1, 3)
        self.assertEqual(original, tuple(id(session) for session in node._sessions.values() if session.ready))
        self.assertTrue(node.synchronization_info()['mining_ready'])
        self.assertTrue(honest.synchronization_info()['mining_ready'])
        record = await self.closed_cleanly(node, server, sampler, 'honest_with_128_partial')
        record.update(burst)
        record['honest_session_preserved'] = True

    async def test_05_valid_getdata_nonreaders_bound_buffers_and_cleanup(self):
        node = await self.node()
        # A valid regtest block near one MB base size, using an unspendable
        # coinbase output. This performs no public/main-network work.
        node.chain.mine(b'\x6a' + bytes(900_000), 1)
        size = len(node.chain.get_block(node.chain.tip_hash).serialize())
        self.assertGreater(size, 900_000)
        server = node._server
        sampler = self.sample(node)
        clients = [await self.raw_ready(node, index) for index in range(8)]
        await eventually(lambda: sum(session.ready for session in node._sessions.values()) == 8)
        for session in node._sessions.values():
            session.writer.get_extra_info('socket').setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 0)
            session.writer.transport.set_write_buffer_limits(high=1024, low=512)
        packet = encode_frame('getdata', encode_inventory((Inventory(INV_BLOCK, node.chain.tip_hash),)),
                              node.network.message_magic)
        began = time.monotonic()
        for client in clients:
            await asyncio.get_running_loop().sock_sendall(client, packet)
        await eventually(lambda: not node._sessions, 3)
        elapsed = time.monotonic() - began
        record = await self.closed_cleanly(node, server, sampler, 'eight_valid_block_nonreaders')
        record.update(valid_regtest_block_bytes=size, nonreading_clients=8,
                      send_timeout_cleanup_seconds=round(elapsed, 3))
        self.assertLessEqual(record['send_buffer_total_bytes_peak'], size * 8 + 64_000)
        self.assertGreater(record['send_buffer_total_bytes_peak'], 0)

    async def test_06_stop_during_128_active_attempts_releases_owned_listener(self):
        node = await self.node(timeout=5)
        server = node._server
        sampler = self.sample(node)
        storm = asyncio.create_task(self.spike(node, 128, partial=True))
        self.fixture_tasks.append(storm)
        await eventually(lambda: len(node._sessions) == 8, 2)
        record = await self.closed_cleanly(node, server, sampler, 'stop_during_128_attempts', limit=2)
        record.update(await storm)
        self.assertLess(record['stop_seconds'], 2)

    async def test_07_listener_recovery_and_configured_reconnect_under_storm(self):
        node = await self.node(allow_internet=True)
        honest = await self.node(peers=(node.address,))
        await eventually(lambda: node.synchronization_info()['mining_ready'])
        address = node.address
        previous = node._server
        self.old_servers.append(previous)
        sampler = self.sample(node)
        previous.close()
        await node._recover_listener()
        self.assertTrue(node._listener_active())
        self.assertEqual(address, node.address)
        self.assertEqual(1, node._listener_restarts)
        storm = asyncio.create_task(self.spike(node, 64, partial=True))
        self.fixture_tasks.append(storm)
        next(iter(node._sessions.values())).writer.close()
        await storm
        await eventually(lambda: node.synchronization_info()['mining_ready'] and
                         honest.synchronization_info()['mining_ready'], 4)
        await eventually(lambda: len(node._sessions) == 1, 3)
        record = await self.closed_cleanly(node, node._server, sampler, 'recover_and_reconnect_with_64_attempts')
        record.update(listener_restarts=node._listener_restarts,
                      successful_handshakes=node._stats['handshakes'], same_selected_port=True,
                      configured_peer_reconnected=True)
        self.assertGreaterEqual(node._stats['handshakes'], 2)

    async def test_08_polling_nonreader_releases_closing_session_promptly(self):
        node = await self.node()
        server = node._server
        sampler = self.sample(node)
        await self.raw_ready(node, 1)
        await eventually(lambda: node.synchronization_info()['mining_ready'])
        session = next(iter(node._sessions.values()))
        session.writer.get_extra_info('socket').setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 0)
        session.writer.transport.set_write_buffer_limits(high=1024, low=512)

        pool = tuple(hashlib.sha256(str(index).encode('ascii')).digest() for index in range(1000))
        # Canonical bounded inventory hints only, not transactions or chain
        # acceptance. Exercise one real delta announcement through the actor
        # instead of relying on the removed periodic whole-pool announcements.
        poller = node._spawn(node._poll_session(session, node.chain.tip_hash, pool,
                            asyncio.get_running_loop().time()), 'owned-delta-inventory-fixture')
        try:
            await eventually(lambda: session.writer.is_closing(), 3)
            began = time.monotonic()
            await asyncio.sleep(2)
            retained = len(node._sessions)
            buffered = session.writer.transport.get_write_buffer_size()
            self.records.append({'phase': 'periodic_inventory_nonreader',
                                 **sampler.values, 'canonical_inventory_hints': 1000,
                                 'retained_closing_sessions_after_two_seconds': retained,
                                 'pending_send_bytes_after_two_seconds': buffered,
                                 'mining_ready_after_close': node.synchronization_info()['mining_ready'],
                                 'ready_idle_read_timeout_seconds': 30,
                                 'observation_seconds': round(time.monotonic() - began, 3)})
        finally:
            await asyncio.wait_for(poller, 2)
        await self.closed_cleanly(node, server, sampler, 'polling_nonreader_final_owned_cleanup')
        self.assertEqual(0, retained, 'Poll send timeout left a closing peer in the admission cap until its idle read expires')
        self.assertEqual(0, buffered, 'Poll send timeout retained a nonreading peer transport buffer')

        # Exercise the separate expired full-block/header-request closure while
        # the owned native socket has canonical inventory bytes pending.
        expired_node = await self.node()
        expired_server = expired_node._server
        expired_sampler = self.sample(expired_node)
        await self.raw_ready(expired_node, 2)
        await eventually(lambda: expired_node.synchronization_info()['mining_ready'])
        expired_session = next(iter(expired_node._sessions.values()))
        expired_session.writer.get_extra_info('socket').setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 0)
        expired_session.writer.transport.set_write_buffer_limits(high=1024, low=512)
        from sumuww.wire import INV_TRANSACTION
        inventory = encode_inventory(tuple(Inventory(INV_TRANSACTION, digest) for digest in pool[:256]))
        for _ in range(4):
            expired_session.writer.write(encode_frame('inv', inventory, expired_node.network.message_magic))
        await eventually(lambda: expired_session.writer.transport.get_write_buffer_size() > 0)
        now = asyncio.get_running_loop().time()
        expired_session.header_requested = True
        expired_session.header_requested_at = now - 31
        expiry = expired_node._spawn(expired_node._poll_session(
            expired_session, expired_node.chain.tip_hash, (), now), 'owned-expired-buffer-fixture')
        await asyncio.wait_for(expiry, 2)
        await eventually(lambda: not expired_node._sessions, 1)
        expired_record = await self.closed_cleanly(
            expired_node, expired_server, expired_sampler, 'expired_request_with_native_buffer')
        expired_record['expired_requests'] = expired_node._stats['requests_expired']
        expired_record['native_buffer_after_expiry'] = expired_session.writer.transport.get_write_buffer_size()
        self.assertGreaterEqual(expired_node._stats['requests_expired'], 1)
        self.assertEqual(0, expired_record['native_buffer_after_expiry'])

    async def test_09_same_ip_cooldown_preserves_existing_healthy_ready_sessions(self):
        node = await self.node()
        server = node._server
        first = await self.node(peers=(node.address,))
        second = await self.node(peers=(node.address,))
        await eventually(lambda: len(node._sessions) == 2 and
                         node.synchronization_info()['synchronized_peers'] == 2 and
                         first.synchronization_info()['mining_ready'] and
                         second.synchronization_info()['mining_ready'])
        healthy = tuple(node._sessions.values())
        self.assertEqual(1, len({session.remote_ip for session in healthy}))
        sampler = self.sample(node)
        for index in range(3):
            malicious = await self.raw_ready(node, 100 + index)
            malformed = encode_frame('ping', b'wrong', node.network.message_magic)
            await asyncio.get_running_loop().sock_sendall(malicious, malformed)
            await eventually(lambda: node._stats['invalid_peer_incidents'] == index + 1)
            if index < 2:
                self.assertTrue(all(not session.writer.is_closing() and session.synchronized for session in healthy))
                await eventually(lambda: len(node._sessions) == 2)
        await eventually(lambda: node._stats['peer_cooldowns'] == 1)
        await asyncio.sleep(.05)
        healthy_remaining = sum(id(session.writer) in node._sessions and not session.writer.is_closing()
                                and session.ready and session.synchronized for session in healthy)
        reader, writer = await asyncio.wait_for(asyncio.open_connection(*node.address), 1)
        self.writers.append(writer)
        rejected_new_attempt = await asyncio.wait_for(reader.read(1), 1) == b''
        self.records.append({'phase': 'shared_ip_active_session_collateral_close',
                             **sampler.values, 'healthy_synchronized_sessions_before': 2,
                             'healthy_synchronized_sessions_remaining_after_third_incident': healthy_remaining,
                             'malformed_incidents_from_separate_offender_sessions': 3,
                             'cooldown_started': node._stats['peer_cooldowns'] == 1,
                             'new_attempt_from_same_ip_rejected': rejected_new_attempt,
                             'tracked_ip_count': len(node._invalid_peers),
                             'maximum_tracked_ips': 128, 'incident_window_seconds': 600,
                             'cooldown_seconds': 300,
                             'mining_ready_after_third_incident': node.synchronization_info()['mining_ready']})
        await self.closed_cleanly(node, server, sampler, 'shared_ip_cooldown_final_owned_cleanup')
        self.assertTrue(rejected_new_attempt, 'Shared-IP new-attempt cooldown was not enforced')
        self.assertEqual(2, healthy_remaining,
                         'One malformed shared-IP offender disconnected existing healthy synchronized peers')


if __name__ == '__main__':
    unittest.main(verbosity=2)
