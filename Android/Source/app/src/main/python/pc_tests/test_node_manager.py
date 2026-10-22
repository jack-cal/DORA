"""Real temporary peers prove an on-demand monitor never hosts or stops nodes."""
import asyncio
import json
from pathlib import Path
import socket
import tempfile
import threading
import time
import unittest
from unittest.mock import Mock, patch

from sumuww.node_manager import MAX_DNS_WORKERS, NodeManagerApp, NodeMonitor, normalize_peers, probe_peer, saved_sumuww_peers
from sumuww.peer import PeerNode
from sumuww.profiles import get_network
from sumuww.wire import (PROTOCOL_VERSION, PeerDisconnected, ProtocolError, Version,
                       decode_version, encode_version, read_frame, write_frame)


class MonitorSocketTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temporary=tempfile.TemporaryDirectory(prefix='sumuww-monitor-peer-test-')
        self.directory=Path(self.temporary.name)
        self.nodes=[]
        self.monitors=[]
        self.servers=[]

    async def asyncTearDown(self):
        for monitor in self.monitors:
            monitor.close()
            if monitor.pending is not None:
                await asyncio.wrap_future(monitor.pending)
        for server in self.servers:
            server.close();await server.wait_closed()
        for node in self.nodes:await node.stop()
        self.temporary.cleanup()

    async def node(self,network='regtest',**options):
        node=PeerNode(self.directory/f'peer{len(self.nodes)}.sqlite',network=network,host='127.0.0.1',port=0,poll_interval=.03,timeout=1,discovery_scope='loopback',**options)
        self.nodes.append(node);await node.start()
        return node

    def address(self,node):return f'{node.address[0]}:{node.address[1]}'

    async def test_real_peer_identity_is_reachable_without_full_chain_claim(self):
        remote=await self.node()
        result=await probe_peer(self.address(remote),network='regtest',timeout=2)
        self.assertEqual(result['status'],'reachable')
        self.assertEqual(result['advertised_tip'],remote.chain.info()['tip'])
        self.assertIsNone(result['claimed_height'])
        self.assertFalse(result['full_chain_validated'])
        self.assertGreaterEqual(result['latency_ms'],0)
        self.assertEqual(result['discovered_peers'],[])
        self.assertEqual(remote.info()['stats']['handshakes'],0)
        self.assertFalse(remote.synchronization_info()['mining_ready'])
        self.assertTrue(remote.running)

    async def test_probe_does_not_interrupt_existing_synced_peer_readiness(self):
        remote=await self.node('dora',discover_peers=False)
        companion=await self.node('dora',discover_peers=False)
        await companion.connect(*remote.address)
        deadline=time.monotonic()+3
        while not remote.synchronization_info()['mining_ready']:
            if time.monotonic()>deadline:self.fail('The ordinary peer fixture did not sync')
            await asyncio.sleep(.01)
        handshakes=remote.info()['stats']['handshakes']
        original_read=read_frame
        async def slow_acknowledgement(*arguments,**options):
            frame=await original_read(*arguments,**options)
            if frame.command=='verack':await asyncio.sleep(.2)
            return frame
        samples=[]
        with patch('sumuww.node_manager.read_frame',side_effect=slow_acknowledgement):
            check=asyncio.create_task(probe_peer(self.address(remote),network='dora',timeout=1))
            while not check.done():
                samples.append(remote.synchronization_info()['mining_ready'])
                await asyncio.sleep(.005)
            result=await check
        self.assertEqual(result['status'],'reachable')
        self.assertGreater(len(samples),10)
        self.assertTrue(all(samples))
        self.assertEqual(remote.info()['stats']['handshakes'],handshakes)
        self.assertTrue(remote.synchronization_info()['mining_ready'])

    async def test_actual_legacy_listener_falls_back_once_without_final_verack(self):
        profile=get_network('regtest')
        attempts,commands=[],[]
        async def legacy(reader,writer):
            try:
                own=Version(1,profile.genesis.block_hash(),9876,profile.profile_id,profile.genesis.block_hash())
                await write_frame(writer,'version',encode_version(own),1,magic=profile.message_magic)
                first=await read_frame(reader,1,magic=profile.message_magic)
                commands.append(first.command)
                remote=decode_version(first.payload)
                attempts.append(remote.protocol)
                if remote.protocol!=1:return
                await write_frame(writer,'verack',b'',1,magic=profile.message_magic)
                try:
                    commands.append((await read_frame(reader,1,magic=profile.message_magic)).command)
                except PeerDisconnected:pass
            finally:writer.close();await writer.wait_closed()
        server=await asyncio.start_server(legacy,'127.0.0.1',0);self.servers.append(server)
        host,port=server.sockets[0].getsockname()
        result=await probe_peer(f'{host}:{port}',network='regtest',timeout=1)
        await asyncio.sleep(.02)
        self.assertEqual(attempts,[2,1])
        self.assertEqual(commands,['version','version'])
        self.assertEqual(result['status'],'reachable')
        self.assertEqual(result['protocol'],1)

    async def test_v3_identity_is_accepted_without_completing_a_node_connection(self):
        profile=get_network('regtest')
        commands=[]
        async def current(reader,writer):
            try:
                own=Version(3,profile.genesis.block_hash(),9876,profile.profile_id,profile.genesis.block_hash())
                await write_frame(writer,'version',encode_version(own),1,magic=profile.message_magic)
                frame=await read_frame(reader,1,magic=profile.message_magic)
                commands.append(frame.command)
                self.assertEqual(decode_version(frame.payload).protocol,3)
                await write_frame(writer,'verack',b'',1,magic=profile.message_magic)
                try:commands.append((await read_frame(reader,1,magic=profile.message_magic)).command)
                except PeerDisconnected:pass
            finally:writer.close();await writer.wait_closed()
        server=await asyncio.start_server(current,'127.0.0.1',0);self.servers.append(server)
        host,port=server.sockets[0].getsockname()
        result=await probe_peer(f'{host}:{port}',network='regtest',timeout=1)
        await asyncio.sleep(.02)
        self.assertEqual(result['status'],'reachable')
        self.assertEqual(result['protocol'],3)
        self.assertEqual(result['peer_id'],'0000000000002694')
        self.assertEqual(commands,['version'])

    async def test_version_without_acknowledgement_is_not_reachable(self):
        profile=get_network('regtest')
        async def incomplete(reader,writer):
            try:
                own=Version(1,profile.genesis.block_hash(),9876,profile.profile_id,profile.genesis.block_hash())
                await write_frame(writer,'version',encode_version(own),1,magic=profile.message_magic)
                await reader.read()
            finally:writer.close();await writer.wait_closed()
        server=await asyncio.start_server(incomplete,'127.0.0.1',0);self.servers.append(server)
        host,port=server.sockets[0].getsockname()
        result=await probe_peer(f'{host}:{port}',network='regtest',timeout=.1)
        self.assertEqual(result['status'],'unreachable')
        self.assertIsNone(result['advertised_tip'])

    async def test_nonempty_acknowledgement_is_rejected(self):
        profile=get_network('regtest')
        async def malformed(reader,writer):
            try:
                own=Version(1,profile.genesis.block_hash(),9876,profile.profile_id,profile.genesis.block_hash())
                await write_frame(writer,'version',encode_version(own),1,magic=profile.message_magic)
                await read_frame(reader,1,magic=profile.message_magic)
                await write_frame(writer,'verack',b'not-empty',1,magic=profile.message_magic)
                await reader.read()
            finally:writer.close();await writer.wait_closed()
        server=await asyncio.start_server(malformed,'127.0.0.1',0);self.servers.append(server)
        host,port=server.sockets[0].getsockname()
        result=await probe_peer(f'{host}:{port}',network='regtest',timeout=1)
        self.assertEqual(result['status'],'protocol_error')
        self.assertIsNone(result['advertised_tip'])

    async def test_closed_port_is_unreachable(self):
        with socket.socket() as unused:
            unused.bind(('127.0.0.1',0));port=unused.getsockname()[1]
        result=await probe_peer(f'127.0.0.1:{port}',network='regtest',timeout=.2)
        self.assertEqual(result['status'],'unreachable')
        self.assertIsNone(result['advertised_tip'])

    async def test_wrong_network_is_not_counted_as_sumuww_response(self):
        remote=await self.node('retarget-lab')
        result=await probe_peer(self.address(remote),network='regtest',timeout=2)
        self.assertEqual(result['status'],'wrong_network')
        self.assertEqual(result['reason'],'Network or genesis mismatch')
        self.assertTrue(remote.running)

    async def test_wrong_genesis_with_same_magic_is_rejected(self):
        profile=get_network('regtest')
        async def wrong(reader,writer):
            await write_frame(writer,'version',encode_version(Version(PROTOCOL_VERSION,b'\xff'*32,123,profile.profile_id,profile.genesis.block_hash())),1,magic=profile.message_magic)
            await reader.read();writer.close();await writer.wait_closed()
        server=await asyncio.start_server(wrong,'127.0.0.1',0);self.servers.append(server)
        host,port=server.sockets[0].getsockname()
        result=await probe_peer(f'{host}:{port}',network='regtest',timeout=1)
        self.assertEqual(result['status'],'wrong_network')

    async def test_nonresponsive_peer_has_bounded_deadline(self):
        async def silent(reader,writer):
            try:await reader.read()
            finally:writer.close();await writer.wait_closed()
        server=await asyncio.start_server(silent,'127.0.0.1',0);self.servers.append(server)
        host,port=server.sockets[0].getsockname()
        started=time.monotonic()
        result=await probe_peer(f'{host}:{port}',network='regtest',timeout=.1)
        self.assertLess(time.monotonic()-started,.8)
        self.assertEqual(result['status'],'unreachable')
        self.assertEqual(result['reason'],'No response before deadline')

    async def test_monitor_close_does_not_stop_remote_or_create_chain(self):
        remote=await self.node()
        monitor=NodeMonitor(self.directory/'monitor',network='regtest',peers=[self.address(remote)],timeout=2)
        self.monitors.append(monitor)
        results=await asyncio.wrap_future(monitor.check())
        self.assertEqual(results[0]['status'],'reachable')
        monitor.close()
        self.assertTrue(remote.running)
        self.assertFalse((monitor.directory/'node.sqlite').exists())
        self.assertFalse(monitor.directory.exists())
        with self.assertRaises(RuntimeError):monitor.check()

    async def test_batch_checks_do_not_requery_when_results_finish(self):
        remote=await self.node()
        monitor=NodeMonitor(self.directory/'monitor',network='regtest',peers=[self.address(remote)],timeout=2)
        self.monitors.append(monitor)
        await asyncio.wrap_future(monitor.check())
        connections=remote.info()['stats']['connections']
        await asyncio.sleep(.15)
        self.assertEqual(remote.info()['stats']['connections'],connections)
        self.assertEqual(remote.info()['stats']['handshakes'],0)
        self.assertEqual(len(monitor.results),1)

    async def test_cancel_closes_only_its_probe_socket(self):
        entered=asyncio.Event()
        async def silent(reader,writer):
            entered.set()
            try:await reader.read()
            finally:writer.close();await writer.wait_closed()
        server=await asyncio.start_server(silent,'127.0.0.1',0);self.servers.append(server)
        host,port=server.sockets[0].getsockname()
        monitor=NodeMonitor(self.directory/'monitor',network='regtest',peers=[f'{host}:{port}'],timeout=5)
        self.monitors.append(monitor)
        pending=monitor.check();await asyncio.wait_for(entered.wait(),2)
        monitor.close();results=await asyncio.wait_for(asyncio.wrap_future(pending),1)
        self.assertEqual(results,[])
        self.assertTrue(server.is_serving())


class MonitorContactTests(unittest.TestCase):
    def test_limit_duplicate_scope_and_deadline_validation(self):
        self.assertEqual(normalize_peers(['127.0.0.1:12345']*2),['127.0.0.1:12345'])
        peers=[f'127.0.0.1:{1000+i}' for i in range(9)]
        self.assertEqual(len(peers),len(normalize_peers(peers)))
        for peers in (['0.0.0.0:12345'],['192.168.0.1:12345']):
            with self.assertRaises(ValueError):normalize_peers(peers)

    def test_saved_contact_reader_touches_only_public_json_and_checks_profile(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);node=root/'node';node.mkdir()
            settings={'schema_version':1,'listen':'127.0.0.1:0','peers':['127.0.0.1:11111'],'allow_internet':False,'allow_lan':False}
            (node/'network-settings.json').write_text(json.dumps(settings),encoding='utf-8')
            profile=get_network('regtest')
            cache={'version':1,'network':profile.profile_id,'genesis':profile.genesis.block_hash().hex(),'peers':[{'host':'127.0.0.1','port':22222,'last_success':100}]}
            (node/'node.sqlite.peers.json').write_text(json.dumps(cache),encoding='utf-8')
            for name in ('wallet.json','rpc-token','node.sqlite'):(node/name).write_bytes(b'must not be read')
            original=Path.read_text;reads=[]
            def read(path,*arguments,**options):
                reads.append(path.name);return original(path,*arguments,**options)
            with patch.object(Path,'read_text',new=read):
                loaded=saved_sumuww_peers(node,network='regtest')
            self.assertEqual(set(reads),{'network-settings.json','node.sqlite.peers.json'})
            self.assertEqual(loaded['peers'],['127.0.0.1:11111','127.0.0.1:22222'])
            foreign=saved_sumuww_peers(node,network='dora')
            self.assertEqual(foreign['peers'],['127.0.0.1:11111'])
            self.assertIsNotNone(foreign['error'])

    def test_bad_saved_json_is_skipped_without_wallet_or_database_fallback(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory=Path(temporary)
            (directory/'network-settings.json').write_text('{invalid',encoding='utf-8')
            loaded=saved_sumuww_peers(directory)
            self.assertEqual(loaded['peers'],[])
            self.assertIsNotNone(loaded['error'])


class MonitorDnsTests(unittest.TestCase):
    def test_one_second_dns_does_not_extend_short_query_deadline(self):
        finished=threading.Event()
        def slow_dns(*arguments,**options):
            try:
                time.sleep(1)
                return []
            finally:finished.set()
        with tempfile.TemporaryDirectory() as temporary:
            monitor=NodeMonitor(temporary,peers=['fixture.invalid:12345'],allow_internet=True,timeout=.05)
            try:
                with patch('sumuww.node_manager.socket.getaddrinfo',side_effect=slow_dns):
                    started=time.monotonic()
                    results=monitor.check().result(timeout=.5)
                    elapsed=time.monotonic()-started
                self.assertLess(elapsed,.4)
                self.assertFalse(finished.is_set())
                self.assertEqual(results[0]['status'],'unreachable')
                self.assertEqual(results[0]['reason'],'No response before deadline')
            finally:
                monitor.close()
                self.assertTrue(finished.wait(2))

    def test_close_cancels_query_without_waiting_for_dns_worker(self):
        entered,released,finished=threading.Event(),threading.Event(),threading.Event()
        def blocked_dns(*arguments,**options):
            entered.set()
            try:released.wait(3);return []
            finally:finished.set()
        with tempfile.TemporaryDirectory() as temporary:
            monitor=NodeMonitor(temporary,peers=['fixture.invalid:12345'],allow_internet=True,timeout=5)
            try:
                with patch('sumuww.node_manager.socket.getaddrinfo',side_effect=blocked_dns):
                    future=monitor.check()
                    self.assertTrue(entered.wait(1))
                    started=time.monotonic();monitor.close()
                    self.assertEqual(future.result(timeout=.5),[])
                    self.assertLess(time.monotonic()-started,.4)
                    self.assertFalse(finished.is_set())
            finally:
                released.set();self.assertTrue(finished.wait(1));monitor.close()

    def test_repeated_queries_never_spawn_more_than_eight_stuck_dns_workers(self):
        release=threading.Event()
        lock=threading.Lock()
        calls=[]
        def blocked_dns(*arguments,**options):
            with lock:calls.append(threading.current_thread().daemon)
            release.wait(3)
            return []
        with tempfile.TemporaryDirectory() as temporary:
            peers=[f'fixture{index}.invalid:12345' for index in range(MAX_DNS_WORKERS)]
            monitor=NodeMonitor(temporary,peers=peers,allow_internet=True,timeout=.1)
            try:
                with patch('sumuww.node_manager.socket.getaddrinfo',side_effect=blocked_dns):
                    first=monitor.check().result(timeout=.5)
                    self.assertEqual(len(first),MAX_DNS_WORKERS)
                    self.assertEqual(len(calls),MAX_DNS_WORKERS)
                    for _ in range(3):
                        results=monitor.check().result(timeout=.5)
                        self.assertTrue(all(result['status']=='unreachable' for result in results))
                    self.assertEqual(len(calls),MAX_DNS_WORKERS)
                    self.assertTrue(all(calls))
            finally:
                monitor.close();release.set()
                deadline=time.monotonic()+1
                while any(thread.name=='sumuww-monitor-dns' for thread in threading.enumerate()):
                    if time.monotonic()>deadline:self.fail('Fixture resolver workers did not finish')
                    time.sleep(.01)


class MonitorGuiTests(unittest.TestCase):
    def test_window_closes_promptly_during_blocked_dns(self):
        import tkinter as tk
        entered,released,finished=threading.Event(),threading.Event(),threading.Event()
        def blocked_dns(*arguments,**options):
            entered.set()
            try:released.wait(3);return []
            finally:finished.set()
        with tempfile.TemporaryDirectory() as temporary:
            monitor=NodeMonitor(temporary,peers=['fixture.invalid:12345'],allow_internet=True,timeout=5)
            root=tk.Tk();root.withdraw()
            app=NodeManagerApp(root,monitor)
            destroyed=[]
            root.bind('<Destroy>',lambda event:destroyed.append(True) if event.widget is root else None)
            try:
                with patch('sumuww.node_manager.socket.getaddrinfo',side_effect=blocked_dns):
                    app._check()
                    self.assertTrue(entered.wait(1))
                    started=time.monotonic();app._close()
                    while not destroyed:
                        root.update()
                        if time.monotonic()-started>.5:self.fail('Monitor window waited for DNS during close')
                        time.sleep(.005)
                    self.assertLess(time.monotonic()-started,.4)
                    self.assertFalse(finished.is_set())
            finally:
                released.set();self.assertTrue(finished.wait(1));monitor.close()
                if not destroyed:root.destroy()

    def test_window_does_not_query_automatically_and_open_sumuww_is_manual(self):
        import tkinter as tk
        with tempfile.TemporaryDirectory() as temporary:
            monitor=NodeMonitor(Path(temporary)/'monitor',peers=[])
            root=tk.Tk();root.withdraw()
            app=NodeManagerApp(root,monitor)
            process=Mock();process.poll.return_value=None
            try:
                with patch.object(monitor,'check',wraps=monitor.check) as query:
                    for _ in range(3):root.update_idletasks();root.update()
                    query.assert_not_called()
                with patch('sumuww.node_manager.subprocess.Popen',return_value=process) as launch:
                    launch.assert_not_called()
                    app._open_smw();app._open_smw()
                    self.assertEqual(launch.call_count,1)
                app._close()
                self.assertTrue(monitor.closed)
                process.terminate.assert_not_called();process.kill.assert_not_called()
                self.assertFalse(list(Path(temporary).rglob('*.sqlite')))
            finally:
                monitor.close();root.destroy()


if __name__=='__main__':unittest.main()
