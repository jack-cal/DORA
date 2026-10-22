"""Wallet/state-path collisions and preservation using owned local fixtures.

All wallet files, passwords, settings and chains are temporary. These tests do
not inspect the active user data directory, use public networking or mine.
"""

import contextlib
import io
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from sumuww.__main__ import _guard_paths, main
from sumuww.app_service import AppService, AppServiceError
from sumuww.keystore import (create_hd_wallet, create_wallet, load_wallet,
                           export_mnemonic, recover_hd_wallet, MAX_WALLET_BYTES)
from sumuww.network_settings import _atomic_json, save_settings
from sumuww.node_manager import NodeMonitor
from sumuww.peer_discovery import PeerAddressBook
from sumuww.profiles import REGTEST
from sumuww.wallet_paths import (NODE_PREFERENCE_NAMES, reserved_node_paths,
                               reject_wallet_overwrite, _MAX_WALLET_BYTES)


PASSWORD = 'owned-wallet-path-password'


class WalletPathFixtures(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='sumuww-wallet-path-v36-')
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        profile = patch.dict(os.environ, {'LOCALAPPDATA': str(self.folder / 'profile')})
        profile.start()
        self.addCleanup(profile.stop)
        self.node = self.folder / 'node'
        self.node.mkdir()
        self.database = self.node / 'node.sqlite'
        self.password = self.folder / 'owned-password.txt'
        self.password.write_text(PASSWORD, encoding='utf-8')

    def call(self, *arguments):
        output, error = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(error):
            code = main(list(arguments))
        self.assertNotIn(PASSWORD, output.getvalue() + error.getvalue())
        return code, json.loads(output.getvalue() or error.getvalue())

    def create_cli(self, wallet, *, database=True, hd=False):
        args = ['--network', 'regtest']
        if database:
            args += ['--database', str(self.database)]
        args += ['wallet-create', '--wallet', str(wallet), '--password-file', str(self.password)]
        if hd:
            args.append('--hd')
        return self.call(*args)

    def service(self):
        service = AppService(self.node, network=REGTEST, peers=[])
        service.start().result(timeout=10)
        self.addCleanup(lambda: service.stop().result(timeout=15))
        return service


class CliWalletPathTests(WalletPathFixtures):
    def test_rpc_collision_is_rejected_before_settings_can_destroy_new_wallet(self):
        wallet = self.node / 'rpc-settings.json'
        code, error = self.create_cli(wallet)
        self.assertEqual(2, code)
        self.assertEqual('ValueError', error['error'])
        self.assertFalse(wallet.exists())
        service = self.service()
        service.configure_rpc(False, 0).result(timeout=10)
        self.assertEqual({'schema_version': 1, 'enabled': False, 'port': 0},
                         json.loads(wallet.read_bytes()))
        self.assertFalse(any(self.node.glob('.sumuww-wallet-*.tmp')))

    def test_explicit_database_reserves_all_preferences_caches_and_policy_files(self):
        self.database = self.node / 'custom-chain.sqlite'
        reserved = reserved_node_paths(self.database)
        self.assertIn(self.node / 'custom-chain.sqlite.peers.json', reserved)
        self.assertIn(self.node / 'custom-chain.sqlite.chain-safety.json', reserved)
        for destination in reserved:
            with self.subTest(destination=destination.name):
                code, _ = self.create_cli(destination)
                self.assertEqual(2, code)
                self.assertFalse(destination.exists())
        self.assertFalse(self.database.exists())

    def test_wallet_only_commands_reserve_basic_node_names_without_active_user_lookup(self):
        with patch('sumuww.network_settings.default_directory', side_effect=AssertionError('User state read')):
            for destination in reserved_node_paths(self.database):
                with self.subTest(destination=destination.name):
                    self.assertEqual(2, self.create_cli(destination, database=False)[0])
                    self.assertFalse(destination.exists())

    def test_relative_case_and_dot_aliases_reject_before_password_input(self):
        self.database = self.node / 'node.sqlite'
        alias = self.node / 'unused' / '..' / 'rpc-settings.json'
        with patch('sumuww.__main__._password', side_effect=AssertionError('Password read')):
            self.assertEqual(2, self.create_cli(alias)[0])
            if os.name == 'nt':
                self.assertEqual(2, self.create_cli(self.node / 'RPC-SETTINGS.JSON')[0])
            with contextlib.chdir(self.folder):
                self.assertEqual(2, self.create_cli(Path('node') / 'rpc-settings.json')[0])
        self.assertFalse((self.node / 'rpc-settings.json').exists())

    def test_existing_hardlink_wallet_alias_rejected_without_reading_or_changing_ciphertext(self):
        reserved = self.node / 'rpc-settings.json'
        key = create_wallet(reserved, PASSWORD, network=REGTEST)
        alias = self.folder / 'ordinary-looking-wallet.json'
        os.link(reserved, alias)
        original = reserved.read_bytes()
        with patch('sumuww.__main__.load_wallet', side_effect=AssertionError('Wallet read')):
            code, _ = self.call('--database', str(self.database), 'wallet-address',
                                '--wallet', str(alias), '--password-file', str(self.password))
        self.assertEqual(2, code)
        self.assertEqual(original, reserved.read_bytes())
        self.assertEqual(original, alias.read_bytes())
        self.assertEqual(key.address, load_wallet(alias, PASSWORD, network=REGTEST).address)

    def test_all_secret_input_output_roles_are_reserved_before_any_file_read(self):
        reserved = self.node / 'rpc-token'
        reserved.write_bytes(b'owned-token-file-preserve')
        before = reserved.read_bytes()
        for role in ('wallet', 'backup', 'password_file', 'hex_file', 'phrase_file', 'phrase_output'):
            arguments = SimpleNamespace(database=self.database,
                **{name: (reserved if name == role else None) for name in
                   ('wallet', 'backup', 'password_file', 'hex_file', 'phrase_file', 'phrase_output')})
            with self.subTest(role=role), self.assertRaises(ValueError):
                _guard_paths(arguments)
        self.assertEqual(before, reserved.read_bytes())
        self.assertFalse(self.database.exists())

    def test_ordinary_unicode_external_folder_v1_v2_backups_restore_and_seed_recovery(self):
        # This is an NTFS folder fixture. It makes no physical USB/cloud claim.
        external = self.folder / 'USB 외장 저장 위치'
        external.mkdir()
        for hd in (False, True):
            with self.subTest(hd=hd):
                wallet = external / ('seed.json' if hd else 'wallet.json')
                code, created = self.create_cli(wallet, database=False, hd=hd)
                self.assertEqual(0, code)
                backup, restored = external / (wallet.stem + '.backup.json'), external / (wallet.stem + '.restored.json')
                self.assertEqual(0, self.call('wallet-backup', '--wallet', str(wallet),
                    '--backup', str(backup), '--password-file', str(self.password))[0])
                code, again = self.call('wallet-restore', '--wallet', str(restored),
                    '--backup', str(backup), '--password-file', str(self.password))
                self.assertEqual(0, code)
                self.assertEqual(created['address'], again['address'])
                self.assertEqual(wallet.read_bytes(), backup.read_bytes())
                self.assertEqual(wallet.read_bytes(), restored.read_bytes())
                if hd:
                    phrase = export_mnemonic(wallet, PASSWORD, network=REGTEST)
                    recovered = recover_hd_wallet(external / 'recovered.json',
                        'owned-new-wallet-password', phrase, network=REGTEST)
                    self.assertEqual(created['address'], recovered.address)
                    self.assertNotIn(phrase, wallet.read_text(encoding='utf-8'))
        self.assertFalse(self.database.exists())


class PublicFirewallPathTests(WalletPathFixtures):
    def record(self):
        return Path(os.environ['LOCALAPPDATA']) / 'SUMUWW' / 'public-firewall.json'

    def test_profile_record_reserved_with_external_database_and_wallet_only_cli(self):
        record = self.record()
        self.assertNotEqual(record.parent, self.database.parent)
        self.assertIn(record, reserved_node_paths(self.database))
        with patch('sumuww.__main__._password', side_effect=AssertionError('Password read')):
            for explicit_database in (False, True):
                with self.subTest(explicit_database=explicit_database):
                    self.assertEqual(2, self.create_cli(record, database=explicit_database)[0])
        self.assertFalse(record.exists())
        self.assertFalse(self.database.exists())
        service = self.service()
        with self.assertRaises(AppServiceError):
            service.create_wallet(record, PASSWORD).result(timeout=10)
        self.assertFalse(record.exists())

    def test_profile_record_reserves_all_secret_roles_and_hardlink_alias(self):
        record = self.record()
        record.parent.mkdir(parents=True)
        create_wallet(record, PASSWORD, network=REGTEST)
        original = record.read_bytes()
        alias = self.folder / 'ordinary-wallet-alias.json'
        os.link(record, alias)
        service = self.service()
        for path in (record, alias):
            for role in ('wallet', 'backup', 'password_file', 'hex_file', 'phrase_file', 'phrase_output'):
                args = SimpleNamespace(database=self.database, **{role: path})
                with self.subTest(role=role, path=path), self.assertRaises(ValueError):
                    _guard_paths(args)
            with self.assertRaises(AppServiceError):
                service._guard_paths(path)
        self.assertEqual(original, record.read_bytes())
        self.assertEqual(original, alias.read_bytes())
        self.assertTrue(load_wallet(record, PASSWORD, network=REGTEST).address)

    def test_profile_record_symlink_alias_is_reserved_before_file_creation(self):
        record = self.record()
        alias = self.folder / 'ordinary-wallet-symlink.json'
        try:
            alias.symlink_to(record)
        except OSError as error:
            if os.name == 'nt' and error.winerror == 1314:
                self.skipTest('Windows symbolic-link privilege is unavailable')
            raise
        with self.assertRaises(ValueError):
            _guard_paths(SimpleNamespace(database=self.database, wallet=alias))
        service = self.service()
        with self.assertRaises(AppServiceError):
            service._guard_paths(alias)
        self.assertFalse(record.exists())

    def test_same_filename_outside_profile_remains_a_valid_wallet_location(self):
        wallet = self.folder / 'external storage' / 'public-firewall.json'
        code, created = self.create_cli(wallet, database=False)
        self.assertEqual(0, code)
        self.assertEqual(created['address'], load_wallet(wallet, PASSWORD, network=REGTEST).address)
        service = self.service()
        service._guard_paths(wallet)
        self.assertFalse(self.record().exists())


class LegacyWalletPreservationTests(WalletPathFixtures):
    def encrypted_bytes(self, hd):
        path = self.folder / ('fixture-seed.json' if hd else 'fixture-wallet.json')
        (create_hd_wallet if hd else create_wallet)(path, PASSWORD, network=REGTEST)
        return path.read_bytes()

    def test_actual_rpc_preferences_keep_legacy_reserved_v1_and_v2_wallets_unchanged(self):
        for hd in (False, True):
            with self.subTest(hd=hd):
                wallet = self.node / 'rpc-settings.json'
                wallet.write_bytes(self.encrypted_bytes(hd))
                original = wallet.read_bytes()
                service = self.service()
                with self.assertRaisesRegex(AppServiceError, 'must not overwrite an encrypted wallet'):
                    service.configure_rpc(False, 0).result(timeout=10)
                self.assertEqual(original, wallet.read_bytes())
                self.assertEqual(hd, load_wallet(wallet, PASSWORD, network=REGTEST).is_hd)
                self.assertEqual(18443, service.status().result(timeout=10)['rpc']['port'])
                service.stop().result(timeout=15)

    def test_network_own_address_public_contact_and_monitor_settings_preserve_legacy_wallets(self):
        for hd in (False, True):
            raw = self.encrypted_bytes(hd)
            for name in ('network-settings.json', 'own-address-settings.json', 'public-contact.json', 'monitor-settings.json'):
                with self.subTest(hd=hd, name=name):
                    for other in NODE_PREFERENCE_NAMES:
                        (self.node / other).unlink(missing_ok=True)
                    service = AppService(self.node, network=REGTEST, peers=[])
                    path = self.node / name
                    path.write_bytes(raw)
                    if name == 'monitor-settings.json':
                        monitor = NodeMonitor(self.node, network='regtest', peers=[])
                        try:
                            with self.assertRaisesRegex(ValueError, 'must not overwrite an encrypted wallet'):
                                monitor.configure([], allow_lan=True)
                        finally:
                            monitor.close()
                    else:
                        # Exercise the real writer chain without starting a node
                        # from deliberately malformed preference documents.
                        settings = {'schema_version': 1, 'listen': '127.0.0.1:0',
                                    'peers': [], 'allow_lan': True, 'allow_internet': False}
                        with self.assertRaisesRegex(ValueError, 'must not overwrite an encrypted wallet'):
                            service._persist_network(settings, '', automatic=True)
                    self.assertEqual(raw, path.read_bytes())
                    self.assertEqual(hd, load_wallet(path, PASSWORD, network=REGTEST).is_hd)

    def test_peer_cache_and_temporary_cache_preserve_legacy_wallet_bytes(self):
        cache = self.node / 'node.sqlite.peers.json'
        temporary = self.node / 'node.sqlite.peers.json.tmp'
        for hd in (False, True):
            raw = self.encrypted_bytes(hd)
            for protected in (cache, temporary):
                with self.subTest(hd=hd, protected=protected.name):
                    cache.unlink(missing_ok=True)
                    temporary.unlink(missing_ok=True)
                    protected.write_bytes(raw)
                    book = PeerAddressBook(cache, REGTEST.profile_id,
                        REGTEST.genesis.block_hash(), scope='loopback')
                    book.verified(('127.0.0.1', 18444))
                    self.assertEqual('ValueError', book.write_error)
                    self.assertEqual(raw, protected.read_bytes())
                    self.assertEqual(hd, load_wallet(protected, PASSWORD, network=REGTEST).is_hd)
                    if protected == cache:
                        self.assertFalse(temporary.exists())
                    else:
                        self.assertFalse(cache.exists())

    def test_hardlinked_wallet_is_preserved_by_settings_and_cache_writers(self):
        wallet = self.folder / 'ordinary-wallet.json'
        create_wallet(wallet, PASSWORD, network=REGTEST)
        raw = wallet.read_bytes()
        setting = self.node / 'rpc-settings.json'
        os.link(wallet, setting)
        with self.assertRaisesRegex(ValueError, 'must not overwrite an encrypted wallet'):
            _atomic_json(setting, {'schema_version': 1, 'enabled': False, 'port': 0})
        cache = self.node / 'node.sqlite.peers.json'
        os.link(wallet, cache)
        book = PeerAddressBook(cache, REGTEST.profile_id, REGTEST.genesis.block_hash(), scope='loopback')
        book.verified(('127.0.0.1', 18444))
        self.assertEqual('ValueError', book.write_error)
        self.assertEqual(raw, wallet.read_bytes())
        self.assertEqual(raw, setting.read_bytes())
        self.assertEqual(raw, cache.read_bytes())

    def test_replacement_wallet_appearing_during_settings_write_is_preserved(self):
        raw = self.encrypted_bytes(False)
        target = self.node / 'rpc-settings.json'
        original_fsync = os.fsync
        def appeared(descriptor):
            original_fsync(descriptor)
            target.write_bytes(raw)
        with patch('sumuww.network_settings.os.fsync', side_effect=appeared):
            with self.assertRaisesRegex(ValueError, 'must not overwrite an encrypted wallet'):
                _atomic_json(target, {'schema_version': 1, 'enabled': False, 'port': 0})
        self.assertEqual(raw, target.read_bytes())
        self.assertEqual([], list(self.node.glob('rpc-settings.json.*.tmp')))

    def test_bounded_format_detection_never_derives_or_decrypts_and_normal_settings_still_save(self):
        self.assertEqual(MAX_WALLET_BYTES, _MAX_WALLET_BYTES)
        target = self.node / 'rpc-settings.json'
        # Recognizable format is conservatively protected even if incomplete.
        with patch('sumuww.keystore._derive_key', side_effect=AssertionError('KDF used')):
            for format_name in ('dora-single-key-wallet', 'dora-hd-wallet'):
                raw = json.dumps({'format': format_name}).encode('utf-8')
                target.write_bytes(raw)
                with self.assertRaises(ValueError):
                    reject_wallet_overwrite(target)
                self.assertEqual(raw, target.read_bytes())
        for raw in (b'{malformed', b'{}', b'X' * 5000):
            target.write_bytes(raw)
            _atomic_json(target, {'schema_version': 1, 'enabled': False, 'port': 0})
            self.assertEqual(0, json.loads(target.read_bytes())['port'])
        settings = {'schema_version': 1, 'listen': '127.0.0.1:0', 'peers': [],
                    'allow_lan': False, 'allow_internet': False}
        save_settings(self.node, settings)
        self.assertEqual(settings, json.loads((self.node / 'network-settings.json').read_bytes()))

    def test_gui_uses_same_reserved_paths_and_preserves_ordinary_wallet_under_rpc_updates(self):
        service = self.service()
        for path in reserved_node_paths(self.database):
            with self.subTest(path=path.name), self.assertRaises(AppServiceError):
                service._guard_paths(path)
        ordinary = self.folder / 'USB 외장 저장 위치' / 'wallet.json'
        created = service.create_wallet(ordinary, PASSWORD).result(timeout=10)
        original = ordinary.read_bytes()
        service.configure_rpc(False, 0).result(timeout=10)
        self.assertEqual(original, ordinary.read_bytes())
        self.assertEqual(created['address'], load_wallet(ordinary, PASSWORD, network=REGTEST).address)

    def test_gui_explicit_external_bootstrap_hardlink_is_reserved_without_changing_wallet(self):
        manifest = self.folder / 'external-bootstrap-fixture.json'
        create_wallet(manifest, PASSWORD, network=REGTEST)
        original = manifest.read_bytes()
        alias = self.folder / 'external-alias.json'
        os.link(manifest, alias)
        service = AppService(self.node, network=REGTEST, peers=[], bootstrap_manifest=manifest)
        with self.assertRaises(AppServiceError):
            service._guard_paths(alias)
        self.assertEqual(original, manifest.read_bytes())
        self.assertEqual(original, alias.read_bytes())


if __name__ == '__main__':
    unittest.main()
