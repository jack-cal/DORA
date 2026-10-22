"""Exercise reward enforcement at transition heights without generating 150k blocks."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from sumuww.block import Block
from sumuww.chain import Chain, ValidationError
from sumuww.primitives import Header, COIN, merkle_root, subsidy
from sumuww.transaction import Transaction, TxInput, TxOutput, coinbase_height_prefix

class HeightContext:
    def __init__(self,height,genesis):self.height=height;self.genesis=genesis
    def __len__(self):return self.height
    def __getitem__(self,key):
        if isinstance(key,slice):return [(bytes(32),self.genesis)]*11
        return (bytes(32),self.genesis)

class IssuanceTransitionTests(unittest.TestCase):
    def check_claim(self,height,amount):
        tx=Transaction(1,(TxInput(bytes(32),0xffffffff,coinbase_height_prefix(height)+b'\x00'),),(TxOutput(amount,b'\x00\x14'+bytes(20)),),0)
        root,_=merkle_root([tx.txid()])
        block=Block(Header(4,bytes(32),root,1700000001,0x207fffff,0),(tx,))
        with tempfile.TemporaryDirectory() as directory,Chain(Path(directory)/'node.sqlite') as chain:
            # Only PoW/header context is replaced; actual coinbase/UTXO validation runs.
            with patch.object(chain,'_validate_block_header'):
                state={}
                chain._connect(block,state,HeightContext(height,chain.network.genesis))
                self.assertEqual(sum(c.output.value for c in state.values()),amount)

    def test_rewards_before_and_after_each_new_boundary(self):
        for h,reward in [(149999,50),(150000,25),(359999,25),(360000,12.5),(569999,12.5),(570000,6.25)]:
            with self.subTest(height=h):self.check_claim(h,int(reward*COIN))

    def test_old_50_reward_rejected_at_150000(self):
        with self.assertRaisesRegex(ValidationError,'overclaims'):self.check_claim(150000,50*COIN)

    def test_one_unit_overclaim_rejected_at_boundaries(self):
        for h in (150000,360000,570000,6870000):
            with self.subTest(height=h),self.assertRaisesRegex(ValidationError,'overclaims'):
                self.check_claim(h,subsidy(h)+1)

    def test_last_reward_and_zero_reward(self):
        self.check_claim(6869999,1)
        self.check_claim(6870000,0)
