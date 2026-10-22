"""Full public transaction history on owned temporary regtest fixtures only."""

import gc
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from coincurve import PrivateKey

from sumuww.app_service import AppService
from sumuww.chain import Chain
from sumuww.keystore import WalletKey
from sumuww.primitives import COIN, hash_to_display
from sumuww.profiles import REGTEST
from sumuww.transaction import Transaction, TxInput, TxOutput
from sumuww.wallet import RegtestKey, sign_p2wpkh
from sumuww.wallet_history import WalletHistory


ALICE = RegtestKey.from_int(1)
BOB = RegtestKey.from_int(2)


class FullHistoryTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='sumuww-v31-history-')
        self.chain = Chain(Path(self.temporary.name) / 'owned.sqlite', network=REGTEST)
        self.history = WalletHistory(ALICE.script_pubkey)

    def tearDown(self):
        self.chain.close()
        self.temporary.cleanup()

    def oldest_reward_spend(self, blocks):
        outpoint = (blocks[0].transactions[0].txid(), 0)
        coin = dict(self.chain.list_utxos(ALICE.script_pubkey))[outpoint]
        transaction = Transaction(2, (TxInput(*outpoint),),
                                  (TxOutput(coin.output.value - 1000, BOB.script_pubkey),))
        return sign_p2wpkh(transaction, 0, coin.output, ALICE)

    def test_recent_view_keeps_all_old_entries_and_unspent_output_accounting(self):
        blocks = self.chain.mine(ALICE.script_pubkey, 120)
        recent = self.history.recent(self.chain)
        self.assertEqual(10, len(recent))
        page = self.history.page(self.chain, 0, 200)
        self.assertEqual(120, page['total'])
        self.assertEqual(list(range(120, 0, -1)), [item['height'] for item in page['transactions']])
        self.assertEqual(120, page['transactions'][-1]['confirmations'])
        self.assertEqual(hash_to_display(blocks[0].transactions[0].txid()),
                         page['transactions'][-1]['txid'])
        spend = self.oldest_reward_spend(blocks)
        self.chain.submit_transaction(spend)
        pending = self.history.page(self.chain, 0, 200)
        self.assertEqual(121, pending['total'])
        self.assertEqual(hash_to_display(spend.txid()), pending['transactions'][0]['txid'])
        self.assertEqual(-50 * COIN, pending['transactions'][0]['net_amount'])
        self.chain.mine(BOB.script_pubkey)
        confirmed = self.history.page(self.chain, 0, 200)
        self.assertEqual(121, confirmed['total'])
        self.assertEqual('confirmed', confirmed['transactions'][0]['status'])
        self.assertEqual(121, confirmed['transactions'][0]['height'])
        self.assertEqual(-50 * COIN, confirmed['transactions'][0]['net_amount'])
        self.assertEqual(121, confirmed['transactions'][-1]['confirmations'])
        self.assertEqual(10, len(self.history.recent(self.chain)))
        self.assertEqual(121, self.history.page(self.chain)['total'])

    def test_pages_cover_every_entry_without_duplicates_and_out_of_range_is_empty(self):
        self.chain.mine(ALICE.script_pubkey, 113)
        pages = [self.history.page(self.chain, offset, 50) for offset in (0, 50, 100, 150)]
        self.assertEqual([50, 50, 13, 0], [len(page['transactions']) for page in pages])
        all_rows = [row for page in pages for row in page['transactions']]
        self.assertEqual(113, len(set(row['txid'] for row in all_rows)))
        self.assertEqual(list(range(113, 0, -1)), [row['height'] for row in all_rows])
        for offset, page in zip((0, 50, 100, 150), pages):
            self.assertEqual((113, offset, 50, 113),
                             (page['total'], page['offset'], page['limit'], page['height']))
            self.assertEqual(hash_to_display(self.chain.tip_hash), page['tip'])
            json.dumps(page)
        self.assertEqual([], self.history.page(self.chain, 10 ** 30, 1)['transactions'])
        self.assertEqual(1, len(self.history.page(self.chain, 112, 1)['transactions']))

    def test_empty_history_and_default_page_metadata(self):
        page = self.history.page(self.chain)
        self.assertEqual([], page['transactions'])
        self.assertEqual((0, 0, 50, 0),
                         (page['total'], page['offset'], page['limit'], page['height']))
        self.assertEqual(hash_to_display(self.chain.tip_hash), page['tip'])

    def test_offset_and_limit_strict_validation_precedes_chain_access(self):
        for value in (-1, True, False, None, '1', 1.0):
            with self.subTest(offset=value), self.assertRaisesRegex(ValueError, 'offset'):
                self.history.page(object(), offset=value)
        for value in (0, -1, 201, True, False, None, '50', 50.0):
            with self.subTest(limit=value), self.assertRaisesRegex(ValueError, 'limit'):
                self.history.page(object(), limit=value)
        self.assertEqual(200, self.history.page(self.chain, 0, 200)['limit'])

    def test_pending_first_confirmation_refresh_and_no_cached_pending_duplicates(self):
        blocks = self.chain.mine(ALICE.script_pubkey, 100)
        spend = self.oldest_reward_spend(blocks)
        self.chain.submit_transaction(spend)
        first = self.history.page(self.chain, 0, 3)
        pending = first['transactions'][0]
        self.assertEqual((hash_to_display(spend.txid()), 'pending', None, 0),
                         (pending['txid'], pending['status'], pending['height'], pending['confirmations']))
        self.assertEqual(101, first['total'])
        self.assertEqual(first, self.history.page(self.chain, 0, 3))
        self.chain.mine(BOB.script_pubkey)
        confirmed = self.history.page(self.chain, 0, 3)
        self.assertEqual(101, confirmed['total'])
        self.assertEqual((pending['txid'], 'confirmed', 101, 1),
                         tuple(confirmed['transactions'][0][name]
                               for name in ('txid', 'status', 'height', 'confirmations')))
        self.chain.mine(BOB.script_pubkey, 3)
        refreshed = self.history.page(self.chain, 0, 200)
        self.assertEqual(4, refreshed['transactions'][0]['confirmations'])
        self.assertEqual(104, refreshed['transactions'][-1]['confirmations'])
        self.assertEqual(101, refreshed['total'])
        self.assertNotEqual(first['tip'], refreshed['tip'])

    def test_active_branch_reorg_rebuild_drops_orphans_and_recalculates_confirmations(self):
        blocks = self.chain.mine(ALICE.script_pubkey, 15)
        before = self.history.page(self.chain)
        orphaned = {hash_to_display(block.transactions[0].txid()) for block in blocks[10:]}
        parent = blocks[9].block_hash()
        for index in range(6):
            block = self.chain.make_block(BOB.script_pubkey, parent_hash=parent,
                                          extra_nonce=1000 + index)
            self.chain.accept_block(block)
            parent = block.block_hash()
        after = self.history.page(self.chain)
        self.assertEqual((16, 10), (after['height'], after['total']))
        self.assertEqual([], [row for row in after['transactions'] if row['txid'] in orphaned])
        self.assertEqual(list(range(10, 0, -1)), [row['height'] for row in after['transactions']])
        self.assertEqual((7, 16), (after['transactions'][0]['confirmations'],
                                  after['transactions'][-1]['confirmations']))
        self.assertNotEqual(before['tip'], after['tip'])
        new_block, = self.chain.mine(ALICE.script_pubkey)
        extended = self.history.page(self.chain)
        self.assertEqual((17, 11), (extended['height'], extended['total']))
        self.assertEqual(hash_to_display(new_block.transactions[0].txid()),
                         extended['transactions'][0]['txid'])
        self.assertTrue(self.chain.verify_persisted_state())

    def test_recent_limit_slicing_compatibility_cannot_prune_page_history(self):
        self.chain.mine(ALICE.script_pubkey, 20)
        self.assertEqual([], self.history.recent(self.chain, 0))
        self.assertEqual(3, len(self.history.recent(self.chain, 3)))
        self.assertEqual(19, len(self.history.recent(self.chain, -1)))
        self.assertEqual(20, len(self.history.recent(self.chain, 500)))
        self.assertEqual(20, self.history.page(self.chain)['total'])
        first = self.history.page(self.chain)
        first['transactions'][0]['height'] = -999
        self.assertEqual(20, self.history.page(self.chain)['transactions'][0]['height'])


class HistoryServiceTests(unittest.TestCase):
    def setUp(self):
        gc.collect()
        self.temporary = tempfile.TemporaryDirectory(prefix='sumuww-v31-history-service-')
        self.directory = Path(self.temporary.name)
        with Chain(self.directory / 'node.sqlite', network=REGTEST) as chain:
            chain.mine(ALICE.script_pubkey, 120)
        self.service = AppService(self.directory, network=REGTEST, listen='127.0.0.1:0',
                                  peers=[], allow_internet=False, allow_lan=False)
        self.service.start().result(timeout=10)

    def tearDown(self):
        self.service.stop().result(timeout=10)
        self.temporary.cleanup()

    def select(self, scalar=1):
        key = WalletKey(PrivateKey(scalar.to_bytes(32, 'big')), REGTEST)
        with patch('sumuww.app_service.keystore_create', return_value=key):
            wallet = self.service.create_wallet(f'owned-fixture-{scalar}.json',
                                                 'public test fixture').result(timeout=5)
        return wallet

    def test_no_wallet_rejection_is_future_error(self):
        future = self.service.transaction_history()
        with self.assertRaisesRegex(RuntimeError, 'Select a wallet'):
            future.result(timeout=5)
        self.assertIsNone(self.service.status().result(timeout=5)['wallet'])

    def test_locked_wallet_reads_full_history_after_recent_status_without_loading_keys(self):
        wallet = self.select()
        recent = self.service.status().result(timeout=5)
        self.assertEqual(10, len(recent['transactions']))
        self.service.lock_wallet().result(timeout=5)
        self.assertIsNone(self.service._key)
        with (patch('sumuww.app_service.keystore_load', side_effect=AssertionError('No private key needed')),
              patch('sumuww.app_service.export_mnemonic', side_effect=AssertionError('No phrase export needed'))):
            first = self.service.transaction_history().result(timeout=5)
            last = self.service.transaction_history(100, 50).result(timeout=5)
        self.assertEqual(wallet['address'], first['address'])
        self.assertEqual(120, first['total'])
        self.assertEqual((50, 20), (len(first['transactions']), len(last['transactions'])))
        self.assertEqual(120, last['transactions'][-1]['confirmations'])
        self.assertEqual({'transactions', 'total', 'offset', 'limit', 'height', 'tip', 'address'},
                         set(first))
        self.assertIsNone(self.service._key)
        json.dumps(first)

    def test_history_follows_selected_public_address_and_invalid_parameters_fail(self):
        alice = self.select()
        self.assertEqual(120, self.service.transaction_history().result(timeout=5)['total'])
        bob = self.select(2)
        self.assertNotEqual(alice['address'], bob['address'])
        empty = self.service.transaction_history().result(timeout=5)
        self.assertEqual((bob['address'], 0, []),
                         (empty['address'], empty['total'], empty['transactions']))
        for offset, limit in ((True, 50), (-1, 50), (0, False), (0, 201)):
            with self.subTest(offset=offset, limit=limit), self.assertRaises(RuntimeError):
                self.service.transaction_history(offset, limit).result(timeout=5)


if __name__ == '__main__':
    unittest.main()
