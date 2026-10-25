"""Wallet-facing failure paths, using only disposable data."""
import base64
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import time
import unittest

from test_wallet_flow import WalletFlow, runtime, keystore, Chain, decode_address

class AdditionalWalletChecks(WalletFlow):
    # Keep the original four checks in their own suite, not inherited duplicates.
    test_recovery_backup_and_background_lock = None
    test_real_signed_transfer_and_single_use_quote = None
    test_lock_invalidates_prepared_payment = None
    test_transfer_reaches_an_independent_peer = None

    def test_legacy_wallet_import_preserves_address_key_and_coins(self):
        legacy_path = self.path / 'original-legacy-wallet.json'
        legacy = keystore.create_wallet(legacy_path, self.password, network='regtest')
        original = legacy_path.read_bytes()
        with Chain(self.path / 'node/node.sqlite', network='regtest') as chain:
            chain.mine(legacy.script_pubkey, 101)
        imported = self.call('restore', self.password, base64.b64encode(original).decode('ascii'))
        self.assertEqual(imported['address'], legacy.address)
        self.assertEqual(legacy_path.read_bytes(), original)
        restored = keystore.load_wallet(self.path / 'node/wallet.json', self.password, network='regtest')
        self.assertEqual(restored.pubkey, legacy.pubkey)
        self.assertEqual(restored.script_pubkey, legacy.script_pubkey)
        self.assertEqual(self.call('status')['wallet']['available_dora'], '100.00000000')

    def funded(self):
        sender = self.call('create', self.password)['address']
        recipient = keystore.create_hd_wallet(self.path / 'recipient.json', self.password, network='regtest')
        script = decode_address(sender, network='regtest')
        with Chain(self.path / 'node/node.sqlite', network='regtest') as chain:
            chain.mine(script, 100)
        return recipient, script

    def test_zero_fee_maturity_pending_reservation_and_confirmation(self):
        recipient, script = self.funded()
        state = self.call('status')['wallet']
        self.assertEqual('5000.00000000', state['total_dora'])
        self.assertEqual('50.00000000', state['available_dora'])
        self.assertEqual('4950.00000000', state['immature_dora'])
        quote = self.call('prepare', recipient.address, '1', '0')
        self.assertEqual('0.00000000', quote['fee_dora'])
        self.assertEqual('accepted', self.call('submit', quote['quote_id'])['outcome'])
        self.assertEqual('0.00000000', self.call('status')['wallet']['available_dora'])
        self.rejected('prepare', recipient.address, '1', '0')
        with Chain(self.path / 'node/node.sqlite', network='regtest') as chain:
            tx, = chain.mempool_transactions()
            self.assertEqual(50 * 100_000_000, sum(o.value for o in tx.outputs))
            chain.accept_block(chain.make_block(script))
            self.assertEqual(100_000_000, chain.balance(recipient.script_pubkey))
        self.assertEqual('0.00000000', self.call('status')['wallet']['pending_dora'])

    def test_timeout_locks_and_invalidates_signed_quote(self):
        recipient, _ = self.funded()
        quote = self.call('prepare', recipient.address, '1', '0')
        runtime._last_activity = time.monotonic() - runtime._timeout - 1
        self.assertFalse(self.call('status')['wallet']['unlocked'])
        self.rejected('prepare', recipient.address, '1', '0')
        self.call('unlock', self.password)
        self.assertEqual('rejected', self.call('submit', quote['quote_id'])['outcome'])
        with Chain(self.path / 'node/node.sqlite', network='regtest') as chain:
            self.assertFalse(chain.mempool_transactions())

    def test_simultaneous_submit_broadcasts_only_one_transaction(self):
        recipient, _ = self.funded()
        quote = self.call('prepare', recipient.address, '1', '0')
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: self.call('submit', quote['quote_id'])['outcome'], range(2)))
        self.assertEqual(['accepted', 'rejected'], sorted(results))
        with Chain(self.path / 'node/node.sqlite', network='regtest') as chain:
            self.assertEqual(1, len(chain.mempool_transactions()))

    def test_failed_restore_never_publishes_a_wallet(self):
        self.call('create', self.password)
        encrypted = self.call('backup', self.password)['encrypted']
        runtime.stop()
        runtime.start(self.path / 'new-node', mobile=False, network='regtest', bootstrap=False)
        self.call('foreground', 'true')
        self.rejected('restore', 'wrong-passphrase', encrypted)
        self.assertFalse((self.path / 'new-node/wallet.json').exists())
        self.rejected('restore', self.password, 'invalid-base64!')
        self.assertFalse((self.path / 'new-node/wallet.json').exists())
        self.rejected('recover', self.password, 'invalid recovery words')
        self.assertFalse((self.path / 'new-node/wallet.json').exists())

    def test_invalid_amounts_addresses_and_fees_never_enter_mempool(self):
        recipient, _ = self.funded()
        for amount in ('0', '-1', 'NaN', '1e2', '1.000000001', '18000001'):
            self.rejected('prepare', recipient.address, amount, '0')
        for fee in ('-1', 'NaN', '1.000000001'):
            self.rejected('prepare', recipient.address, '1', fee)
        self.rejected('parse_address', recipient.address[:-1] + ('q' if recipient.address[-1] != 'q' else 'p'))
        with Chain(self.path / 'node/node.sqlite', network='regtest') as chain:
            self.assertFalse(chain.mempool_transactions())

