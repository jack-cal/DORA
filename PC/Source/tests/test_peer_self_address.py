"""Actual isolated listeners and runtime address state; no public probes."""
import asyncio
from contextlib import contextmanager
import errno
import os
from pathlib import Path
import socket
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from sumuww import peer
from sumuww.self_address import InterfaceAddress
from sumuww import self_address
from sumuww.__main__ import create_payment
from sumuww.primitives import COIN
from sumuww.wallet import RegtestKey

WORK=Path(os.environ.get('SUMUWW_TEST_WORKDIR',tempfile.gettempdir()))
COLLISION_FIXTURE_MODES=[]


async def eventually(predicate,timeout=3):
    deadline=time.monotonic()+timeout
    while not predicate():
        if time.monotonic()>deadline:raise AssertionError('Local address fixture did not reach its expected state')
        await asyncio.sleep(.02)


class PeerOwnAddressTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        WORK.mkdir(parents=True,exist_ok=True)
        self.temporary=tempfile.TemporaryDirectory(prefix='sumuww-own-address-',dir=WORK)
        self.directory=Path(self.temporary.name);self.nodes=[]

    async def asyncTearDown(self):
        await asyncio.gather(*(node.stop() for node in self.nodes),return_exceptions=True)
        self.temporary.cleanup()

    def node(self,name,**options):
        node=peer.PeerNode(self.directory/(name+'.sqlite'),poll_interval=.03,timeout=.5,**options)
        self.nodes.append(node);return node

    @contextmanager
    def occupied_standard_port(self,host):
        """Own a real conflict when possible; never disturb another port owner."""
        blocker=socket.socket(socket.AF_INET,socket.SOCK_STREAM)
        if hasattr(socket,'SO_EXCLUSIVEADDRUSE'):
            blocker.setsockopt(socket.SOL_SOCKET,socket.SO_EXCLUSIVEADDRUSE,1)
        try:
            blocker.bind((host,18444));blocker.listen(1)
        except OSError as error:
            blocker.close()
            if not (error.errno==errno.EADDRINUSE or getattr(error,'winerror',None)==10048):raise
            # An existing app is left untouched. Keep subsequent fallback and
            # P2P traffic real; only the first occupied bind is synthesized.
            actual=asyncio.start_server
            async def occupied(callback,address,port,**options):
                if address==host and port==18444:
                    raise OSError(errno.EADDRINUSE,'standard port occupied by an existing owner')
                return await actual(callback,address,port,**options)
            COLLISION_FIXTURE_MODES.append({'test':self._testMethodName,'mode':'mocked_occupied_bind_existing_owner_untouched'})
            with patch('sumuww.peer.asyncio.start_server',side_effect=occupied):yield
        else:
            COLLISION_FIXTURE_MODES.append({'test':self._testMethodName,'mode':'actual_owned_loopback_socket' if host=='127.0.0.1' else 'actual_owned_wildcard_socket'})
            try:yield
            finally:blocker.close()

    async def test_automatic_wildcard_local_contact_connects_without_own_ip_input(self):
        server=self.node('server',host='0.0.0.0',allow_internet=True,auto_address=True)
        with patch('sumuww.peer.enumerate_ipv4_interfaces',return_value=[InterfaceAddress('192.168.3.4')]):
            await server.start()
        state=server.info()
        self.assertGreater(server.address[1],0)
        self.assertEqual([f'127.0.0.1:{server.address[1]}',f'192.168.3.4:{server.address[1]}'],state['own_addresses'])
        self.assertEqual('local_interface',state['self_address']['status'])
        self.assertIsNone(server._own_listener())
        self.assertFalse(state['mining_ready'])
        client=self.node('client');await client.start()
        await client.connect('127.0.0.1',server.address[1])
        await eventually(lambda:server.synchronization_info()['mining_ready'] and client.synchronization_info()['mining_ready'])
        self.assertEqual('not_verified',server.info()['self_address']['external_reachability'])

    async def test_direct_public_interface_is_runtime_hint_not_reachability_proof(self):
        node=self.node('public-hint',host='0.0.0.0',allow_internet=True,auto_address=True)
        with patch('sumuww.peer.enumerate_ipv4_interfaces',return_value=[InterfaceAddress('8.8.8.8')]):await node.start()
        self.assertEqual(('8.8.8.8',node.address[1]),node._own_listener())
        self.assertEqual('direct_public_interface',node.info()['self_address']['status'])
        self.assertEqual('not_verified',node.info()['self_address']['external_reachability'])
        self.assertFalse(node.info()['mining_ready'])
        self.assertEqual(0,node.info()['stats']['reconnect_attempts'])
        self.assertFalse(node._addresses.path.exists())
        self.assertEqual(0,node._add_bootstrap_hints([('8.8.8.8',node.address[1])]))

    async def test_refresh_replaces_stale_addresses_and_never_writes_them(self):
        node=self.node('refresh',host='0.0.0.0',allow_internet=True,auto_address=True)
        now=[0];node._self_clock=lambda:now[0]
        with patch('sumuww.peer.enumerate_ipv4_interfaces',return_value=[InterfaceAddress('8.8.8.8')]) as enumeration:
            await node.start();self.assertEqual(1,enumeration.call_count)
            now[0]=29;await asyncio.sleep(.06);self.assertEqual(1,enumeration.call_count)
            enumeration.return_value=[InterfaceAddress('192.168.3.4')]
            now[0]=30
            await eventually(lambda:enumeration.call_count==2)
        self.assertIsNone(node._own_listener())
        self.assertNotIn(f'8.8.8.8:{node.address[1]}',node.info()['own_addresses'])
        self.assertFalse(node._addresses.path.exists())

    async def test_interface_failure_removes_public_claim_but_listener_stays_usable(self):
        node=self.node('failed-interface',host='0.0.0.0',allow_internet=True,auto_address=True)
        with patch('sumuww.peer.enumerate_ipv4_interfaces',side_effect=OSError('synthetic private detail')):await node.start()
        state=node.info()['self_address']
        self.assertTrue(node.running);self.assertIsNone(node._own_listener())
        self.assertEqual('interface_lookup_failed',state['status'])
        self.assertEqual('interface_lookup_failed',state['refresh_error'])
        self.assertNotIn('synthetic private detail',str(state))
        reader,writer=await asyncio.open_connection('127.0.0.1',node.address[1])
        writer.close();await writer.wait_closed()

    async def test_manual_contact_precedence_survives_interface_failure(self):
        node=self.node('manual',host='0.0.0.0',allow_internet=True,auto_address=True,
                       advertised_endpoint=('1.1.1.1',18444))
        with patch('sumuww.peer.enumerate_ipv4_interfaces',side_effect=OSError('failed')):await node.start()
        self.assertEqual(('1.1.1.1',18444),node._own_listener())
        self.assertEqual('manual_contact',node.info()['self_address']['status'])

    async def test_optout_and_legacy_default_do_not_enumerate(self):
        for name,options in (('optout',{'auto_address':True}),('old',{})):
            node=self.node(name,**options)
            with patch('sumuww.peer.enumerate_ipv4_interfaces') as enumeration:await node.start()
            enumeration.assert_not_called()
            self.assertEqual([f'127.0.0.1:{node.address[1]}'],node.info()['own_addresses'])
            self.assertIsNone(node.info()['self_address']['public_contact'])
            await node.stop();self.assertEqual('not_running',node.info()['self_address']['status'])

    async def test_standard_port_collision_falls_back_before_start_failure(self):
        node=self.node('collision',port=18444,auto_address=True)
        actual=asyncio.start_server;calls=[]
        async def occupied(callback,host,port,**options):
            calls.append(port)
            if len(calls)==1:raise OSError(errno.EADDRINUSE,'fixture standard port occupied')
            return await actual(callback,host,port,**options)
        with patch('sumuww.peer.asyncio.start_server',side_effect=occupied):await node.start()
        self.assertEqual([18444,0],calls)
        self.assertTrue(node.running);self.assertGreater(node.address[1],0)
        self.assertTrue(node.info()['self_address']['port_fallback'])
        self.assertEqual([f'127.0.0.1:{node.address[1]}'],node.info()['own_addresses'])

    async def test_permission_manual_port_and_nonautomatic_errors_never_fallback(self):
        for i,(port,automatic,code) in enumerate(((18444,True,errno.EACCES),(18445,True,errno.EADDRINUSE),(18444,False,errno.EADDRINUSE))):
            node=self.node('failure'+str(i),port=port,auto_address=automatic)
            with patch('sumuww.peer.asyncio.start_server',side_effect=OSError(code,'injected')) as listen:
                with self.assertRaises(OSError):await node.start()
            self.assertEqual(1,listen.call_count)
            self.assertFalse(node.running)
            self.assertFalse(node.info()['self_address']['port_fallback'])

    async def test_fixed_advertised_contact_never_moves_listener_on_port_conflict(self):
        node=self.node('fixed-public-contact',host='0.0.0.0',port=18444,
                       allow_internet=True,auto_address=True,
                       advertised_endpoint=('1.1.1.1',18444))
        actual=asyncio.start_server;attempted=[]
        async def tracked(callback,host,port,**options):
            attempted.append(port)
            return await actual(callback,host,port,**options)
        with self.occupied_standard_port('0.0.0.0'):
            # Resolve after the collision fixture, including its optional mock.
            actual=asyncio.start_server
            with patch('sumuww.peer.asyncio.start_server',side_effect=tracked):
                with self.assertRaises(OSError):await node.start()
        self.assertEqual([18444],attempted)
        self.assertFalse(node.running)
        self.assertFalse(node.info()['self_address']['port_fallback'])
        self.assertEqual(('1.1.1.1',18444),node.advertised_endpoint)

    async def test_real_replacement_port_sync_mining_and_payment_relay(self):
        # The selected profile is regtest throughout. This creates no main coin
        # and uses only publicly known test keys in fresh temporary databases.
        alice=RegtestKey.from_int(1);bob=RegtestKey.from_int(2)
        server=self.node('replacement-miner',port=18444,auto_address=True)
        self.assertEqual('regtest',server.network.name)
        server.chain.mine(alice.script_pubkey,100)
        with self.occupied_standard_port('127.0.0.1'):
            await server.start()
            self.assertNotEqual(18444,server.address[1])
            self.assertTrue(server.info()['self_address']['port_fallback'])
            self.assertEqual([f'127.0.0.1:{server.address[1]}'],server.info()['own_addresses'])
            client=self.node('replacement-client');await client.start()
            await client.connect(*server.address)
            await eventually(lambda:client.chain.info()['height']==100 and
                             server.synchronization_info()['mining_ready'] and
                             client.synchronization_info()['mining_ready'],timeout=15)
            transaction=create_payment(server.chain,alice,bob.script_pubkey,COIN,1000)
            server.chain.submit_transaction(transaction)
            await eventually(lambda:any(tx.txid()==transaction.txid() for tx in client.chain.mempool_transactions()))
            server.chain.mine(alice.script_pubkey,1)
            await eventually(lambda:client.chain.info()['height']==101)
            self.assertEqual(server.chain.tip_hash,client.chain.tip_hash)
            self.assertEqual(COIN,client.chain.balance(bob.script_pubkey))
            self.assertFalse(client.chain.mempool_transactions())
            await client.stop()
            await eventually(lambda:not server.synchronization_info()['mining_ready'])

    async def test_invalid_auto_flag_rejected_before_database_creation(self):
        path=self.directory/'invalid.sqlite'
        with self.assertRaises(ValueError):peer.PeerNode(path,auto_address=1)
        self.assertFalse(path.exists())

    async def test_blocked_periodic_os_lookup_does_not_stall_poll_or_shutdown(self):
        node=self.node('blocked-lookup',host='0.0.0.0',allow_internet=True,auto_address=True)
        now=[0];node._self_clock=lambda:now[0]
        with patch('sumuww.peer.enumerate_ipv4_interfaces',return_value=[]):await node.start()
        client=self.node('companion');await client.start()
        await client.connect('127.0.0.1',node.address[1])
        await eventually(lambda:node.synchronization_info()['mining_ready'])
        entered,release,finished=threading.Event(),threading.Event(),threading.Event()
        def blocked():
            entered.set()
            try:release.wait(2);return ()
            finally:finished.set()
        try:
            with patch.object(self_address,'_ENUMERATION_SLOT',threading.BoundedSemaphore(1)),\
                 patch.object(self_address,'_windows_interfaces',side_effect=blocked):
                frames=node.info()['stats']['frames_sent'];now[0]=30
                await eventually(lambda:entered.is_set())
                heartbeat=time.monotonic();await asyncio.sleep(.05)
                self.assertLess(time.monotonic()-heartbeat,.2)
                self.assertFalse(finished.is_set())
                # Quiet connections no longer emit repeated pool/header
                # traffic. New valid work must still be relayed immediately
                # while the unrelated OS enumeration worker is blocked.
                node.chain.mine(RegtestKey.from_int(3801).script_pubkey,1)
                await eventually(lambda:node.info()['stats']['frames_sent']>frames,timeout=.2)
                self.assertTrue(node.synchronization_info()['mining_ready'])
                started=time.monotonic();await node.stop()
                self.assertLess(time.monotonic()-started,.3)
                self.assertFalse(finished.is_set())
                self.assertEqual('not_running',node.info()['self_address']['status'])
                release.set();await eventually(lambda:finished.is_set())
        finally:release.set()


if __name__=='__main__':unittest.main()
