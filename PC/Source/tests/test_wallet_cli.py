"""Wallet CLI boundaries and a recovered-key confirmed payment."""

import contextlib
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
import getpass
import warnings
from unittest.mock import patch

from sumuww.__main__ import main, create_payment
from sumuww.chain import Chain
from sumuww.keystore import create_wallet, load_wallet
from sumuww.primitives import COIN

PASSWORD = 'cli-test-password-only'
WORK = Path(os.environ.get('SUMUWW_TEST_WORKDIR', tempfile.gettempdir()))


class WalletCliTests(unittest.TestCase):
    def setUp(self):
        WORK.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(prefix='wallet-cli-', dir=WORK)
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.database = self.directory / 'chain.sqlite'
        self.wallet = self.directory / 'alice.json'
        self.password = self.directory / 'password.txt'
        self.password.write_text(PASSWORD + '\n', encoding='utf-8')

    def invoke(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = main(list(args))
        self.assertNotIn(PASSWORD, out.getvalue() + err.getvalue())
        return code, json.loads(out.getvalue() or err.getvalue())

    def wallet_call(self, command, *args, path=None):
        return self.invoke('--database', str(self.database), command, '--wallet', str(path or self.wallet), '--password-file', str(self.password), *args)

    def test_create_address_backup_restore_without_creating_database(self):
        code, created = self.wallet_call('wallet-create')
        self.assertEqual(code, 0)
        self.assertFalse(self.database.exists())
        self.assertEqual(self.wallet_call('wallet-address')[1]['address'], created['address'])
        backup, restored = self.directory / 'backup.json', self.directory / 'restored.json'
        self.assertEqual(self.wallet_call('wallet-backup', '--backup', str(backup))[0], 0)
        code, recovered = self.wallet_call('wallet-restore', '--backup', str(backup), path=restored)
        self.assertEqual(code, 0)
        self.assertEqual(created['address'], recovered['address'])
        self.assertEqual(self.wallet.read_bytes(), backup.read_bytes())
        self.assertEqual(self.wallet.read_bytes(), restored.read_bytes())
        self.assertFalse(self.database.exists())

    def test_wrong_password_send_does_not_open_database(self):
        alice = create_wallet(self.wallet, PASSWORD)
        self.password.write_text('wrong-password\n')
        code, error = self.wallet_call('wallet-send', '--to-address', alice.address, '--amount', '1')
        self.assertEqual(code, 2)
        self.assertEqual(error['error'], 'WalletAuthenticationError')
        self.assertFalse(self.database.exists())

    def test_database_and_sidecar_collisions_rejected_before_writes(self):
        for suffix in ('', '-wal', '-shm', '-journal'):
            with self.subTest(suffix=suffix):
                collision = Path(str(self.database) + suffix)
                code, _ = self.wallet_call('wallet-create', path=collision)
                self.assertEqual(code, 2)
                self.assertFalse(collision.exists())
        self.assertFalse(self.database.exists())

    def test_password_wallet_and_backup_path_collisions_preserve_files(self):
        before = self.password.read_bytes()
        code, _ = self.wallet_call('wallet-create', path=self.password)
        self.assertEqual(code, 2)
        self.assertEqual(self.password.read_bytes(), before)
        create_wallet(self.wallet, PASSWORD)
        wallet_before = self.wallet.read_bytes()
        for destination in (self.wallet, self.password):
            code, _ = self.wallet_call('wallet-backup', '--backup', str(destination))
            self.assertEqual(code, 2)
        self.assertEqual(self.wallet.read_bytes(), wallet_before)

    def test_hardlink_database_collision_rejected(self):
        self.database.write_bytes(b'preserve')
        os.link(self.database, self.wallet)
        code, _ = self.wallet_call('wallet-create')
        self.assertEqual(code, 2)
        self.assertEqual(self.database.read_bytes(), b'preserve')

    def test_invalid_address_rejected_before_database_creation(self):
        code, _ = self.invoke('--database', str(self.database), 'mine', '--address', 'invalid')
        self.assertEqual(code, 2)
        self.assertFalse(self.database.exists())

    def test_password_file_size_and_multiline_rejected(self):
        for raw in (b'X' * 1025, b'one\ntwo\n', b'\xff', b''):
            self.password.write_bytes(raw)
            code, _ = self.wallet_call('wallet-create')
            self.assertEqual(code, 2)
            self.assertFalse(self.wallet.exists())

    def test_interactive_confirmation_mismatch_does_not_write(self):
        with patch('sumuww.__main__.getpass.getpass', side_effect=[PASSWORD, 'different']):
            code, _ = self.invoke('wallet-create', '--wallet', str(self.wallet))
        self.assertEqual(code, 2)
        self.assertFalse(self.wallet.exists())

    def test_hidden_password_fallback_is_rejected_before_echo_input(self):
        def fallback(*args):
            warnings.warn('Password input may echo', getpass.GetPassWarning)
            self.fail('Fallback must stop at the warning')
        with patch('sumuww.__main__.getpass.getpass', side_effect=fallback):
            code, _ = self.invoke('wallet-create', '--wallet', str(self.wallet))
        self.assertEqual(code, 2)
        self.assertFalse(self.wallet.exists())

    def test_hex_sidecar_collision_is_rejected_before_database_writes(self):
        source = Path(str(self.database) + '-wal')
        source.write_text('preserve-input', encoding='utf-8')
        code, _ = self.invoke('--database', str(self.database), 'submit-block', '--hex-file', str(source))
        self.assertEqual(code, 2)
        self.assertEqual(source.read_text(), 'preserve-input')
        self.assertFalse(self.database.exists())

    def test_invalid_hex_input_is_rejected_before_database_creation(self):
        source = self.directory / 'block.hex'
        source.write_bytes(b'\xff')
        code, _ = self.invoke('--database', str(self.database), 'submit-block', '--hex-file', str(source))
        self.assertEqual(code, 2)
        self.assertFalse(self.database.exists())

    def test_corrupt_database_reports_json_preserves_bytes_and_closes_file(self):
        original = b'This is not an SQLite database'
        self.database.write_bytes(original)
        code, error = self.invoke('--database', str(self.database), 'info')
        self.assertEqual(code, 2)
        self.assertEqual(error['error'], 'DatabaseError')
        self.assertEqual(self.database.read_bytes(), original)
        moved = self.database.with_name('corrupt-preserved')
        self.database.rename(moved)
        self.assertEqual(moved.read_bytes(), original)

    def test_confirmed_payment_pending_exclusion_and_recovered_spend(self):
        alice = create_wallet(self.wallet, PASSWORD)
        bob_path = self.directory / 'bob.json'
        bob = create_wallet(bob_path, PASSWORD)
        with Chain(self.database) as chain:
            chain.mine(alice.script_pubkey, 100)
        code, payment = self.wallet_call('wallet-send', '--to-address', bob.address, '--amount', '3', '--fee', '0.001')
        self.assertEqual(code, 0)
        self.assertEqual(payment['from_address'], alice.address)
        # The first coinbase is now reserved by the pending payment; others are immature.
        code, _ = self.wallet_call('wallet-send', '--to-address', bob.address, '--amount', '1')
        self.assertEqual(code, 2)
        with Chain(self.database) as chain:
            self.assertEqual(len(chain.mempool_transactions()), 1)
            chain.mine(alice.script_pubkey)
            self.assertEqual(chain.balance(bob.script_pubkey), 3 * COIN)
        backup, restored = self.directory / 'backup.json', self.directory / 'restored.json'
        self.assertEqual(self.wallet_call('wallet-backup', '--backup', str(backup), path=bob_path)[0], 0)
        self.assertEqual(self.wallet_call('wallet-restore', '--backup', str(backup), path=restored)[0], 0)
        code, _ = self.wallet_call('wallet-send', '--to-address', alice.address, '--amount', '1', '--fee', '0.001', path=restored)
        self.assertEqual(code, 0)
        with Chain(self.database) as chain:
            chain.mine(alice.script_pubkey)
            self.assertEqual(chain.balance(bob.script_pubkey), 199_900_000)
        self.assertEqual(self.wallet_call('wallet-balance', path=restored)[1]['total_smw'], '1.99900000')

    def test_payment_rejects_negative_fee_and_invalid_amount(self):
        alice = create_wallet(self.wallet, PASSWORD)
        with Chain(self.database) as chain:
            for amount, fee in ((0, 0), (-1, 0), (True, 0), (1, -1), (1, True)):
                with self.subTest(amount=amount, fee=fee), self.assertRaises(ValueError):
                    create_payment(chain, alice, alice.script_pubkey, amount, fee)
            self.assertEqual(chain.info()['mempool'], 0)


if __name__ == '__main__':
    unittest.main()
