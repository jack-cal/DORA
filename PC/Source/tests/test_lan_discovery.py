"""Bounded protocol/opt-in checks and local fixtures; no real public peers.

The multicast integration explicitly substitutes loopback for the RFC1918 test
scope, since a real LAN adapter is not available on every test host. Production
beacons continue to reject loopback and public source addresses.
"""
import asyncio
import ipaddress
import os
from pathlib import Path
import socket
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, Mock, patch

from sumuww import lan_discovery as lan
from sumuww.lan_discovery import LanDiscovery, encode_beacon, decode_beacon
from sumuww.peer import PeerNode, _endpoint
from sumuww.profiles import SUMUWW, REGTEST, RETARGET_LAB
from sumuww.wallet import RegtestKey
from sumuww.__main__ import create_payment
from sumuww.node_manager import probe_peer
from sumuww.primitives import COIN
from sumuww.self_address import InterfaceAddress

WORK=Path(os.environ.get('SUMUWW_TEST_WORKDIR',tempfile.gettempdir()))


async def eventually(predicate,timeout=8):
    end=asyncio.get_running_loop().time()+timeout
    while not predicate():
        if asyncio.get_running_loop().time()>end:
            raise AssertionError('Isolated LAN fixture did not reach its expected state')
        await asyncio.sleep(.02)


class BeaconTests(unittest.TestCase):
    def test_all_registered_profiles_have_a_bound_exact_beacon(self):
        for network in (SUMUWW,REGTEST,RETARGET_LAB):
            raw=encode_beacon(network,34567,123)
            self.assertEqual((34567,123),decode_beacon(raw,network))
            self.assertLessEqual(len(raw),lan.MAX_BEACON_BYTES)
            for other in (SUMUWW,REGTEST,RETARGET_LAB):
                if other is not network:
                    with self.assertRaises(ValueError):decode_beacon(raw,other)

    def test_malformed_genesis_profile_magic_lengths_and_trailing_bytes_rejected(self):
        valid=encode_beacon(REGTEST,18444,2)
        mutations=[b'',valid[:-1],valid+b'x',bytearray(valid),b'x'*120]
        for offset in (0,8,12,44,45):
            raw=bytearray(valid);raw[offset]^=1;mutations.append(bytes(raw))
        raw=bytearray(valid);raw[-10:-8]=b'\0\0';mutations.append(bytes(raw))
        for raw in mutations:
            with self.subTest(payload_type=type(raw),length=len(raw)),self.assertRaises(ValueError):
                decode_beacon(raw,REGTEST)

    def test_encode_numeric_arguments_are_strict(self):
        for port in (0,-1,65536,True,'18444'):
            with self.assertRaises(ValueError):encode_beacon(REGTEST,port,2)
        for nonce in (-1,2**64,True,'2'):
            with self.assertRaises(ValueError):encode_beacon(REGTEST,18444,nonce)

    def test_public_loopback_cgnat_linklocal_and_dns_sources_rejected(self):
        hints=[];service=LanDiscovery(REGTEST,18444,1,hints.append,[])
        payload=encode_beacon(REGTEST,34567,2)
        for host in ('8.8.8.8','127.0.0.1','100.64.1.1','169.254.1.1','224.0.0.1','0.0.0.0','peer.example','::1'):
            service.datagram_received(payload,(host,12345))
        self.assertFalse(hints)
        self.assertEqual(8,service.stats['rejected'])

    def test_endpoint_is_udp_source_plus_tcp_port_without_claimed_ip_or_work(self):
        hints=[];service=LanDiscovery(REGTEST,18444,1,hints.append,[])
        service.datagram_received(encode_beacon(REGTEST,34567,2),('192.168.1.7',55555))
        self.assertEqual([('192.168.1.7',34567)],hints)
        self.assertTrue(service.info()['hint_only'])
        self.assertNotIn('height',service.info())
        self.assertNotIn('balance',service.info())

    def test_self_and_foreign_profile_beacons_never_add_hints(self):
        hints=[];service=LanDiscovery(REGTEST,18444,1,hints.append,[])
        for raw in (encode_beacon(REGTEST,34567,1),encode_beacon(SUMUWW,34567,2)):
            service.datagram_received(raw,('10.1.2.3',18445))
        self.assertFalse(hints)

    def test_per_source_and_global_receive_rates_are_bounded(self):
        now=[0];hints=[];service=LanDiscovery(REGTEST,18444,1,hints.append,[],clock=lambda:now[0])
        raw=encode_beacon(REGTEST,34567,2)
        service.datagram_received(raw,('10.1.2.3',18445))
        for _ in range(100):service.datagram_received(raw,('10.1.2.3',18445))
        self.assertEqual(1,len(hints))
        self.assertEqual(100,service.stats['rate_limited'])
        now[0]=5;service.datagram_received(raw,('10.1.2.3',18445))
        self.assertEqual(2,len(hints))

    def test_tracked_sources_and_interface_input_are_bounded(self):
        now=[0];hints=[]
        interfaces=['10.0.0.'+str(i) for i in range(1,33)]+['8.8.8.8']*10000
        service=LanDiscovery(REGTEST,18444,1,hints.append,interfaces,clock=lambda:now[0])
        self.assertEqual(lan.MAX_INTERFACES,len(service.interfaces))
        raw=encode_beacon(REGTEST,34567,2)
        for i in range(200):
            now[0]=i
            service.datagram_received(raw,(f'10.1.{i//250}.{i%250+1}',18445))
        self.assertEqual(lan.MAX_TRACKED_SOURCES,len(service._sources))


class DatagramLifecycleTests(unittest.IsolatedAsyncioTestCase):
    async def test_missing_interface_opens_no_socket(self):
        service=LanDiscovery(REGTEST,18444,1,Mock(),['127.0.0.1','8.8.8.8'])
        with patch.object(lan.socket,'socket') as sock:
            await service.start();sock.assert_not_called()
        self.assertEqual('no_lan_interface',service.state)
        await service.stop()

    async def test_socket_failure_is_unavailable_without_aborting_node_operations(self):
        service=LanDiscovery(REGTEST,18444,1,Mock(),['10.1.2.3'])
        with patch.object(lan.socket,'socket',side_effect=OSError('isolated socket error')):
            await service.start()
        self.assertEqual('unavailable',service.state)
        self.assertNotIn('isolated socket error',str(service.info()))
        await service.stop()

    async def test_multicast_setup_has_ttl_one_bounded_interfaces_and_no_unicast_destination(self):
        service=LanDiscovery(REGTEST,34567,1,Mock(),['10.1.2.3','192.168.1.7'])
        sock=Mock();transport=Mock()
        loop=asyncio.get_running_loop()
        # Do not replace the shared socket.socket type: the Windows event loop
        # still needs that type while this fixture awaits its announcement.
        socket_module=SimpleNamespace(**vars(socket));socket_module.socket=Mock(return_value=sock)
        with patch.object(lan,'socket',socket_module),\
             patch.object(loop,'create_datagram_endpoint',AsyncMock(return_value=(transport,service))):
            await service.start();await asyncio.sleep(.01)
            sock.bind.assert_called_once_with(('0.0.0.0',lan.PORT))
            self.assertIn(((socket.IPPROTO_IP,socket.IP_MULTICAST_TTL,1),{}),[(c.args,c.kwargs) for c in sock.setsockopt.call_args_list])
            self.assertEqual(2,transport.sendto.call_count)
            self.assertEqual([(lan.GROUP,lan.PORT)]*2,[c.args[1] for c in transport.sendto.call_args_list])
            await service.stop();transport.close.assert_called_once()

    async def test_real_loopback_udp_is_received_but_not_promoted_to_lan_hint(self):
        hints=[];service=LanDiscovery(REGTEST,18444,1,hints.append,[])
        transport,_=await asyncio.get_running_loop().create_datagram_endpoint(lambda:service,local_addr=('127.0.0.1',0))
        sender=socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
        try:
            sender.sendto(encode_beacon(REGTEST,34567,2),transport.get_extra_info('sockname'))
            await eventually(lambda:service.stats['datagrams_received']==1)
            self.assertEqual(1,service.stats['rejected']);self.assertFalse(hints)
        finally:sender.close();transport.close();await service.stop()


class PeerLanIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        WORK.mkdir(parents=True,exist_ok=True)
        self.temporary=tempfile.TemporaryDirectory(prefix='sumuww-lan-integration-',dir=WORK)
        self.nodes=[]

    async def asyncTearDown(self):
        await asyncio.gather(*(n.stop() for n in self.nodes),return_exceptions=True)
        self.temporary.cleanup()

    def node(self,name,**options):
        node=PeerNode(Path(self.temporary.name)/(name+'.sqlite'),poll_interval=.03,timeout=2,**options)
        self.nodes.append(node);return node

    async def test_lan_and_discovery_optout_open_no_beacon_component(self):
        for i,options in enumerate(({}, {'allow_internet':True}, {'allow_lan':True,'discover_peers':False})):
            node=self.node(str(i),**options)
            with patch('sumuww.peer.LanDiscovery') as component:
                await node.start();component.assert_not_called()
            self.assertEqual('disabled',node.info()['lan_discovery']['state'])

    async def test_lan_optin_scope_keeps_public_hints_only_with_internet_permission(self):
        mixed=self.node('mixed',allow_lan=True,allow_internet=True)
        self.assertTrue(mixed._addresses.add_hint(('192.168.1.7',18444)))
        self.assertTrue(mixed._addresses.add_hint(('8.8.8.8',18444)))
        local=self.node('lan-only',allow_lan=True)
        self.assertTrue(local._addresses.add_hint(('192.168.1.7',18444)))
        with self.assertRaises(ValueError):local._addresses.add_hint(('8.8.8.8',18444))
        with self.assertRaises(ValueError):_endpoint('peer.example',18444,allow_lan=True)

    async def test_udp_hint_alone_never_sets_mining_ready_or_saves_unverified_contact(self):
        node=self.node('hint-only',allow_lan=True)
        node._received_lan_hint(('192.168.1.7',18444))
        self.assertFalse(node.info()['mining_ready'])
        self.assertEqual(0,node.chain.info()['height'])
        self.assertFalse(node._addresses.path.exists())

    async def test_manual_wildcard_lan_discovery_reads_interfaces_without_changing_port(self):
        node=self.node('manual-wildcard-lan',host='0.0.0.0',port=0,allow_lan=True)
        with patch('sumuww.peer.enumerate_ipv4_interfaces',return_value=[InterfaceAddress('192.168.1.7')]) as interfaces,\
             patch.object(LanDiscovery,'start',AsyncMock()):
            await node.start()
        interfaces.assert_awaited_once()
        self.assertFalse(node.auto_address)
        self.assertEqual(('192.168.1.7',),node._lan_discovery.interfaces)
        self.assertEqual(node.address[1],decode_beacon(node._lan_discovery.payload,REGTEST)[0])
        self.assertFalse(node.allow_internet)

    async def test_loopback_multicast_fixture_finds_nodes_without_manual_tcp_addresses(self):
        # The temporary scope override below is fixture-only. Production LAN
        # source validation excludes 127/8; no public or physical-LAN claim.
        with patch.object(lan,'_LAN',(ipaddress.IPv4Network('127.0.0.0/8'),)):
            a=self.node('multicast-a',allow_lan=True,discovery_scope='loopback')
            b=self.node('multicast-b',allow_lan=True,discovery_scope='loopback')
            alice,bob=RegtestKey.from_int(1),RegtestKey.from_int(2)
            a.chain.mine(alice.script_pubkey,100)
            await a.start();await b.start()
            # Start both receivers before the ordinary interval's next beacon.
            for node in (a,b):
                if node._lan_discovery.state!='active':
                    self.fail('Loopback multicast fixture could not start')
                node._lan_discovery._socket.setsockopt(socket.IPPROTO_IP,socket.IP_MULTICAST_IF,
                                                       socket.inet_aton('127.0.0.1'))
                node._lan_discovery.transport.sendto(node._lan_discovery.payload,(lan.GROUP,lan.PORT))
            await eventually(lambda:b.chain.info()['height']==100 and
                             a.synchronization_info()['mining_ready'] and
                             b.synchronization_info()['mining_ready'],timeout=15)
            self.assertFalse(a._configured);self.assertFalse(b._configured)
            self.assertGreater(a._lan_discovery.stats['hints_received']+b._lan_discovery.stats['hints_received'],0)
            tx=create_payment(a.chain,alice,bob.script_pubkey,COIN,1000);a.chain.submit_transaction(tx)
            await eventually(lambda:any(t.txid()==tx.txid() for t in b.chain.mempool_transactions()))
            b.chain.mine(alice.script_pubkey,1)
            await eventually(lambda:a.chain.info()['height']==101)
            self.assertEqual(COIN,a.chain.balance(bob.script_pubkey))
            query=await probe_peer(f'127.0.0.1:{a.address[1]}',network='regtest',timeout=2)
            self.assertEqual('reachable',query['status'])
            self.assertTrue(a.synchronization_info()['mining_ready'])


if __name__=='__main__':unittest.main()
