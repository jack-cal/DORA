"""A slow public reply differs from a stalled partial frame or unknown chain."""
import asyncio,time,tempfile,unittest
from pathlib import Path
from sumuww import peer

class DelayedVersion(peer.PeerNode):
    async def _handshake(self,session):
        await asyncio.sleep(.2)
        await super()._handshake(session)

class PublicReplyTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.folder=tempfile.TemporaryDirectory();self.nodes=[]
    async def asyncTearDown(self):
        for node in reversed(self.nodes):await node.stop()
        self.folder.cleanup()
    async def node(self,kind=peer.PeerNode,**options):
        node=kind(Path(self.folder.name)/f'{len(self.nodes)}.sqlite',
                  discover_peers=False,dht_enabled=False,auto_address=False,
                  poll_interval=.02,**options)
        self.nodes.append(node);await node.start();return node
    async def until(self,predicate):
        async with asyncio.timeout(4):
            while not predicate():await asyncio.sleep(.01)
    async def test_slow_first_reply_keeps_one_outgoing_attempt(self):
        remote=await self.node(DelayedVersion,timeout=1)
        client=await self.node(timeout=.05,allow_internet=True)
        task=asyncio.create_task(client._discovered_connection(remote.address))
        try:
            await self.until(lambda:client.synchronization_info()['mining_ready'])
            self.assertEqual(1,client._stats['reconnect_attempts'])
            self.assertEqual(0,client._stats['protocol_errors'])
            self.assertEqual(remote.chain.tip_hash,client.chain.tip_hash)
        finally:
            task.cancel();await asyncio.gather(task,return_exceptions=True)
    async def test_first_byte_still_starts_short_partial_frame_deadline(self):
        writers=[]
        def partial(reader,writer):writers.append(writer);writer.write(b'\xfa')
        server=await asyncio.start_server(partial,'127.0.0.1',0)
        client=await self.node(timeout=.05,allow_internet=True)
        try:
            started=time.monotonic()
            await client._discovered_connection(server.sockets[0].getsockname()[:2])
            self.assertLess(time.monotonic()-started,1)
            self.assertIn('Whole-frame read timed out',client._last_error)
            self.assertFalse(client.synchronization_info()['mining_ready'])
        finally:
            for writer in writers:writer.close();await writer.wait_closed()
            server.close();await server.wait_closed()
    async def test_only_known_verified_tip_gets_bounded_refresh_grace(self):
        remote=await self.node(timeout=1)
        client=await self.node(timeout=1,allow_internet=True)
        await client.connect(*remote.address)
        await self.until(lambda:client.synchronization_info()['mining_ready'])
        session=next(iter(client._sessions.values()))
        now=asyncio.get_running_loop().time()
        session.last_verified_at=now-40
        session.header_requested=True;session.header_requested_at=now-30
        self.assertTrue(client.synchronization_info()['mining_ready'])
        session.unknown_blocks.add(bytes([42])*32)
        self.assertFalse(client.synchronization_info()['mining_ready'])
        session.unknown_blocks.clear()
        session.verified_once=False
        self.assertFalse(client.synchronization_info()['mining_ready'])
        session.verified_once=True
        session.header_requested=False
        self.assertFalse(client.synchronization_info()['mining_ready'])
        session.header_requested=True
        session.last_verified_at=now-150
        self.assertFalse(client.synchronization_info()['mining_ready'])
        session.header_requested_at=now-client._reply_timeout()-1
        await client._poll_session(session,client.chain.tip_hash,(),now)
        self.assertTrue(session.writer.is_closing())
        self.assertEqual('block_response_timeout',session.local_close_reason)
