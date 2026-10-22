import asyncio,tempfile,unittest
from pathlib import Path
from sumuww.peer import PeerNode
from unittest.mock import patch

class UniquePeerTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.nodes=[]
    async def asyncTearDown(self):
        await asyncio.gather(*(n.stop() for n in self.nodes))
        self.assertTrue(all(not n._sessions and not n._tasks for n in self.nodes))
        self.tmp.cleanup()
    def node(self,**options):
        n=PeerNode(Path(self.tmp.name)/f'{len(self.nodes)}.sqlite',allow_internet=True,
            discover_peers=False,dht_enabled=False,poll_interval=.05,timeout=2,**options)
        self.nodes.append(n);return n
    async def wait(self,check):
        for _ in range(200):
            if check():return
            await asyncio.sleep(.025)
        self.fail('Unique peer condition timed out')
    async def test_discovered_session_promoted_without_replacement_or_duplicate(self):
        a=self.node();b=self.node();await a.start();await b.start()
        task=a._spawn(a._discovered_connection(b.address),'owned-discovered')
        await self.wait(lambda:a.info()['peers']==1)
        original=next(iter(a._sessions.values()))
        await a.connect(*b.address)
        for _ in range(12):
            await asyncio.sleep(.05)
            self.assertEqual(1,a.info()['peers']);self.assertIn(original,a._sessions.values())
        self.assertEqual(1,a.info()['stats']['connections'])
    async def test_simultaneous_cross_dial_converges_to_one_session(self):
        a=self.node();b=self.node();await a.start();await b.start()
        await asyncio.gather(a.add_peer(*b.address),b.add_peer(*a.address))
        await self.wait(lambda:a.info()['peers']==b.info()['peers']==1)
        for _ in range(12):
            await asyncio.sleep(.05)
            self.assertEqual(1,a.info()['peers']);self.assertEqual(1,b.info()['peers'])
    async def test_cross_dial_before_sync_preserves_reconnect_contacts_after_sync(self):
        a=self.node(discovery_scope='loopback');b=self.node(discovery_scope='loopback');a.nonce=1;b.nonce=2
        await a.start();await b.start()
        gate=asyncio.Event()
        original=PeerNode._received_headers
        async def held_headers(node,session,payload):
            # Other AppService nodes may run on separate loops in a combined
            # Android test run. Never attach their traffic to this test's gate.
            if node in (a,b):await gate.wait()
            return await original(node,session,payload)
        with patch.object(PeerNode,'_received_headers',held_headers):
            try:
                await a.connect(*b.address)
                await self.wait(lambda:a.info()['peers']==b.info()['peers']==1)
                await b.add_peer(*a.address)
                await self.wait(lambda:b.info()['stats']['duplicate_connection_rejections']>0)
                self.assertNotIn(a.address,b._addresses.known())
                gate.set()
                await self.wait(lambda:a.synchronization_info()['mining_ready'] and b.synchronization_info()['mining_ready'])
                await self.wait(lambda:a.address in b._addresses.known() and b.address in a._addresses.known())
                self.assertEqual(1,a.info()['peers']);self.assertEqual(1,b.info()['peers'])
            finally:
                gate.set()
    async def test_ipv4_ipv6_alias_keeps_existing_and_can_reconnect_after_stop(self):
        a=self.node();b=self.node(host='0.0.0.0');await a.start();await b.start()
        self.assertTrue(b.info()['ipv6_listener']['active'],b.info())
        await a.connect('127.0.0.1',b.address[1])
        await self.wait(lambda:len(a._healthy_sessions())==1)
        original=next(iter(a._sessions.values()))
        await a.add_peer('::1',b.address[1])
        await asyncio.sleep(.5)
        self.assertGreater(a.info()['stats']['duplicate_connection_rejections'],0,a.info())
        await asyncio.sleep(.4)
        self.assertEqual(1,a.info()['peers']);self.assertEqual(1,b.info()['peers'])
        self.assertIs(original,a._outgoing_session(('::1',b.address[1])))
        attempts=a.info()['stats']['connections'];await asyncio.sleep(.4)
        self.assertEqual(attempts,a.info()['stats']['connections'])
        original.writer.close()
        await self.wait(lambda:a.info()['peers']==b.info()['peers']==1 and original not in a._sessions.values())
    async def test_asymmetric_sync_rejecting_alternate_keeps_original_route(self):
        a=self.node(discovery_scope='loopback');b=self.node(discovery_scope='loopback')
        a.nonce=2;b.nonce=1
        await a.start();await b.start()
        gate=asyncio.Event();original=PeerNode._received_headers
        async def held_headers(node,session,payload):
            if node is b:await gate.wait()
            return await original(node,session,payload)
        with patch.object(PeerNode,'_received_headers',held_headers):
            try:
                await a.connect(*b.address)
                await self.wait(lambda:a.synchronization_info()['mining_ready'])
                preserved=next(iter(a._sessions.values()))
                await b.add_peer(*a.address)
                await self.wait(lambda:b.info()['stats']['duplicate_connection_rejections']>0)
                for _ in range(10):
                    await asyncio.sleep(.03)
                    self.assertIn(preserved,a._sessions.values())
                    self.assertTrue(a.synchronization_info()['mining_ready'])
                gate.set()
                await self.wait(lambda:b.synchronization_info()['mining_ready'])
                self.assertEqual(1,a.info()['peers']);self.assertEqual(1,b.info()['peers'])
            finally:gate.set()
    async def test_dns_alias_does_not_consume_second_peer_slot(self):
        a=self.node();b=self.node();await a.start();await b.start();await a.connect(*b.address)
        original=next(iter(a._sessions.values()))
        await a.add_peer('localhost',b.address[1])
        await self.wait(lambda:a.info()['stats']['duplicate_connection_rejections']>0)
        self.assertEqual(1,a.info()['peers']);self.assertIn(original,a._sessions.values())
        self.assertGreater(a.info()['stats']['duplicate_connection_rejections'],0)
    async def test_discovery_and_manual_race_has_single_reserved_endpoint(self):
        a=self.node();b=self.node();await a.start();await b.start()
        a._spawn(a._discovered_connection(b.address),'owned-racing-discovery')
        await a.add_peer(*b.address)
        await self.wait(lambda:a.info()['peers']==1)
        await asyncio.sleep(.5)
        self.assertEqual(1,a.info()['peers']);self.assertEqual(1,len(a._sessions))

