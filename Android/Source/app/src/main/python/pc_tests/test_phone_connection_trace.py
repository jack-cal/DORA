import asyncio,json,tempfile,unittest
from pathlib import Path
from sumuww.peer import PeerNode

class PhoneConnectionTraceTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temporary=tempfile.TemporaryDirectory()
        self.nodes=[]
        for name in ('client','server'):
            node=PeerNode(Path(self.temporary.name)/(name+'.sqlite'),network='regtest',
                          host='127.0.0.1',port=0,poll_interval=.02,timeout=1)
            self.nodes.append(node)
            await node.start()
        self.client,self.server=self.nodes
        await self.client.connect(*self.server.address)
        await self.wait(lambda:self.client.synchronization_info()['synchronized_peers']==1)

    async def asyncTearDown(self):
        for node in self.nodes:await node.stop()
        self.temporary.cleanup()

    async def wait(self,predicate):
        for _ in range(300):
            if predicate():return
            await asyncio.sleep(.01)
        self.fail('Expected live transport event was not recorded')

    async def test_remote_eof_survives_unrelated_failed_discovery_attempts(self):
        await self.server.stop()
        await self.wait(lambda:bool(self.client._connected_peer_events))
        event=self.client.info()['recent_connected_peer_events'][-1]
        self.assertEqual('disconnected',event['outcome'])
        self.assertTrue(event['reader_eof'])
        self.assertFalse(event['local_writer_closing'])
        self.assertIsNotNone(event['last_received'])
        self.assertIsNotNone(event['peer_id'])
        for i in range(64):self.client._record_peer_attempt(('127.0.0.1',10000+i),'connect_timeout')
        state=self.client.info()
        self.assertEqual(16,len(state['recent_peer_attempts']))
        self.assertEqual(event,state['recent_connected_peer_events'][-1])
        json.dumps(state,allow_nan=False)

    async def test_local_writer_close_is_distinguishable_from_remote_eof(self):
        session=next(s for s in self.client._sessions.values() if s.ready)
        session.writer.close()
        await self.wait(lambda:bool(self.client._connected_peer_events))
        event=self.client.info()['recent_connected_peer_events'][-1]
        self.assertTrue(event['local_writer_closing'])
        self.assertGreaterEqual(event['duration_seconds'],0)

if __name__=='__main__':unittest.main()
