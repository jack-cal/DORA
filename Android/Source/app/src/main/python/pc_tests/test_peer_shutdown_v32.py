"""Shutdown must release owned real TCP sockets before waiting for the server.

All fixtures are regtest/loopback. The blocked-send case deliberately fills an
owned transport buffer; its synthetic bytes are never accepted as chain data.
"""
import asyncio
from pathlib import Path
import socket
import tempfile
import time
import unittest

from sumuww.peer import PeerNode


async def eventually(predicate, timeout=3):
    deadline=asyncio.get_running_loop().time()+timeout
    while not predicate():
        if asyncio.get_running_loop().time()>=deadline:
            raise AssertionError('Owned TCP fixture state deadline')
        await asyncio.sleep(.005)


class PeerShutdownTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temporary=tempfile.TemporaryDirectory(prefix='sumuww-owned-peer-shutdown-')
        self.folder=Path(self.temporary.name)
        self.nodes=[];self.raw_writers=[];self.raw_sockets=[];self.stops=[]

    async def asyncTearDown(self):
        # Test failure on the old ordering must itself remain bounded. These
        # are only this case's TCP transports, never user or external sockets.
        for writer in self.raw_writers:
            writer.transport.abort()
        for sock in self.raw_sockets:
            sock.close()
        for node in self.nodes:
            for session in tuple(node._sessions.values()):
                session.writer.transport.abort()
        await asyncio.sleep(0)
        for node in self.nodes:
            try:
                await asyncio.wait_for(node.stop(),3)
            except (OSError,TimeoutError):
                for task in tuple(node._tasks):task.cancel()
                if not node._closed:
                    node.chain.close();node._closed=True
        for task in self.stops:
            if not task.done():task.cancel()
        if self.stops:await asyncio.gather(*self.stops,return_exceptions=True)
        self.temporary.cleanup()

    async def node(self):
        instance=PeerNode(self.folder/f'node-{len(self.nodes)}.sqlite',network='regtest',
                          host='127.0.0.1',port=0,timeout=30,poll_interval=5,
                          discover_peers=False,dht_enabled=False)
        self.nodes.append(instance);await instance.start()
        return instance

    async def stop_within(self,node,seconds):
        server=node._server
        task=asyncio.create_task(node.stop());self.stops.append(task)
        began=time.monotonic()
        done,_=await asyncio.wait((task,),timeout=seconds)
        self.assertIn(task,done,'Shutdown waited for a remote peer before closing/cancelling its own sessions')
        await task
        self.assertLess(time.monotonic()-began,seconds)
        self.assertTrue(node._closed)
        self.assertFalse(node.running)
        self.assertFalse(node._sessions)
        self.assertFalse(node._tasks)
        self.assertIsNone(node._server)
        self.assertEqual(0,server._active_count)
        return time.monotonic()-began

    async def test_active_synchronized_inbound_stops_without_remote_peer_io(self):
        source=await self.node();other=await self.node()
        await other.connect(*source.address)
        await eventually(lambda:source.synchronization_info()['mining_ready'] and
                         other.synchronization_info()['mining_ready'])
        await asyncio.sleep(.1)
        self.assertEqual(1,source._server._active_count)
        await self.stop_within(source,.8)

    async def test_pre_handshake_connection_is_cancelled_before_server_wait(self):
        node=await self.node()
        _,writer=await asyncio.open_connection(*node.address)
        self.raw_writers.append(writer)
        await eventually(lambda:len(node._sessions)==1)
        self.assertFalse(next(iter(node._sessions.values())).ready)
        await self.stop_within(node,.8)

    async def test_nonreading_outbound_peer_buffer_is_aborted(self):
        node=await self.node()
        # Set the receive limit before the TCP handshake, then never read the
        # accepted socket. No mocked writer or transport participates.
        listener=socket.socket(socket.AF_INET,socket.SOCK_STREAM)
        self.raw_sockets.append(listener)
        listener.setsockopt(socket.SOL_SOCKET,socket.SO_RCVBUF,1024)
        listener.bind(('127.0.0.1',0));listener.listen(1);listener.setblocking(False)
        await node.add_peer(*listener.getsockname())
        receiver,_=await asyncio.wait_for(asyncio.get_running_loop().sock_accept(listener),2)
        self.raw_sockets.append(receiver)
        await eventually(lambda:len(node._sessions)==1)
        session=next(iter(node._sessions.values()))
        self.assertIsNotNone(session.outgoing)
        session.writer.get_extra_info('socket').setsockopt(socket.SOL_SOCKET,socket.SO_SNDBUF,0)
        session.writer.transport.set_write_buffer_limits(high=1024,low=512)
        chunk=b'x'*4_000_000
        for _ in range(8):session.writer.write(chunk)
        await asyncio.sleep(.02)
        self.assertGreater(session.writer.transport.get_write_buffer_size(),0)
        # The receiver never reads the pending bytes. Abort is therefore needed
        # after the writer's graceful-close deadline to release this transport.
        await self.stop_within(node,2.5)
        self.assertTrue(session.writer.transport.is_closing())
        self.assertEqual(0,session.writer.transport.get_write_buffer_size())

    async def test_concurrent_stops_finish_for_an_active_inbound_connection(self):
        source=await self.node();other=await self.node()
        await other.connect(*source.address)
        await eventually(lambda:source.synchronization_info()['mining_ready'])
        await asyncio.sleep(.1)
        tasks=[asyncio.create_task(source.stop()) for _ in range(3)]
        self.stops.extend(tasks)
        done,_=await asyncio.wait(tasks,timeout=.8)
        self.assertEqual(3,len(done),'Serialized stop callers remained blocked by the same open TCP connection')
        await asyncio.gather(*tasks)
        self.assertTrue(source._closed)


if __name__=='__main__':unittest.main()
