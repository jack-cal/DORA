"""Bounded peer work, quiet relay, verified anchors and durable discovery.

Only generated regtest keys, owned temporary databases and loopback sockets.
"""
import asyncio
from collections import Counter
import hashlib
import os
from pathlib import Path
import shutil
import tempfile
import time
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from sumuww.block import GENESIS_TIME
from sumuww.chain import Chain
from sumuww.peer import PeerNode, _Session, PEER_INVENTORY_BURST, PEER_INVENTORY_RATE
from sumuww.transaction import Transaction, TxInput, TxOutput
from sumuww.wallet import RegtestKey, sign_p2wpkh
from sumuww.wire import (INV_BLOCK, INV_TRANSACTION, MAX_INV, Frame, Inventory, Version,
                       decode_getheaders, decode_version, encode_frame, encode_getheaders,
                       encode_headers, encode_inventory, encode_version,
                       read_frame, write_frame)

NOW = GENESIS_TIME + 6000
ALICE = RegtestKey.from_int(3801)
BOB = RegtestKey.from_int(3802)
LOAD_RECORDS = []


async def eventually(predicate, timeout=10):
    deadline = asyncio.get_running_loop().time() + timeout
    while not predicate():
        if asyncio.get_running_loop().time() >= deadline:
            raise AssertionError('Owned peer did not reach the required state')
        await asyncio.sleep(.01)


class PeerPolicyTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='sumuww-owned-policy38-',
                                                     dir=os.environ.get('SUMUWW_TEST_WORKDIR'))
        self.folder = Path(self.temporary.name)
        self.nodes, self.writers, self.tasks = [], [], []

    async def asyncTearDown(self):
        for writer in self.writers:
            writer.close()
        for task in self.tasks:
            task.cancel()
        await asyncio.gather(*self.tasks, return_exceptions=True)
        await asyncio.gather(*(node.stop() for node in self.nodes), return_exceptions=True)
        for node in self.nodes:
            self.assertFalse(node._sessions)
            self.assertFalse(node._tasks)
        self.temporary.cleanup()

    def node(self, *, seed=None, **options):
        database = self.folder / ('node' + str(len(self.nodes)) + '.sqlite')
        if seed is not None:
            shutil.copy2(seed, database)
        options.setdefault('discover_peers', False)
        options.setdefault('dht_enabled', False)
        options.setdefault('poll_interval', .05)
        options.setdefault('timeout', 2)
        node = PeerNode(database, clock=lambda: NOW, **options)
        self.nodes.append(node)
        return node

    async def pair(self):
        source, target = self.node(), self.node()
        await asyncio.gather(source.start(), target.start())
        await target.connect(*source.address)
        await eventually(lambda: source.synchronization_info()['mining_ready'] and
                         target.synchronization_info()['mining_ready'])
        await asyncio.sleep(.15)
        return source, target

    async def send(self, writer, node, command, payload=b''):
        await write_frame(writer, command, payload, timeout=2, magic=node.network.message_magic)

    async def command(self, reader, node, wanted):
        while True:
            frame = await read_frame(reader, timeout=3, magic=node.network.message_magic)
            if frame.command == wanted:
                return frame

    async def raw(self, node, *, synchronized=True):
        reader, writer = await asyncio.open_connection(*node.address)
        self.writers.append(writer)
        version = decode_version((await self.command(reader, node, 'version')).payload)
        remote = Version(version.protocol, node.genesis, version.nonce ^ (len(self.writers) + 17),
                         node.network.profile_id, node.chain.tip_hash)
        await self.send(writer, node, 'version', encode_version(remote))
        await self.command(reader, node, 'verack')
        await self.send(writer, node, 'verack')
        await self.command(reader, node, 'getheaders')
        if synchronized:
            await self.send(writer, node, 'headers', encode_headers(()))
            await eventually(lambda: any(session.nonce == remote.nonce and session.synchronized
                                        for session in node._sessions.values()))
        return reader, writer

    async def test_01_stable_tip_pool_are_quiet_and_new_block_relays_immediately(self):
        source, target = await self.pair()
        sent = source._stats['frames_sent'] + target._stats['frames_sent']
        await asyncio.sleep(1.3)
        self.assertEqual(sent, source._stats['frames_sent'] + target._stats['frames_sent'])
        began = time.monotonic()
        source.chain.mine(ALICE.script_pubkey)
        await eventually(lambda: target.chain.tip_hash == source.chain.tip_hash)
        self.assertLess(time.monotonic() - began, 2)
        self.assertEqual(source.chain.state_commitment(), target.chain.state_commitment())

    async def test_02_keepalive_and_fallback_preserve_fresh_verified_sessions(self):
        with patch('sumuww.peer.HEADER_REFRESH_INTERVAL', .2), patch('sumuww.peer.KEEPALIVE_INTERVAL', .2):
            source, target = await self.pair()
            sessions = tuple(source._sessions) + tuple(target._sessions)
            before = source._stats['frames_sent'] + target._stats['frames_sent']
            await asyncio.sleep(.65)
            self.assertGreater(source._stats['frames_sent'] + target._stats['frames_sent'], before)
            self.assertEqual(sessions, tuple(source._sessions) + tuple(target._sessions))
            self.assertTrue(all(node.synchronization_info()['mining_ready'] for node in (source, target)))
            self.assertEqual(0, source._stats['protocol_errors'] + target._stats['protocol_errors'])

    async def test_03_unverified_backup_does_not_block_anchor_but_stale_anchor_does(self):
        source, target = await self.pair()
        _, writer = await self.raw(target, synchronized=False)
        self.assertEqual(2, target.info()['peers'])
        self.assertTrue(target.synchronization_info()['mining_ready'])
        self.assertEqual(1, target.synchronization_info()['synchronized_peers'])
        source.chain.mine(ALICE.script_pubkey)
        await eventually(lambda: target.chain.tip_hash == source.chain.tip_hash)
        await eventually(lambda: target.synchronization_info()['mining_ready'])
        normal_clock = target._peer_clock
        target._peer_clock = lambda: normal_clock() + 26
        self.assertFalse(target.synchronization_info()['mining_ready'])
        target._peer_clock = normal_clock
        writer.close()

    async def test_04_live_extensions_keep_mining_on_validated_tip_until_body_validates(self):
        node = self.node()
        await node.start()
        first_reader, first = await self.raw(node)
        _, second = await self.raw(node)
        before = node.chain.state_commitment()
        block = node.chain.make_block(ALICE.script_pubkey)
        hint = encode_inventory((Inventory(INV_BLOCK, block.block_hash()),))
        await self.send(first, node, 'inv', hint)
        await self.send(second, node, 'inv', hint)
        await eventually(lambda: node.synchronization_info()['live_block_updates'] == 2)
        self.assertTrue(node.synchronization_info()['mining_ready'])
        self.assertEqual(before, node.chain.state_commitment())
        self.assertFalse(node.chain.has_block(block.block_hash()))
        await self.command(first_reader, node, 'getheaders')
        await self.send(first, node, 'headers', encode_headers((block.header,)))
        await self.command(first_reader, node, 'getdata')
        self.assertTrue(node.synchronization_info()['mining_ready'])
        self.assertEqual(before, node.chain.state_commitment())
        await self.send(first, node, 'block', block.serialize())
        await self.command(first_reader, node, 'getheaders')
        await self.send(first, node, 'headers', encode_headers(()))
        await eventually(lambda: node.synchronization_info()['synchronized_peers'] == 1)
        self.assertTrue(node.synchronization_info()['mining_ready'])
        self.assertEqual(block.block_hash(), node.chain.tip_hash)
        self.assertEqual(1, node.synchronization_info()['synchronized_peers'])

    async def test_05_512_normal_headers_backpressure_isolates_healthy_relay(self):
        source, target = await self.pair()
        reader, writer = await self.raw(source)
        counts = Counter()
        async def consume():
            while True:
                frame = await read_frame(reader, timeout=5, magic=source.network.message_magic)
                counts[frame.command] += 1
        self.tasks.append(asyncio.create_task(consume()))
        payload = encode_getheaders((source.chain.tip_hash,))
        writer.write(encode_frame('getheaders', payload, source.network.message_magic) * 512)
        await writer.drain()
        await asyncio.sleep(.8)
        self.assertLessEqual(counts['headers'], 20)
        self.assertGreater(source._stats['quota_work_waits'], 0)
        sessions = tuple(target._sessions)
        began = time.monotonic()
        source.chain.mine(ALICE.script_pubkey)
        await eventually(lambda: target.chain.tip_hash == source.chain.tip_hash, 2)
        self.assertLess(time.monotonic() - began, 2)
        self.assertEqual(sessions, tuple(target._sessions))
        self.assertEqual(0, source._stats['invalid_peer_incidents'])
        self.assertLessEqual(len(source._sessions), 2)
        LOAD_RECORDS.append({'case': '512_normal_requests_isolate_healthy_relay',
                             'attempted_requests': 512, 'initial_headers_responses': counts['headers'],
                             'healthy_block_relay_seconds': round(time.monotonic() - began, 4),
                             'quota_work_waits': source._stats['quota_work_waits']})

    async def test_06_10000_transaction_hints_have_1000_total_256_active_bound(self):
        node = self.node()
        node._send = AsyncMock()
        writer = MagicMock()
        writer.is_closing.return_value = False
        session = _Session(asyncio.StreamReader(), writer, ready=True)
        for offset in range(0, 10000, MAX_INV):
            items = tuple(Inventory(INV_TRANSACTION, hashlib.sha256(str(index).encode()).digest())
                          for index in range(offset, min(offset + MAX_INV, 10000)))
            await node._received_inventory(session, encode_inventory(items))
            self.assertLessEqual(len(session.tx_requests), 256)
            self.assertLessEqual(len(session.tx_requests) + len(session.pending_transactions), 1000)
        self.assertEqual(1000, len(session.tx_requests) + len(session.pending_transactions))
        self.assertEqual(9000, node._stats['transaction_hint_drops'])
        self.assertEqual(0, node.chain.summary()['mempool'])

    async def test_07_wire_egress_and_validation_allowance_preserve_maximum_frame(self):
        node = self.node()
        session = _Session(asyncio.StreamReader(), MagicMock(), ready=True)
        for _ in range(8):
            await node._take_quota(session, 'egress', 100_000 + 24)
        self.assertEqual(0, node._stats['quota_egress_waits'])
        await node._take_quota(session, 'validation', 4 * 1024 * 1024)
        self.assertEqual(0, node._stats['quota_validation_waits'])
        began = time.monotonic()
        await node._take_quota(session, 'validation', 1024 * 1024)
        self.assertGreaterEqual(time.monotonic() - began, .4)
        self.assertLess(time.monotonic() - began, 2)
        self.assertEqual(1, node._stats['quota_validation_waits'])

    async def test_08_one_slot_settles_and_two_slots_reserve_outgoing_backup(self):
        one, seed = self.node(max_peers=1), self.node()
        await asyncio.gather(one.start(), seed.start())
        await one.connect(*seed.address)
        await eventually(one._discovery_settled)
        automatic = self.node(max_peers=2, allow_internet=True,
                              discover_peers=True, discovery_scope='loopback')
        incoming = self.node()
        await asyncio.gather(automatic.start(), incoming.start())
        await incoming.connect(*automatic.address)
        await eventually(lambda: automatic.synchronization_info()['mining_ready'])
        self.assertFalse(automatic._discovery_settled())
        original = next(iter(automatic._sessions))
        automatic._addresses.add_hint(seed.address)
        await eventually(automatic._discovery_settled)
        self.assertIn(original, automatic._sessions)
        self.assertEqual(2, len(automatic._sessions))
        self.assertEqual(1, sum(session.outgoing is not None for session in automatic._sessions.values()))

    async def test_09_settled_outgoing_backups_stop_new_dials_and_replace_loss(self):
        seeds = [self.node() for _ in range(4)]
        await asyncio.gather(*(seed.start() for seed in seeds))
        automatic = self.node(max_peers=2, allow_internet=True, discover_peers=True, discovery_scope='loopback')
        await automatic.start()
        for seed in seeds:
            automatic._addresses.add_hint(seed.address)
        await eventually(automatic._discovery_settled)
        self.assertEqual(2, sum(session.outgoing is not None for session in automatic._healthy_sessions()))
        original = set(automatic._sessions)
        attempts = automatic._stats['reconnect_attempts']
        await asyncio.sleep(.4)
        self.assertEqual(original, set(automatic._sessions))
        self.assertEqual(attempts, automatic._stats['reconnect_attempts'])
        victim = next(session for session in automatic._healthy_sessions())
        healthy_other = original - {id(victim.writer)}
        victim.writer.close()
        await eventually(lambda: automatic._discovery_settled() and set(automatic._sessions) != original)
        self.assertTrue(healthy_other <= set(automatic._sessions))

    async def test_12_repeated_inventory_discount_is_bounded_and_new_hints_pay_work(self):
        node = self.node()
        session = _Session(asyncio.StreamReader(), MagicMock(), ready=True)
        items = tuple(Inventory(INV_TRANSACTION, hashlib.sha256(str(i).encode()).digest())
                      for i in range(256))
        payload = encode_inventory(items)
        decoded, first = node._inventory_work(session, payload)
        self.assertEqual(items, decoded)
        self.assertEqual(257, first)
        self.assertEqual(1, node._inventory_work(session, payload)[1])
        for offset in range(256, 2816, 256):
            new = tuple(Inventory(INV_TRANSACTION, hashlib.sha256(str(i).encode()).digest())
                        for i in range(offset, offset + 256))
            self.assertEqual(257, node._inventory_work(session, encode_inventory(new))[1])
            self.assertLessEqual(len(session.recent_inventory), 1256)
        # Eviction restores the charge; no permanent hash whitelist exists.
        self.assertEqual(257, node._inventory_work(session, payload)[1])
        self.assertEqual(0, node.chain.summary()['mempool'])

    async def test_13_verified_known_128_page_progress_is_fast_and_terminal_resets(self):
        node = self.node(poll_interval=.1)
        blocks = node.chain.mine(ALICE.script_pubkey, 129)
        node._running = True
        node._send = AsyncMock()
        writer = MagicMock()
        writer.is_closing.return_value = False
        writer.wait_closed = AsyncMock()
        session = _Session(asyncio.StreamReader(), writer, ready=True, header_requested=True)
        session.last_announced_tip = node.chain.tip_hash
        node._sessions[id(writer)] = session
        # A prior terminal exchange is a valid anchor. Known pagination later
        # must advance quickly without revoking that fully validated anchor.
        await node._received_headers(session, encode_headers(()))
        self.assertFalse(session.headers_continuing)
        self.assertTrue(node.synchronization_info()['mining_ready'])
        session.header_requested = True
        await node._received_headers(session, encode_headers(tuple(block.header for block in blocks[:128])))
        self.assertTrue(session.headers_continuing)
        self.assertTrue(node.synchronization_info()['mining_ready'])
        completed = session.last_headers_at
        await node._poll_session(session, node.chain.tip_hash, (), completed + .09)
        node._send.assert_not_awaited()
        await node._poll_session(session, node.chain.tip_hash, (), completed + .11)
        self.assertEqual('getheaders', node._send.await_args.args[1])
        locator, _ = decode_getheaders(node._send.await_args.args[2])
        self.assertEqual(blocks[127].block_hash(), locator[0])
        await node._received_headers(session, encode_headers((blocks[128].header,)))
        await node._poll_session(session, node.chain.tip_hash, (), session.last_headers_at + .11)
        await node._received_headers(session, encode_headers(()))
        self.assertFalse(session.headers_continuing)
        self.assertTrue(node.synchronization_info()['mining_ready'])
        node._send.reset_mock()
        completed = session.last_headers_at
        await node._poll_session(session, node.chain.tip_hash, (), completed + .11)
        node._send.assert_not_awaited()
        await node._poll_session(session, node.chain.tip_hash, (), completed + 10.01)
        self.assertIn('getheaders', [call.args[1] for call in node._send.await_args_list])

    async def test_14_inventory_item_budget_waits_before_sql_and_cancel_is_isolated(self):
        node = self.node()
        node._send = AsyncMock()
        first = _Session(asyncio.StreamReader(), MagicMock(), ready=True)
        other = _Session(asyncio.StreamReader(), MagicMock(), ready=True)
        payload = encode_inventory(tuple(Inventory(INV_TRANSACTION, hashlib.sha256(str(i).encode()).digest())
                                         for i in range(256)))
        frame = Frame('inv', payload)
        node._inventory_work(first, payload)
        self.assertEqual(16384, PEER_INVENTORY_BURST)
        self.assertEqual(4096, PEER_INVENTORY_RATE)
        # Freeze the clock for deterministic credit accounting. All operations
        # here finish immediately or are cancelled before a timer can fire.
        loop = asyncio.get_running_loop()
        fixed_time = loop.time()
        with patch.object(loop, 'time', return_value=fixed_time), \
                patch.object(node.chain, 'has_mempool_transaction', return_value=True) as membership:
            for _ in range(64):
                await node._handle(first, frame)
            self.assertEqual(16384, membership.call_count)
            self.assertEqual(0, first.inventory_credit)
            waiting = asyncio.create_task(node._handle(first, frame))
            await asyncio.sleep(0)
            self.assertEqual(1, node._stats['quota_inventory_waits'])
            self.assertEqual(16384, membership.call_count, 'Item throttle must precede every DB membership check')
            await node._handle(other, frame)
            self.assertEqual(16384 + 256, membership.call_count)
            self.assertEqual(16384 - 256, other.inventory_credit)
            waiting.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await waiting
        self.assertEqual(0, node._stats['invalid_peer_incidents'])
        self.assertEqual(0, node.chain.summary()['mempool'])


class PeerSignedPoolTests(PeerPolicyTests):
    # Inherit only socket helpers; suppress the separate policy case methods.
    for _name in tuple(vars(PeerPolicyTests)):
        if _name.startswith('test_'):
            locals()[_name] = None

    @classmethod
    def setUpClass(cls):
        cls.seed_directory = tempfile.TemporaryDirectory(prefix='sumuww-owned-1000-seed38-',
                                                       dir=os.environ.get('SUMUWW_TEST_WORKDIR'))
        cls.seed = Path(cls.seed_directory.name) / 'seed.sqlite'
        with Chain(cls.seed, clock=lambda: NOW) as chain:
            first = chain.mine(ALICE.script_pubkey, 100)[0].transactions[0]
            unit = (first.outputs[0].value - 100_000) // 1000
            funding = Transaction(2, (TxInput(first.txid(), 0),),
                                  tuple(TxOutput(unit, ALICE.script_pubkey) for _ in range(1000)))
            cls.funding = sign_p2wpkh(funding, 0, first.outputs[0], ALICE)
            chain.submit_transaction(cls.funding)
            chain.mine(ALICE.script_pubkey)
            chain.connection.execute('PRAGMA wal_checkpoint(TRUNCATE)')
        cls.transactions = tuple(cls.spend(index) for index in range(1000))

    @classmethod
    def tearDownClass(cls):
        cls.seed_directory.cleanup()

    @classmethod
    def spend(cls, index, previous=None):
        previous = cls.funding if previous is None else previous
        output = previous.outputs[index]
        transaction = Transaction(2, (TxInput(previous.txid(), index),),
                                  (TxOutput(output.value - 1000, ALICE.script_pubkey),))
        return sign_p2wpkh(transaction, 0, output, ALICE)

    async def test_10_1000_real_transactions_relay_once_in_bounded_inventory_pages(self):
        source, target = self.node(seed=self.seed, timeout=5), self.node(seed=self.seed, timeout=5)
        # Every transaction gets real P2WPKH validation before advertising.
        for transaction in self.transactions:
            source.chain.submit_transaction(transaction)
        sent = Counter()
        original_send = PeerNode._send
        peak_active = peak_total = 0
        async def observe(node, session, command, payload=b''):
            nonlocal peak_active, peak_total
            if node is source and command == 'inv':
                sent['source_inventory_frames'] += 1
            if node is target:
                peak_active = max(peak_active, len(session.tx_requests))
                peak_total = max(peak_total, len(session.tx_requests) + len(session.pending_transactions))
            return await original_send(node, session, command, payload)
        began = time.monotonic()
        with patch.object(PeerNode, '_send', observe):
            await asyncio.gather(source.start(), target.start())
            await target.connect(*source.address)
            await eventually(lambda: target.chain.summary()['mempool'] == 1000, 30)
            self.assertEqual({tx.txid() for tx in self.transactions},
                             {tx.txid() for tx in target.chain.mempool_transactions()})
            self.assertLessEqual(peak_active, 256)
            self.assertLessEqual(peak_total, 1000)
            self.assertEqual(5, sent['source_inventory_frames'])  # one tip plus four TX pages
            before = sent['source_inventory_frames']
            await asyncio.sleep(1.1)
            self.assertEqual(before, sent['source_inventory_frames'])
            source.chain.mine(ALICE.script_pubkey)
            await eventually(lambda: target.chain.tip_hash == source.chain.tip_hash and
                             target.chain.summary()['mempool'] == 0, 20)
        self.assertEqual(source.chain.state_commitment(), target.chain.state_commitment())
        self.assertEqual(0, source._stats['protocol_errors'] + target._stats['protocol_errors'])
        LOAD_RECORDS.append({'case': '1000_real_signed_transaction_delta_relay',
                             'validated_transactions': 1000, 'peak_active_tx_requests': peak_active,
                             'peak_total_tx_hints': peak_total, 'source_initial_inventory_frames': before,
                             'full_block_confirmation_and_equal_state': True,
                             'seconds': round(time.monotonic() - began, 4)})

    async def test_11_rejected_child_retries_after_fully_validated_parent(self):
        node = self.node(seed=self.seed)
        await node.start()
        reader, writer = await self.raw(node)
        parent = self.transactions[0]
        child = self.spend(0, previous=parent)
        await self.send(writer, node, 'inv', encode_inventory((Inventory(INV_TRANSACTION, child.txid()),)))
        await self.command(reader, node, 'getdata')
        await self.send(writer, node, 'tx', child.serialize())
        await eventually(lambda: node._stats['validation_rejections'] == 1)
        self.assertFalse(node.chain.has_mempool_transaction(child.txid()))
        self.assertEqual(0, node.chain.summary()['mempool'])
        await self.send(writer, node, 'inv', encode_inventory((Inventory(INV_TRANSACTION, parent.txid()),)))
        await self.command(reader, node, 'getdata')
        await self.send(writer, node, 'tx', parent.serialize())
        await self.command(reader, node, 'getdata')
        await self.send(writer, node, 'tx', child.serialize())
        await eventually(lambda: node.chain.has_mempool_transaction(child.txid()))
        self.assertEqual(2, node.chain.summary()['mempool'])
        self.assertEqual(2, node._stats['transactions_accepted'])


if __name__ == '__main__':
    unittest.main()
