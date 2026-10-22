"""Owned real UDP sockets; Android network changes represented by a network ID.

These tests run on the build PC. They are not a physical 5G reachability test.
"""
import asyncio
import socket
import tempfile
import unittest
from pathlib import Path

from sumuww.dht_discovery import DhtDiscovery
from tests.test_dht_discovery_v29 import KrpcFixture
from sumuww.peer import PeerNode
from sumuww.wallet import RegtestKey


class MobileDhtRecoveryTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.services = []
        self.transports = []

    async def asyncTearDown(self):
        for service in self.services:
            await service.stop()
        for transport in self.transports:
            transport.close()
        await asyncio.sleep(.01)

    async def client(self, family=socket.AF_INET, **options):
        host = '::1' if family == socket.AF_INET6 else '127.0.0.1'
        def respond(server, request, source):
            raw = socket.inet_pton(family, host) + (34567).to_bytes(2, 'big')
            server.reply(request, source, {b'values': [raw]})
        router = KrpcFixture(responder=respond)
        transport, _ = await asyncio.get_running_loop().create_datagram_endpoint(
            lambda: router, local_addr=(host, 0), family=family)
        self.transports.append(transport)
        client = DhtDiscovery('regtest', lambda _: None, family=family,
                              scope='loopback', routers=[router.address],
                              query_timeout=.1, round_timeout=.3, **options)
        self.services.append(client)
        await client._ensure_transport()
        client._active = True
        return client, router, (host, 34567)

    async def test_closed_real_udp_socket_recovers_ipv4_and_ipv6(self):
        for family in (socket.AF_INET, socket.AF_INET6):
            with self.subTest(family=family):
                client, router, peer = await self.client(family)
                self.assertIn(peer, await client.lookup_once())
                first = client._transport
                first.close()
                await asyncio.sleep(.01)
                self.assertIn(peer, await client.lookup_once())
                self.assertIsNot(first, client._transport)
                self.assertGreaterEqual(client.info()['stats']['transport_restarts'], 1)

    async def test_default_network_change_reopens_even_when_ipv4_host_is_unchanged(self):
        current = ['wifi-network-1']
        client, router, peer = await self.client(network_provider=lambda: current[0])
        self.assertIn(peer, await client.lookup_once())
        first = client._transport
        current[0] = 'cellular-network-2'
        self.assertIn(peer, await client.lookup_once())
        self.assertIsNot(first, client._transport)
        self.assertTrue(first.is_closing())
        # The old transport's delayed connection_lost must not discard the new one.
        await asyncio.sleep(.01)
        self.assertIn(peer, await client.lookup_once())

    async def test_disconnected_network_releases_socket_then_reconnects(self):
        current = ['mobile-1']
        client, router, peer = await self.client(network_provider=lambda: current[0])
        self.assertIn(peer, await client.lookup_once())
        first = client._transport
        current[0] = None
        self.assertEqual((), await client.lookup_once())
        self.assertTrue(first.is_closing())
        self.assertIsNone(client._transport)
        current[0] = 'mobile-2'
        self.assertIn(peer, await client.lookup_once())

    async def test_network_change_wakes_a_settled_idle_search(self):
        current = ['wifi']
        client, router, peer = await self.client(network_provider=lambda: current[0],
                                                connected_provider=lambda: True,
                                                settled_provider=lambda: True)
        waiter = asyncio.create_task(client._wait_for_next_query())
        await asyncio.sleep(.02)
        current[0] = 'mobile'
        await asyncio.wait_for(waiter, 1.5)

    async def test_start_without_a_network_can_recover_without_restarting_node(self):
        current = [None]
        client, router, peer = await self.client(network_provider=lambda: current[0])
        client._active = False
        await client.start()
        self.assertTrue(client._active)
        current[0] = 'mobile'
        deadline = asyncio.get_running_loop().time() + 1.5
        while client.info()['stats']['accepted_hints'] == 0:
            if asyncio.get_running_loop().time() > deadline:
                self.fail('DHT did not recover after initial network absence')
            await asyncio.sleep(.02)

    async def test_mobile_network_without_ipv6_does_not_busy_loop(self):
        client = DhtDiscovery('regtest', lambda _: None, family=socket.AF_INET6,
                              network_provider=lambda: 'ipv4-only-mobile',
                              source_provider=lambda: None,
                              routers=[('dht.transmissionbt.com', 6881)],
                              query_timeout=.1, round_timeout=.3)
        self.services.append(client)
        await client.start()
        await asyncio.sleep(.15)
        self.assertEqual('unavailable', client.info()['state'])
        self.assertLessEqual(client.info()['stats']['rounds'], 2)
        self.assertEqual(0, client.info()['pending_queries'])

    async def test_closed_socket_wakes_settled_worker_without_a_network_id_change(self):
        client, router, peer = await self.client(connected_provider=lambda: True,
                                                settled_provider=lambda: True)
        self.assertIn(peer, await client.lookup_once())
        waiter = asyncio.create_task(client._wait_for_next_query())
        await asyncio.sleep(.02)
        client._transport.close()
        await asyncio.wait_for(waiter, 1.5)
        self.assertIn(peer, await client.lookup_once())

    async def test_no_cache_empty_dht_then_network_change_discovers_syncs_and_keeps_tcp(self):
        # Real UDP -> peer address -> real TCP -> validated block synchronization.
        # All sockets and chains are owned local regtest fixtures on the PC.
        from tests.test_dht_discovery_v29 import eventually
        current = ['wifi']
        temp = tempfile.TemporaryDirectory(prefix='mobile-network-recovery-')
        nodes = []
        try:
            server = PeerNode(Path(temp.name)/'remote.sqlite', discover_peers=False,
                              poll_interval=.03, timeout=1)
            nodes.append(server)
            await server.start()
            server.chain.mine(RegtestKey.from_int(91).script_pubkey, 2)
            router = KrpcFixture()
            transport, _ = await asyncio.get_running_loop().create_datagram_endpoint(
                lambda: router, local_addr=('127.0.0.1', 0))
            self.transports.append(transport)
            client = PeerNode(Path(temp.name)/'client.sqlite', allow_internet=True,
                              dht_enabled=True, dht_scope='loopback',
                              discovery_scope='loopback', dht_routers=[router.address],
                              dht_query_timeout=.1, dht_round_timeout=.3,
                              network_provider=lambda: current[0],
                              poll_interval=.03, timeout=1)
            nodes.append(client)
            await client.start()
            await eventually(lambda: client.info()['dht_discovery']['stats']['responses'] > 0)
            self.assertEqual(0, client.info()['configured_peers'])
            self.assertEqual(0, client.info()['peer_discovery']['candidates'])
            self.assertEqual(0, client.info()['peers'])
            router.peers = (server.address,)
            current[0] = 'mobile'
            await eventually(lambda: client.info()['synchronized_peers'] == 1
                             and client.chain.tip_hash == server.chain.tip_hash)
            session = next(s for s in client._sessions.values() if s.ready)
            first = client._dht_discovery._transport
            current[0] = 'mobile-reconnected'
            await eventually(lambda: client._dht_discovery._transport is not first)
            self.assertIn(session, client._sessions.values())
            self.assertFalse(session.writer.is_closing())
            server.chain.mine(RegtestKey.from_int(91).script_pubkey, 1)
            await eventually(lambda: client.chain.tip_hash == server.chain.tip_hash)
            self.assertEqual(3, client.info()['height'])
            self.assertEqual(1, client.info()['peers'])
        finally:
            for node in reversed(nodes):
                await node.stop()
            temp.cleanup()
