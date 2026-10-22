"""Actual IPv4 loopback socket checks; no public peers or production keys."""

import asyncio
from dataclasses import replace
from pathlib import Path
import os
import shutil
import tempfile
import unittest

from sumuww.block import Block, GENESIS_TIME, PROFILE_ID, genesis_block, mine_header
from sumuww.chain import Chain
from sumuww.peer import PeerNode
from sumuww.primitives import COIN, merkle_root
from sumuww.transaction import Transaction, TxInput, TxOutput
from sumuww.wallet import RegtestKey, sign_p2wpkh
from sumuww.wire import (
    INV_BLOCK, INV_TRANSACTION, PROTOCOL_VERSION, DISCOVERY_PROTOCOL_VERSION, IPV6_PROTOCOL_VERSION, Inventory, ProtocolError,
    Version, decode_inventory, decode_version, encode_headers, encode_inventory,
    encode_ping, encode_version, read_frame, write_frame,
)


NOW = GENESIS_TIME + 1000
ALICE = RegtestKey.from_int(1)
BOB = RegtestKey.from_int(2)
WORK = Path(os.environ.get('SUMUWW_TEST_WORKDIR', tempfile.gettempdir()))


async def eventually(predicate, timeout=15):
    deadline = asyncio.get_running_loop().time() + timeout
    while not predicate():
        if asyncio.get_running_loop().time() >= deadline:
            raise AssertionError('Loopback nodes did not reach the expected state before the deadline')
        await asyncio.sleep(.03)


class PeerSocketTests(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        WORK.mkdir(exist_ok=True)
        cls.seed_directory = tempfile.TemporaryDirectory(prefix='peer-seed-', dir=WORK)
        cls.seed = Path(cls.seed_directory.name) / 'seed.sqlite'
        with Chain(cls.seed, clock=lambda: NOW) as chain:
            cls.seed_blocks = chain.mine(ALICE.script_pubkey, 100)
            chain.connection.execute('PRAGMA wal_checkpoint(TRUNCATE)')

    @classmethod
    def tearDownClass(cls):
        cls.seed_directory.cleanup()

    async def asyncSetUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix='peer-case-', dir=WORK)
        self.nodes = []
        self.writers = []
        self.counter = 0

    async def asyncTearDown(self):
        for writer in self.writers:
            writer.close()
        await asyncio.gather(*(node.stop() for node in self.nodes), return_exceptions=True)
        for writer in self.writers:
            try:
                await asyncio.wait_for(writer.wait_closed(), 1)
            except (OSError, TimeoutError):
                pass
        self.directory.cleanup()

    def node(self, *, seeded=False, database=None, **options):
        self.counter += 1
        path = Path(self.directory.name) / f'node{self.counter}.sqlite' if database is None else database
        if seeded:
            shutil.copy2(self.seed, path)
        instance = PeerNode(path, poll_interval=.1, timeout=2, clock=lambda: NOW, **options)
        self.nodes.append(instance)
        return instance

    async def raw_peer(self, node, *, version_change=None):
        reader, writer = await asyncio.open_connection(*node.address)
        self.writers.append(writer)
        first = await read_frame(reader, 2)
        self.assertEqual(first.command, 'version')
        ours = decode_version(first.payload)
        remote = Version(PROTOCOL_VERSION, genesis_block().block_hash(), ours.nonce ^ 1,
                         PROFILE_ID, genesis_block().block_hash())
        if version_change is not None:
            remote = version_change(remote, ours)
        await write_frame(writer, 'version', encode_version(remote), 2)
        if version_change is None:
            self.assertEqual((await read_frame(reader, 2)).command, 'verack')
            await write_frame(writer, 'verack', b'', 2)
        return reader, writer

    async def next_command(self, reader, command):
        for _ in range(20):
            frame = await read_frame(reader, 2)
            if frame.command == command:
                return frame
        self.fail(f'Expected {command} within bounded response count')

    def spend(self):
        first = self.seed_blocks[0].transactions[0]
        transaction = Transaction(2, (TxInput(first.txid(), 0),),
                                  (TxOutput(3 * COIN, BOB.script_pubkey),
                                   TxOutput(47 * COIN - 100_000, ALICE.script_pubkey)))
        return sign_p2wpkh(transaction, 0, first.outputs[0], ALICE)

    async def test_two_nodes_catch_up_over_real_sockets(self):
        source, target = self.node(), self.node()
        source.chain.mine(ALICE.script_pubkey, 9)
        await source.start()
        await target.start()
        self.assertEqual(await target.connect(*source.address), source.address)
        await eventually(lambda: target.chain.tip_hash == source.chain.tip_hash)
        self.assertEqual(target.chain.info()['utxo_commitment'], source.chain.info()['utxo_commitment'])
        self.assertEqual(target.info()['stats']['blocks_stored'], 9)
        self.assertEqual(target.info()['peers'], 1)

    async def test_external_sqlite_transaction_relay_and_confirmation(self):
        source, target = self.node(seeded=True), self.node(seeded=True)
        await source.start()
        await target.start()
        await target.connect(*source.address)
        transaction = self.spend()
        with Chain(source.database, clock=lambda: NOW) as external_cli:
            external_cli.submit_transaction(transaction)
        await eventually(lambda: target.chain.has_mempool_transaction(transaction.txid()))
        self.assertEqual(target.chain.get_mempool_transaction(transaction.txid()).serialize(), transaction.serialize())
        with Chain(source.database, clock=lambda: NOW) as external_cli:
            external_cli.mine(ALICE.script_pubkey, 1)
        await eventually(lambda: target.chain.tip_hash == source.chain.tip_hash and not target.chain.mempool_transactions())
        self.assertEqual(target.chain.info()['height'], 101)
        self.assertEqual(target.chain.info()['utxo_commitment'], source.chain.info()['utxo_commitment'])

    async def test_header_pagination_crosses_128(self):
        source, target = self.node(), self.node()
        source.chain.mine(ALICE.script_pubkey, 135)
        await source.start()
        await target.start()
        await target.connect(*source.address)
        await eventually(lambda: target.chain.tip_hash == source.chain.tip_hash, 25)
        self.assertEqual(target.info()['stats']['blocks_stored'], 135)
        self.assertGreaterEqual(target.info()['stats']['headers_received'], 135)

    async def test_shorter_side_branch_pagination_converges_by_work(self):
        shorter, longer = self.node(), self.node()
        shorter.chain.mine(ALICE.script_pubkey, 130)
        longer.chain.mine(BOB.script_pubkey, 135)
        own_tip = shorter.chain.tip_hash
        await shorter.start()
        await longer.start()
        await shorter.connect(*longer.address)
        await eventually(lambda: shorter.chain.tip_hash == longer.chain.tip_hash, 35)
        self.assertNotEqual(shorter.chain.tip_hash, own_tip)
        self.assertTrue(shorter.chain.has_block(own_tip))
        self.assertEqual(shorter.info()['height'], 135)
        self.assertEqual(shorter.info()['stats']['blocks_stored'], 135)
        self.assertEqual(shorter.chain.info()['utxo_commitment'], longer.chain.info()['utxo_commitment'])

    async def test_reconnect_after_partition_reconciles_divergent_branches(self):
        source, follower = self.node(), self.node()
        source.chain.mine(ALICE.script_pubkey, 3)
        await source.start()
        await follower.start()
        await follower.connect(*source.address)
        await eventually(lambda: follower.chain.tip_hash == source.chain.tip_hash)
        old_address, database = source.address, source.database
        await source.stop()
        follower.chain.mine(BOB.script_pubkey, 4)
        partition_tip = follower.chain.tip_hash
        restarted = self.node(database=database, host=old_address[0], port=old_address[1])
        restarted.chain.mine(ALICE.script_pubkey, 6)
        await restarted.start()
        await eventually(lambda: follower.chain.tip_hash == restarted.chain.tip_hash, 20)
        self.assertNotEqual(follower.chain.tip_hash, partition_tip)
        self.assertTrue(follower.chain.has_block(partition_tip))
        self.assertGreaterEqual(follower.info()['stats']['handshakes'], 2)

    async def test_foreign_version_and_self_connections_are_isolated(self):
        target = self.node()
        await target.start()
        variants = (
            lambda remote, ours: replace(remote, genesis=b'x' * 32),
            lambda remote, ours: replace(remote, profile='foreign-development-profile'),
            lambda remote, ours: replace(remote, protocol=IPV6_PROTOCOL_VERSION + 1),
            lambda remote, ours: replace(remote, nonce=ours.nonce),
        )
        for change in variants:
            with self.subTest(change=change):
                reader, _ = await self.raw_peer(target, version_change=change)
                self.assertEqual(await asyncio.wait_for(reader.read(), 2), b'')
        await eventually(lambda: target.info()['sessions'] == 0)
        self.assertEqual(target.info()['height'], 0)
        self.assertEqual(target.info()['stats']['handshakes'], 0)
        healthy = self.node()
        healthy.chain.mine(ALICE.script_pubkey, 1)
        await healthy.start()
        await target.connect(*healthy.address)
        await eventually(lambda: target.chain.tip_hash == healthy.chain.tip_hash)
        self.assertTrue(target.running)

    async def test_unknown_command_closes_only_its_peer(self):
        target = self.node()
        await target.start()
        reader, writer = await self.raw_peer(target)
        await write_frame(writer, 'unknown', b'', 2)
        # A queued getheaders may precede EOF, so drain bounded bytes.
        await asyncio.wait_for(reader.read(), 2)
        await eventually(lambda: target.info()['sessions'] == 0)
        healthy = self.node()
        healthy.chain.mine(ALICE.script_pubkey, 2)
        await healthy.start()
        await target.connect(*healthy.address)
        await eventually(lambda: target.chain.tip_hash == healthy.chain.tip_hash)
        self.assertGreaterEqual(target.info()['stats']['protocol_errors'], 1)

    async def test_valid_header_does_not_activate_invalid_block_body(self):
        target = self.node()
        await target.start()
        valid = target.chain.make_block(ALICE.script_pubkey)
        coinbase = replace(valid.transactions[0], outputs=(TxOutput(51 * COIN, ALICE.script_pubkey),))
        root, _ = merkle_root([coinbase.txid()])
        invalid = Block(mine_header(replace(valid.header, merkle_root=root)), (coinbase,))
        reader, writer = await self.raw_peer(target)
        await self.next_command(reader, 'getheaders')
        before = target.chain.info()
        await write_frame(writer, 'headers', encode_headers((invalid.header,)), 2)
        request = await self.next_command(reader, 'getdata')
        self.assertEqual(decode_inventory(request.payload), (Inventory(INV_BLOCK, invalid.block_hash()),))
        self.assertEqual(before, target.chain.info())
        await write_frame(writer, 'block', invalid.serialize(), 2)
        await asyncio.wait_for(reader.read(), 2)
        await eventually(lambda: target.info()['sessions'] == 0)
        self.assertEqual(before, target.chain.info())
        self.assertFalse(target.chain.has_block(invalid.block_hash()))
        self.assertEqual(target.info()['stats']['validation_rejections'], 1)
        self.assertTrue(target.running)

    async def test_invalid_header_is_rejected_before_block_request(self):
        target = self.node()
        await target.start()
        header = replace(target.chain.make_block(ALICE.script_pubkey).header, bits=0)
        reader, writer = await self.raw_peer(target)
        await self.next_command(reader, 'getheaders')
        await write_frame(writer, 'headers', encode_headers((header,)), 2)
        await asyncio.wait_for(reader.read(), 2)
        await eventually(lambda: target.info()['sessions'] == 0)
        self.assertEqual(target.info()['height'], 0)
        self.assertEqual(target.info()['stats']['blocks_received'], 0)
        self.assertEqual(target.info()['stats']['protocol_errors'], 1)

    async def test_unsupported_transaction_can_be_retried_without_invalid_cache(self):
        target = self.node(seeded=True)
        await target.start()
        transaction = self.spend()
        txin = transaction.inputs[0]
        unsupported = replace(transaction, inputs=(replace(txin, witness=(txin.witness[0][:-1] + b'\x02', txin.witness[1])),))
        reader, writer = await self.raw_peer(target)
        await self.next_command(reader, 'getheaders')
        await write_frame(writer, 'headers', encode_headers(()), 2)
        for wanted_count in (1, 2):
            await write_frame(writer, 'inv', encode_inventory((Inventory(INV_TRANSACTION, unsupported.txid()),)), 2)
            request = await self.next_command(reader, 'getdata')
            self.assertEqual(decode_inventory(request.payload), (Inventory(INV_TRANSACTION, unsupported.txid()),))
            await write_frame(writer, 'tx', unsupported.serialize(), 2)
            await eventually(lambda: target.info()['stats']['unsupported_features'] == wanted_count)
        self.assertFalse(target.chain.has_mempool_transaction(unsupported.txid()))
        self.assertEqual(target.info()['peers'], 1)
        self.assertEqual(target.info()['stats']['validation_rejections'], 0)

    async def test_peer_limit_and_stop_clean_pending_handshake_tasks(self):
        target = self.node(max_peers=1)
        await target.start()
        first_reader, first_writer = await asyncio.open_connection(*target.address)
        self.writers.append(first_writer)
        self.assertEqual((await read_frame(first_reader, 2)).command, 'version')
        second_reader, second_writer = await asyncio.open_connection(*target.address)
        self.writers.append(second_writer)
        self.assertEqual(await asyncio.wait_for(second_reader.read(), 2), b'')
        self.assertEqual(target.info()['sessions'], 1)
        self.assertEqual(target.info()['stats']['peer_limit_rejections'], 1)
        started = asyncio.get_running_loop().time()
        await target.stop()
        await target.stop()
        self.assertLess(asyncio.get_running_loop().time() - started, 4.5)
        self.assertEqual(target.info()['sessions'], 0)
        self.assertEqual(target.info()['peer_tasks'], 0)
        live = [task for task in asyncio.all_tasks() if task is not asyncio.current_task()
                and task.get_name().startswith('sumuww-peer:') and not task.done()]
        self.assertEqual(live, [])

    async def test_start_failure_and_stop_before_start_are_safe(self):
        first = self.node()
        await first.start()
        conflicting = self.node(host=first.address[0], port=first.address[1])
        with self.assertRaises(OSError):
            await conflicting.start()
        await conflicting.stop()
        self.assertFalse(conflicting.running)
        never_started = self.node()
        await never_started.stop()
        await never_started.stop()
        self.assertFalse(never_started.info()['running'])

    async def test_numeric_loopback_parameter_boundaries(self):
        database = Path(self.directory.name) / 'forbidden.sqlite'
        for host in ('0.0.0.0', '192.0.2.1', 'localhost', 'fe80::1', '::ffff:127.0.0.1', '127.1', ''):
            with self.subTest(host=host), self.assertRaises(ValueError):
                PeerNode(database, host=host)
        for peers in ((('localhost', 1234),), (('127.0.0.1', 0),), (('127.0.0.1', True),)):
            with self.subTest(peers=peers), self.assertRaises(ValueError):
                PeerNode(database, peers=peers)
        for options in ({'max_peers': 0}, {'timeout': float('inf')}, {'timeout': 10 ** 1000}, {'poll_interval': 0}):
            with self.subTest(options=options), self.assertRaises(ValueError):
                PeerNode(database, **options)
        self.assertFalse(database.exists())

    async def test_serves_canonical_requested_block_and_witness_transaction(self):
        source = self.node(seeded=True)
        transaction = self.spend()
        source.chain.submit_transaction(transaction)
        await source.start()
        reader, writer = await self.raw_peer(source)
        await self.next_command(reader, 'getheaders')
        await write_frame(writer, 'headers', encode_headers(()), 2)
        block = source.chain.get_block(source.chain.tip_hash)
        await write_frame(writer, 'getdata', encode_inventory((Inventory(INV_BLOCK, block.block_hash()),)), 2)
        self.assertEqual((await self.next_command(reader, 'block')).payload, block.serialize())
        await write_frame(writer, 'getdata', encode_inventory((Inventory(INV_TRANSACTION, transaction.txid()),)), 2)
        self.assertEqual((await self.next_command(reader, 'tx')).payload, transaction.serialize())
        missing = Inventory(INV_BLOCK, b'?' * 32)
        await write_frame(writer, 'getdata', encode_inventory((missing,)), 2)
        self.assertEqual(decode_inventory((await self.next_command(reader, 'notfound')).payload), (missing,))

    async def test_inventory_burst_does_not_exceed_pending_transaction_cap(self):
        target = self.node()
        await target.start()
        reader, writer = await self.raw_peer(target)
        await self.next_command(reader, 'getheaders')
        await write_frame(writer, 'headers', encode_headers(()), 2)
        first = tuple(Inventory(INV_TRANSACTION, number.to_bytes(32, 'little')) for number in range(1, 257))
        second = tuple(Inventory(INV_TRANSACTION, number.to_bytes(32, 'little')) for number in range(257, 513))
        await write_frame(writer, 'inv', encode_inventory(first), 2)
        self.assertEqual(decode_inventory((await self.next_command(reader, 'getdata')).payload), first)
        received_before = target.info()['stats']['frames_received']
        await write_frame(writer, 'inv', encode_inventory(second), 2)
        await eventually(lambda: target.info()['stats']['frames_received'] > received_before)
        self.assertEqual(sum(len(session.tx_requests) for session in target._sessions.values()), 256)
        self.assertEqual(target.info()['mempool'], 0)

    async def test_clean_eof_counts_disconnect_and_concurrent_stop_is_safe(self):
        source, follower = self.node(), self.node()
        await source.start()
        await follower.start()
        await follower.connect(*source.address)
        await eventually(lambda: source.info()['peers'] == 1)
        await asyncio.gather(source.stop(), source.stop())
        await eventually(lambda: follower.info()['stats']['disconnects'] >= 1)
        self.assertEqual(follower.info()['stats']['protocol_errors'], 0)
        self.assertEqual(source.info()['peer_tasks'], 0)


if __name__ == '__main__':
    unittest.main()
