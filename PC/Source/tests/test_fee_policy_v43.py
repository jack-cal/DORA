"""Real signed transactions on disposable databases; no production funds."""
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import shutil
import unittest
from unittest.mock import patch

from sumuww.block import GENESIS_TIME
from sumuww.chain import Chain
from sumuww.errors import InvalidTransaction
from sumuww.fees import estimate_fee, estimate_payment_fee, parse_rate
from sumuww.mempool_policy import MempoolPolicy, MempoolPolicyError, vsize
from sumuww.primitives import COIN, YUGEON
from sumuww.rpc import RpcServer, RpcError
from sumuww.transaction import Transaction, TxInput, TxOutput
from sumuww.wallet import RegtestKey, sign_p2wpkh

KEY = RegtestKey.from_int(43001)
NOW = GENESIS_TIME + 20000


class FeePolicyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.seed_dir = TemporaryDirectory(prefix='sumuww-policy-seed-')
        cls.seed = Path(cls.seed_dir.name)/'seed.sqlite'
        with Chain(cls.seed, clock=lambda: NOW) as chain:
            first = chain.mine(KEY.script_pubkey, 100)[0].transactions[0]
            value = (first.outputs[0].value - 1000)//8
            funding = Transaction(2, (TxInput(first.txid(), 0),), tuple(TxOutput(value, KEY.script_pubkey) for _ in range(8)))
            cls.funding = sign_p2wpkh(funding, 0, first.outputs[0], KEY)
            chain.submit_transaction(cls.funding)
            chain.mine(KEY.script_pubkey)
            chain.connection.execute('PRAGMA wal_checkpoint(TRUNCATE)')

    @classmethod
    def tearDownClass(cls):
        cls.seed_dir.cleanup()

    def setUp(self):
        directory = TemporaryDirectory(prefix='sumuww-policy-case-')
        self.addCleanup(directory.cleanup)
        self.path = Path(directory.name)/'chain.sqlite'
        shutil.copy2(self.seed, self.path)
        self.chain = Chain(self.path, clock=lambda: NOW, mempool_policy=MempoolPolicy())
        self.addCleanup(self.chain.close)

    def spend(self, index=0, fee=1000, previous=None):
        previous = previous or self.funding
        output = previous.outputs[index]
        tx = Transaction(2, (TxInput(previous.txid(), index),), (TxOutput(output.value-fee, KEY.script_pubkey),))
        return sign_p2wpkh(tx, 0, output, KEY)

    def test_yugeon_and_floor_are_policy_not_block_consensus(self):
        self.assertEqual(100_000_000*YUGEON, COIN)
        tx = self.spend(fee=0)
        before = self.chain.state_commitment()
        self.assertFalse(self.chain.test_mempool_accept(tx)['allowed'])
        with self.assertRaises(MempoolPolicyError): self.chain.submit_transaction(tx)
        self.assertEqual(before, self.chain.state_commitment())
        block = self.chain.make_block(KEY.script_pubkey, transactions=(tx,))
        self.chain.accept_block(block)
        self.assertEqual('confirmed', self.chain.transaction_status(tx.txid())['status'])

    def test_dry_run_then_atomic_replacement_includes_descendant_fees(self):
        parent = self.spend()
        child = self.spend(previous=parent)
        self.chain.submit_transaction(parent)
        self.chain.submit_transaction(child)
        self.assertFalse(self.chain.test_mempool_accept(self.spend(fee=2000))['allowed'])
        candidate = self.spend(fee=3000)
        cache = self.chain._validated_mempool_cache
        result = self.chain.test_mempool_accept(candidate)
        self.assertTrue(result['allowed'])
        self.assertEqual(2, len(result['replaces']))
        self.assertEqual((parent, child), self.chain.mempool_transactions())
        self.assertIs(cache, self.chain._validated_mempool_cache)
        self.chain.submit_transaction(candidate)
        self.assertEqual((candidate,), self.chain.mempool_transactions())
        self.assertEqual('ancestor_replaced', self.chain.transaction_status(child.txid())['reason'])
        self.chain.mine(KEY.script_pubkey)
        self.assertEqual('confirmed', self.chain.transaction_status(candidate.txid())['status'])

    def test_invalid_signature_cannot_remove_existing_transaction(self):
        original = self.spend()
        self.chain.submit_transaction(original)
        forged = replace(original, outputs=(replace(original.outputs[0], value=original.outputs[0].value-4000),))
        with self.assertRaises(InvalidTransaction): self.chain.submit_transaction(forged)
        self.assertEqual((original,), self.chain.mempool_transactions())
        self.assertEqual(0, self.chain.connection.execute('SELECT count(*) FROM mempool_replacements').fetchone()[0])

    def test_full_pool_can_replace_but_never_overflow(self):
        original = self.spend()
        with patch('sumuww.chain.MAX_MEMPOOL_TRANSACTIONS', 1):
            self.chain.submit_transaction(original)
            candidate = self.spend(fee=2000)
            self.chain.submit_transaction(candidate)
            self.assertEqual((candidate,), self.chain.mempool_transactions())
            self.assertFalse(self.chain.test_mempool_accept(self.spend(index=1))['allowed'])

    def test_replacement_limit_is_checked_before_removal(self):
        self.chain.mempool_policy = MempoolPolicy(max_replacements=1)
        original = self.spend()
        child = self.spend(previous=original)
        self.chain.submit_transaction(original)
        self.chain.submit_transaction(child)
        with self.assertRaises(MempoolPolicyError): self.chain.submit_transaction(self.spend(fee=5000))
        self.assertEqual((original, child), self.chain.mempool_transactions())

    def test_new_unconfirmed_input_cannot_be_added(self):
        original, other = self.spend(), self.spend(index=1)
        self.chain.submit_transaction(original)
        self.chain.submit_transaction(other)
        previous = (self.funding.outputs[0], other.outputs[0])
        candidate = Transaction(2, (TxInput(self.funding.txid(), 0), TxInput(other.txid(), 0)),
                                (TxOutput(sum(o.value for o in previous)-10000, KEY.script_pubkey),))
        for index, output in enumerate(previous): candidate = sign_p2wpkh(candidate, index, output, KEY)
        with self.assertRaises(MempoolPolicyError): self.chain.submit_transaction(candidate)
        self.assertEqual((original, other), self.chain.mempool_transactions())

    def test_failed_commit_rolls_back_replacement_and_cache(self):
        from tests.test_mempool_cache_v37 import ConnectionProxy
        original = self.spend()
        self.chain.submit_transaction(original)
        cache = self.chain._validated_mempool_cache
        raw = self.chain.connection
        self.chain.connection = ConnectionProxy(raw, fail_commit=True)
        import sqlite3
        with self.assertRaises(sqlite3.OperationalError): self.chain.submit_transaction(self.spend(fee=3000))
        self.chain.connection = raw
        self.assertEqual((original,), self.chain.mempool_transactions())
        self.assertIs(cache, self.chain._validated_mempool_cache)

    def test_second_writer_and_restart_recheck_current_pool(self):
        self.chain.submit_transaction(self.spend())
        with Chain(self.path, clock=lambda: NOW, mempool_policy=MempoolPolicy()) as other:
            candidate = self.spend(fee=2000)
            other.submit_transaction(candidate)
        with self.assertRaises(MempoolPolicyError): self.chain.submit_transaction(self.spend(fee=1500))
        self.assertEqual((candidate,), self.chain.mempool_transactions())
        self.chain.submit_transaction(self.spend(fee=4000))

    def test_reorganization_revalidates_pool_against_new_chain(self):
        parent = self.chain.tip_hash
        original = self.spend()
        self.chain.submit_transaction(original)
        candidate = self.spend(fee=3000)
        self.chain.submit_transaction(candidate)
        self.chain.mine(KEY.script_pubkey)
        side = self.chain.make_block(KEY.script_pubkey, transactions=(original,), parent_hash=parent)
        self.chain.accept_block(side)
        extension = self.chain.make_block(KEY.script_pubkey, transactions=(), parent_hash=side.block_hash())
        self.chain.accept_block(extension)
        self.assertEqual('confirmed', self.chain.transaction_status(original.txid())['status'])
        self.assertFalse(self.chain.has_mempool_transaction(candidate.txid()))

    def test_fee_presets_manual_rate_and_rpc_preflight(self):
        result = estimate_fee(self.chain, 200)
        self.assertGreaterEqual(result['fee_units'], 200)
        self.assertEqual('yugeon', result['amount_unit'])
        self.assertFalse(result['confirmation_time_guaranteed'])
        for invalid in ('0', '-1', 'NaN', '1e3', '1.0001'):
            with self.assertRaises(ValueError): parse_rate(invalid, self.chain)
        quote = estimate_payment_fee(self.chain, KEY.script_pubkey, KEY.script_pubkey, COIN, rate='2.5')
        self.assertEqual((quote['estimated_vsize']*5+1)//2, quote['fee_units'])
        node = SimpleNamespace(running=True, chain=self.chain)
        rpc = RpcServer(lambda: node, '43'*32, port=0)
        tx = self.spend()
        self.assertTrue(rpc.call('testmempoolaccept', [tx.serialize().hex()])['allowed'])
        self.assertEqual(0, self.chain.mempool_info()['size'])
        rpc.call('sendrawtransaction', [tx.serialize().hex()])
        entry = rpc.call('getmempoolentry', [tx.txid()[::-1].hex()])
        self.assertEqual(1000, entry['fee_units'])
        rates = [rpc.call('estimatefee', [200, mode])['fee_units'] for mode in ('slow','normal','fast')]
        self.assertEqual(sorted(rates), rates)
        with self.assertRaises(RpcError): rpc.call('estimatefee', [True])


if __name__ == '__main__': unittest.main()
