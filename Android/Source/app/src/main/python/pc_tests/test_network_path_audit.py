"""Whole connection paths on owned regtest sockets, not public phone peers."""
import asyncio
from pathlib import Path
import socket
import tempfile
import unittest

from sumuww.app_service import AppService
from sumuww.peer import PeerNode
from sumuww.privacy import settings
from sumuww.wallet import RegtestKey
from tests.test_dht_discovery_v29 import KrpcFixture, eventually


class NetworkPathAuditTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='whole-network-path-')
        self.nodes = []
        self.transports = []
        self.retired_servers = []

    async def asyncTearDown(self):
        for node in reversed(self.nodes):
            await node.stop()
        for transport in self.transports:
            transport.close()
        for server in self.retired_servers:
            await asyncio.wait_for(server.wait_closed(), 1)
        await asyncio.sleep(.02)
        self.temp.cleanup()

    async def node(self, name, **options):
        defaults = dict(discovery_scope='loopback', poll_interval=.03, timeout=1,
                        discovery_interval=1, dht_enabled=False)
        defaults.update(options)
        node = PeerNode(Path(self.temp.name)/(name+'.sqlite'), **defaults)
        self.nodes.append(node)
        await node.start()
        return node

    async def test_automatic_discovery_survives_first_contact_loss_and_finds_another_peer(self):
        remote = await self.node('independent')
        remote.chain.mine(RegtestKey.from_int(92).script_pubkey, 2)
        first = await self.node('first-contact')
        await first.connect(*remote.address)
        await eventually(lambda: first.info()['synchronized_peers'] == 1)
        # Only an owned, dynamic DHT router is supplied to the new client.
        router = KrpcFixture(peers=(first.address,))
        transport, _ = await asyncio.get_running_loop().create_datagram_endpoint(
            lambda: router, local_addr=('127.0.0.1', 0))
        self.transports.append(transport)
        current = ['network-1']
        client = await self.node('new-client', allow_internet=True, dht_enabled=True,
                                 dht_scope='loopback', dht_routers=[router.address],
                                 network_provider=lambda: current[0],
                                 dht_query_timeout=.1, dht_round_timeout=.5)
        self.assertEqual(0, client.info()['configured_peers'])
        await eventually(lambda: client.info()['synchronized_peers'] == 2, timeout=6)
        self.assertEqual({first.nonce, remote.nonce},
                         {session.nonce for session in client._healthy_sessions()})
        await first.stop()
        await eventually(lambda: all(s.nonce != first.nonce for s in client._sessions.values()), timeout=3)
        remote.chain.mine(RegtestKey.from_int(92).script_pubkey, 1)
        await eventually(lambda: client.chain.tip_hash == remote.chain.tip_hash)
        self.assertEqual(1, client.info()['peers'])
        # A fresh third node appears after the original contact has stopped.
        # The client discovers it from DHT, without manual peer registration.
        newcomer = await self.node('newcomer')
        router.peers = (newcomer.address,)
        current[0] = 'network-2'
        await eventually(lambda: any(s.nonce == newcomer.nonce for s in client._healthy_sessions()), timeout=6)
        self.assertEqual(0, client.info()['configured_peers'])
        self.assertEqual(2, client.info()['peers'])

    async def test_ipv6_listener_restarts_without_dropping_existing_tcp(self):
        listener = await self.node('v6-listener', host='0.0.0.0', allow_internet=True,
                                   discover_peers=False)
        client = await self.node('v6-client', host='::1', discover_peers=False)
        await client.connect('::1', listener.address[1])
        await eventually(lambda: listener.info()['synchronized_peers'] == 1)
        retained = next(s for s in listener._sessions.values() if s.ready)
        old = listener._server6
        self.assertIsNotNone(old)
        old.close()
        # Server.wait_closed waits for accepted transports too on Python 3.12+.
        # Keep them alive for this test and await server cleanup after node stop.
        self.retired_servers.append(old)
        await eventually(lambda: listener._server6 is not old
                         and listener._server6.is_serving(), timeout=7)
        self.assertIn(retained, listener._sessions.values())
        self.assertFalse(retained.writer.is_closing())
        second = await self.node('second-v6-client', host='::1', discover_peers=False)
        await second.connect('::1', listener.address[1])
        await eventually(lambda: listener.info()['synchronized_peers'] == 2)

    async def test_tor_i2p_without_contacts_cannot_discover_peers_or_enable_direct_fallback(self):
        # This is a mode/configuration test, not an operational overlay test.
        for mode in ('tor', 'i2p'):
            with self.subTest(mode=mode):
                node = await self.node('empty-'+mode, allow_internet=True, allow_lan=True,
                                       auto_address=True, privacy=settings(mode),
                                       bootstrap_seeds=(), bootstrap_peers=())
                await asyncio.sleep(.1)
                info = node.info()
                self.assertEqual(0, info['peers'])
                self.assertEqual(0, info['configured_peers'])
                self.assertFalse(info['dht_discovery']['enabled'])
                self.assertFalse(info['dht_discovery_ipv6']['enabled'])
                self.assertFalse(info['lan_discovery']['enabled'])
                self.assertFalse(info['privacy']['direct_fallback'])

    async def test_manual_registration_is_not_a_connection_or_a_ready_peer(self):
        # The OS owns an unused ephemeral port, released before this attempt.
        with socket.socket() as reserve:
            reserve.bind(('127.0.0.1', 0))
            port = reserve.getsockname()[1]
        service = AppService(Path(self.temp.name)/'isolated-service', network='regtest',
                             listen='127.0.0.1:0', allow_internet=False, allow_lan=False)
        try:
            await asyncio.wrap_future(service.start())
            result = await asyncio.wrap_future(service.add_peer(f'127.0.0.1:{port}'))
            self.assertTrue(result['registered'])
            await asyncio.sleep(.15)
            status = await asyncio.wrap_future(service.status())
            self.assertEqual(0, status['node']['peers'])
            self.assertEqual(0, status['node']['synchronized_peers'])
            self.assertFalse(status['node']['mining_ready'])
        finally:
            await asyncio.wrap_future(service.stop())
