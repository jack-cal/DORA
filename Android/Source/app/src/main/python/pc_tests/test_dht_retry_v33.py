"""Deterministic retry scheduling and owned UDP/TCP disconnect recovery.

Virtual time is limited to scheduler unit tests. The recovery test uses real
loopback sockets and regtest PoW; no public router, real wallet or main coin.
"""
import asyncio
from pathlib import Path
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from sumuww import dht_discovery as dht
from sumuww.peer import PeerNode
from sumuww.profiles import REGTEST
from sumuww.wallet import RegtestKey
from tests.test_dht_discovery_v29 import KrpcFixture,eventually


class RetryScheduleTests(unittest.IsolatedAsyncioTestCase):
    def discovery(self,connected,clock):
        result=dht.DhtDiscovery(REGTEST,lambda hints:None,scope='loopback',
                                routers=[('127.0.0.1',1)],clock=clock,
                                connected_provider=lambda:connected[0],
                                settled_provider=lambda:connected[0],
                                contact_provider=lambda:('127.0.0.1',18444))
        result._active=True
        return result

    def sleep_module(self,sleep):
        return SimpleNamespace(**{**vars(asyncio),'sleep':sleep})

    async def test_no_connected_peer_retries_after_15_even_after_successful_announce(self):
        now=[1000.];connected=[False];service=self.discovery(connected,lambda:now[0])
        delays=[];round_times=[]
        async def lookup():
            self.assertTrue(service.info()['round_in_progress'])
            self.assertEqual(0,service.info()['next_query_seconds'])
            round_times.append(now[0])
            service._stats['announcements']+=1
            if len(round_times)==2:service._active=False
            return ()
        async def sleep(delay):
            delays.append(delay)
            self.assertLessEqual(delay,1)
            self.assertFalse(service.info()['round_in_progress'])
            now[0]+=delay
        service._lookup=lookup
        with patch.object(dht,'asyncio',self.sleep_module(sleep)):
            await service._run()
        self.assertEqual([1000.,1015.],round_times)
        self.assertEqual(15,sum(delays))
        self.assertEqual(0,service.info()['next_query_seconds'])

    async def test_connected_refresh_300_and_loss_wakes_after_one_poll(self):
        now=[1000.];connected=[True];service=self.discovery(connected,lambda:now[0])
        snapshots=[]
        async def sleep(delay):
            snapshots.append(service.info()['next_query_seconds'])
            now[0]+=delay;connected[0]=False
        with patch.object(dht,'asyncio',self.sleep_module(sleep)):
            await service._wait_for_next_query()
        self.assertEqual([300],snapshots)
        self.assertEqual(1001.,now[0])
        self.assertEqual(0,service.info()['next_query_seconds'])

    async def test_new_connection_extends_refresh_then_loss_wakes(self):
        now=[1000.];connected=[False];service=self.discovery(connected,lambda:now[0])
        snapshots=[]
        async def sleep(delay):
            snapshots.append(service.info()['next_query_seconds'])
            now[0]+=delay;connected[0]=len(snapshots)==1
        with patch.object(dht,'asyncio',self.sleep_module(sleep)):
            await service._wait_for_next_query()
        self.assertEqual([15,300],snapshots)
        self.assertEqual(1002.,now[0])
        self.assertEqual(0,service.info()['next_query_seconds'])

    async def test_countdown_ceil_and_round_flag_follow_actual_lock(self):
        now=[1000.2];service=self.discovery([False],lambda:now[0])
        service._next_query_at=1000.21
        self.assertEqual(1,service.info()['next_query_seconds'])
        entered=asyncio.Event();release=asyncio.Event()
        async def lookup():entered.set();await release.wait();return ()
        service._lookup=lookup
        task=asyncio.create_task(service.lookup_once())
        await asyncio.wait_for(entered.wait(),1)
        self.assertTrue(service.info()['round_in_progress'])
        release.set();await task
        self.assertFalse(service.info()['round_in_progress'])

    async def test_stop_cancels_wait_and_has_no_delayed_requery(self):
        service=self.discovery([True],time.monotonic)
        calls=[]
        async def lookup():calls.append(1);return ()
        service._lookup=lookup
        service._task=asyncio.create_task(service._run())
        await eventually(lambda:service.info()['next_query_seconds']>=299)
        await asyncio.wait_for(service.stop(),.2)
        await asyncio.sleep(.02)
        self.assertEqual(1,len(calls))
        self.assertFalse(service.info()['round_in_progress'])
        self.assertEqual(0,service.info()['next_query_seconds'])
        self.assertIsNone(service._task)

    def test_connected_provider_must_be_callable(self):
        with self.assertRaises(ValueError):
            dht.DhtDiscovery(REGTEST,lambda hints:None,connected_provider=True)


class RealRetryRecoveryTests(unittest.IsolatedAsyncioTestCase):
    async def test_last_tcp_peer_loss_wakes_dht_and_syncs_replacement(self):
        nodes=[];transport=None
        with tempfile.TemporaryDirectory(prefix='sumuww-owned-dht-retry-') as temporary:
            folder=Path(temporary)
            def node(name,**extra):
                result=PeerNode(folder/(name+'.sqlite'),network='regtest',host='127.0.0.1',port=0,
                                poll_interval=.03,timeout=.5,allow_internet=True,
                                discovery_scope='loopback',bootstrap_scope='loopback',
                                discovery_interval=1,**extra)
                nodes.append(result);return result
            try:
                first=node('first',dht_enabled=False)
                replacement=node('replacement',dht_enabled=False)
                key=RegtestKey.from_int(333)
                first.chain.mine(key.script_pubkey,3)
                replacement.chain.mine(key.script_pubkey,4)
                await first.start();await replacement.start()
                router=KrpcFixture(peers=[first.address])
                transport,_=await asyncio.get_running_loop().create_datagram_endpoint(
                    lambda:router,local_addr=('127.0.0.1',0))
                client=node('client',dht_enabled=True,dht_scope='loopback',
                            dht_routers=[router.address],dht_query_timeout=.2,dht_round_timeout=2)
                await client.start()
                # A single healthy peer does not settle discovery anymore.
                # Wait for sync and a scheduled retry, then allow one polling
                # cycle to observe the live connection before disconnecting it.
                await eventually(lambda:client.synchronization_info()['mining_ready']
                                 and client.info()['dht_discovery']['next_query_seconds']>0,timeout=8)
                await asyncio.sleep(dht.CONNECTION_POLL_INTERVAL+.05)
                self.assertEqual(3,client.chain.info()['height'])
                before=client.info()['dht_discovery']['stats']['rounds']
                router.peers=(replacement.address,)
                began=time.monotonic()
                await first.stop()
                await eventually(lambda:client.info()['dht_discovery']['stats']['rounds']>before,timeout=1.5)
                self.assertLess(time.monotonic()-began,1.4)
                await eventually(lambda:client.chain.tip_hash==replacement.chain.tip_hash
                                 and client.synchronization_info()['mining_ready'],timeout=5)
                self.assertEqual(4,client.chain.info()['height'])
                self.assertTrue(client._has_dht_connected_peer())
                self.assertGreaterEqual(client.info()['dht_discovery']['stats']['rounds'],2)
                self.assertFalse(router.errors)
            finally:
                await asyncio.gather(*(item.stop() for item in nodes),return_exceptions=True)
                if transport is not None:transport.close()
                await asyncio.sleep(.01)


if __name__=='__main__':unittest.main()
