"""Different signing generations must not poison native peer connectivity."""
import asyncio
import tempfile
from pathlib import Path
import unittest
from sumuww.peer import PeerNode
from sumuww.wire import (Version,encode_version,decode_version,read_frame,write_frame,
                         encode_headers,encode_getheaders)

class LegacyLinkTransportTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp=tempfile.TemporaryDirectory();self.writers=[];self.tasks=set()
        self.node=PeerNode(Path(self.temp.name)/'node.sqlite',boundary_activation=9000,
                           discover_peers=True,discovery_scope='loopback',dht_enabled=False,
                           poll_interval=.05,timeout=2)
        await self.node.start()
    async def asyncTearDown(self):
        for writer in self.writers:writer.close()
        await self.node.stop()
        for task in tuple(self.tasks):task.cancel()
        await asyncio.gather(*tuple(self.tasks),return_exceptions=True)
        self.temp.cleanup()
    async def test_outgoing_v5_falls_back_without_sending_new_hello_to_v4_peer(self):
        attempts=[];unexpected=[]
        async def old_peer(reader,writer):
            self.writers.append(writer);task=asyncio.current_task();self.tasks.add(task)
            try:
                own=Version(1,self.node.genesis,self.node.nonce^1,self.node.network.profile_id,self.node.chain.tip_hash)
                await write_frame(writer,'version',encode_version(own),2)
                frame=await read_frame(reader,2);remote=decode_version(frame.payload);attempts.append(remote.protocol)
                if remote.protocol>4:return
                self.assertEqual('verack',(await read_frame(reader,2)).command)
                await write_frame(writer,'verack',b'',2)
                while True:
                    frame=await read_frame(reader,5)
                    if frame.command=='getheaders':await write_frame(writer,'headers',encode_headers(()),2)
                    elif frame.command=='ping':await write_frame(writer,'pong',frame.payload,2)
                    elif frame.command.startswith('b'):unexpected.append(frame.command)
            except (OSError,EOFError,ValueError,TimeoutError):pass
            finally:writer.close();self.tasks.discard(task)
        server=await asyncio.start_server(old_peer,'127.0.0.1',0)
        try:
            await self.node.connect('127.0.0.1',server.sockets[0].getsockname()[1])
            deadline=asyncio.get_running_loop().time()+10
            while not any(s.synchronized for s in self.node._sessions.values()):
                self.assertLess(asyncio.get_running_loop().time(),deadline)
                await asyncio.sleep(.05)
            self.assertEqual([5,3],attempts[:2]);self.assertFalse(unexpected)
            self.assertEqual(0,self.node._stats['invalid_peer_incidents'])
        finally:server.close();await server.wait_closed()
    async def test_incoming_old_v4_hello_keeps_native_sync_alive(self):
        reader,writer=await asyncio.open_connection(*self.node.address);self.writers.append(writer)
        own=decode_version((await read_frame(reader,2)).payload)
        remote=Version(4,self.node.genesis,own.nonce^1,self.node.network.profile_id,self.node.chain.tip_hash)
        await write_frame(writer,'version',encode_version(remote),2)
        self.assertEqual('verack',(await read_frame(reader,2)).command)
        await write_frame(writer,'verack',b'',2)
        # Legacy signing bytes are irrelevant to the new attachment protocol.
        await write_frame(writer,'bhello',b'{"oldSigningProtocol":true}',2)
        await write_frame(writer,'getheaders',encode_getheaders((self.node.chain.tip_hash,)),2)
        for _ in range(10):
            frame=await read_frame(reader,2)
            self.assertNotEqual('bhello',frame.command)
            if frame.command=='headers':break
        else:self.fail('Native header response missing')
        self.assertEqual(0,self.node._stats['invalid_peer_incidents'])

if __name__=='__main__':unittest.main()
