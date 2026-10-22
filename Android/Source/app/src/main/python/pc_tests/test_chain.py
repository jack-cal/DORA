"""Integration checks for the deliberately limited single-host regtest profile.

All databases and process-crash fixtures live in temporary directories. Set
SUMUWW_TEST_WORKDIR to select their parent; otherwise the OS temporary directory
is used. The keys are public test fixtures, never custody credentials.
"""

from dataclasses import replace
from contextlib import closing
from pathlib import Path
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest

from sumuww.block import Block, GENESIS_TIME, REGTEST_BITS, build_coinbase, genesis_block, mine_header
from sumuww.chain import Chain
from sumuww.errors import InvalidTransaction, StorageError, UnsupportedFeature, ValidationError
from sumuww.primitives import COIN, REGTEST_POW_LIMIT, check_pow, hash_to_display, merkle_root
from sumuww.transaction import Transaction, TxInput, TxOutput
from sumuww.wallet import RegtestKey, sign_p2wpkh


WORK = Path(os.environ.get('SUMUWW_TEST_WORKDIR', tempfile.gettempdir()))
NOW = GENESIS_TIME + 1000
ALICE = RegtestKey.from_int(1)
BOB = RegtestKey.from_int(2)
MINER = RegtestKey.from_int(3)


def changed_block(block, *, transactions=None, header=None):
    txs = block.transactions if transactions is None else tuple(transactions)
    h = block.header if header is None else header
    root, _ = merkle_root([tx.txid() for tx in txs])
    return Block(mine_header(replace(h, merkle_root=root)), txs)


class ChainIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        WORK.mkdir(exist_ok=True)
        cls.seed_dir = tempfile.TemporaryDirectory(prefix='chain-seed-', dir=WORK)
        cls.seed = Path(cls.seed_dir.name) / 'seed.sqlite'
        with Chain(cls.seed, clock=lambda: NOW) as chain:
            cls.seed_blocks = chain.mine(ALICE.script_pubkey, 100)
            cls.first = cls.seed_blocks[0].transactions[0]
            cls.seed_info = chain.info()
            chain.connection.execute('PRAGMA wal_checkpoint(TRUNCATE)')

    @classmethod
    def tearDownClass(cls):
        cls.seed_dir.cleanup()

    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory(prefix='chain-case-', dir=WORK)
        self.addCleanup(self.scratch.cleanup)
        self.database = Path(self.scratch.name) / 'chain.sqlite'
        shutil.copy2(self.seed, self.database)
        self.now = NOW
        self.chain = Chain(self.database, clock=lambda: self.now)
        self.addCleanup(self.close_chain)

    def close_chain(self):
        if self.chain is not None:
            self.chain.close()
            self.chain = None

    def spend(self, *, sequence=0xFFFFFFFF, lock_time=0, version=2,
              outputs=None, key=ALICE, previous=None):
        previous = self.first if previous is None else previous
        outputs = outputs or (TxOutput(3 * COIN, BOB.script_pubkey),
                              TxOutput(47 * COIN - 100_000, ALICE.script_pubkey))
        tx = Transaction(version, (TxInput(previous.txid(), 0, sequence=sequence),),
                         tuple(outputs), lock_time)
        return sign_p2wpkh(tx, 0, previous.outputs[0], key)

    def assert_rejected_without_state_change(self, action, error=ValidationError):
        before = self.chain.info()
        with self.assertRaises(error):
            action()
        self.assertEqual(before, self.chain.info())

    def test_distinct_genesis_is_excluded_from_utxo(self):
        genesis = genesis_block()
        self.assertNotEqual(hash_to_display(genesis.block_hash()),
                            '000000000019d6689c085ae165831e934ff763ae46a2a6c172b3f1b60a8ce26f')
        self.assertFalse(any(key[0] == genesis.transactions[0].txid()
                             for key, _ in self.chain.list_utxos()))
        self.assertEqual(100 * 50 * COIN, self.chain.balance(ALICE.script_pubkey))
        with Chain(Path(self.scratch.name) / 'fresh.sqlite', clock=lambda: NOW) as fresh:
            self.assertEqual(0, fresh.info()['height'])
            self.assertEqual([], fresh.list_utxos())

    def test_coinbase_maturity_boundary(self):
        tx = self.spend()
        height_99 = self.seed_blocks[98].block_hash()
        self.assert_rejected_without_state_change(
            lambda: self.chain.make_block(MINER.script_pubkey, (tx,), parent_hash=height_99),
            InvalidTransaction)
        self.assertEqual(50 * COIN, self.chain.balance(ALICE.script_pubkey, mature_only=True))
        self.chain.submit_transaction(tx)  # Candidate height 101: 101 - 1 == 100.
        self.chain.mine(MINER.script_pubkey)
        self.assertEqual(3 * COIN, self.chain.balance(BOB.script_pubkey))

    def test_signed_transfer_fee_change_and_restart(self):
        tx = self.spend()
        self.chain.submit_transaction(tx)
        mined = self.chain.mine(MINER.script_pubkey)[0]
        self.assertEqual(tx.txid(), mined.transactions[1].txid())
        self.assertEqual(50 * COIN + 100_000, mined.transactions[0].outputs[0].value)
        self.assertEqual(3 * COIN, self.chain.balance(BOB.script_pubkey))
        self.assertEqual(5000 * COIN - 3 * COIN - 100_000,
                         self.chain.balance(ALICE.script_pubkey))
        self.assertEqual(0, self.chain.info()['mempool'])
        expected = self.chain.info()
        self.close_chain()
        self.chain = Chain(self.database, clock=lambda: self.now)
        self.assertEqual(expected, self.chain.info())

    def test_mempool_duplicate_and_conflicting_spend(self):
        tx = self.spend()
        self.chain.submit_transaction(tx)
        self.assert_rejected_without_state_change(lambda: self.chain.submit_transaction(tx), InvalidTransaction)
        conflict = self.spend(outputs=(TxOutput(49 * COIN, BOB.script_pubkey),))
        self.assert_rejected_without_state_change(lambda: self.chain.submit_transaction(conflict), InvalidTransaction)
        self.chain.mine(MINER.script_pubkey)
        self.assert_rejected_without_state_change(lambda: self.chain.submit_transaction(conflict), InvalidTransaction)

    def test_duplicate_input_is_rejected(self):
        tx = self.spend()
        duplicate = replace(tx, inputs=(tx.inputs[0], tx.inputs[0]))
        self.assert_rejected_without_state_change(lambda: self.chain.submit_transaction(duplicate), InvalidTransaction)

    def test_missing_input_is_rejected(self):
        tx = self.spend()
        missing = replace(tx, inputs=(replace(tx.inputs[0], prev_txid=b'\x55' * 32),))
        self.assert_rejected_without_state_change(lambda: self.chain.submit_transaction(missing), InvalidTransaction)

    def test_signature_does_not_authorize_output_mutation(self):
        tx = self.spend()
        forged = replace(tx, outputs=(TxOutput(3 * COIN + 1, BOB.script_pubkey),) + tx.outputs[1:])
        self.assert_rejected_without_state_change(lambda: self.chain.submit_transaction(forged), InvalidTransaction)

    def test_transaction_cannot_create_value(self):
        tx = self.spend(outputs=(TxOutput(50 * COIN + 1, BOB.script_pubkey),))
        self.assert_rejected_without_state_change(lambda: self.chain.submit_transaction(tx), InvalidTransaction)

    def test_native_witness_scriptsig_must_be_empty(self):
        tx = self.spend()
        invalid = replace(tx, inputs=(replace(tx.inputs[0], script_sig=b'\x00'),))
        self.assert_rejected_without_state_change(lambda: self.chain.submit_transaction(invalid), InvalidTransaction)

    def test_unsupported_sighash_is_a_separate_error(self):
        tx = self.spend()
        signature, pubkey = tx.inputs[0].witness
        unsupported = replace(tx, inputs=(replace(tx.inputs[0], witness=(signature[:-1] + b'\x02', pubkey)),))
        self.assertFalse(issubclass(UnsupportedFeature, ValidationError))
        self.assert_rejected_without_state_change(lambda: self.chain.submit_transaction(unsupported), UnsupportedFeature)
        self.chain.submit_transaction(tx)

    def test_unsupported_script_is_a_separate_error(self):
        funding = self.spend(outputs=(TxOutput(49 * COIN, b'\x51'),))
        self.chain.submit_transaction(funding)
        self.chain.mine(MINER.script_pubkey)
        tx = Transaction(2, (TxInput(funding.txid(), 0),), (TxOutput(48 * COIN, BOB.script_pubkey),))
        self.assert_rejected_without_state_change(lambda: self.chain.submit_transaction(tx), UnsupportedFeature)

    def test_witness_commitment_required(self):
        valid = self.chain.make_block(MINER.script_pubkey, (self.spend(),))
        cb = valid.transactions[0]
        cb = replace(cb, inputs=(replace(cb.inputs[0], witness=()),), outputs=cb.outputs[:1])
        missing = changed_block(valid, transactions=(cb,) + valid.transactions[1:])
        self.assert_rejected_without_state_change(lambda: self.chain.accept_block(missing))

    def test_wrong_witness_same_header_is_not_cached_as_invalid(self):
        valid = self.chain.make_block(MINER.script_pubkey, (self.spend(),))
        cb = valid.transactions[0]
        cb = replace(cb, inputs=(replace(cb.inputs[0], witness=(b'\x01' * 32,)),))
        wrong = Block(valid.header, (cb,) + valid.transactions[1:])
        self.assertEqual(wrong.block_hash(), valid.block_hash())
        self.assert_rejected_without_state_change(lambda: self.chain.accept_block(wrong))
        self.assertTrue(self.chain.accept_block(valid))

    def test_last_matching_witness_commitment_wins(self):
        valid = self.chain.make_block(MINER.script_pubkey, (self.spend(),))
        cb = valid.transactions[0]
        fake = TxOutput(0, b'\x6a\x24\xaa\x21\xa9\xed' + b'\x77' * 32)
        wrong_cb = replace(cb, outputs=cb.outputs + (fake,))
        wrong = changed_block(valid, transactions=(wrong_cb,) + valid.transactions[1:])
        self.assert_rejected_without_state_change(lambda: self.chain.accept_block(wrong))
        okay_cb = replace(cb, outputs=(cb.outputs[0], fake, cb.outputs[1]))
        okay = changed_block(valid, transactions=(okay_cb,) + valid.transactions[1:])
        self.assertTrue(self.chain.accept_block(okay))

    def test_coinbase_overclaim_is_rejected(self):
        valid = self.chain.make_block(MINER.script_pubkey)
        cb = valid.transactions[0]
        cb = replace(cb, outputs=(replace(cb.outputs[0], value=cb.outputs[0].value + 1),))
        invalid = changed_block(valid, transactions=(cb,))
        self.assert_rejected_without_state_change(lambda: self.chain.accept_block(invalid))

    def test_coinbase_height_commitment_is_required(self):
        valid = self.chain.make_block(MINER.script_pubkey)
        cb = build_coinbase(102, MINER.script_pubkey)
        invalid = changed_block(valid, transactions=(cb,))
        self.assert_rejected_without_state_change(lambda: self.chain.accept_block(invalid))

    def test_coinbase_nonfinal_locktime_is_rejected(self):
        valid = self.chain.make_block(MINER.script_pubkey)
        cb = valid.transactions[0]
        cb = replace(cb, inputs=(replace(cb.inputs[0], sequence=0),), lock_time=102)
        nonfinal = changed_block(valid, transactions=(cb,))
        self.assert_rejected_without_state_change(lambda: self.chain.accept_block(nonfinal))

    def test_coinbase_underclaim_and_op_return_burn_are_allowed(self):
        valid = self.chain.make_block(MINER.script_pubkey)
        cb = replace(valid.transactions[0], outputs=(TxOutput(49 * COIN, MINER.script_pubkey),
                                                   TxOutput(COIN, b'\x6a\x01x')))
        burned = changed_block(valid, transactions=(cb,))
        self.assertTrue(self.chain.accept_block(burned))
        self.assertEqual(49 * COIN, self.chain.balance(MINER.script_pubkey))
        next_block = self.chain.make_block(MINER.script_pubkey)
        cb = replace(next_block.transactions[0], outputs=(TxOutput(0, b'\x6a'),))
        self.assertTrue(self.chain.accept_block(changed_block(next_block, transactions=(cb,))))
        self.assertEqual(49 * COIN, self.chain.balance(MINER.script_pubkey))

    def test_wrong_bits_is_rejected_even_with_valid_pow(self):
        valid = self.chain.make_block(MINER.script_pubkey)
        invalid = changed_block(valid, header=replace(valid.header, bits=REGTEST_BITS - 1))
        self.assertTrue(check_pow(invalid.block_hash(), invalid.header.bits, REGTEST_POW_LIMIT))
        self.assert_rejected_without_state_change(lambda: self.chain.accept_block(invalid))

    def test_invalid_pow_is_rejected(self):
        valid = self.chain.make_block(MINER.script_pubkey)
        bad_header = next(replace(valid.header, nonce=nonce) for nonce in range(1000)
                          if not check_pow(replace(valid.header, nonce=nonce).digest(), REGTEST_BITS, REGTEST_POW_LIMIT))
        self.assert_rejected_without_state_change(lambda: self.chain.accept_block(Block(bad_header, valid.transactions)))

    def test_median_time_past_is_strict(self):
        mtp = self.chain._mtp(self.chain._path(self.chain.tip_hash))
        valid = self.chain.make_block(MINER.script_pubkey, timestamp=mtp)
        self.assert_rejected_without_state_change(lambda: self.chain.accept_block(valid))
        okay = self.chain.make_block(MINER.script_pubkey, timestamp=mtp + 1)
        self.assertTrue(self.chain.accept_block(okay))

    def test_future_timestamp_can_be_retried(self):
        future = self.chain.make_block(MINER.script_pubkey, timestamp=self.now + 7201)
        self.assert_rejected_without_state_change(lambda: self.chain.accept_block(future))
        self.now += 1
        self.assertTrue(self.chain.accept_block(future))

    def test_modern_header_version_required(self):
        valid = self.chain.make_block(MINER.script_pubkey)
        invalid = changed_block(valid, header=replace(valid.header, version=3))
        self.assert_rejected_without_state_change(lambda: self.chain.accept_block(invalid))

    def test_absolute_height_lock_and_final_sequence_override(self):
        locked = self.spend(sequence=0xFFFFFFFE, lock_time=101)
        self.assert_rejected_without_state_change(lambda: self.chain.submit_transaction(locked), InvalidTransaction)
        final_sequence = self.spend(lock_time=101)
        self.chain.submit_transaction(final_sequence)
        self.chain.mine(MINER.script_pubkey)
        self.assertEqual(3 * COIN, self.chain.balance(BOB.script_pubkey))

    def test_absolute_height_lock_becomes_final_next_height(self):
        locked = self.spend(sequence=0xFFFFFFFE, lock_time=101)
        self.assert_rejected_without_state_change(lambda: self.chain.submit_transaction(locked), InvalidTransaction)
        self.chain.mine(MINER.script_pubkey)
        self.chain.submit_transaction(locked)

    def test_relative_height_lock_boundary(self):
        locked = self.spend(sequence=101)
        self.assert_rejected_without_state_change(lambda: self.chain.submit_transaction(locked), InvalidTransaction)
        self.chain.mine(MINER.script_pubkey)
        self.chain.submit_transaction(locked)

    def test_relative_time_lock_and_version_one_exemption(self):
        locked = self.spend(sequence=(1 << 22) | 3)
        self.assert_rejected_without_state_change(lambda: self.chain.submit_transaction(locked), InvalidTransaction)
        unlocked = self.spend(sequence=(1 << 22) | 2)
        self.chain.submit_transaction(unlocked)
        self.chain.mine(MINER.script_pubkey)
        # A different matured coin permits checking pre-v2 sequence semantics.
        old_version = self.spend(sequence=0xFFFF, version=1, previous=self.seed_blocks[1].transactions[0])
        self.chain.submit_transaction(old_version)

    def test_side_branch_tie_then_reorganization_returns_transaction(self):
        anchor = self.chain.tip_hash
        tx = self.spend()
        self.chain.submit_transaction(tx)
        main = self.chain.mine(MINER.script_pubkey)[0]
        side = self.chain.make_block(ALICE.script_pubkey, (), parent_hash=anchor, extra_nonce=9)
        self.assertFalse(self.chain.accept_block(side))
        self.assertEqual(main.block_hash(), self.chain.tip_hash)
        self.assertEqual(3 * COIN, self.chain.balance(BOB.script_pubkey))
        side_next = self.chain.make_block(ALICE.script_pubkey, (), parent_hash=side.block_hash(), extra_nonce=9)
        self.assertTrue(self.chain.accept_block(side_next))
        self.assertEqual(side_next.block_hash(), self.chain.tip_hash)
        self.assertEqual(0, self.chain.balance(BOB.script_pubkey))
        self.assertEqual((tx.txid(),), tuple(t.txid() for t in self.chain.mempool_transactions()))
        self.chain.mine(MINER.script_pubkey)
        self.assertEqual(3 * COIN, self.chain.balance(BOB.script_pubkey))
        expected = self.chain.info()
        self.close_chain()
        self.chain = Chain(self.database, clock=lambda: self.now)
        self.assertEqual(expected, self.chain.info())

    def test_invalid_side_branch_cannot_affect_tip(self):
        self.chain.mine(MINER.script_pubkey)
        side = self.chain.make_block(ALICE.script_pubkey, (), parent_hash=self.seed_blocks[-1].block_hash(), extra_nonce=9)
        cb = side.transactions[0]
        cb = replace(cb, outputs=(replace(cb.outputs[0], value=cb.outputs[0].value + 1),))
        invalid = changed_block(side, transactions=(cb,))
        self.assert_rejected_without_state_change(lambda: self.chain.accept_block(invalid))

    def test_mempool_parent_and_child_can_be_mined_in_one_block(self):
        parent = self.spend()
        child = self.spend(previous=parent, key=BOB,
                           outputs=(TxOutput(2 * COIN, ALICE.script_pubkey),))
        self.chain.submit_transaction(parent)
        self.chain.submit_transaction(child)
        mined = self.chain.mine(MINER.script_pubkey)[0]
        self.assertEqual((parent.txid(), child.txid()),
                         tuple(tx.txid() for tx in mined.transactions[1:]))
        self.assertEqual(0, self.chain.balance(BOB.script_pubkey))
        self.assertEqual(51 * COIN + 100_000, mined.transactions[0].outputs[0].value)
        self.assertEqual(0, self.chain.info()['mempool'])

    def test_child_before_parent_reorg_mempool_dependency_recovery(self):
        anchor = self.chain.tip_hash
        parent = self.spend()
        self.chain.submit_transaction(parent)
        self.chain.mine(MINER.script_pubkey)
        child = self.spend(previous=parent, key=BOB,
                           outputs=(TxOutput(2 * COIN, ALICE.script_pubkey),))
        self.chain.submit_transaction(child)
        # Existing child is considered before its disconnected parent during
        # pool rebuild. Recovery must revisit it after the parent is admitted.
        side = self.chain.make_block(ALICE.script_pubkey, (), parent_hash=anchor, extra_nonce=17)
        self.assertFalse(self.chain.accept_block(side))
        side_next = self.chain.make_block(ALICE.script_pubkey, (), parent_hash=side.block_hash(), extra_nonce=17)
        self.assertTrue(self.chain.accept_block(side_next))
        self.assertEqual((parent.txid(), child.txid()),
                         tuple(tx.txid() for tx in self.chain.mempool_transactions()))
        mined = self.chain.mine(MINER.script_pubkey)[0]
        self.assertEqual((parent.txid(), child.txid()),
                         tuple(tx.txid() for tx in mined.transactions[1:]))

    def test_valid_mempool_persists_across_restart(self):
        parent = self.spend()
        child = self.spend(previous=parent, key=BOB,
                           outputs=(TxOutput(2 * COIN, ALICE.script_pubkey),))
        self.chain.submit_transaction(parent)
        self.chain.submit_transaction(child)
        expected = self.chain.info()
        self.close_chain()
        self.chain = Chain(self.database, clock=lambda: self.now)
        self.assertEqual(expected, self.chain.info())
        self.assertEqual((parent, child), self.chain.mempool_transactions())

    def test_startup_drops_malformed_pool_bytes(self):
        self.chain.submit_transaction(self.spend())
        expected_tip = self.chain.tip_hash
        expected_utxos = self.chain.state_commitment()
        self.close_chain()
        with closing(sqlite3.connect(self.database)) as connection:
            connection.execute('UPDATE mempool SET raw=?', (b'\x01',))
            connection.commit()
        self.chain = Chain(self.database, clock=lambda: self.now)
        self.assertEqual(expected_tip, self.chain.tip_hash)
        self.assertEqual(expected_utxos, self.chain.state_commitment())
        self.assertEqual((), self.chain.mempool_transactions())

    def test_startup_drops_pool_txid_bytes_mismatch(self):
        self.chain.submit_transaction(self.spend())
        expected_tip = self.chain.tip_hash
        self.close_chain()
        with closing(sqlite3.connect(self.database)) as connection:
            connection.execute('UPDATE mempool SET txid=?', (b'\x77' * 32,))
            connection.commit()
        self.chain = Chain(self.database, clock=lambda: self.now)
        self.assertEqual(expected_tip, self.chain.tip_hash)
        self.assertEqual((), self.chain.mempool_transactions())

    def test_template_selects_weight_budget_and_retains_unselected_pool_tx(self):
        self.chain.mine(MINER.script_pubkey)
        script = b'\x6a' + b'\x00' * 599_999
        first = self.spend(outputs=(TxOutput(49 * COIN, script),))
        second = self.spend(previous=self.seed_blocks[1].transactions[0],
                            outputs=(TxOutput(49 * COIN, script),))
        self.chain.submit_transaction(first)
        self.chain.submit_transaction(second)
        # Raw byte policy admits both, while their combined base weight exceeds
        # a block's 4,000,000 WU consensus bound.
        self.assertLess(len(first.serialize()) + len(second.serialize()), 4_000_000)
        self.assertGreater(first.weight() + second.weight(), 4_000_000)
        template = self.chain.make_block(MINER.script_pubkey)
        self.assertLessEqual(template.weight(), 4_000_000)
        self.assertEqual((first.txid(),), tuple(tx.txid() for tx in template.transactions[1:]))
        self.assertTrue(self.chain.accept_block(template))
        self.assertEqual((second.txid(),), tuple(tx.txid() for tx in self.chain.mempool_transactions()))
        second_block = self.chain.mine(MINER.script_pubkey)[0]
        self.assertEqual((second.txid(),), tuple(tx.txid() for tx in second_block.transactions[1:]))
        self.assertEqual(0, self.chain.info()['mempool'])

    def test_confirmed_live_transaction_cannot_overwrite_utxo(self):
        tx = self.spend()
        self.chain.submit_transaction(tx)
        self.chain.mine(MINER.script_pubkey)
        valid = self.chain.make_block(MINER.script_pubkey)
        duplicate = changed_block(valid, transactions=valid.transactions + (tx,))
        with self.assertRaisesRegex(ValidationError, 'BIP30'):
            self.chain.accept_block(duplicate)

    def test_merkle_duplicate_pair_mutation_is_rejected(self):
        self.chain.mine(MINER.script_pubkey)
        first = self.spend()
        second = self.spend(previous=self.seed_blocks[1].transactions[0])
        valid = self.chain.make_block(MINER.script_pubkey, (first, second))
        mutated = changed_block(valid, transactions=valid.transactions + (second,))
        with self.assertRaisesRegex(ValidationError, 'mutated'):
            self.chain.accept_block(mutated)

    def test_duplicate_block_is_idempotent(self):
        block = self.chain.mine(MINER.script_pubkey)[0]
        info = self.chain.info()
        self.assertFalse(self.chain.accept_block(block))
        self.assertEqual(info, self.chain.info())

    def test_failure_hooks_roll_back_every_state_component(self):
        tx = self.spend()
        self.chain.submit_transaction(tx)
        block = self.chain.make_block(MINER.script_pubkey)
        for stage in ('after_block_saved', 'after_utxos_saved', 'after_tip_saved'):
            with self.subTest(stage=stage):
                def fail(name, expected=stage):
                    if name == expected:
                        raise RuntimeError('injected storage failure')
                self.chain.fault_hook = fail
                self.assert_rejected_without_state_change(lambda: self.chain.accept_block(block), RuntimeError)
                self.assertIsNone(self.chain.connection.execute('SELECT hash FROM blocks WHERE hash=?', (block.block_hash(),)).fetchone())
                self.assertEqual((tx,), self.chain.mempool_transactions())
        self.chain.fault_hook = None
        self.assertTrue(self.chain.accept_block(block))

    def test_process_exit_before_commit_recovers_atomic_state(self):
        expected = self.chain.info()
        self.close_chain()
        code = (
            'import os,sys\n'
            'from sumuww.chain import Chain\n'
            'from sumuww.wallet import RegtestKey\n'
            'def crash(stage):\n'
            "    if stage == 'after_tip_saved': os._exit(73)\n"
            f'c=Chain(sys.argv[1],clock=lambda:{NOW},fault_hook=crash)\n'
            'c.mine(RegtestKey.from_int(3).script_pubkey)\n'
        )
        env = dict(os.environ)
        env['PYTHONDONTWRITEBYTECODE'] = '1'
        # Preserve the caller's installed dependency path as well as this package.
        paths = [str(Path(__file__).resolve().parents[1])]
        if env.get('PYTHONPATH'):
            paths.append(env['PYTHONPATH'])
        env['PYTHONPATH'] = os.pathsep.join(paths)
        result = subprocess.run([sys.executable, '-B', '-c', code, str(self.database)],
                                env=env, capture_output=True, text=True, timeout=30)
        self.assertEqual(73, result.returncode, result.stdout + result.stderr)
        self.chain = Chain(self.database, clock=lambda: self.now)
        self.assertEqual(expected, self.chain.info())
        self.assertEqual(101, self.chain.connection.execute('SELECT COUNT(*) FROM blocks').fetchone()[0])
        self.chain.mine(MINER.script_pubkey)
        self.assertEqual(101, self.chain.info()['height'])

    def test_persisted_utxo_tampering_is_detected(self):
        self.close_chain()
        with closing(sqlite3.connect(self.database)) as connection:
            connection.execute('UPDATE utxos SET value=value-1 WHERE height=1')
            connection.commit()
        with self.assertRaises(StorageError):
            Chain(self.database, clock=lambda: self.now)

    def test_persisted_chainwork_tampering_is_detected(self):
        self.close_chain()
        with closing(sqlite3.connect(self.database)) as connection:
            connection.execute("UPDATE blocks SET work='99999' WHERE height=100")
            connection.commit()
        with self.assertRaises(StorageError):
            Chain(self.database, clock=lambda: self.now)

    def test_foreign_database_profile_is_rejected(self):
        self.close_chain()
        with closing(sqlite3.connect(self.database)) as connection:
            connection.execute("UPDATE metadata SET value='foreign-network' WHERE name='profile'")
            connection.commit()
        with self.assertRaises(StorageError):
            Chain(self.database, clock=lambda: self.now)

    def test_block_codec_rejects_noncanonical_count_and_trailing_bytes(self):
        block = self.chain.make_block(MINER.script_pubkey)
        raw = block.serialize()
        with self.assertRaises(ValidationError):
            Block.deserialize(raw[:80] + b'\xfd\x01\x00' + raw[81:])
        with self.assertRaises(ValidationError):
            Block.deserialize(raw + b'\x00')


if __name__ == '__main__':
    unittest.main()
