"""Seed recovery through real actors, confirmed payments and safe CLI outputs."""
import contextlib
import io
import json
from pathlib import Path
import shutil
import tempfile
import unittest

from sumuww.__main__ import main
from sumuww.app_service import AppService, AppServiceError
from sumuww.keystore import create_hd_wallet
from sumuww.profiles import REGTEST

PASSWORD = 'test-seed-password-only'
RECOVERED_PASSWORD = 'a-new-test-password'


class SeedServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='sumuww-seed-service-')
        self.directory = Path(self.temp.name)
        self.service = AppService(self.directory / 'node', network=REGTEST, peers=[])
        self.service.start().result(timeout=10)

    def tearDown(self):
        self.service.stop().result(timeout=15)
        self.temp.cleanup()

    def test_seed_recovery_after_file_loss_preserves_address_and_spends_confirmed_balance(self):
        original = self.directory / 'original.json'
        wallet = self.service.create_seed_wallet(original, PASSWORD).result(timeout=10)
        phrase = self.service.recovery_phrase(PASSWORD).result(timeout=10)
        self.assertEqual(24, len(phrase.split()))
        self.assertEqual('hd', wallet['kind'])
        self.assertNotIn(phrase, json.dumps(self.service.status().result(timeout=10)))
        with self.assertRaisesRegex(AppServiceError, 'WalletAuthenticationError'):
            self.service.recovery_phrase('incorrect').result(timeout=10)
        for _ in range(100):
            self.service.mine_one().result(timeout=10)
        self.service.lock_wallet().result(timeout=10)
        original.unlink()
        recovered = self.directory / 'USB 외장 저장장치' / 'restored.json'
        recovered.parent.mkdir()
        again = self.service.recover_seed_wallet(recovered, RECOVERED_PASSWORD, phrase).result(timeout=10)
        self.assertEqual(wallet['address'], again['address'])
        self.assertEqual(phrase, self.service.recovery_phrase(RECOVERED_PASSWORD).result(timeout=10))
        recipient = self.service.create_wallet(self.directory / 'recipient.json', PASSWORD).result(timeout=10)
        self.service.open_wallet(recovered, RECOVERED_PASSWORD).result(timeout=10)
        sent = self.service.send(recipient['address'], '1', '0.001').result(timeout=10)
        self.assertIn('txid', sent)
        self.service.mine_one().result(timeout=10)
        status = self.service.status().result(timeout=10)
        self.assertEqual('0.00000000', status['wallet']['pending_smw'])
        self.assertTrue(any(item['txid'] == sent['txid'] and item['confirmations'] == 1
                            for item in status['transactions']))

    def test_file_move_backup_restore_and_selected_wallet_replacement_guard(self):
        path = self.directory / 'seed.json'
        wallet = self.service.create_seed_wallet(path, PASSWORD).result(timeout=10)
        phrase = self.service.recovery_phrase(PASSWORD).result(timeout=10)
        locked = self.service.lock_wallet().result(timeout=10)
        self.assertEqual('hd', locked['kind'])
        self.assertEqual(phrase, self.service.recovery_phrase(PASSWORD).result(timeout=10))
        moved = self.directory / '다른 저장 위치' / 'renamed.json'
        moved.parent.mkdir()
        shutil.move(str(path), moved)
        self.assertEqual(wallet['address'], self.service.open_wallet(moved, PASSWORD).result(timeout=10)['address'])
        backup = self.directory / 'backup.json'
        self.service.backup_wallet(backup, PASSWORD).result(timeout=10)
        self.assertEqual(moved.read_bytes(), backup.read_bytes())
        restored = self.directory / 'restored.json'
        self.assertEqual(wallet['address'], self.service.restore_wallet(backup, restored, PASSWORD).result(timeout=10)['address'])
        restored.unlink()
        create_hd_wallet(restored, PASSWORD, network=REGTEST)
        with self.assertRaisesRegex(AppServiceError, 'wallet file has changed'):
            self.service.recovery_phrase(PASSWORD).result(timeout=10)

    def test_legacy_wallet_has_no_invented_seed_and_recovery_paths_are_guarded(self):
        wallet = self.service.create_wallet(self.directory / 'legacy.json', PASSWORD).result(timeout=10)
        self.assertEqual('single_key', wallet['kind'])
        with self.assertRaises(AppServiceError):
            self.service.recovery_phrase(PASSWORD).result(timeout=10)
        for reserved in ('node.sqlite', 'node.sqlite-wal', 'network-settings.json', 'rpc-token'):
            with self.subTest(reserved=reserved):
                path = self.service.directory / reserved
                before = path.read_bytes() if path.exists() else None
                with self.assertRaises(AppServiceError):
                    self.service.create_seed_wallet(path, PASSWORD).result(timeout=10)
                self.assertEqual(before, path.read_bytes() if path.exists() else None)


class SeedCliTests(unittest.TestCase):
    def test_private_export_recover_and_collision_preserve_files(self):
        with tempfile.TemporaryDirectory(prefix='sumuww-seed-cli-') as directory:
            folder = Path(directory)
            password = folder / 'password.txt'
            password.write_text(PASSWORD, encoding='utf-8')
            wallet, output, recovered = (folder / name for name in ('wallet.json', 'words.txt', 'recovered.json'))
            def call(command, path=wallet, *extra):
                stdout, stderr = io.StringIO(), io.StringIO()
                with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                    code = main([command, '--wallet', str(path), '--password-file', str(password), *extra])
                self.assertNotIn(PASSWORD, stdout.getvalue() + stderr.getvalue())
                return code, json.loads(stdout.getvalue() or stderr.getvalue())
            code, created = call('wallet-create', wallet, '--hd')
            self.assertEqual(0, code)
            self.assertTrue(created['hd'])
            self.assertFalse(created['single_key'])
            code, exported = call('wallet-export-seed', wallet, '--phrase-output', str(output))
            self.assertEqual(0, code)
            phrase = output.read_text(encoding='utf-8').strip()
            self.assertEqual(24, len(phrase.split()))
            self.assertNotIn(phrase, json.dumps(exported))
            code, restored = call('wallet-recover-seed', recovered, '--phrase-file', str(output))
            self.assertEqual(0, code)
            self.assertEqual(created['address'], restored['address'])
            before = wallet.read_bytes()
            self.assertEqual(2, call('wallet-export-seed', wallet, '--phrase-output', str(wallet))[0])
            self.assertEqual(before, wallet.read_bytes())
            self.assertEqual(2, call('wallet-export-seed', wallet, '--phrase-output', str(output))[0])
            self.assertEqual(phrase, output.read_text(encoding='utf-8').strip())


if __name__ == '__main__':
    unittest.main()
