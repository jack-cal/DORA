"""Modified miners cannot make invalid outputs spendable through wallet hops.

Every key and database is a disposable public test fixture. SUMUWW's actual
profile is checked without solving its production difficulty; fast regtest and
retarget-lab profiles exercise the same validator and spending code.
"""

from dataclasses import replace
from contextlib import closing
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
import unittest

from sumuww.block import Block, GENESIS_TIME, REGTEST_BITS, mine_header
from sumuww.chain import Chain
from sumuww.errors import InvalidTransaction, StorageError, ValidationError
from sumuww.primitives import (COIN, REGTEST_POW_LIMIT, block_work, check_pow,
                             merkle_root, sha256d, valid_target)
from sumuww.profiles import SUMUWW, RETARGET_LAB
from sumuww.transaction import Transaction, TxInput, TxOutput
from sumuww.wallet import RegtestKey, sign_p2wpkh


MINER = RegtestKey.from_int(901)
WALLET = RegtestKey.from_int(902)
RECIPIENT = RegtestKey.from_int(903)


class ModifiedMinerTests(unittest.TestCase):
    def setUp(self):
        self.scratch = TemporaryDirectory(prefix='sumuww-miner-attacks-v15-')
        self.addCleanup(self.scratch.cleanup)
        self.root = Path(self.scratch.name)

    def open_chain(self, name='chain', network='regtest'):
        now = SUMUWW.genesis.header.timestamp + 1000 if network == 'dora' else GENESIS_TIME + 1000
        chain = Chain(self.root / (name + '.sqlite'), network=network, clock=lambda: now)
        self.addCleanup(chain.close)
        return chain

    @staticmethod
    def ledger(chain):
        """Compare stored side branches as well as active balances and tip."""
        with chain.read_snapshot():
            return {
                'blocks': chain.connection.execute('SELECT * FROM blocks ORDER BY hash').fetchall(),
                'metadata': chain.connection.execute('SELECT * FROM metadata ORDER BY name').fetchall(),
                'utxos': chain.connection.execute('SELECT * FROM utxos ORDER BY txid,idx').fetchall(),
                'mempool': chain.connection.execute('SELECT * FROM mempool ORDER BY id').fetchall(),
            }

    def reject_unchanged(self, chain, block, message):
        before = self.ledger(chain)
        with self.assertRaisesRegex(ValidationError, message):
            chain.accept_block(Block.deserialize(block.serialize()))
        self.assertEqual(before, self.ledger(chain))
        self.assertFalse(chain.has_block(block.block_hash()))

    def test_actual_sumuww_rejects_attacker_relaxed_pow_limit(self):
        chain = self.open_chain(network='dora')
        with chain.read_snapshot():
            template = chain._block_template(MINER.script_pubkey)
        self.assertEqual(template.header.bits, SUMUWW.initial_bits)
        # A custom program changes both nBits and its own pow_limit. Its own
        # success is irrelevant to the receiving SUMUWW validator's fixed rules.
        header = mine_header(replace(template.header, bits=REGTEST_BITS),
                             pow_limit=REGTEST_POW_LIMIT)
        self.assertTrue(check_pow(header.digest(), header.bits, REGTEST_POW_LIMIT))
        self.assertGreater(valid_target(header.bits, REGTEST_POW_LIMIT), SUMUWW.pow_limit)
        self.reject_unchanged(chain, Block(header, template.transactions), 'contextual nBits')

    def test_easier_in_limit_pow_at_retarget_cannot_create_sidebranch(self):
        chain = self.open_chain(network='retarget-lab')
        for _ in range(15):
            # Strictly increasing MTP permits a fast private laboratory branch.
            timestamp = chain._mtp(chain._path(chain.tip_hash)) + 1
            chain.accept_block(chain.make_block(MINER.script_pubkey, timestamp=timestamp))
        expected = chain.expected_bits()
        self.assertLess(valid_target(expected, RETARGET_LAB.pow_limit),
                        valid_target(RETARGET_LAB.initial_bits, RETARGET_LAB.pow_limit))
        with chain.read_snapshot():
            template = chain._block_template(MINER.script_pubkey)
        easier = mine_header(replace(template.header, bits=RETARGET_LAB.initial_bits),
                             pow_limit=RETARGET_LAB.pow_limit)
        self.assertTrue(check_pow(easier.digest(), easier.bits, RETARGET_LAB.pow_limit))
        self.reject_unchanged(chain, Block(easier, template.transactions), 'contextual nBits')

    def test_excess_reward_cannot_be_laundered_through_signed_wallet_payment(self):
        chain = self.open_chain()
        valid = chain.make_block(MINER.script_pubkey)
        original = valid.transactions[0]
        forged = replace(original, outputs=(replace(original.outputs[0], value=51 * COIN),))
        root, _ = merkle_root([forged.txid()])
        attack = Block(mine_header(replace(valid.header, merkle_root=root)), (forged,))
        self.reject_unchanged(chain, attack, 'overclaims')
        # Waiting through maturity and signing with the correct owner's key
        # cannot supply a UTXO that the validator never accepted.
        chain.mine(RECIPIENT.script_pubkey, 100)
        payment = sign_p2wpkh(Transaction(2, (TxInput(forged.txid(), 0),),
                                          (TxOutput(50 * COIN, WALLET.script_pubkey),)),
                              0, forged.outputs[0], MINER)
        before = self.ledger(chain)
        with self.assertRaisesRegex(InvalidTransaction, 'Missing or already spent'):
            chain.submit_transaction(payment)
        self.assertEqual(before, self.ledger(chain))
        self.assertEqual(chain.balance(WALLET.script_pubkey), 0)

    def test_difficulty_invalid_coinbase_cannot_supply_wallet_payment(self):
        chain = self.open_chain()
        valid = chain.make_block(MINER.script_pubkey)
        # Change coinbase identity as well, so a later legitimate height-one
        # coinbase cannot coincidentally create the same transaction output.
        coinbase = replace(valid.transactions[0], inputs=(replace(
            valid.transactions[0].inputs[0], script_sig=valid.transactions[0].inputs[0].script_sig + b'attack'),))
        root, _ = merkle_root([coinbase.txid()])
        attack_header = mine_header(replace(valid.header, bits=REGTEST_BITS - 1, merkle_root=root))
        self.reject_unchanged(chain, Block(attack_header, (coinbase,)), 'contextual nBits')
        chain.mine(RECIPIENT.script_pubkey, 100)
        payment = sign_p2wpkh(Transaction(2, (TxInput(coinbase.txid(), 0),),
                                          (TxOutput(49 * COIN, WALLET.script_pubkey),)),
                              0, coinbase.outputs[0], MINER)
        before = self.ledger(chain)
        with self.assertRaisesRegex(InvalidTransaction, 'Missing or already spent'):
            chain.submit_transaction(payment)
        self.assertEqual(before, self.ledger(chain))

    def test_forged_local_chainwork_is_rejected_on_restart(self):
        database = self.root / 'forged-work.sqlite'
        with Chain(database) as chain:
            chain.mine(MINER.script_pubkey, 3)
            tip = chain.tip_hash
            real_work = int(chain.info()['chainwork'])
            commitment = chain.state_commitment()
        # Peers send headers/blocks, not an authoritative chainwork index.
        # Even tampering with one's own disk index cannot become validated work.
        with closing(sqlite3.connect(database)) as connection:
            with connection:
                connection.execute('UPDATE blocks SET work=? WHERE hash=?', (str(real_work + (1 << 255)), tip))
        with self.assertRaisesRegex(StorageError, 'Height/chainwork index mismatch'):
            Chain(database)
        with closing(sqlite3.connect(database)) as connection:
            self.assertEqual(connection.execute("SELECT value FROM metadata WHERE name='tip'").fetchone()[0], tip)
            self.assertEqual(connection.execute('SELECT COUNT(*) FROM utxos').fetchone()[0], 3)
            with connection:
                connection.execute('UPDATE blocks SET work=? WHERE hash=?', (str(real_work), tip))
        with Chain(database) as repaired:
            self.assertEqual(repaired.state_commitment(), commitment)
            self.assertEqual(int(repaired.info()['chainwork']), real_work)

    def test_optimized_hashing_has_identical_proof_and_spendable_normal_outputs(self):
        chain = self.open_chain()
        with chain.read_snapshot():
            template = chain._block_template(MINER.script_pubkey)
        target = valid_target(template.header.bits, chain.network.pow_limit)
        # Reference miner serializes/hashes all 80 bytes per attempt. The built
        # in miner reuses SHA256 prefix state. No wall-time speed assertion is
        # needed: identical mathematical results determine eligibility.
        reference = next(replace(template.header, nonce=nonce) for nonce in range(1000)
                         if int.from_bytes(sha256d(replace(template.header, nonce=nonce).serialize()), 'little') <= target)
        optimized = mine_header(template.header, pow_limit=chain.network.pow_limit)
        self.assertEqual(reference, optimized)
        block = Block(optimized, template.transactions)
        self.assertTrue(chain.accept_block(block))
        expected_work = block_work(chain.network.initial_bits, chain.network.pow_limit) + block_work(optimized.bits, chain.network.pow_limit)
        self.assertEqual(int(chain.info()['chainwork']), expected_work)
        chain.mine(RECIPIENT.script_pubkey, 99)
        reward = block.transactions[0]
        payment = sign_p2wpkh(Transaction(2, (TxInput(reward.txid(), 0),),
                                          (TxOutput(49 * COIN, WALLET.script_pubkey),)),
                              0, reward.outputs[0], MINER)
        chain.submit_transaction(payment)
        chain.mine(RECIPIENT.script_pubkey)
        onward = sign_p2wpkh(Transaction(2, (TxInput(payment.txid(), 0),),
                                         (TxOutput(48 * COIN, RECIPIENT.script_pubkey),)),
                             0, payment.outputs[0], WALLET)
        chain.submit_transaction(onward)
        chain.mine(MINER.script_pubkey)
        self.assertEqual(chain.balance(WALLET.script_pubkey), 0)
        self.assertTrue(chain.verify_persisted_state())


if __name__ == '__main__':
    unittest.main()
