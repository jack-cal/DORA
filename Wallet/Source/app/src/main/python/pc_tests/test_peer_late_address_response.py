"""Delayed optional discovery replies must not evict validated TCP peers."""
import asyncio
from pathlib import Path
import tempfile
import unittest
from sumuww.peer import PeerNode
from sumuww.wire import encode_addresses

async def until(check,seconds=8):
    async with asyncio.timeout(seconds):
        while not check():await asyncio.sleep(.02)

class DelayedAddresses(PeerNode):
    delay_enabled=False
    async def _serve_addresses(self,session,payload):
        if self.delay_enabled:
            self.delay_enabled=False
            await asyncio.sleep(1.1)
        await super()._serve_addresses(session,payload)

class OutgoingClient(PeerNode):
    # This fixture has no public listener claim. Prevent an unrelated
    # cross-dial/duplicate-route retirement from replacing the measured socket.
    def _own_listener(self):return None

class LateAddressTests(unittest.IsolatedAsyncioTestCase):
    async def test_late_reply_keeps_anchor_and_connects_fresh_advertised_peer(self):
        asyncio.get_running_loop().set_debug(False)
        nodes=[]
        with tempfile.TemporaryDirectory() as tmp:
            async def start(cls=PeerNode,timeout=3):
                node=cls(Path(tmp)/str(len(nodes))/'node.sqlite',network='regtest',
                         host='127.0.0.1',port=0,discover_peers=True,discovery_scope='loopback',
                         dht_enabled=False,poll_interval=.02,timeout=timeout,max_peers=None,outgoing_target=None)
                nodes.append(node);await node.start();return node
            try:
                remote=await start(DelayedAddresses);third=await start()
                await remote.connect(*third.address)
                await until(lambda:remote.info()['synchronized_peers']==1)
                remote.delay_enabled=True
                client=await start(OutgoingClient,timeout=.25)
                await client.connect(*remote.address)
                await until(lambda:client.info()['synchronized_peers']==1)
                anchor=next(s for s in client._sessions.values() if s.ready)
                await asyncio.sleep(.45)
                self.assertFalse(anchor.discovery_requested, 'The short optional-query timer really expired')
                self.assertTrue(anchor.synchronized)
                await until(lambda:client.info()['synchronized_peers']==2)
                self.assertEqual(client.info()['stats']['protocol_errors'],0,client.info()['last_peer_error'])
                self.assertTrue(id(anchor.writer) in client._sessions,client.info()['last_peer_error'])
                self.assertFalse(anchor.writer.is_closing())
                self.assertEqual(client.info()['stats']['protocol_errors'],0,client.info())
                self.assertGreater(anchor.address_response_count,0)
                # A duplicate from overlapping old/new requests is optional
                # discovery data, not grounds to discard a validated chain.
                sender=next(s for s in remote._sessions.values() if s.nonce==client.nonce)
                await remote._send(sender,'addr',encode_addresses(None,()))
                await asyncio.sleep(.5)
                self.assertEqual(client.info()['synchronized_peers'],2,client.info())
                self.assertEqual(client.info()['stats']['protocol_errors'],0)
            finally:
                for node in nodes:await node.stop()

if __name__=='__main__':unittest.main(verbosity=2)
