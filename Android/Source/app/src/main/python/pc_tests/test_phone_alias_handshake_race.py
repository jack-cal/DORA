import asyncio,tempfile,unittest
from pathlib import Path
from sumuww.peer import PeerNode
from sumuww.profiles import get_network
from sumuww.wire import Version,encode_version,read_frame,write_frame,encode_headers,encode_addresses

class PhoneAliasHandshakeRaceTests(unittest.IsolatedAsyncioTestCase):
    async def test_automatic_aliases_keep_path_until_one_has_validated_sync(self):
        """The listener keeps A, but verack B arrives at the caller first."""
        network=get_network('regtest');b_ack=asyncio.Event();a_ack=asyncio.Event()
        writers=[];tasks=set();errors=[]
        async def connection(reader,writer,alias):
            writers.append(writer)
            try:
                await write_frame(writer,'version',encode_version(Version(1,network.genesis.block_hash(),567890,network.profile_id,network.genesis.block_hash())),magic=network.message_magic)
                self.assertEqual('version',(await read_frame(reader,2,magic=network.message_magic)).command)
                self.assertEqual('verack',(await read_frame(reader,2,magic=network.message_magic)).command)
                if alias=='A':
                    await asyncio.wait_for(b_ack.wait(),2)
                    await asyncio.sleep(.12)
                    await write_frame(writer,'verack',b'',magic=network.message_magic)
                    a_ack.set()
                else:
                    await write_frame(writer,'verack',b'',magic=network.message_magic)
                    b_ack.set()
                    # The original listener rejects this duplicate. Its EOF
                    # arrives after A's delayed acknowledgement.
                    await asyncio.wait_for(a_ack.wait(),2)
                    await asyncio.sleep(.35)
                    return
                while True:
                    frame=await read_frame(reader,2,magic=network.message_magic)
                    if frame.command=='getheaders':await write_frame(writer,'headers',encode_headers(()),magic=network.message_magic)
                    elif frame.command=='getaddr':await write_frame(writer,'addr',encode_addresses(None,()),magic=network.message_magic)
                    elif frame.command=='ping':await write_frame(writer,'pong',frame.payload,magic=network.message_magic)
            except (OSError,ValueError,asyncio.CancelledError):pass
            except Exception as error:errors.append(error)
            finally:
                writer.close()
                try:await writer.wait_closed()
                except OSError:pass
        def accept(alias):
            def accepted(reader,writer):
                task=asyncio.create_task(connection(reader,writer,alias));tasks.add(task);task.add_done_callback(tasks.discard)
            return accepted
        with tempfile.TemporaryDirectory() as folder:
            servers=[await asyncio.start_server(accept(alias),'127.0.0.1',0) for alias in ('A','B')]
            node=PeerNode(Path(folder)/'phone.sqlite',network='regtest',host='127.0.0.1',port=0,
                          discover_peers=True,discovery_scope='loopback',allow_lan=True,
                          outgoing_target=2,poll_interval=.02,timeout=1)
            try:
                for server in servers:node._addresses.add_hint(('127.0.0.1',server.sockets[0].getsockname()[1]))
                await node.start()
                await asyncio.wait_for(a_ack.wait(),3)
                await asyncio.sleep(.65)
                self.assertEqual(1,node.synchronization_info()['synchronized_peers'],node.info()['recent_peer_attempts'])
                self.assertEqual(1,node.info()['peers'])
                self.assertFalse(errors)
            finally:
                await node.stop()
                for server in servers:server.close();await server.wait_closed()
                for writer in writers:writer.close()
                for task in tuple(tasks):task.cancel()
                await asyncio.gather(*tasks,return_exceptions=True)

if __name__=='__main__':unittest.main()
