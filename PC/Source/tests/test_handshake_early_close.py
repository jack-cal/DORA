import asyncio
import tempfile
import unittest
from pathlib import Path
from sumuww.peer import PeerNode
from sumuww.wire import Version,decode_version,encode_version,read_frame,write_frame,encode_headers,ProtocolError

class EarlyCloseTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.nodes=[];self.writers=[];self.servers=[]
    async def asyncTearDown(self):
        await asyncio.gather(*(n.stop() for n in self.nodes))
        for w in self.writers:w.close()
        for s in self.servers:s.close();await s.wait_closed()
        self.tmp.cleanup()
    async def wait(self,predicate,timeout=3):
        async with asyncio.timeout(timeout):
            while not predicate():await asyncio.sleep(.02)
    async def fixture(self,accepted=1,foreign=False,malformed=False):
        node=PeerNode(Path(self.tmp.name)/'test.sqlite',poll_interval=.05,timeout=.5,
                      discovery_scope='loopback',dht_enabled=False)
        self.nodes.append(node);attempts=[]
        async def hold_discovery():
            while node.running:await asyncio.sleep(1)
        node._discover=hold_discovery
        async def listener(reader,writer):
            self.writers.append(writer)
            try:
                remote=decode_version((await read_frame(reader,1)).payload);attempts.append(remote.protocol)
                if malformed:
                    await write_frame(writer,'version',b'broken',1);return
                if foreign:
                    await write_frame(writer,'version',encode_version(Version(1,b'X'*32,123,node.network.profile_id,node.chain.tip_hash)),1);return
                if remote.protocol!=accepted:return
                await write_frame(writer,'version',encode_version(Version(accepted,node.genesis,node.nonce^99,node.network.profile_id,node.chain.tip_hash)),1)
                await read_frame(reader,1);await write_frame(writer,'verack',b'',1)
                while True:
                    frame=await read_frame(reader,1)
                    if frame.command=='getheaders':await write_frame(writer,'headers',encode_headers(()),1)
            except (ProtocolError,OSError):pass
            finally:writer.close()
        s=await asyncio.start_server(listener,'127.0.0.1',0);self.servers.append(s);await node.start()
        return node,s.sockets[0].getsockname()[:2],attempts
    async def test_pre_version_eof_recovers_through_bounded_protocols(self):
        node,target,attempts=await self.fixture()
        await node.add_peer(*target)
        await self.wait(lambda:node.synchronization_info()['mining_ready'])
        self.assertEqual([3,2,1],attempts)
        self.assertEqual(2,node.info()['stats']['legacy_fallbacks'])
        self.assertEqual(1,node.info()['peers'])
        self.assertNotIn(target,node._v2_targets)
        self.assertNotIn(target,node._legacy_targets)
    async def test_pre_version_eof_does_not_evict_discovered_endpoint_as_failure(self):
        node,target,attempts=await self.fixture(accepted=2);node._addresses.add_hint(target)
        await node._discovered_connection(target)
        self.assertEqual(0,node._addresses._entries[target].failures)
        self.assertFalse(node.synchronization_info()['mining_ready'])
        self.assertEqual([3],attempts)
    async def test_foreign_genesis_never_downgrades_or_grants_ready(self):
        node,target,attempts=await self.fixture(foreign=True);await node.add_peer(*target)
        await self.wait(lambda:node.info()['stats']['protocol_errors']>0)
        self.assertEqual(0,node.info()['stats']['legacy_fallbacks']);self.assertFalse(node.synchronization_info()['mining_ready'])
    async def test_malformed_version_never_downgrades_or_grants_ready(self):
        node,target,attempts=await self.fixture(malformed=True);await node.add_peer(*target)
        await self.wait(lambda:node.info()['stats']['protocol_errors']>0)
        self.assertEqual(0,node.info()['stats']['legacy_fallbacks']);self.assertFalse(node.synchronization_info()['mining_ready'])

    async def test_local_poll_failure_is_distinguished_from_unknown_eof(self):
        from unittest.mock import patch
        node,target,attempts=await self.fixture(accepted=3);await node.add_peer(*target)
        await self.wait(lambda:node.synchronization_info()['mining_ready'])
        session=next(iter(node._healthy_sessions()));session.last_announced_tip=None
        with patch.object(node,'_send',side_effect=OSError('owned poll failure')):
            await node._poll_session(session,node.chain.tip_hash,(),asyncio.get_running_loop().time())
        await self.wait(lambda:session not in node._sessions.values())
        rows=node.info()['recent_peer_attempts']
        self.assertTrue(any('owned poll failure' in (r.get('local_close_reason') or '') for r in rows))
        self.assertEqual(0,node.info()['stats']['legacy_fallbacks'])

    async def test_reconnect_probes_highest_protocol_again(self):
        node,target,attempts=await self.fixture(accepted=1);await node.add_peer(*target)
        await self.wait(lambda:node.synchronization_info()['mining_ready'])
        next(iter(node._healthy_sessions())).writer.close()
        await self.wait(lambda:len(attempts)>=6 and node.synchronization_info()['mining_ready'])
        self.assertEqual([3,2,1,3,2,1],attempts[:6])
