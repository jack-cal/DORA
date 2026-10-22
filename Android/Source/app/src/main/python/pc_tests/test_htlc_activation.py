import hashlib,json,sqlite3,tempfile,unittest
from pathlib import Path
from sumuww.chain import Chain
from sumuww.htlc_policy import PUBLIC_HTLC_ACTIVATION_HEIGHT
from sumuww.htlc_selftest import run
from sumuww.errors import StorageError
from sumuww.profiles import SUMUWW


class HtlcActivationTests(unittest.TestCase):
    def test_real_transactions_before_and_after_boundary(self):
        result=run()
        self.assertTrue(result['passed'])
        self.assertTrue(result['checks']['pre_activation_coins_spendable'])
        self.assertTrue(result['checks']['ordinary_transfer_before_activation'])

    def test_public_9100_and_bls_9000_are_independent(self):
        with tempfile.TemporaryDirectory() as temp:
            with Chain(Path(temp)/'public.sqlite',network='sumuww') as chain:
                self.assertEqual(chain.htlc_activation,9100)
                self.assertEqual(chain.boundary.activation,9000)
                self.assertEqual(chain.tip_hash,SUMUWW.genesis.block_hash())
                self.assertFalse(chain.htlc_policy.info(9099)['active'])
                self.assertTrue(chain.htlc_policy.info(9100)['active'])
                self.assertTrue(chain.htlc_policy.info(9099)['next_block_active'])
            for bad in (9000,9101,True,9100.0):
                with self.assertRaises(StorageError):Chain(Path(temp)/'invalid.sqlite',network='sumuww',htlc_activation=bad)

    def test_existing_regtest_keeps_original_rules_without_opt_in(self):
        with tempfile.TemporaryDirectory() as temp:
            database=Path(temp)/'legacy.sqlite'
            with Chain(database) as chain:
                self.assertIsNone(chain.htlc_activation)
                self.assertFalse(chain.htlc_policy.active(99999))
                self.assertFalse(chain.connection.execute("SELECT 1 FROM sqlite_master WHERE name='htlc_config'").fetchone())
            with Chain(database,htlc_activation=106):pass
            with self.assertRaises(StorageError):Chain(database)
