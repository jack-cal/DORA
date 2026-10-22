"""Actual isolated UDP KRPC -> SUMUWW TCP handshake -> validated chain sync.

Every node/file is an owned temporary regtest fixture. Loopback discovery is
explicitly enabled only for non-main test profiles; no public UDP is sent.
"""
import asyncio
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import AsyncMock, patch

from sumuww.peer import PeerNode
from sumuww.wallet import RegtestKey
from tests.test_dht_discovery_v29 import KrpcFixture, eventually

WORK = Path(os.environ.get('SUMUWW_TEST_WORKDIR', tempfile.gettempdir()))


class PeerDhtTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        WORK.mkdir(parents=True, exist_ok=True)
        self.temporary = tempfile.TemporaryDirectory(prefix='sumuww-dht-first-contact-', dir=WORK)
        self.directory = Path(self.temporary.name)
        self.nodes, self.transports = [], []

    async def asyncTearDown(self):
        await asyncio.gather(*(node.stop() for node in self.nodes), return_exceptions=True)
        for transport in self.transports:
            transport.close()
        await asyncio.sleep(.01)
        self.temporary.cleanup()

    def node(self, name, **options):
        options.setdefault('network', 'regtest')
        options.setdefault('allow_internet', True)
        options.setdefault('discovery_scope', 'loopback')
        options.setdefault('bootstrap_scope', 'loopback')
        options.setdefault('discovery_interval', 1)
        options.setdefault('dht_enabled', False)
        node = PeerNode(self.directory / (name + '.sqlite'), poll_interval=.03, timeout=.5, **options)
        self.nodes.append(node)
        return node

    async def server(self, peers=(), **options):
        protocol = KrpcFixture(peers=peers, **options)
        transport, _ = await asyncio.get_running_loop().create_datagram_endpoint(
            lambda: protocol, local_addr=('127.0.0.1', 0))
        self.transports.append(transport)
        return protocol

    def discovered_node(self, name, router, **options):
        options.update(dht_enabled=True, dht_scope='loopback', dht_routers=[router.address],
                       dht_query_timeout=.2, dht_round_timeout=2)
        return self.node(name, **options)

    async def test_empty_manual_dns_fallback_cache_discovers_udp_hint_then_handshakes_and_syncs(self):
        seed = self.node('seed')
        seed.chain.mine(RegtestKey.from_int(41).script_pubkey, 3)
        await seed.start()
        router = await self.server(peers=(seed.address,))
        client = self.discovered_node('empty-client', router)
        self.assertFalse(client._addresses.path.exists())
        self.assertFalse(client._configured)
        await client.start()
        await eventually(lambda: client.chain.tip_hash == seed.chain.tip_hash
                         and client.synchronization_info()['mining_ready'], timeout=8)
        info = client.info()
        self.assertEqual(3, info['height'])
        self.assertEqual(0, info['configured_peers'])
        self.assertEqual(0, info['bootstrap']['dns_seed_providers'])
        self.assertEqual(0, info['bootstrap']['fallback_peers'])
        self.assertGreater(info['stats']['handshakes'], 0)
        self.assertGreater(info['stats']['blocks_stored'], 0)
        # An inbound route may finish syncing while an alternate outbound
        # handshake is still completing its reconnect-address proof.
        await eventually(lambda: client._addresses.info()['verified'] > 0, timeout=8)
        self.assertGreater(client._addresses.info()['verified'], 0)
        self.assertTrue(client._addresses.path.exists())
        self.assertTrue(info['dht_discovery']['hint_only'])
        self.assertFalse(router.errors)
        # Continued chain progress still uses SUMUWW block validation/relay.
        seed.chain.mine(RegtestKey.from_int(41).script_pubkey, 1)
        await eventually(lambda: client.chain.tip_hash == seed.chain.tip_hash, timeout=5)
        self.assertEqual(4, client.chain.info()['height'])

    async def test_udp_hint_alone_grants_no_chain_height_work_funds_or_mining_readiness(self):
        # Port 1 has no owned SUMUWW listener; only a KRPC contact is received.
        router = await self.server(peers=(('127.0.0.1', 1),))
        client = self.discovered_node('hint-only', router)
        original = client.chain.tip_hash
        original_info = client.chain.info()
        fixture_script = RegtestKey.from_int(42).script_pubkey
        self.assertEqual(0, client.chain.balance(fixture_script))
        await client.start()
        await eventually(lambda: client._addresses.info()['candidates'] > 0)
        await asyncio.sleep(.1)
        self.assertEqual(original, client.chain.tip_hash)
        self.assertEqual(0, client.chain.info()['height'])
        for field in ('chainwork', 'utxos', 'utxo_commitment'):
            self.assertEqual(original_info[field], client.chain.info()[field])
        self.assertEqual(0, client.chain.balance(fixture_script))
        self.assertFalse(client.synchronization_info()['mining_ready'])
        self.assertEqual(0, client._addresses.info()['verified'])
        self.assertFalse(client._addresses.path.exists())

    async def test_discovered_foreign_profile_is_rejected_by_real_sumuww_handshake(self):
        foreign = self.node('foreign', network='retarget-lab')
        await foreign.start()
        router = await self.server(peers=(foreign.address,))
        client = self.discovered_node('foreign-client', router)
        await client.start()
        await eventually(lambda: client.info()['stats']['protocol_errors'] > 0)
        self.assertEqual(client.genesis, client.chain.tip_hash)
        self.assertEqual(0, client.chain.info()['height'])
        self.assertFalse(client.synchronization_info()['mining_ready'])
        self.assertEqual(0, client._addresses.info()['verified'])
        self.assertFalse(client._addresses.path.exists())

    async def test_opt_out_discovery_disabled_and_default_regtest_open_no_dht_udp(self):
        for index, flags in enumerate(({'allow_internet': False, 'dht_enabled': True},
                                        {'discover_peers': False, 'dht_enabled': True},
                                        {'dht_enabled': False}, {'dht_enabled': None})):
            client = self.node(str(index), **flags)
            # Patch the component lifecycle, not all UDP in the shared loop.
            with patch('sumuww.dht_discovery.DhtDiscovery.start', new_callable=AsyncMock) as start:
                await client.start()
                await asyncio.sleep(.06)
                start.assert_not_called()
            self.assertFalse(client.info()['dht_discovery']['enabled'])
            self.assertIsNone(client._dht_discovery)
            self.assertFalse(client.synchronization_info()['mining_ready'])

    async def test_mainnet_rejects_test_only_scope_before_creating_database(self):
        path = self.directory / 'invalid-main.sqlite'
        with self.assertRaises(ValueError):
            PeerNode(path, network='dora', allow_internet=True, dht_enabled=True,
                     dht_scope='loopback', dht_routers=[('127.0.0.1', 12345)])
        self.assertFalse(path.exists())


if __name__ == '__main__':
    unittest.main()
