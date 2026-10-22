"""Mined laboratory-chain tests; independent from the 2016-block design vectors."""

from dataclasses import replace
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest

from sumuww.block import Block, GENESIS_TIME, REGTEST_BITS, genesis_block, mine_header
from sumuww.chain import Chain
from sumuww.errors import StorageError, ValidationError
from sumuww.primitives import block_work, check_pow
from sumuww.profiles import REGTEST, RETARGET_LAB
from sumuww.wallet import RegtestKey

WORK = Path(os.environ.get('SUMUWW_TEST_WORKDIR', tempfile.gettempdir()))
ALICE = RegtestKey.from_int(1)
BOB = RegtestKey.from_int(2)


class RetargetChainTests(unittest.TestCase):
    def setUp(self):
        WORK.mkdir(parents=True, exist_ok=True)
        self.directory = tempfile.TemporaryDirectory(prefix='retarget-chain-', dir=WORK)
        self.addCleanup(self.directory.cleanup)
        self.database = Path(self.directory.name) / 'lab.sqlite'
        self.chain = Chain(self.database, network=RETARGET_LAB, clock=lambda: GENESIS_TIME + 1000)
        self.addCleanup(self.close_chain)

    def close_chain(self):
        if self.chain is not None:
            self.chain.close()
            self.chain = None

    def extend(self, final_height, *, parent_hash=None, first_height=None,
               time_for=None, pay_script=None):
        parent = self.chain.tip_hash if parent_hash is None else parent_hash
        height = self.chain._row(parent)[2] + 1 if first_height is None else first_height
        result = []
        for current in range(height, final_height + 1):
            timestamp = GENESIS_TIME + current if time_for is None else time_for(current)
            block = self.chain.make_block(pay_script or ALICE.script_pubkey,
                                          parent_hash=parent, timestamp=timestamp)
            self.chain.accept_block(block)
            parent = block.block_hash()
            result.append(block)
        return result

    def test_first_and_second_adjustments_are_mined_and_validated(self):
        blocks = self.extend(15)
        self.assertEqual(blocks[-1].header.bits, 0x2000FFFF)
        self.assertEqual(self.chain.expected_bits(), 0x2000EFFF)
        self.assertEqual(self.chain.info()['next_bits'], '2000efff')
        block16 = self.extend(16)[0]
        self.assertEqual(block16.header.bits, 0x2000EFFF)
        self.extend(31)
        self.assertEqual(self.chain.expected_bits(), 0x2000E0FF)
        block32 = self.extend(32)[0]
        self.assertEqual(block32.header.bits, 0x2000E0FF)
        self.assertTrue(check_pow(block32.block_hash(), block32.header.bits, RETARGET_LAB.pow_limit))
        self.assertEqual(self.chain.info()['bits'], '2000e0ff')
        self.assertTrue(self.chain.verify_persisted_state())

    def test_nonboundary_old_bits_continue(self):
        blocks = self.extend(17)
        self.assertEqual(blocks[14].header.bits, 0x2000FFFF)
        self.assertEqual(blocks[15].header.bits, 0x2000EFFF)
        self.assertEqual(blocks[16].header.bits, 0x2000EFFF)

    def test_wrong_boundary_bits_with_real_valid_pow_are_rejected_atomically(self):
        self.extend(15)
        valid = self.chain.make_block(ALICE.script_pubkey, timestamp=GENESIS_TIME + 16)
        wrong = Block(mine_header(replace(valid.header, bits=0x2000FFFF),
                                  pow_limit=RETARGET_LAB.pow_limit), valid.transactions)
        self.assertTrue(check_pow(wrong.block_hash(), wrong.header.bits, RETARGET_LAB.pow_limit))
        before = self.chain.info()
        with self.assertRaisesRegex(ValidationError, 'contextual nBits'):
            self.chain.accept_block(wrong)
        self.assertEqual(self.chain.info(), before)
        self.assertFalse(self.chain.has_block(wrong.block_hash()))

    def test_wrong_nonboundary_bits_are_rejected(self):
        self.extend(16)
        valid = self.chain.make_block(ALICE.script_pubkey, timestamp=GENESIS_TIME + 17)
        wrong = Block(mine_header(replace(valid.header, bits=0x2000E0FF),
                                  pow_limit=RETARGET_LAB.pow_limit), valid.transactions)
        before = self.chain.info()
        with self.assertRaises(ValidationError):
            self.chain.accept_block(wrong)
        self.assertEqual(self.chain.info(), before)

    def test_same_height_sidebranches_use_their_own_period_start(self):
        common = self.extend(15)[-1].block_hash()
        branch_a = self.extend(31, parent_hash=common,
                               time_for=lambda h: GENESIS_TIME + 16 + (h - 16) * 31 // 15)
        branch_b = self.extend(31, parent_hash=common, pay_script=BOB.script_pubkey,
                               time_for=lambda h: GENESIS_TIME + 32 + (h - 16))
        tip_a, tip_b = branch_a[-1], branch_b[-1]
        self.assertEqual(tip_a.header.timestamp, tip_b.header.timestamp)
        self.assertEqual(self.chain.expected_bits(tip_a.block_hash()), 0x2000FFFF)
        self.assertEqual(self.chain.expected_bits(tip_b.block_hash()), 0x2000E0FF)
        block_a = self.chain.make_block(ALICE.script_pubkey, parent_hash=tip_a.block_hash(),
                                        timestamp=GENESIS_TIME + 48)
        block_b = self.chain.make_block(BOB.script_pubkey, parent_hash=tip_b.block_hash(),
                                        timestamp=GENESIS_TIME + 48)
        self.assertEqual(block_a.header.bits, 0x2000FFFF)
        self.assertEqual(block_b.header.bits, 0x2000E0FF)
        self.assertTrue(self.chain.accept_block(block_a))
        work_a = int(self.chain.info()['chainwork'])
        self.assertTrue(self.chain.accept_block(block_b))
        self.assertEqual(self.chain.tip_hash, block_b.block_hash())
        self.assertEqual(self.chain.info()['height'], 32)
        self.assertGreater(int(self.chain.info()['chainwork']), work_a)
        self.assertGreater(self.chain.balance(BOB.script_pubkey), 0)
        self.assertTrue(self.chain.verify_persisted_state())

    def test_shorter_harder_branch_wins_by_cumulative_work(self):
        self.extend(20, time_for=lambda h: GENESIS_TIME + 2 * h)
        longer_tip = self.chain.tip_hash
        longer_work = int(self.chain.info()['chainwork'])
        parent = RETARGET_LAB.genesis.block_hash()
        for height in range(1, 18):
            timestamp = self.chain._mtp(self.chain._path(parent)) + 1
            block = self.chain.make_block(BOB.script_pubkey, parent_hash=parent, timestamp=timestamp)
            self.chain.accept_block(block)
            parent = block.block_hash()
        self.assertNotEqual(parent, longer_tip)
        self.assertEqual(self.chain.tip_hash, parent)
        self.assertEqual(self.chain.info()['height'], 17)
        self.assertGreater(int(self.chain.info()['chainwork']), longer_work)
        self.assertTrue(self.chain.verify_persisted_state())

    def test_chainwork_sum_and_restart_replay_use_selected_pow_limit(self):
        blocks = self.extend(34)
        expected_work = sum(block_work(block.header.bits, RETARGET_LAB.pow_limit)
                            for block in [RETARGET_LAB.genesis] + blocks)
        before = self.chain.info()
        self.assertEqual(int(before['chainwork']), expected_work)
        self.close_chain()
        self.chain = Chain(self.database, network='retarget-lab', clock=lambda: GENESIS_TIME + 1000)
        self.assertEqual(self.chain.info(), before)
        self.assertEqual(self.chain.expected_bits(), 0x2000E0FF)
        self.assertEqual(self.chain.list_utxos().__len__(), 34)
        self.assertFalse(any(outpoint[0] == RETARGET_LAB.genesis.transactions[0].txid()
                             for outpoint, _ in self.chain.list_utxos()))

    def test_unknown_parent_and_bad_hash_queries_are_rejected(self):
        for digest in (b'', bytes(31), bytearray(32), '00' * 32):
            with self.subTest(type=type(digest).__name__), self.assertRaises(ValidationError):
                self.chain.expected_bits(digest)
        with self.assertRaises(ValidationError):
            self.chain.expected_bits(bytes(32))

    def test_invalid_network_is_rejected_before_file_creation(self):
        destination = Path(self.directory.name) / 'not-created' / 'db.sqlite'
        with self.assertRaises(ValueError):
            Chain(destination, network='mainnet')
        self.assertFalse(destination.parent.exists())

    def test_cross_network_database_is_rejected_without_mutating_closed_files(self):
        self.extend(2)
        self.close_chain()
        # DELETE journal mode proves a mismatched opener cannot first change it
        # to WAL through the normal writable startup pragmas.
        connection = sqlite3.connect(self.database)
        self.assertEqual(connection.execute('PRAGMA journal_mode=DELETE').fetchone()[0], 'delete')
        connection.close()
        before = {path.name: path.read_bytes() for path in Path(self.directory.name).iterdir()}
        with self.assertRaisesRegex(StorageError, 'network/profile/schema'):
            Chain(self.database, network='regtest')
        after = {path.name: path.read_bytes() for path in Path(self.directory.name).iterdir()}
        self.assertEqual(after, before)
        with Chain(self.database, network='retarget-lab', clock=lambda: GENESIS_TIME + 1000) as reopened:
            self.assertEqual(reopened.info()['height'], 2)

    def test_default_regtest_is_preserved_and_rejects_laboratory_database(self):
        other = Path(self.directory.name) / 'regtest.sqlite'
        with Chain(other, clock=lambda: GENESIS_TIME + 1000) as chain:
            self.assertIs(chain.network, REGTEST)
            self.assertEqual(chain.tip_hash, genesis_block().block_hash())
            chain.mine(ALICE.script_pubkey, 17)
            self.assertEqual(chain.expected_bits(), REGTEST_BITS)
            self.assertEqual(chain.info()['bits'], '207fffff')
            self.assertTrue(chain.info()['no_retarget'])
        before = other.read_bytes()
        with self.assertRaises(StorageError):
            Chain(other, network=RETARGET_LAB)
        self.assertEqual(other.read_bytes(), before)

    def test_empty_network_metadata_is_rejected_before_journal_changes(self):
        self.close_chain()
        connection = sqlite3.connect(self.database)
        connection.execute('DELETE FROM metadata')
        connection.commit()
        connection.execute('PRAGMA journal_mode=DELETE')
        connection.close()
        before = {path.name: path.read_bytes() for path in Path(self.directory.name).iterdir()}
        with self.assertRaisesRegex(StorageError, 'network/profile/schema'):
            Chain(self.database, network='regtest')
        after = {path.name: path.read_bytes() for path in Path(self.directory.name).iterdir()}
        self.assertEqual(after, before)
        connection = sqlite3.connect(self.database)
        self.assertEqual(connection.execute('PRAGMA journal_mode').fetchone()[0], 'delete')
        connection.close()

    def test_database_without_metadata_accepts_only_an_empty_sqlite_file(self):
        self.close_chain()
        # Existing SUMUWW tables and an unrelated application's table both require
        # identity metadata. Refusal must preserve even a DELETE journal mode.
        for name in ('orphaned-sumuww', 'foreign'):
            database = Path(self.directory.name) / (name + '.sqlite')
            connection = sqlite3.connect(database)
            connection.execute('CREATE TABLE ' + ('blocks' if name == 'orphaned-sumuww' else 'foreign_data') + ' (data TEXT)')
            connection.commit()
            connection.close()
            before = database.read_bytes()
            with self.subTest(name=name), self.assertRaisesRegex(StorageError, 'lacks network metadata'):
                Chain(database, network='retarget-lab')
            self.assertEqual(database.read_bytes(), before)
            self.assertFalse(Path(str(database) + '-wal').exists())
            self.assertFalse(Path(str(database) + '-shm').exists())
        blank = Path(self.directory.name) / 'blank.sqlite'
        connection = sqlite3.connect(blank)
        # Materialize a valid, empty SQLite header without user tables.
        connection.execute('VACUUM')
        connection.close()
        with Chain(blank, network='retarget-lab') as initialized:
            self.assertEqual(initialized.tip_hash, RETARGET_LAB.genesis.block_hash())
            self.assertEqual(initialized.info()['height'], 0)


if __name__ == '__main__':
    unittest.main()
