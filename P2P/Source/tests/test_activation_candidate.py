import hashlib
import tempfile
import unittest
from pathlib import Path
from smw_trade.activation_candidate import ConditionalSpendCandidate
from smw_trade.settlement import smw_fund,spend
from smw_trade.htlc import Contract,sign_spend
from sumuww.wallet import RegtestKey
from sumuww.errors import UnsupportedFeature
from sumuww.profiles import SUMUWW


class ActivationCandidateTests(unittest.TestCase):
    def test_activation_boundary_and_existing_ownership(self):
        with tempfile.TemporaryDirectory() as temp:
            database=Path(temp)/'candidate.sqlite'
            seller,buyer=RegtestKey.from_int(889),RegtestKey.from_int(998)
            secret=hashlib.sha256(b'isolated activation test').digest()
            contract=Contract(hashlib.sha256(secret).digest(),buyer.pubkey,seller.pubkey,150)
            with ConditionalSpendCandidate(database,activation_height=106) as chain:
                chain.mine(seller.script_pubkey,103)
                funding=smw_fund(chain,seller,contract,100001000) # height 104
                claim,previous=spend(funding,contract,buyer)
                claim=sign_spend(claim,0,previous,contract,buyer,secret=secret)
                with self.assertRaises(UnsupportedFeature):chain.submit_transaction(claim) # candidate height 105
                chain.mine(seller.script_pubkey)
                chain.submit_transaction(claim);chain.mine(seller.script_pubkey) # height 106
                self.assertEqual(chain.balance(buyer.script_pubkey),100000000)
                self.assertTrue(chain.info()['conditional_spend']['active'])
            with self.assertRaises(ValueError):ConditionalSpendCandidate(database,activation_height=107)
            with ConditionalSpendCandidate(database,activation_height=106) as chain:
                self.assertEqual(chain.balance(buyer.script_pubkey),100000000)

    def test_public_genesis_unchanged_but_no_implicit_activation(self):
        with tempfile.TemporaryDirectory() as temp:
            with ConditionalSpendCandidate.public_upgrade(Path(temp)/'public.sqlite') as chain:
                self.assertEqual(chain.tip_hash,SUMUWW.genesis.block_hash())
                self.assertFalse(chain.info()['conditional_spend']['active'])
                self.assertEqual(chain.info()['height'],0)
                self.assertEqual(chain.info()['conditional_spend']['activation_height'],9100)
                self.assertEqual(chain.boundary.activation,9000)
            with self.assertRaises(ValueError):ConditionalSpendCandidate(Path(temp)/'wrong.sqlite',network='sumuww',activation_height=9101)
            with self.assertRaises(TypeError):ConditionalSpendCandidate(Path(temp)/'unset.sqlite')
