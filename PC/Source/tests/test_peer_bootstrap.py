"""Actual temporary nodes; bootstrap hints never replace normal chain checks."""
import asyncio
import os
from pathlib import Path
import socket
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from sumuww.bootstrap import SeedResult
from sumuww.peer import PeerNode
from sumuww.wallet import RegtestKey
from sumuww.wire import Version, encode_version, read_frame, write_frame


WORK=Path(os.environ.get('SUMUWW_TEST_WORKDIR',tempfile.gettempdir()))


def records(address):
    return [(socket.AF_INET,socket.SOCK_STREAM,socket.IPPROTO_TCP,'',address)]


async def eventually(predicate,timeout=4):
    end=time.monotonic()+timeout
    while not predicate():
        if time.monotonic()>end:raise AssertionError('The isolated bootstrap fixture did not reach its expected state')
        await asyncio.sleep(.02)


class PeerBootstrapTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        WORK.mkdir(parents=True,exist_ok=True)
        self.temporary=tempfile.TemporaryDirectory(prefix='sumuww-bootstrap-peers-',dir=WORK)
        self.directory=Path(self.temporary.name)
        self.nodes=[]

    async def asyncTearDown(self):
        await asyncio.gather(*(node.stop() for node in self.nodes),return_exceptions=True)
        self.temporary.cleanup()

    def node(self,name,**options):
        options.setdefault('allow_internet',True)
        options.setdefault('discovery_scope','loopback')
        options.setdefault('bootstrap_scope','loopback')
        options.setdefault('network','regtest')
        # A second address response must be possible inside the fixture's
        # deadline; the production address-exchange interval remains 30s.
        options.setdefault('discovery_interval',1)
        node=PeerNode(self.directory/(name+'.sqlite'),poll_interval=.03,timeout=.5,**options)
        self.nodes.append(node);return node

    async def test_fresh_empty_cache_and_no_manual_peer_connects_using_dns_hint(self):
        seed=self.node('seed');await seed.start()
        client=self.node('client',bootstrap_seeds=[('seed.fixture.invalid',seed.address[1])])
        self.assertFalse(client._addresses.path.exists())
        with patch('sumuww.bootstrap.socket.getaddrinfo',return_value=records(seed.address)):
            await client.start()
            await eventually(lambda:client.synchronization_info()['mining_ready'])
        self.assertEqual(client.info()['configured_peers'],0)
        self.assertEqual(client.info()['bootstrap']['provider_attempts'],1)
        self.assertGreater(client.info()['bootstrap']['accepted_hints'],0)
        self.assertTrue(client._addresses.path.exists())
        seed.chain.mine(RegtestKey.from_int(21).script_pubkey,1)
        await eventually(lambda:client.chain.tip_hash==seed.chain.tip_hash)
        self.assertEqual(client.chain.info()['height'],1)

    async def test_numeric_fallback_connects_even_when_dns_is_blocked(self):
        seed=self.node('seed');await seed.start()
        entered,release,finished=threading.Event(),threading.Event(),threading.Event()
        def blocked(*arguments,**options):
            entered.set()
            try:release.wait(3);return []
            finally:finished.set()
        client=self.node('client',bootstrap_seeds=[('blocked.fixture.invalid',seed.address[1])],
                         bootstrap_peers=[seed.address])
        try:
            with patch('sumuww.bootstrap.socket.getaddrinfo',side_effect=blocked):
                await client.start()
                await eventually(lambda:entered.is_set())
                await eventually(lambda:client.synchronization_info()['mining_ready'])
                self.assertFalse(finished.is_set())
                self.assertEqual(client.info()['configured_peers'],0)
        finally:
            release.set();await eventually(lambda:finished.is_set())

    async def test_independent_good_provider_survives_another_provider_timeout(self):
        seed=self.node('seed');await seed.start()
        release=threading.Event();finished=threading.Event()
        def resolver(host,*arguments,**options):
            if host=='blocked.fixture.invalid':
                try:release.wait(3);return []
                finally:finished.set()
            return records(seed.address)
        client=self.node('client',bootstrap_seeds=[('blocked.fixture.invalid',seed.address[1]),
                                                 ('working.fixture.invalid',seed.address[1])])
        try:
            with patch('sumuww.bootstrap.socket.getaddrinfo',side_effect=resolver),patch('sumuww.peer.DNS_DEADLINE',.15):
                await client.start()
                await eventually(lambda:client.synchronization_info()['mining_ready'])
                self.assertFalse(finished.is_set())
                self.assertEqual(client.info()['bootstrap']['provider_attempts'],2)
                self.assertEqual(client.info()['bootstrap']['provider_errors'],1)
                self.assertGreater(client.info()['bootstrap']['accepted_hints'],0)
        finally:release.set();await eventually(lambda:finished.is_set())

    async def test_dns_hints_with_foreign_genesis_never_sync_or_cache_as_valid(self):
        foreign=self.node('foreign',network='retarget-lab');await foreign.start()
        client=self.node('client',bootstrap_seeds=[('foreign.fixture.invalid',foreign.address[1])])
        with patch('sumuww.bootstrap.socket.getaddrinfo',return_value=records(foreign.address)):
            await client.start()
            await eventually(lambda:client.info()['stats']['protocol_errors']>0)
        self.assertFalse(client.synchronization_info()['mining_ready'])
        self.assertEqual(client.chain.info()['height'],0)
        self.assertEqual(client._addresses.info()['verified'],0)
        self.assertFalse(client._addresses.path.exists())

    async def test_all_provider_failures_do_not_manufacture_a_peer_or_funds(self):
        client=self.node('client',bootstrap_seeds=[('one.fixture.invalid',18444),('two.fixture.invalid',18444)])
        with patch('sumuww.bootstrap.socket.getaddrinfo',side_effect=socket.gaierror('offline fixture')):
            await client.start()
            await eventually(lambda:client.info()['bootstrap']['provider_errors']==2)
        value=client.info()
        self.assertEqual(value['peers'],0)
        self.assertFalse(value['mining_ready'])
        self.assertEqual(value['height'],0)
        self.assertEqual(value['peer_discovery']['candidates'],0)
        self.assertGreater(value['bootstrap']['next_query_seconds'],0)
        self.assertEqual(value['stats']['internal_errors'],0)

    async def test_same_wire_magic_with_wrong_genesis_is_rejected_after_dns_discovery(self):
        client=self.node('client')
        async def wrong_genesis(reader,writer):
            try:
                await read_frame(reader,.5,magic=client.network.message_magic)
                identity=Version(2,b'\xff'*32,987654,client.network.profile_id,client.genesis)
                await write_frame(writer,'version',encode_version(identity),.5,magic=client.network.message_magic)
                await reader.read()
            finally:
                writer.close()
                try:await writer.wait_closed()
                except OSError:pass
        server=await asyncio.start_server(wrong_genesis,'127.0.0.1',0)
        address=server.sockets[0].getsockname()[:2]
        # Create another node so all normal constructor input validation is
        # exercised rather than mutating the registered source list in place.
        discovered=self.node('discovered',bootstrap_seeds=[('wrong.fixture.invalid',address[1])])
        try:
            with patch('sumuww.bootstrap.socket.getaddrinfo',return_value=records(address)):
                await discovered.start()
                await eventually(lambda:discovered.info()['stats']['protocol_errors']>0)
            self.assertEqual(discovered.chain.tip_hash,discovered.genesis)
            self.assertFalse(discovered.synchronization_info()['mining_ready'])
            self.assertFalse(discovered._addresses.path.exists())
            self.assertEqual(discovered._addresses.info()['verified'],0)
        finally:
            await discovered.stop();server.close();await server.wait_closed()

    async def test_opt_out_or_disabled_discovery_performs_no_seed_lookup_or_dial(self):
        for flags in ({'allow_internet':False},{'discover_peers':False}):
            client=self.node(str(len(self.nodes)),bootstrap_seeds=[('seed.fixture.invalid',18444)],
                             bootstrap_peers=[('127.0.0.1',18444)],**flags)
            with patch('sumuww.bootstrap.socket.getaddrinfo') as resolver:
                await client.start();await asyncio.sleep(.12)
                resolver.assert_not_called()
            self.assertFalse(client.info()['bootstrap']['enabled'])
            self.assertEqual(client.info()['bootstrap']['accepted_hints'],0)
            self.assertEqual(client.info()['stats']['connections'],0)

    async def test_default_regtest_has_no_hidden_seed_configuration_or_queries(self):
        client=self.node('client')
        with patch('sumuww.bootstrap.socket.getaddrinfo') as resolver:
            await client.start();await asyncio.sleep(.12)
            resolver.assert_not_called()
        self.assertEqual(client.info()['bootstrap']['dns_seed_providers'],0)
        self.assertEqual(client.info()['bootstrap']['fallback_peers'],0)
        self.assertEqual(client.info()['bootstrap']['query_rounds'],0)

    async def test_stopping_node_is_prompt_while_os_dns_is_blocked(self):
        entered,release,finished=threading.Event(),threading.Event(),threading.Event()
        def blocked(*arguments,**options):
            entered.set()
            try:release.wait(3);return []
            finally:finished.set()
        client=self.node('client',bootstrap_seeds=[('blocked.fixture.invalid',18444)])
        try:
            with patch('sumuww.bootstrap.socket.getaddrinfo',side_effect=blocked):
                await client.start();await eventually(lambda:entered.is_set())
                started=time.monotonic();await client.stop()
                self.assertLess(time.monotonic()-started,.5)
                self.assertFalse(finished.is_set())
                self.assertFalse(client.running)
                self.assertFalse(any(task.get_name().startswith('sumuww-peer:bootstrap') for task in asyncio.all_tasks()))
        finally:release.set();await eventually(lambda:finished.is_set())

    async def test_query_retry_spacing_and_failure_backoff_are_bounded(self):
        client=self.node('client',bootstrap_seeds=[('offline.fixture.invalid',18444)])
        now=[100.0];client._bootstrap_clock=lambda:now[0]
        with patch('sumuww.peer.lookup_seed',return_value=SeedResult(error='resolution_failed')) as lookup:
            await client.start()
            await eventually(lambda:client.info()['bootstrap']['query_rounds']==1
                             and client._bootstrap_next_query==160)
            await asyncio.sleep(.1)
            self.assertEqual(lookup.call_count,1)
            self.assertEqual(client._bootstrap_next_query,160)
            intervals=[]
            for advance in (160,280,520,820):
                now[0]=advance
                count=client.info()['bootstrap']['query_rounds']
                await eventually(lambda:client.info()['bootstrap']['query_rounds']==count+1
                                 and client._bootstrap_next_query>now[0])
                intervals.append(client._bootstrap_next_query-now[0])
            self.assertEqual(intervals,[120,240,300,300])

    async def test_eight_synced_peers_do_not_stop_unlimited_discovery(self):
        seeds=[self.node('anchor'+str(i),discover_peers=False) for i in range(8)]
        await asyncio.gather(*(n.start() for n in seeds))
        client=self.node('client',bootstrap_seeds=[('fixture.seed.invalid',18444)],peers=[n.address for n in seeds])
        with patch('sumuww.peer.lookup_seed',return_value=SeedResult(error='resolution_failed')) as lookup:
            await client.start()
            await eventually(lambda:client.synchronization_info()['synchronized_peers']>=8)
            before=lookup.call_count
            client._bootstrap_next_query=0
            await asyncio.sleep(.15)
            self.assertGreater(lookup.call_count,before)

    async def test_address_budget_is_bounded_and_seeds_do_not_gain_manual_peer_authority(self):
        seeds=[(f'seed{index}.fixture.invalid',18444) for index in range(8)]
        client=self.node('client',bootstrap_seeds=seeds)
        async def hints(seed,**options):
            index=int(seed[0].split('.')[0][4:])
            return SeedResult(tuple((f'8.8.{index}.{number}',18444) for number in range(1,33)))
        with patch('sumuww.peer.lookup_seed',side_effect=hints):
            await client._refresh_bootstrap()
        self.assertEqual(client.info()['peer_discovery']['candidates'],128)
        self.assertEqual(client.info()['bootstrap']['accepted_hints'],128)
        self.assertEqual(len({int(host.split('.')[2]) for host,port in client._addresses._entries}),8)
        self.assertEqual(client.info()['configured_peers'],0)
        self.assertFalse(client._addresses.path.exists())
        self.assertFalse(client.synchronization_info()['mining_ready'])

    async def test_initial_node_can_retire_and_a_restart_uses_verified_cache_without_sources(self):
        first=self.node('first');await first.start()
        client=self.node('client',bootstrap_peers=[first.address]);await client.start()
        survivor=self.node('survivor',bootstrap_peers=[first.address]);await survivor.start()
        await eventually(lambda:survivor.address in client._addresses.known()
                         and client.address in survivor._addresses.known(),timeout=8)
        await first.stop()
        await eventually(lambda:client.synchronization_info()['mining_ready']
                         and survivor.synchronization_info()['mining_ready'])
        db=client.database;await client.stop()
        replacement=PeerNode(db,network='regtest',allow_internet=True,discovery_scope='loopback',
                             poll_interval=.03,timeout=.5)
        self.nodes.append(replacement)
        await replacement.start()
        await eventually(lambda:replacement.synchronization_info()['mining_ready'])
        self.assertEqual(replacement.info()['bootstrap']['fallback_peers'],0)
        self.assertEqual(replacement.info()['bootstrap']['dns_seed_providers'],0)
        self.assertEqual(replacement.info()['configured_peers'],0)
        self.assertEqual(replacement.chain.tip_hash,survivor.chain.tip_hash)

    async def test_invalid_bootstrap_input_is_rejected_before_database_creation(self):
        path=self.directory/'invalid.sqlite'
        for options in ({'bootstrap_seeds':[('localhost',18444)]},
                        {'bootstrap_peers':[('127.0.0.1',18444)]},
                        {'bootstrap_scope':'unrestricted'}):
            with self.assertRaises(ValueError):PeerNode(path,allow_internet=True,**options)
            self.assertFalse(path.exists())


if __name__=='__main__':unittest.main()
