"""IPv6 discovery, publication and real TCP validation; owned loopback only."""
import asyncio
import ipaddress
from pathlib import Path
import socket
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from sumuww import dht_discovery as dht
from sumuww.peer import PeerNode
from sumuww.profiles import REGTEST
from sumuww.wallet import RegtestKey
from tests.test_dht_discovery_v29 import KrpcFixture, eventually


def compact6(endpoint):
    return socket.inet_pton(socket.AF_INET6, endpoint[0]) + endpoint[1].to_bytes(2, 'big')


class AndroidIPv6Tests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='android-ipv6-')
        self.nodes, self.services, self.transports = [], [], []

    async def asyncTearDown(self):
        await asyncio.gather(*(service.stop() for service in self.services))
        for node in reversed(self.nodes):
            await node.stop()
        for transport in self.transports:
            transport.close()
        await asyncio.sleep(.01)
        self.temp.cleanup()

    def service(self, callback=lambda hints: None, **options):
        options.setdefault('family', socket.AF_INET6)
        options.setdefault('scope', 'loopback')
        options.setdefault('routers', [('::1', 1)])
        result = dht.DhtDiscovery(REGTEST, callback, query_timeout=.1, round_timeout=1, **options)
        self.services.append(result)
        return result

    async def server(self, responder):
        server = KrpcFixture(responder=responder)
        transport, _ = await asyncio.get_running_loop().create_datagram_endpoint(
            lambda: server, local_addr=('::1', 0), family=socket.AF_INET6)
        self.transports.append(transport)
        return server

    async def node(self, name, *, discover=True):
        result = PeerNode(Path(self.temp.name) / (name + '.sqlite'), host='::1', port=0,
            network='regtest', dht_enabled=False, discovery_scope='loopback', discover_peers=discover,
            poll_interval=.03, timeout=1)
        self.nodes.append(result)
        await result.start()
        return result

    async def test_ipv6_dht_first_contact_leads_to_validated_tcp_sync_without_seed(self):
        remote = await self.node('remote')
        remote.chain.mine(RegtestKey.from_int(71).script_pubkey, 3)
        client = await self.node('client')
        self.assertFalse(client._configured)
        self.assertEqual(0, client._addresses.info()['candidates'])
        def respond(server, request, source):
            fields = ({b'values': [compact6(remote.address)], b'token': b'ipv6-token'}
                      if request[b'q'] == b'get_peers' else {})
            server.reply(request, source, fields)
        router = await self.server(respond)
        service = self.service(client._received_dht_hints, routers=[router.address],
                               contact_provider=lambda: client.address)
        await service.start()
        await eventually(lambda: client.chain.tip_hash == remote.chain.tip_hash
                         and client.info()['synchronized_peers'] == 1)
        self.assertEqual(3, client.info()['height'])
        await eventually(lambda: service.info()['stats']['announcements'] > 0)
        queries = [m for m, s in router.messages if m[b'q'] == b'get_peers']
        self.assertEqual([b'n6'], queries[0][b'a'][b'want'])
        announces = [m for m, s in router.messages if m[b'q'] == b'announce_peer']
        self.assertEqual(client.address[1], announces[0][b'a'][b'port'])
        self.assertEqual(0, announces[0][b'a'][b'implied_port'])
        self.assertFalse(router.errors)

    async def test_nodes6_referral_is_walked_before_delivering_contact(self):
        target = ('::1', 34567)
        next_router = await self.server(lambda s, q, a: s.reply(q, a, {b'values': [compact6(target)]}))
        first = await self.server(lambda s, q, a: s.reply(q, a,
            {b'nodes6': next_router.identifier + compact6(next_router.address)}))
        hints = []
        service = self.service(hints.extend, routers=[first.address])
        await service.start()
        await eventually(lambda: bool(hints))
        self.assertEqual([target], hints)
        self.assertEqual(2, service.info()['stats']['queries'])

    async def test_changed_router_reply_port_requires_a_new_correlated_query(self):
        legitimate = ('::1', 34567)
        unsolicited = ('::1', 34568)
        second = await self.server(lambda s, q, a: s.reply(q, a, {b'values': [compact6(legitimate)]}))
        first = await self.server(lambda s, q, a: second.reply(q, a, {b'values': [compact6(unsolicited)]}))
        hints = []
        service = self.service(hints.extend, routers=[first.address])
        await service.start()
        await eventually(lambda: bool(hints))
        self.assertEqual([legitimate], hints)
        self.assertGreater(len(second.messages), 0)
        self.assertEqual(2, service.info()['stats']['queries'])
        self.assertEqual(1, service.info()['stats']['uncorrelated_datagrams'])

    async def test_hybrid_values_parse_and_nodes_have_combined_budget(self):
        service = self.service()
        ipv4 = socket.inet_aton('127.0.0.1') + (1).to_bytes(2, 'big')
        ipv6 = compact6(('::1', 2))
        hints, nodes, token = service._parse_contacts({b'values': [ipv4, ipv6],
            b'nodes': b'a' * 20 + ipv4, b'nodes6': b'b' * 20 + ipv6})
        self.assertEqual([('127.0.0.1', 1), ('::1', 2)], hints)
        self.assertEqual([(b'b' * 20, ('::1', 2))], nodes)
        for body in ({b'values': [b'x' * 17]}, {b'nodes6': b'x' * 37},
                     {b'nodes': (b'a' * 20 + ipv4) * 128, b'nodes6': b'b' * 20 + ipv6}):
            with self.assertRaises(ValueError):
                service._parse_contacts(body)

    async def test_ipv4_contact_is_never_announced_over_ipv6(self):
        service = self.service(contact_provider=lambda: ('127.0.0.1', 18444))
        self.assertIsNone(service._contact())
        await service.start()
        with self.assertRaises(OSError):
            await service._query(('127.0.0.1', 1), b'get_peers', {b'info_hash': service.key})

    async def test_no_active_ipv6_source_stays_unavailable_without_wildcard_binding(self):
        service = self.service(scope='public', routers=[('dht.transmissionbt.com', 6881)])
        with patch.object(asyncio.get_running_loop(), 'create_datagram_endpoint') as create:
            self.assertIs(service, await service.start())
            create.assert_not_called()
        self.assertEqual('unavailable', service.info()['state'])
        self.assertEqual(0, service.info()['stats']['announcements'])

    async def test_active_source_change_rebinds_to_new_interface(self):
        source = ['2606:4700:4700::1111']
        service = self.service(scope='public', routers=[('dht.transmissionbt.com', 6881)],
                               source_provider=lambda: source[0])
        class Transport:
            def __init__(self): self.closed = False
            def close(self): self.closed = True
            def is_closing(self): return self.closed
        bindings, transports = [], []
        async def create(factory, *, local_addr, family):
            bindings.append((local_addr[0], family))
            t = Transport(); transports.append(t)
            return t, None
        with patch.object(asyncio.get_running_loop(), 'create_datagram_endpoint', create):
            self.assertTrue(await service._ensure_transport())
            source[0] = '2606:4700:4700::1001'
            self.assertTrue(await service._ensure_transport())
        self.assertTrue(transports[0].closed)
        self.assertEqual([(host, socket.AF_INET6) for host in
                          ('2606:4700:4700::1111', '2606:4700:4700::1001')], bindings)

    async def test_stop_cancels_ipv6_queries_and_closes_socket(self):
        router = await self.server(lambda *args: None)
        service = self.service(routers=[router.address])
        await service.start()
        await eventually(lambda: bool(router.messages))
        await service.stop()
        self.assertEqual(0, service.info()['pending_queries'])
        self.assertIsNone(service._transport)
        self.assertFalse(service._active)

    async def test_eight_distinct_ipv6_nodes_are_counted_without_collapsing_ip(self):
        remotes = [await self.node('remote-' + str(index), discover=False) for index in range(8)]
        client = await self.node('client-eight', discover=False)
        await asyncio.gather(*(client.connect(*remote.address) for remote in remotes))
        await eventually(lambda: client.info()['synchronized_peers'] == 8)
        info = client.info()
        self.assertEqual(8, info['peers'])
        self.assertEqual(8, info['active_connections'])
        self.assertEqual(8, len({row['peer_id'] for row in info['peer_connections']}))

    async def test_connected_but_below_target_retries_without_waiting_five_minutes(self):
        now = [1000.0]
        service = self.service(clock=lambda: now[0], connected_provider=lambda: True,
                               settled_provider=lambda: False)
        service._active = True
        async def sleep(delay): now[0] += delay
        fake = SimpleNamespace(**{**vars(asyncio), 'sleep': sleep})
        with patch.object(dht, 'asyncio', fake):
            await service._wait_for_next_query()
        self.assertEqual(dht.DISCONNECTED_RETRY_INTERVAL, now[0] - 1000)
