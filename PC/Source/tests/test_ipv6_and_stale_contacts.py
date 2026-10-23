"""Owned TCP fixtures; never contact production nodes or read user wallets."""
import asyncio
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from sumuww.peer import PeerNode, _endpoint
from sumuww.peer_discovery import PeerAddressBook, discovery_endpoint
from sumuww.self_address import InterfaceAddress, resolve_self_address
from sumuww.peerd import endpoint
from sumuww.wire import (PeerAddress, encode_addresses, decode_addresses, Version,
                       encode_version, decode_version, encode_headers, read_frame, write_frame)
from sumuww.wallet import RegtestKey


class AddressTests(unittest.TestCase):
    def test_ipv6_scope_and_text_parser(self):
        self.assertEqual(('::1', 1234), endpoint('[::1]:1234'))
        self.assertEqual(('2606:4700::1111', 18444), discovery_endpoint('2606:4700::1111', 18444))
        for host in ('fe80::1', 'ff02::1', '::', '::1', 'fc00::1', '::ffff:8.8.8.8', 'fe80::1%7'):
            with self.subTest(host=host), self.assertRaises(ValueError):
                discovery_endpoint(host, 18444)
        self.assertEqual(('fd00::1', 4), _endpoint('fd00::1', 4, allow_lan=True))
        with self.assertRaises(ValueError):
            _endpoint('2606:4700::1111', 4)

    def test_wire_ipv6_round_trip(self):
        listener=PeerAddress('2606:4700::1111', 18444)
        others=(PeerAddress('8.8.8.8', 1234),)
        self.assertEqual((listener, others), decode_addresses(encode_addresses(listener, others)))

    def test_public_ipv6_only_advertised_with_actual_ipv6_listener(self):
        interfaces=(InterfaceAddress('192.0.0.2'), InterfaceAddress('2606:4700::1111'))
        args=dict(allow_internet=True, automatic=True, interfaces=interfaces)
        self.assertIsNone(resolve_self_address(('0.0.0.0',18444), **args).advertised_endpoint)
        self.assertEqual(('2606:4700::1111',18444), resolve_self_address(
            ('0.0.0.0',18444), include_ipv6=True, **args).advertised_endpoint)

    def test_failed_verified_contact_kept_for_retry_without_duplicate_hints(self):
        with tempfile.TemporaryDirectory() as directory:
            now=[10000.]
            path=Path(directory)/'contacts.json'
            book=PeerAddressBook(path,'fixture',bytes(32),scope='loopback',clock=lambda:now[0],retry_clock=lambda:now[0])
            old=('127.0.0.1',9151); good=('127.0.0.1',18444)
            book.verified(old);book.verified(good)
            book.attempted(old)
            self.assertIn(old,book.known())  # A temporary outage must not erase a verified route.
            book.verified(old)  # Fresh verified connectivity can restore it.
            book.attempted(old,success=True)
            for _ in range(1):book.attempted(old)
            self.assertIn(old,book.known())
            self.assertIn(good,book.known())
            self.assertFalse(book.add_hint(old))
            self.assertEqual({9151,18444},{row['port'] for row in json.loads(path.read_text())['peers']})
            reloaded=PeerAddressBook(path,'fixture',bytes(32),scope='loopback',clock=lambda:now[0])
            self.assertIn(old,reloaded.known())
            now[0]+=59
            self.assertFalse(book.add_hint(old))
            now[0]+=2
            self.assertFalse(book.add_hint(old))  # Already retained; no rediscovery is required.
            self.assertEqual(old,book.candidate(excluded=[good]))


class SocketTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.directory=tempfile.TemporaryDirectory();self.nodes=[]
    async def asyncTearDown(self):
        await asyncio.gather(*(n.stop() for n in self.nodes))
        self.directory.cleanup()
    async def node(self,name,**kwargs):
        node=PeerNode(Path(self.directory.name)/(name+'.sqlite'),poll_interval=.05,
                      timeout=2,discovery_interval=1,discovery_scope='loopback',dht_enabled=False,**kwargs)
        self.nodes.append(node);await node.start();return node
    async def wait(self,predicate):
        async with asyncio.timeout(10):
            while not predicate():await asyncio.sleep(.03)

    async def test_ipv6_connection_sync_and_block_propagation(self):
        first=await self.node('v6',host='::1')
        second=await self.node('v4',peers=(first.address,))
        await self.wait(lambda:second.synchronization_info()['mining_ready'])
        self.assertEqual(3,next(iter(second._sessions.values())).protocol)
        first.chain.mine(RegtestKey.from_int(49).script_pubkey,1)
        await self.wait(lambda:second.chain.info()['height']==1)
        self.assertEqual(first.chain.tip_hash,second.chain.tip_hash)

    async def test_dual_listener_accepts_both_families_without_replacing_ipv4_connection(self):
        hub=await self.node('dual',host='0.0.0.0',allow_internet=True,auto_address=True)
        self.assertTrue(hub._server6.is_serving())
        a=await self.node('a',peers=(('127.0.0.1',hub.address[1]),))
        await self.wait(lambda:a.synchronization_info()['mining_ready'])
        before=next(iter(a._sessions.values()))
        b=await self.node('b',peers=(('::1',hub.address[1]),))
        await self.wait(lambda:b.synchronization_info()['mining_ready'])
        self.assertIs(before,next(iter(a._sessions.values())))
        self.assertEqual(2,len({s.nonce for s in hub._sessions.values() if s.ready}))

    async def test_protocol2_only_peer_is_retried_with_v2_and_remains_connected(self):
        attempts=[]; tasks=set()
        profile_node=await self.node('profile',discover_peers=False)
        async def serve(reader,writer):
            try:
                await write_frame(writer,'version',encode_version(Version(1,profile_node.genesis,999,
                    profile_node.network.profile_id,profile_node.chain.tip_hash)),magic=profile_node.network.message_magic)
                version=decode_version((await read_frame(reader,magic=profile_node.network.message_magic)).payload)
                attempts.append(version.protocol)
                if version.protocol>2:return
                await write_frame(writer,'verack',b'',magic=profile_node.network.message_magic)
                await read_frame(reader,magic=profile_node.network.message_magic)
                while True:
                    frame=await read_frame(reader,magic=profile_node.network.message_magic)
                    if frame.command=='getheaders':
                        await write_frame(writer,'headers',encode_headers(()),magic=profile_node.network.message_magic)
                    elif frame.command=='getaddr':
                        await write_frame(writer,'addr',encode_addresses(None),magic=profile_node.network.message_magic)
            except (OSError,Exception):pass
            finally:writer.close();await writer.wait_closed()
        def accepted(r,w):
            task=asyncio.create_task(serve(r,w));tasks.add(task);task.add_done_callback(tasks.discard)
        server=await asyncio.start_server(accepted,'127.0.0.1',0)
        try:
            target=server.sockets[0].getsockname()[:2]
            client=await self.node('fallback',peers=(target,))
            await self.wait(lambda:client.synchronization_info()['mining_ready'])
            self.assertEqual([3,2],attempts)
            self.assertEqual(2,next(iter(client._sessions.values())).protocol)
        finally:
            server.close()
            for task in tuple(tasks):task.cancel()
            await asyncio.gather(*tuple(tasks),return_exceptions=True)
            await asyncio.wait_for(server.wait_closed(),2)

    async def test_ipv4_peer_learns_ipv6_contact_and_retains_one_healthy_route_to_third_peer(self):
        hub=await self.node('hub')
        ipv6=await self.node('ipv6',host='::1',peers=(hub.address,))
        await self.wait(lambda:ipv6.synchronization_info()['mining_ready'])
        ipv4=await self.node('ipv4',peers=(hub.address,))
        # Address exchange supplies a hint. An inbound IPv4 route can win the
        # race, so the unconnected IPv6 alias must not be marked verified.
        await self.wait(lambda:ipv6.address in ipv4._addresses._entries)
        # The third node can establish its IPv4 return route first. Dedup
        # must retain that healthy route rather than force its IPv6 alias.
        await self.wait(lambda:any(s.nonce==ipv6.nonce and s.synchronized
                                   for s in ipv4._sessions.values()))
        self.assertEqual(1,sum(s.nonce==ipv6.nonce and s.ready and not s.writer.is_closing()
                               for s in ipv4._sessions.values()))

    async def test_incremental_discovery_fills_eight_slots_and_replaces_only_lost_peer(self):
        seeds=[await self.node('eight-seed-'+str(i),discover_peers=False) for i in range(9)]
        client=await self.node('eight-client',allow_internet=True,max_peers=8)
        original=()
        for count in (2,4,8):
            for seed in seeds[:count]:client._addresses.add_hint(seed.address)
            await self.wait(lambda:len({s.nonce for s in client._healthy_sessions()})==count)
            self.assertTrue(all(s in client._sessions.values() for s in original))
            self.assertLessEqual(len(client._sessions),8)
            original=tuple(client._healthy_sessions())
        self.assertTrue(client._discovery_settled())
        client._addresses.add_hint(seeds[8].address)
        attempts=client._stats['reconnect_attempts']
        await asyncio.sleep(.3)
        self.assertEqual(attempts,client._stats['reconnect_attempts'])
        victim=original[0]
        victim_nonce=victim.nonce
        seed=next(n for n in seeds if n.nonce==victim_nonce)
        await seed.stop()
        await self.wait(lambda:any(s.nonce==seeds[8].nonce for s in client._healthy_sessions()))
        await self.wait(client._discovery_settled)
        self.assertTrue(all(s in client._sessions.values() for s in original[1:]))
        self.assertEqual(8,len(client._sessions))

    async def test_two_addresses_of_same_node_do_not_stop_backup_discovery(self):
        hub=await self.node('alias-hub',host='0.0.0.0',allow_internet=True,discover_peers=False)
        phone=await self.node('alias-phone',allow_internet=True)
        await phone.connect('127.0.0.2',hub.address[1])
        await phone.connect('127.0.0.3',hub.address[1])
        await self.wait(lambda:len(phone._healthy_sessions())==1)
        original=tuple(phone._healthy_sessions())
        self.assertFalse(phone._discovery_settled())
        other=await self.node('alias-other',discover_peers=False)
        phone._addresses.add_hint(other.address)
        await self.wait(lambda:any(s.nonce==other.nonce and s.synchronized for s in phone._sessions.values()))
        self.assertTrue(all(s in phone._sessions.values() for s in original))
        self.assertEqual(2,len({s.nonce for s in phone._healthy_sessions()}))


if __name__=='__main__':unittest.main()
