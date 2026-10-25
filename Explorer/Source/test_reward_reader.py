"""Read-only reward display tests; fixtures are not consensus-valid blocks."""
from dataclasses import replace
import unittest
import server
import test_explorer as support
from sumuww.block import Block
from sumuww.transaction import TxOutput
from sumuww.primitives import COIN, merkle_root, hash_to_display

class RewardReaderTests(unittest.TestCase):
    setUp=support.ExplorerTests.setUp
    tearDown=support.ExplorerTests.tearDown
    make=support.ExplorerTests.make
    add=support.ExplorerTests.add
    def test_full_claim_fees_and_coinbase_view(self):
        cb=replace(self.two.transactions[0],outputs=(TxOutput(51*COIN,self.script),))
        txs=(cb,self.tx);root,_=merkle_root([t.txid() for t in txs])
        block=Block(replace(self.two.header,merkle_root=root,nonce=123),txs)
        self.add(block,2);self.c.commit();self.explorer.refresh(force=True)
        data=self.explorer.run('block',2)['reward_breakdown']
        self.assertEqual(('50.00000000','1.00000000','51.00000000'),tuple(data[k+'_smw'] for k in ('subsidy_reward','fee_reward','claimed_reward')))
        self.assertEqual(data,self.explorer.run('transaction',hash_to_display(cb.txid()))['mining_reward'])
    def test_underclaim_keeps_limit_separate(self):
        data=self.explorer.run('block',2)['reward_breakdown']
        self.assertEqual('underclaimed',data['allocation']);self.assertIsNone(data['subsidy_reward_units'])
        self.assertEqual(COIN,data['unclaimed_reward_units'])
    def test_zero_fees_and_genesis(self):
        one=self.explorer.run('block',1)['reward_breakdown']
        self.assertEqual('0.00000000',one['fee_reward_smw'])
        genesis=self.explorer.run('block',0)['reward_breakdown']
        self.assertEqual('genesis_unspendable',genesis['allocation'])
        self.assertIsNone(genesis['subsidy_reward_units'])
    def test_reorg_reward_snapshot_is_refreshed(self):
        old=self.explorer.run('block',2)['snapshot']
        fork=self.make(self.one,2,nonce=555);self.add(fork,2);self.c.commit();self.explorer.refresh(force=True)
        data=self.explorer.run('block',2)
        self.assertNotEqual(old,data['snapshot']);self.assertEqual('0.00000000',data['reward_breakdown']['fee_reward_smw'])

if __name__=='__main__':unittest.main()
