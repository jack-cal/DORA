"""Reward reporting from verified spends, including historic migrations and forks."""
import tempfile
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
import unittest
from sumuww.chain import Chain
from sumuww.block import Block, build_coinbase, mine_header
from sumuww.block_history import block_transactions
from sumuww.primitives import COIN, ZERO_SUBSIDY_HEIGHT, hash_to_display, merkle_root
from sumuww.rewards import read_reward, reward_info, reward_rows
from sumuww.wallet import RegtestKey, sign_p2wpkh
from sumuww.wallet_history import WalletHistory
from sumuww.transaction import Transaction, TxInput, TxOutput
from sumuww.rpc import RpcServer
from sumuww.compatibility import compatibility_fields

A=RegtestKey.from_int(701); B=RegtestKey.from_int(702)

class RewardTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.path=Path(self.temp.name)/'chain.sqlite'
        self.chain=Chain(self.path); self.blocks=self.chain.mine(A.script_pubkey,100)
    def tearDown(self):
        self.chain.close();self.temp.cleanup()
    def paid(self,fee=100000):
        previous=self.blocks[0].transactions[0]
        tx=Transaction(2,(TxInput(previous.txid(),0),),(TxOutput(50*COIN-fee,B.script_pubkey),))
        self.chain.submit_transaction(sign_p2wpkh(tx,0,previous.outputs[0],A))
        return self.chain.mine(A.script_pubkey)[0]
    def info(self,block):
        return read_reward(self.chain.connection,block,self.chain._row(block.block_hash())[2])
    def test_fees_and_subsidy_match_history_block_and_rpc(self):
        block=self.paid();expected=self.info(block)
        self.assertEqual((50*COIN,100000,50*COIN+100000),tuple(expected[k+'_units'] for k in ('subsidy_reward','fee_reward','claimed_reward')))
        history=WalletHistory(A.script_pubkey).recent(self.chain)
        self.assertEqual(expected,next(r for r in history if r['coinbase'])['mining_reward'])
        self.assertEqual(expected,block_transactions(self.path,hash_to_display(block.block_hash()))['transactions'][0]['mining_reward'])
        rpc=RpcServer(lambda:SimpleNamespace(chain=self.chain,running=True),'a'*64)
        self.assertEqual(compatibility_fields(expected),rpc.call('getblock',{'hash':hash_to_display(block.block_hash())})['reward'])
        self.assertEqual(compatibility_fields(expected),rpc.call('getrawtransaction',{'txid':hash_to_display(block.transactions[0].txid())})['mining_reward'])
    def test_existing_database_backfill_repairs_derived_index(self):
        block=self.paid();expected=self.info(block);balance=self.chain.balance(A.script_pubkey)
        self.chain.connection.execute('DROP TABLE block_reward_fees');self.chain.close()
        self.chain=Chain(self.path)
        self.assertEqual(expected,self.info(block));self.assertEqual(balance,self.chain.balance(A.script_pubkey))
        self.chain.connection.execute('UPDATE block_reward_fees SET fees=999')
        self.chain.close();self.chain=Chain(self.path)
        self.assertEqual(expected,self.info(block))
    def test_reorg_history_uses_new_branch_and_keeps_old_block_amount(self):
        old=self.paid();cache=WalletHistory(A.script_pubkey);cache.recent(self.chain)
        parent=self.blocks[-1].block_hash()
        for nonce in (31,32):
            fork=self.chain.make_block(B.script_pubkey,transactions=(),parent_hash=parent,extra_nonce=nonce)
            self.chain.accept_block(fork);parent=fork.block_hash()
        self.assertNotIn(hash_to_display(old.transactions[0].txid()),[r['txid'] for r in cache.recent(self.chain)])
        self.assertEqual(100000,self.info(old)['fee_reward_units'])
        self.assertEqual(0,self.info(fork)['fee_reward_units'])
    def test_failed_write_leaves_no_reward_index(self):
        block=self.chain.make_block(A.script_pubkey)
        def fault(stage):
            if stage=='after_block_saved':raise RuntimeError('fixture rollback')
        self.chain.fault_hook=fault
        with self.assertRaises(RuntimeError):self.chain.accept_block(block)
        self.chain.fault_hook=None
        self.assertIsNone(self.chain.connection.execute('SELECT fees FROM block_reward_fees WHERE blockhash=?',(block.block_hash(),)).fetchone())

    def test_legacy_inactive_branch_backfills_when_it_returns(self):
        old=self.paid()
        parent=self.blocks[-1].block_hash()
        for nonce in (91,92):
            fork=self.chain.make_block(B.script_pubkey,transactions=(),parent_hash=parent,extra_nonce=nonce)
            self.chain.accept_block(fork);parent=fork.block_hash()
        self.chain.connection.execute('DROP TABLE block_reward_fees');self.chain.close()
        self.chain=Chain(self.path)
        self.assertEqual('unavailable',self.info(old)['allocation'])
        parent=old.block_hash()
        for nonce in (93,94):
            restored=self.chain.make_block(A.script_pubkey,transactions=(),parent_hash=parent,extra_nonce=nonce)
            self.chain.accept_block(restored);parent=restored.block_hash()
        self.assertEqual(restored.block_hash(),self.chain.tip_hash)
        self.assertEqual(100000,self.info(old)['fee_reward_units'])
        row=next(r for r in WalletHistory(A.script_pubkey).recent(self.chain)
                 if r['txid']==hash_to_display(old.transactions[0].txid()))
        self.assertEqual(100000,row['mining_reward']['fee_reward_units'])
    def test_split_payout_keeps_block_and_wallet_amount_separate(self):
        block=self.chain.make_block(A.script_pubkey)
        cb=replace(block.transactions[0],outputs=(TxOutput(20*COIN,A.script_pubkey),TxOutput(30*COIN,B.script_pubkey)))
        root,_=merkle_root([cb.txid()]);block=Block(mine_header(replace(block.header,merkle_root=root)),(cb,))
        self.chain.accept_block(block)
        row=WalletHistory(A.script_pubkey).recent(self.chain)[0]
        self.assertEqual(20*COIN,row['net_amount']);self.assertEqual(50*COIN,row['mining_reward']['claimed_reward_units'])
    def test_underclaim_is_not_falsely_assigned_to_subsidy_or_fees(self):
        block=self.chain.make_block(A.script_pubkey)
        cb=replace(block.transactions[0],outputs=(TxOutput(49*COIN,A.script_pubkey),))
        root,_=merkle_root([cb.txid()]);block=Block(mine_header(replace(block.header,merkle_root=root)),(cb,))
        self.chain.accept_block(block);info=self.info(block)
        self.assertEqual('underclaimed',info['allocation']);self.assertEqual(COIN,info['unclaimed_reward_units'])
        self.assertIsNone(info['subsidy_reward_units']);self.assertIsNone(info['fee_reward_units'])
        self.assertEqual(6,len(reward_rows(info)))
    def test_zero_subsidy_and_genesis_have_distinct_meaning(self):
        block=SimpleNamespace(transactions=(build_coinbase(ZERO_SUBSIDY_HEIGHT,A.script_pubkey,12345),))
        info=reward_info(block,ZERO_SUBSIDY_HEIGHT,12345)
        self.assertEqual(0,info['subsidy_reward_units']);self.assertEqual(12345,info['fee_reward_units'])
        genesis=self.info(self.chain.network.genesis)
        self.assertEqual('genesis_unspendable',genesis['allocation']);self.assertIsNone(genesis['subsidy_reward_units'])
    def test_legacy_read_only_missing_index_is_unknown_not_zero(self):
        block=self.paid();self.chain.connection.execute('DROP TABLE block_reward_fees')
        data=block_transactions(self.path,hash_to_display(block.block_hash()))['reward']
        self.assertEqual('unavailable',data['allocation']);self.assertIsNone(data['transaction_fees_units'])

if __name__=='__main__':unittest.main()
