"""Owned loopback listeners must survive cancellation without leaking sockets.

Native serving/transport operations run unchanged; only a boundary pause or
task cancellation is injected. Fixtures use fresh regtest databases and do not
inspect or touch user ports, state, wallets, preferences, or public peers.
"""
import asyncio
import errno
import os
from pathlib import Path
import socket
import tempfile
import time
import unittest
from unittest.mock import patch

from sumuww.peer import PeerNode
from sumuww.rpc import RpcServer


async def eventually(predicate, timeout=2):
    deadline = asyncio.get_running_loop().time() + timeout
    while not predicate():
        if asyncio.get_running_loop().time() >= deadline:
            raise AssertionError('Owned startup lifecycle deadline')
        await asyncio.sleep(.005)


class StartupLifecycleTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        work = Path(os.environ.get('SUMUWW_TEST_WORKDIR', tempfile.gettempdir()))
        work.mkdir(parents=True, exist_ok=True)
        self.temporary = tempfile.TemporaryDirectory(prefix='sumuww-owned-startup-v36-', dir=work)
        self.folder = Path(self.temporary.name)
        self.nodes = []
        self.rpcs = []
        self.servers = []
        self.clients = []
        self.tasks = []

    async def asyncTearDown(self):
        for client in self.clients:
            client.close()
        for rpc in self.rpcs:
            for writer in tuple(rpc._writers):
                writer.transport.abort()
        for task in self.tasks:
            if not task.done():
                task.cancel()
        if self.tasks:
            await asyncio.gather(*self.tasks, return_exceptions=True)
        await asyncio.gather(*(rpc.stop() for rpc in self.rpcs), return_exceptions=True)
        await asyncio.gather(*(node.stop() for node in self.nodes), return_exceptions=True)
        for server in self.servers:
            server.close()
            await asyncio.wait_for(server.wait_closed(), 1)
        self.temporary.cleanup()

    def node(self, **options):
        node = PeerNode(self.folder / f'fixture-{len(self.nodes)}.sqlite', network='regtest',
                        discover_peers=False, dht_enabled=False, timeout=.5, **options)
        self.nodes.append(node)
        return node

    def rpc(self, node):
        rpc = RpcServer(lambda: node, 'a' * 64, port=0)
        self.rpcs.append(rpc)
        return rpc

    async def assert_port_released(self, address):
        with self.assertRaises(OSError):
            await asyncio.wait_for(asyncio.open_connection(*address), .5)
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            if hasattr(socket, 'SO_EXCLUSIVEADDRUSE'):
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
            sock.bind(address)
            sock.listen(1)

    async def cancel_native_serving_yield(self, component):
        original = asyncio.base_events.Server._start_serving
        starting = None
        address = None

        def cancelled(server):
            nonlocal address
            original(server)
            if asyncio.current_task() is starting:
                self.servers.append(server)
                address = server.sockets[0].getsockname()[:2]
                starting.cancel()

        with patch.object(asyncio.base_events.Server, '_start_serving', cancelled):
            starting = asyncio.create_task(component.start())
            self.tasks.append(starting)
            with self.assertRaises(asyncio.CancelledError):
                await starting
        await component.stop()
        self.assertIsNone(component._server)
        self.assertEqual(1, len(self.servers))
        self.assertFalse(self.servers[0].is_serving())
        self.assertFalse(self.servers[0].sockets)
        await self.assert_port_released(address)
        return address

    async def test_peer_cancel_at_native_initial_serving_yield_releases_selected_port(self):
        node = self.node()
        address = await self.cancel_native_serving_yield(node)
        self.assertFalse(node.running)
        self.assertTrue(node._closed)
        self.assertFalse(node._tasks)
        replacement = self.node(host=address[0], port=address[1])
        await replacement.start()
        self.assertEqual(address, replacement.address)
        self.assertTrue(replacement._listener_active())

    async def test_peer_cancel_at_fallback_serving_yield_releases_replacement_port(self):
        node = self.node(port=18444, auto_address=True)
        original = asyncio.start_server
        attempts = []

        async def occupied(callback, host, port, **options):
            attempts.append(port)
            if port == 18444:
                raise OSError(errno.EADDRINUSE, 'owned simulated standard port conflict')
            return await original(callback, host, port, **options)

        with patch('sumuww.peer.asyncio.start_server', side_effect=occupied):
            address = await self.cancel_native_serving_yield(node)
        self.assertEqual([18444, 0], attempts)
        self.assertTrue(node._port_fallback)
        self.assertNotEqual(18444, address[1])

    async def test_rpc_cancel_at_native_serving_yield_can_restart_and_serve_same_port(self):
        node = self.node()
        await node.start()
        rpc = self.rpc(node)
        address = await self.cancel_native_serving_yield(rpc)
        await rpc.start()
        self.assertEqual(address, rpc.address)
        reader, writer = await asyncio.open_connection(*address)
        body = b'{"jsonrpc":"2.0","id":1,"method":"getblockcount","params":[]}'
        header = (f'POST /rpc HTTP/1.1\r\nHost: {address[0]}:{address[1]}\r\n'
                  f'Authorization: Bearer {"a" * 64}\r\nContent-Type: application/json\r\n'
                  f'Content-Length: {len(body)}\r\n\r\n').encode('ascii')
        try:
            writer.write(header + body)
            await writer.drain()
            response = await asyncio.wait_for(reader.read(), 2)
            self.assertIn(b'HTTP/1.1 200 OK', response)
            self.assertIn(b'"result":0', response)
        finally:
            writer.close()
            await writer.wait_closed()

    async def stop_during_serving(self, component):
        original = asyncio.base_events.Server.start_serving
        entered = asyncio.Event()
        addresses = []

        async def delayed(server):
            await original(server)
            self.servers.append(server)
            addresses.append(server.sockets[0].getsockname()[:2])
            entered.set()
            await asyncio.Event().wait()

        with patch.object(asyncio.base_events.Server, 'start_serving', delayed):
            starting = asyncio.create_task(component.start())
            self.tasks.append(starting)
            await asyncio.wait_for(entered.wait(), 1)
            await asyncio.wait_for(component.stop(), 1)
            with self.assertRaises(asyncio.CancelledError):
                await starting
        self.assertIsNone(component._server)
        self.assertFalse(self.servers[0].is_serving())
        self.assertFalse(self.servers[0].sockets)
        await self.assert_port_released(addresses[0])

    async def test_peer_stop_during_initial_activation_cancels_start_and_closes_listener(self):
        node = self.node()
        await self.stop_during_serving(node)
        self.assertFalse(node.running)
        self.assertTrue(node._closed)
        self.assertFalse(node._tasks)

    async def test_rpc_stop_during_initial_activation_cancels_start_and_closes_listener(self):
        rpc = self.rpc(self.node())
        await self.stop_during_serving(rpc)
        await rpc.start()
        self.assertTrue(rpc._server.is_serving())

    async def test_cancelled_rpc_activation_closes_already_accepted_partial_client(self):
        rpc = self.rpc(self.node())
        original = asyncio.base_events.Server.start_serving
        entered = asyncio.Event()

        async def delayed(server):
            await original(server)
            self.servers.append(server)
            entered.set()
            await asyncio.Event().wait()

        with patch.object(asyncio.base_events.Server, 'start_serving', delayed):
            starting = asyncio.create_task(rpc.start())
            self.tasks.append(starting)
            await asyncio.wait_for(entered.wait(), 1)
            reader, writer = await asyncio.open_connection(*rpc.address)
            await eventually(lambda: len(rpc._writers) == 1)
            starting.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await starting
        try:
            self.assertIsNone(rpc._server)
            self.assertFalse(rpc._writers)
            self.assertFalse(rpc._tasks)
            self.assertEqual(0, self.servers[0]._active_count)
            self.assertEqual(b'', await asyncio.wait_for(reader.read(1), 1))
        finally:
            writer.close()
            await writer.wait_closed()

    async def concurrent_start(self, component):
        original = asyncio.start_server
        bound = []

        async def counted(*args, **options):
            self.assertFalse(options['start_serving'])
            server = await original(*args, **options)
            bound.append(server)
            return server

        with patch('asyncio.start_server', side_effect=counted):
            results = await asyncio.gather(*(component.start() for _ in range(4)))
        self.assertEqual([component] * 4, results)
        self.assertEqual(1, len(bound))
        self.assertIs(bound[0], component._server)

    async def test_concurrent_peer_starts_create_one_owned_listener(self):
        await self.concurrent_start(self.node())

    async def test_concurrent_rpc_starts_create_one_owned_listener(self):
        await self.concurrent_start(self.rpc(self.node()))

    async def test_peer_stop_during_self_address_refresh_cancels_start_before_worker_spawn(self):
        node = self.node(host='0.0.0.0', allow_internet=True, auto_address=True)
        entered = asyncio.Event()

        async def blocked():
            entered.set()
            await asyncio.Event().wait()

        with patch('sumuww.peer.enumerate_ipv4_interfaces', side_effect=blocked):
            starting = asyncio.create_task(node.start())
            self.tasks.append(starting)
            await asyncio.wait_for(entered.wait(), 1)
            port = node.address[1]
            await asyncio.wait_for(node.stop(), 1)
            with self.assertRaises(asyncio.CancelledError):
                await starting
        self.assertFalse(node._tasks)
        self.assertIsNone(node._server)
        self.assertEqual('not_running', node._self_state.status)
        await self.assert_port_released(('127.0.0.1', port))

    async def test_rpc_nonreading_client_is_aborted_before_server_wait(self):
        rpc = self.rpc(self.node())
        await rpc.start()
        server = rpc._server
        client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.clients.append(client)
        client.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 1024)
        client.setblocking(False)
        await asyncio.get_running_loop().sock_connect(client, rpc.address)
        await eventually(lambda: len(rpc._writers) == 1)
        writer = next(iter(rpc._writers))
        writer.get_extra_info('socket').setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 0)
        writer.transport.set_write_buffer_limits(high=1024, low=512)
        # A native transport buffer close to the RPC response cap. The owned
        # nonreading client receives synthetic bytes with no chain authority.
        for _ in range(4):
            writer.write(b'x' * 4_000_000)
        await asyncio.sleep(.02)
        self.assertGreater(writer.transport.get_write_buffer_size(), 0)
        began = time.monotonic()
        await asyncio.wait_for(rpc.stop(), 2.5)
        self.assertLess(time.monotonic() - began, 2.5)
        self.assertEqual(0, writer.transport.get_write_buffer_size())
        self.assertEqual(0, server._active_count)
        self.assertFalse(rpc._writers)
        self.assertFalse(rpc._tasks)


if __name__ == '__main__':
    unittest.main()
