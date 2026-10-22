"""Real loopback streams, owned delayed handshake, no public endpoints."""
import asyncio
import tempfile
import time
import unittest
from pathlib import Path
from sumuww.peer import PeerNode
from sumuww.profiles import REGTEST
from sumuww.wire import (read_frame,write_frame,Version,decode_version,encode_version,
                         encode_headers,encode_addresses,decode_ping,encode_ping)

class HandshakeProgressTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp=tempfile.TemporaryDirectory();self.writers=[];self.tasks=[]
        self.client=PeerNode(Path(self.temp.name)/'client.sqlite',network='regtest',timeout=.25,poll_interval=.02)
        await self.client.start()
    async def asyncTearDown(self):
        await self.client.stop()
        if hasattr(self,'server'):self.server.close()
        for writer in self.writers:writer.close()
        for task in self.tasks:
            if not task.done():task.cancel()
        await asyncio.gather(*self.tasks,return_exceptions=True)
        if hasattr(self,'server'):await self.server.wait_closed()
        self.temp.cleanup()
    async def serve(self,reader,writer):
        self.writers.append(writer);self.tasks.append(asyncio.current_task())
        try:
            request=await read_frame(reader,timeout=1,magic=REGTEST.message_magic)
            remote=decode_version(request.payload)
            await asyncio.sleep(getattr(self, 'version_delay', .16))
            await write_frame(writer,'version',encode_version(Version(remote.protocol,REGTEST.genesis.block_hash(),12345,REGTEST.profile_id,REGTEST.genesis.block_hash())),magic=REGTEST.message_magic)
            await read_frame(reader,timeout=1,magic=REGTEST.message_magic)
            await asyncio.sleep(getattr(self, 'ack_delay', .16))
            await write_frame(writer,'verack',b'',magic=REGTEST.message_magic)
            while True:
                frame=await read_frame(reader,timeout=1,magic=REGTEST.message_magic)
                if frame.command=='getheaders':await write_frame(writer,'headers',encode_headers(()),magic=REGTEST.message_magic)
                elif frame.command=='getaddr':await write_frame(writer,'addr',encode_addresses(None,()),magic=REGTEST.message_magic)
                elif frame.command=='ping':await write_frame(writer,'pong',encode_ping(decode_ping(frame.payload)),magic=REGTEST.message_magic)
        except (Exception,asyncio.CancelledError):
            pass
        finally:writer.close()

    async def test_valid_progress_gets_next_reply_budget(self):
        self.server=await asyncio.start_server(self.serve,'127.0.0.1',0)
        await self.client.add_peer(*self.server.sockets[0].getsockname()[:2])
        deadline=time.monotonic()+1.2
        while time.monotonic()<deadline and not self.client.synchronization_info()['synchronized_peers']:
            await asyncio.sleep(.01)
        self.assertEqual(1,self.client.synchronization_info()['synchronized_peers'])

    async def test_silent_peer_keeps_original_first_reply_deadline(self):
        elapsed=asyncio.get_running_loop().create_future()
        async def silent(reader,writer):
            self.writers.append(writer);self.tasks.append(asyncio.current_task())
            started=time.monotonic()
            await reader.read()
            if not elapsed.done():elapsed.set_result(time.monotonic()-started)
        self.server=await asyncio.start_server(silent,'127.0.0.1',0)
        await self.client.add_peer(*self.server.sockets[0].getsockname()[:2])
        observed=await asyncio.wait_for(elapsed,timeout=.65)
        self.assertGreater(observed,.18)
        self.assertLess(observed,.45)

    async def _observed_5g_timing(self, shared_deadline):
        # Actual physical 5G trace 29792:88: version at 4.919 s and
        # verack another .481 s later. The endpoint is intentionally absent:
        # replay timing through an owned TCP listener, never a fixed peer.
        self.client.timeout = 5
        self.version_delay = 4.919
        self.ack_delay = .481
        if shared_deadline:
            handshake = self.client._handshake
            async def old_handshake(session):
                # Reproduce the old outer 5 s deadline without progress reset.
                session.handshake_deadline = None
                await handshake(session)
            self.client._handshake = old_handshake
        self.server = await asyncio.start_server(self.serve, '127.0.0.1', 0)
        reader, writer = await asyncio.open_connection(*self.server.sockets[0].getsockname()[:2])
        session = self.client._reserve(reader, writer, self.server.sockets[0].getsockname()[:2])
        task = asyncio.create_task(self.client._run_session(session))
        self.tasks.append(task)
        deadline = time.monotonic() + 7
        while time.monotonic() < deadline and not session.synchronized and not task.done():
            await asyncio.sleep(.01)
        if shared_deadline:
            self.assertFalse(session.ready)
            self.assertTrue(task.done())
            self.assertEqual('handshake_phase_timeout: waiting_verack', session.local_close_reason)
        else:
            self.assertTrue(session.ready)
            self.assertTrue(session.synchronized)
            self.assertFalse(writer.is_closing())

    async def test_observed_5g_timing_old_shared_deadline_rejects(self):
        await self._observed_5g_timing(shared_deadline=True)

    async def test_observed_5g_timing_fixed_deadline_synchronizes(self):
        await self._observed_5g_timing(shared_deadline=False)
