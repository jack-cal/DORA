"""Opt-in internet scope checks and local TCP fixtures, without external hosts.

DNS answers are controlled mocks. Actual sockets stay on this one computer's
loopback; these tests do not demonstrate router traversal or a deployed peer.
"""

import asyncio
import os
from pathlib import Path
import socket
import tempfile
import unittest
from unittest.mock import AsyncMock, Mock, patch

from sumuww import peerd
from sumuww.block import GENESIS_TIME
from sumuww.peer import PeerNode, _endpoint
from sumuww.primitives import COIN
from sumuww.profiles import SUMUWW
from sumuww.transaction import Transaction, TxInput, TxOutput
from sumuww.wallet import RegtestKey, sign_p2wpkh


WORK = Path(os.environ.get('SUMUWW_TEST_WORKDIR', tempfile.gettempdir()))
NOW = GENESIS_TIME + 1000
ALICE = RegtestKey.from_int(1)  # Published fixture scalars, never a user wallet.
BOB = RegtestKey.from_int(2)


async def eventually(predicate, timeout=15):
    deadline = asyncio.get_running_loop().time() + timeout
    while not predicate():
        if asyncio.get_running_loop().time() >= deadline:
            raise AssertionError('Local opt-in nodes did not converge within the deadline')
        await asyncio.sleep(.03)


class PublicEndpointTests(unittest.TestCase):
    def test_existing_modes_reject_public_dns_and_wildcard(self):
        for options in ({}, {'allow_lan': True}):
            for host in ('8.8.8.8', 'peer.example', '0.0.0.0'):
                with self.subTest(options=options, host=host), self.assertRaises(ValueError):
                    _endpoint(host, 8123, **options)
                with self.subTest(daemon=True, host=host), self.assertRaises(ValueError):
                    peerd.endpoint(host + ':8123', **options)

    def test_internet_mode_accepts_global_lan_loopback_and_outbound_dns(self):
        for host in ('8.8.8.8', '1.1.1.1', '10.0.0.1', '127.0.0.1'):
            with self.subTest(host=host):
                self.assertEqual((host, 8123), _endpoint(host, 8123, allow_internet=True))
        self.assertEqual(('peer.example', 8123), _endpoint('Peer.Example.', 8123, allow_internet=True))
        self.assertEqual(('peer.example', 8123), peerd.endpoint('peer.example:8123', allow_zero=False, allow_internet=True))

    def test_wildcard_is_only_an_explicit_lan_or_internet_listener(self):
        self.assertEqual(('0.0.0.0', 0), _endpoint('0.0.0.0', 0, allow_zero=True, allow_internet=True, for_listen=True))
        self.assertEqual(('0.0.0.0', 0), _endpoint('0.0.0.0', 0, allow_zero=True, allow_lan=True, for_listen=True))
        for options in ({}, {'allow_lan': True}, {'allow_internet': True}, {'for_listen': True}):
            with self.subTest(options=options), self.assertRaises(ValueError):
                _endpoint('0.0.0.0', 8123, **options)
        with self.assertRaises(ValueError):
            _endpoint('peer.example', 8123, allow_internet=True, for_listen=True)

    def test_special_non_unicast_and_malformed_addresses_are_rejected(self):
        hosts = ('0.0.0.0', '0.1.2.3', '100.64.0.1', '169.254.1.1',
                 '192.0.0.9', '192.0.2.1', '192.88.99.1', '198.18.0.1',
                 '198.51.100.1', '203.0.113.1', '224.0.0.1', '240.0.0.1',
                 '255.255.255.255', 'fe80::1', '::ffff:8.8.8.8', '127.1',
                 '999.0.0.1', '', ' peer.example', 'peer.example ',
                 'a..example', '-a.example', 'a-.example', '\ud55c\uae00.example',
                 'x' * 64 + '.example', 'x.' * 130 + 'example')
        for host in hosts:
            with self.subTest(host=host), self.assertRaises(ValueError):
                _endpoint(host, 8123, allow_internet=True)

    def test_flags_and_outgoing_port_types_are_strict(self):
        for flag in ('allow_zero', 'allow_lan', 'allow_internet', 'for_listen'):
            for value in (1, 'true', None):
                with self.subTest(flag=flag, value=value), self.assertRaises(ValueError):
                    _endpoint('127.0.0.1', 8123, **{flag: value})
        for port in (0, -1, 65536, True, '8123', 8123.0):
            with self.subTest(port=port), self.assertRaises(ValueError):
                _endpoint('8.8.8.8', port, allow_internet=True)

    def test_invalid_configured_target_fails_before_database_creation(self):
        WORK.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='public-invalid-', dir=WORK) as directory:
            for mode in (False, True):
                database = Path(directory) / ('invalid-' + str(mode) + '.sqlite')
                with self.assertRaises(ValueError):
                    PeerNode(database, peers=(('0.0.0.0', 8123),), allow_internet=mode)
                self.assertFalse(database.exists())


class PublicResolverTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        WORK.mkdir(exist_ok=True)
        self.directory = tempfile.TemporaryDirectory(prefix='public-resolver-', dir=WORK)
        self.node = PeerNode(Path(self.directory.name) / 'node.sqlite', allow_internet=True, max_peers=2)

    async def asyncTearDown(self):
        await self.node.stop()
        self.directory.cleanup()

    @staticmethod
    def record(host, *, family=socket.AF_INET, kind=socket.SOCK_STREAM):
        return family, kind, socket.IPPROTO_TCP, '', (host, 9999)

    async def test_dns_answers_filter_actual_addresses_and_preserve_requested_port(self):
        records = [self.record(host) for host in ('0.0.0.0', '224.0.0.1', '192.0.2.1', '8.8.8.8', '8.8.8.8', '127.0.0.1', '192.168.1.2')]
        records += [self.record('::1', family=socket.AF_INET6), self.record('1.1.1.1', kind=socket.SOCK_DGRAM)]
        loop = asyncio.get_running_loop()
        with patch.object(loop, 'getaddrinfo', AsyncMock(return_value=records)) as resolver:
            targets = await self.node._resolve_target(('peer.example', 8123))
        self.assertEqual((('8.8.8.8', 8123), ('127.0.0.1', 8123), ('192.168.1.2', 8123), ('::1',8123)), targets)
        resolver.assert_awaited_once_with('peer.example', 8123, family=socket.AF_UNSPEC, type=socket.SOCK_STREAM, proto=socket.IPPROTO_TCP)
        self.assertGreaterEqual(self.node.info()['stats']['address_rejections'], 4)

    async def test_all_forbidden_dns_answers_fail_before_any_dial(self):
        records = [self.record(host) for host in ('0.0.0.0', '224.0.0.1', '169.254.0.1', '240.0.0.1')]
        with patch.object(asyncio.get_running_loop(), 'getaddrinfo', AsyncMock(return_value=records)), patch('sumuww.peer.asyncio.open_connection', AsyncMock()) as dial:
            with self.assertRaises(OSError):
                await self.node._open_target(('peer.example', 8123))
        dial.assert_not_awaited()

    async def test_dial_uses_checked_numeric_answer_without_second_dns_resolution(self):
        records = [self.record('8.8.8.8'), self.record('1.1.1.1')]
        reader, writer = object(), object()
        with patch.object(asyncio.get_running_loop(), 'getaddrinfo', AsyncMock(return_value=records)) as resolver, patch('sumuww.peer.asyncio.open_connection', AsyncMock(side_effect=[OSError('fixture failure'), (reader, writer)])) as dial:
            self.assertEqual((reader, writer), await self.node._open_target(('peer.example', 8123)))
        self.assertEqual(1, resolver.await_count)
        self.assertEqual([('8.8.8.8', 8123), ('1.1.1.1', 8123)], [call.args for call in dial.await_args_list])
        for call in dial.await_args_list:
            self.assertEqual(socket.AF_INET, call.kwargs['family'])

    async def test_numeric_target_never_calls_dns(self):
        with patch.object(asyncio.get_running_loop(), 'getaddrinfo', AsyncMock()) as resolver:
            self.assertEqual((('8.8.8.8', 8123),), await self.node._resolve_target(('8.8.8.8', 8123)))
        resolver.assert_not_awaited()

    async def test_dns_candidates_are_bounded(self):
        records = [self.record('8.8.8.' + str(index)) for index in range(1, 20)]
        with patch.object(asyncio.get_running_loop(), 'getaddrinfo', AsyncMock(return_value=records)):
            self.assertEqual(8, len(await self.node._resolve_target(('peer.example', 8123))))
        records = [self.record('224.0.0.1')] * 64 + [self.record('8.8.8.8')]
        with patch.object(asyncio.get_running_loop(), 'getaddrinfo', AsyncMock(return_value=records)):
            with self.assertRaises(OSError):
                await self.node._resolve_target(('peer.example', 8123))

    @staticmethod
    def writer(host='8.8.8.8'):
        writer = Mock()
        writer.get_extra_info.return_value = (host, 8123)
        writer.wait_closed = AsyncMock(return_value=None)
        return writer

    async def test_incoming_actual_global_source_allowed_but_zero_and_dns_rejected(self):
        self.node._running = True
        with patch.object(self.node, '_run_session', new=Mock(return_value=None)), patch.object(self.node, '_spawn') as spawn:
            permitted = self.writer('8.8.8.8')
            self.node._accepted(Mock(), permitted)
            spawn.assert_called_once()
            permitted.close.assert_not_called()
            for host in ('0.0.0.0', 'peer.example', '224.0.0.1'):
                writer = self.writer(host)
                self.node._accepted(Mock(), writer)
                writer.close.assert_called_once()
        self.assertEqual(1, self.node.info()['sessions'])
        self.assertEqual(3, self.node.info()['stats']['address_rejections'])

    async def test_configured_outbound_slot_cannot_be_consumed_by_incoming(self):
        self.node._running = True
        target = ('127.0.0.1', 8123)
        self.node._configured[target] = asyncio.Event()
        first, excess, outgoing = self.writer(), self.writer(), self.writer()
        self.assertIsNotNone(self.node._reserve(Mock(), first))
        self.assertIsNone(self.node._reserve(Mock(), excess))
        excess.close.assert_called_once()
        self.assertIsNotNone(self.node._reserve(Mock(), outgoing, target))
        self.assertEqual(2, self.node.info()['sessions'])
        self.assertEqual(1, self.node.info()['incoming_capacity'])

    async def test_adding_outbound_peer_closes_excess_incoming(self):
        # This checks manual-peer eviction; automatic mode now reserves its
        # outbound slot before any incoming session is accepted.
        self.node.discover_peers = False
        self.node._running = True
        first, excess = self.writer(), self.writer()
        self.assertIsNotNone(self.node._reserve(Mock(), first))
        self.assertIsNotNone(self.node._reserve(Mock(), excess))
        with patch.object(self.node, '_outgoing', new=Mock(return_value=None)), patch.object(self.node, '_spawn'):
            self.assertEqual(('127.0.0.1', 8123), await self.node.add_peer('127.0.0.1', 8123))
        first.close.assert_not_called()
        excess.close.assert_called_once()
        self.assertEqual(1, self.node.info()['stats']['incoming_evictions'])

    async def test_automatic_discovery_keeps_one_outbound_slot_without_manual_peers(self):
        self.node._running = True
        self.assertFalse(self.node._configured)
        incoming,excess,outgoing=self.writer(),self.writer(),self.writer()
        self.assertIsNotNone(self.node._reserve(Mock(),incoming))
        self.assertIsNone(self.node._reserve(Mock(),excess))
        self.assertIsNotNone(self.node._reserve(Mock(),outgoing,('127.0.0.1',8123)))
        self.assertEqual(1,self.node.info()['incoming_capacity'])

    async def test_discovery_optout_and_internet_optout_keep_full_incoming_capacity(self):
        self.node.discover_peers=False
        self.assertEqual(2,self.node._incoming_capacity())
        self.node.discover_peers=True
        self.node.allow_internet=False
        self.assertEqual(2,self.node._incoming_capacity())

    async def test_full_eight_peer_configuration_keeps_four_incoming_slots(self):
        self.node.max_peers = 8
        self.node._running = True
        self.node._configured = {('127.0.0.' + str(index), 8123): asyncio.Event()
                                 for index in range(1, 9)}
        self.assertEqual(4, self.node.info()['incoming_capacity'])
        for _ in range(4):
            self.assertIsNotNone(self.node._reserve(Mock(), self.writer()))
        excess = self.writer()
        self.assertIsNone(self.node._reserve(Mock(), excess))
        excess.close.assert_called_once()
        self.assertIsNotNone(self.node._reserve(Mock(), self.writer(), ('127.0.0.1', 8123)))

    async def test_one_session_limit_keeps_incoming_usable_with_configured_peer(self):
        self.node.max_peers = 1
        self.node._running = True
        self.node._configured[('127.0.0.1', 8123)] = asyncio.Event()
        self.assertEqual(1, self.node.info()['incoming_capacity'])
        self.assertIsNotNone(self.node._reserve(Mock(), self.writer()))
        excess = self.writer()
        self.assertIsNone(self.node._reserve(Mock(), excess))
        excess.close.assert_called_once()


class PublicOptInSocketTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        WORK.mkdir(exist_ok=True)
        self.directory = tempfile.TemporaryDirectory(prefix='public-local-tcp-', dir=WORK)
        self.nodes = []

    async def asyncTearDown(self):
        await asyncio.gather(*(node.stop() for node in self.nodes), return_exceptions=True)
        self.directory.cleanup()

    def node(self, *, database=None, **options):
        database = database or Path(self.directory.name) / f'node-{len(self.nodes)}.sqlite'
        options.setdefault('allow_internet', True)
        options.setdefault('clock', lambda: NOW)
        node = PeerNode(database, poll_interval=.1, timeout=2, **options)
        self.nodes.append(node)
        return node

    async def test_sumuww_identity_handshake_and_wildcard_listener_on_local_tcp(self):
        source = self.node(host='0.0.0.0', network=SUMUWW)
        target = self.node(network=SUMUWW)
        await source.start()
        await target.start()
        await target.connect('127.0.0.1', source.address[1])
        await eventually(lambda: source.info()['peers'] == target.info()['peers'] == 1)
        self.assertEqual('0.0.0.0', source.address[0])
        for node in (source, target):
            info = node.info()
            self.assertEqual('dora', info['network'])
            self.assertEqual('d052470c', info['network_magic'])
            self.assertEqual(SUMUWW.genesis.block_hash(), node.chain.tip_hash)
            self.assertTrue(info['allow_internet'])
            self.assertFalse(info['public_network_ready'])

    async def test_opt_in_transaction_block_relay_and_reconnect_on_local_tcp(self):
        source, target = self.node(), self.node()
        blocks = source.chain.mine(ALICE.script_pubkey, 100)
        await source.start()
        await target.start()
        await target.connect(*source.address)
        await eventually(lambda: source.chain.tip_hash == target.chain.tip_hash)
        first = blocks[0].transactions[0]
        unsigned = Transaction(2, (TxInput(first.txid(), 0),),
                               (TxOutput(3 * COIN, BOB.script_pubkey),
                                TxOutput(47 * COIN - 100_000, ALICE.script_pubkey)))
        transaction = sign_p2wpkh(unsigned, 0, first.outputs[0], ALICE)
        source.chain.submit_transaction(transaction)
        await eventually(lambda: target.chain.has_mempool_transaction(transaction.txid()))
        source.chain.mine(ALICE.script_pubkey, 1)
        await eventually(lambda: source.chain.tip_hash == target.chain.tip_hash and not target.chain.mempool_transactions())
        self.assertEqual(3 * COIN, target.chain.balance(BOB.script_pubkey))
        address, database = source.address, source.database
        await source.stop()
        restarted = self.node(database=database, host=address[0], port=address[1])
        restarted.chain.mine(ALICE.script_pubkey, 2)
        await restarted.start()
        await eventually(lambda: target.chain.tip_hash == restarted.chain.tip_hash, 20)
        self.assertEqual(103, target.chain.info()['height'])
        self.assertEqual(restarted.chain.state_commitment(), target.chain.state_commitment())
        self.assertGreaterEqual(target.info()['stats']['handshakes'], 2)


if __name__ == '__main__':
    unittest.main()
