import asyncio,tempfile,unittest
from pathlib import Path
from sumuww.peer import PeerNode

class FullOutgoingAdmissionTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):self.tmp=tempfile.TemporaryDirectory();self.nodes=[]
    async def asyncTearDown(self):
        for n in reversed(self.nodes):await n.stop()
        self.tmp.cleanup()
    def node(self,limit=8):
        n=PeerNode(Path(self.tmp.name)/f'{len(self.nodes)}.sqlite',allow_internet=True,
                   discover_peers=True,dht_enabled=False,discovery_scope='loopback',
                   max_peers=limit,outgoing_target=min(8,limit),poll_interval=.02,timeout=1)
        async def hold_background_discovery():
            while n.running:await asyncio.sleep(1)
        n._discover=hold_background_discovery
        self.nodes.append(n);return n
    async def wait(self,p):
        async with asyncio.timeout(4):
            while not p():await asyncio.sleep(.01)
    async def test_validated_newcomer_can_replace_excess_learned_outgoing(self):
        hub=self.node(2);a=self.node();b=self.node();new=self.node()
        for n in self.nodes:await n.start()
        for target in (a.address,b.address):
            hub._discovery_workers[target]=hub._spawn(hub._discovered_connection(target),'owned-learned')
        await self.wait(lambda:len(hub._healthy_sessions())==2)
        old=set(hub._healthy_sessions())
        await new.add_peer(*hub.address)
        await self.wait(lambda:any(s.outgoing is None and s.synchronized for s in hub._sessions.values()))
        hub._maintain_incoming_probe()
        self.assertIsNone(hub._incoming_probe,'Newcomer remains temporary when all old routes are outgoing')
        await self.wait(lambda:len(hub._sessions)==2)
        self.assertEqual(1,sum(s.outgoing is None for s in hub._healthy_sessions()))
        self.assertEqual(1,sum(s.outgoing is not None for s in hub._healthy_sessions()))
        self.assertTrue(new.synchronization_info()['mining_ready'])
        self.assertEqual(1,sum(s.writer.is_closing() or s not in hub._sessions.values() for s in old))
    async def test_unvalidated_probe_never_displaces_healthy_outgoing(self):
        hub=self.node(2);a=self.node();b=self.node()
        for n in self.nodes:await n.start()
        for target in (a.address,b.address):hub._discovery_workers[target]=hub._spawn(hub._discovered_connection(target),'owned-learned')
        await self.wait(lambda:len(hub._healthy_sessions())==2)
        old=set(hub._healthy_sessions());reader,writer=await asyncio.open_connection(*hub.address)
        try:
            await self.wait(lambda:hub._incoming_probe is not None);hub._maintain_incoming_probe()
            self.assertTrue(all(not s.writer.is_closing() for s in old));self.assertFalse(hub._incoming_probe.synchronized)
        finally:writer.close();await writer.wait_closed()

    async def test_explicit_outgoing_preferences_are_not_displaced(self):
        hub=self.node(2);a=self.node();b=self.node();new=self.node()
        for n in self.nodes:await n.start()
        await hub.add_peer(*a.address);await hub.add_peer(*b.address)
        await self.wait(lambda:len(hub._healthy_sessions())==2)
        old=set(hub._healthy_sessions());await new.add_peer(*hub.address)
        await self.wait(lambda:any(s.outgoing is None and s.synchronized for s in hub._sessions.values()))
        hub._maintain_incoming_probe()
        self.assertTrue(all(not s.writer.is_closing() for s in old))
        self.assertIsNotNone(hub._incoming_probe)
        self.assertEqual(0,hub.info()['stats']['incoming_replacements'])
