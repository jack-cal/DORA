"""An admission EOF is not proof of a legacy-only peer. Owned TCP only."""
import asyncio
import tempfile
import time
import unittest
from pathlib import Path
from sumuww.peer import PeerNode
from sumuww.wire import read_frame, decode_version, ProtocolError


class AdmissionGate(PeerNode):
    closes_remaining = 0

    def _accepted(self, reader, writer):
        if self.closes_remaining:
            self.closes_remaining -= 1
            writer.close()  # Listener admission refusal, no version read.
            return
        super()._accepted(reader, writer)


class ProtocolRetryRecoveryTests(unittest.IsolatedAsyncioTestCase):
    async def test_failed_protocol_cycles_preserve_backoff_and_never_verify(self):
        writers=[]
        attempts=[]
        async def refuse(reader, writer):
            writers.append(writer)
            try:attempts.append(decode_version((await read_frame(reader,1)).payload).protocol)
            except (ProtocolError,OSError):pass
            finally:writer.close()
        server=await asyncio.start_server(refuse,'127.0.0.1',0)
        target=server.sockets[0].getsockname()[:2]
        with tempfile.TemporaryDirectory() as folder:
            node=PeerNode(Path(folder)/'client.sqlite',discovery_scope='loopback',dht_enabled=False)
            async def manual_attempts_only():
                while node.running:await asyncio.sleep(1)
            node._discover=manual_attempts_only
            try:
                await node.start()
                node._addresses.add_hint(target)
                for _ in range(6):await node._discovered_connection(target)
                entry=node._addresses._entries[target]
                self.assertEqual([3,2,1,3,2,1],attempts)
                self.assertEqual(2,entry.failures)
                self.assertEqual(20,entry.retry_at-entry.attempted_at)
                self.assertEqual(0,entry.verified_at)
                self.assertEqual(0,node.info()['peers'])
                self.assertNotIn(target,node._legacy_targets)
                self.assertNotIn(target,node._v2_targets)
            finally:
                await node.stop()
                server.close()
                for writer in writers:writer.close()
                await server.wait_closed()

    async def test_transient_pre_version_closes_do_not_pin_modern_peer_to_v1(self):
        nodes = []
        with tempfile.TemporaryDirectory() as folder:
            async def make(name, cls=PeerNode, **kw):
                opts = dict(network='regtest', allow_internet=True, discovery_scope='loopback',
                            dht_enabled=False, poll_interval=.02, timeout=.5)
                opts.update(kw)
                node = cls(Path(folder)/(name+'.sqlite'), **opts)
                nodes.append(node)
                await node.start()
                return node
            async def until(predicate, seconds=3):
                deadline=time.monotonic()+seconds
                while time.monotonic()<deadline and not predicate():await asyncio.sleep(.01)
                self.assertTrue(predicate())
            try:
                other = await make('independent', discover_peers=False)
                first = await make('first-contact', cls=AdmissionGate)
                await first.connect(*other.address)
                await until(lambda:first.info()['synchronized_peers']==1)
                first.closes_remaining=3
                client=await make('client', max_peers=3, outgoing_target=3)
                # Speed up only the owned fixture's retry clock, not wire timeouts.
                client._addresses.retry_clock=lambda:time.monotonic()*100
                client._addresses.add_hint(first.address)
                await until(lambda:any(s.nonce==first.nonce for s in client._healthy_sessions()))
                anchor=next(s for s in client._healthy_sessions() if s.nonce==first.nonce)
                self.assertEqual(3,anchor.protocol, 'Pre-version admission EOFs pinned a v3-capable listener to v1; address exchange is disabled')
                await until(lambda:client.info()['synchronized_peers']==2)
                self.assertEqual(0,first.closes_remaining)
                self.assertEqual({first.nonce,other.nonce},
                                 {s.nonce for s in client._healthy_sessions()})
                self.assertGreater(client.info()['stats']['address_hints_received'],0)
            finally:
                for node in reversed(nodes):await node.stop()
