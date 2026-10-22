"""V2 recovery and authenticated metadata; every mnemonic is a public fixture."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from coincurve import PublicKey
from sumuww.hd import SUMUWW_NAMESPACE, HARDENED, HDNode, entropy_to_mnemonic, mnemonic_to_seed
import sumuww.keystore as keystore
from sumuww.keystore import (HDWalletKey, WalletAuthenticationError, WalletError,
                           WalletFormatError, backup_wallet, create_hd_wallet,
                           create_wallet, export_mnemonic, load_wallet,
                           recover_hd_wallet, restore_wallet)
from sumuww.profiles import SUMUWW, REGTEST, RETARGET_LAB
from sumuww.transaction import Transaction, TxInput, TxOutput
from sumuww.wallet import RegtestKey, sign_p2wpkh, verify_p2wpkh

PASSWORD = 'Only public fixture wallet password'
ENTROPY = bytes(32)
MNEMONIC = entropy_to_mnemonic(ENTROPY)


class HDKeystoreTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture = tempfile.TemporaryDirectory(prefix='hd-keystore-public-fixture-')
        cls.path = Path(cls.fixture.name) / 'wallet.json'
        cls.key = recover_hd_wallet(cls.path, PASSWORD, MNEMONIC, network=REGTEST)
        cls.raw = cls.path.read_bytes()
        cls.envelope = json.loads(cls.raw)

    @classmethod
    def tearDownClass(cls):
        cls.fixture.cleanup()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='hd-keystore-test-')
        self.root = Path(self.temp.name)
        self.source = self.root / 'wallet.json'
        self.source.write_bytes(self.raw)

    def tearDown(self):
        self.temp.cleanup()

    def test_new_random_hd_wallets_are_distinct_and_no_implicit_seed_export(self):
        first = self.root / 'new one.json'; second = self.root / 'new two.json'
        a = create_hd_wallet(first, PASSWORD)
        b = create_hd_wallet(second, PASSWORD)
        self.assertIsInstance(a, HDWalletKey)
        self.assertTrue(a.is_hd)
        self.assertEqual(a.wallet_version, 2)
        self.assertNotEqual(a.pubkey, b.pubkey)
        envelope = json.loads(first.read_bytes())
        self.assertEqual(envelope['version'], 2)
        self.assertEqual(envelope['format'], 'sumuww-hd-wallet')
        self.assertNotIn('mnemonic', envelope)
        self.assertNotIn('seed', envelope)
        self.assertNotIn('entropy', envelope)
        self.assertNotIn('_entropy', repr(a))
        self.assertEqual(load_wallet(first, PASSWORD).pubkey, a.pubkey)

    def test_known_24_words_recover_same_first_key_with_different_file_password(self):
        fresh = self.root / 'recovered different password.json'
        restored = recover_hd_wallet(fresh, 'Different temporary wallet password', MNEMONIC)
        self.assertEqual(restored.pubkey, self.key.pubkey)
        self.assertEqual(restored.address, self.key.address)
        self.assertNotEqual(fresh.read_bytes(), self.raw)
        self.assertEqual(export_mnemonic(fresh, 'Different temporary wallet password'), MNEMONIC)
        self.assertNotIn(MNEMONIC, fresh.read_text())
        self.assertNotIn(ENTROPY.hex(), fresh.read_text())

    def test_network_hardened_accounts_match_documented_sumuww_namespace(self):
        master = HDNode.from_seed(mnemonic_to_seed(MNEMONIC))
        public_keys = []
        for profile, account in ((SUMUWW, 0), (REGTEST, 1), (RETARGET_LAB, 2)):
            path = self.root / (profile.name + '.json')
            key = recover_hd_wallet(path, PASSWORD, MNEMONIC, network=profile)
            expected_path = f"m/{SUMUWW_NAMESPACE}'/{account}'/0/0"
            self.assertEqual(key.derivation_path, expected_path)
            self.assertEqual(key.pubkey, master.derive_path(expected_path, skip_invalid=False).pubkey)
            self.assertEqual(load_wallet(path, PASSWORD, network=profile).pubkey, key.pubkey)
            public_keys.append(key.pubkey)
        self.assertEqual(len(set(public_keys)), 3)

    def test_child_receive_and_change_keys_are_distinct_stable_and_sign(self):
        key = load_wallet(self.source, PASSWORD)
        self.assertEqual(key.child(0).pubkey, key.pubkey)
        self.assertEqual(key.derive(2).pubkey, key.child(2).pubkey)
        self.assertNotEqual(key.child(0).pubkey, key.child(1).pubkey)
        self.assertNotEqual(key.child(1).pubkey, key.child(1, change=True).pubkey)
        child = key.child(19)
        digest = b'\x77' * 32
        self.assertTrue(PublicKey(child.pubkey).verify(child.sign_digest(digest), digest, hasher=None))
        for index in (True, -1, HARDENED, 1.0, None):
            with self.assertRaises(WalletError):
                key.child(index)
        with self.assertRaises(WalletError):
            key.child(0, change=1)

    def test_hd_first_key_signs_existing_native_p2wpkh_format(self):
        key = load_wallet(self.source, PASSWORD)
        spent = TxOutput(5_000_000_000, key.script_pubkey)
        payment = Transaction(2, (TxInput(b'\x99' * 32, 0),),
                              (TxOutput(4_999_990_000, RegtestKey.from_int(2).script_pubkey),))
        signed = sign_p2wpkh(payment, 0, spent, key)
        self.assertTrue(verify_p2wpkh(signed, 0, spent))
        self.assertEqual(signed.txid(), payment.txid())

    def test_export_requires_correct_password_and_v1_has_no_invented_seed(self):
        with self.assertRaises(WalletAuthenticationError):
            export_mnemonic(self.source, 'wrong temporary fixture password')
        self.assertEqual(export_mnemonic(self.source, PASSWORD), MNEMONIC)
        legacy = self.root / 'legacy.json'
        key = create_wallet(legacy, PASSWORD)
        before = legacy.read_bytes()
        self.assertFalse(key.is_hd)
        self.assertEqual(key.wallet_version, 1)
        with self.assertRaises(WalletError):
            export_mnemonic(legacy, PASSWORD)
        backup = self.root / 'legacy backup.json'
        backup_wallet(legacy, backup, PASSWORD)
        self.assertEqual(before, legacy.read_bytes())
        self.assertEqual(before, backup.read_bytes())
        self.assertEqual(load_wallet(legacy, PASSWORD).pubkey, key.pubkey)

    def test_export_compares_expected_public_identity_to_the_single_loaded_snapshot(self):
        with patch('sumuww.keystore.load_wallet', wraps=load_wallet) as observed:
            phrase = export_mnemonic(self.source, PASSWORD, expected_script=self.key.script_pubkey)
            self.assertEqual(phrase, MNEMONIC)
            self.assertEqual(observed.call_count, 1)
        with self.assertRaisesRegex(WalletError, 'changed since it was opened'):
            export_mnemonic(self.source, PASSWORD, expected_script=RegtestKey.from_int(2).script_pubkey)
        for expected in (b'', b'wrong', bytearray(self.key.script_pubkey), 'private fixture text'):
            with patch('sumuww.keystore.load_wallet', side_effect=AssertionError('No file read for malformed expectation')):
                with self.assertRaises(WalletError):
                    export_mnemonic(self.source, PASSWORD, expected_script=expected)

    def test_v2_encrypted_backup_restore_preserve_every_byte_and_first_key(self):
        backup = self.root / 'backup.json'; recovered = self.root / 'restored.json'
        backup_wallet(self.source, backup, PASSWORD)
        key = restore_wallet(backup, recovered, PASSWORD)
        self.assertEqual(backup.read_bytes(), self.raw)
        self.assertEqual(recovered.read_bytes(), self.raw)
        self.assertEqual(key.pubkey, self.key.pubkey)
        self.assertEqual(export_mnemonic(recovered, PASSWORD), MNEMONIC)

    def test_backup_expected_identity_uses_one_snapshot_and_mismatch_publishes_nothing(self):
        destination = self.root / 'selected backup.json'
        with patch('sumuww.keystore._read_wallet', wraps=keystore._read_wallet) as observed:
            backup_wallet(self.source, destination, PASSWORD, expected_script=self.key.script_pubkey)
            self.assertEqual(observed.call_count, 1)
        self.assertEqual(destination.read_bytes(), self.raw)
        missing = self.root / 'must not exist.json'
        with self.assertRaisesRegex(WalletError, 'changed since it was opened'):
            backup_wallet(self.source, missing, PASSWORD, expected_script=RegtestKey.from_int(3).script_pubkey)
        self.assertFalse(missing.exists())

    def test_wrong_restore_password_and_existing_destinations_publish_nothing(self):
        output = self.root / 'missing.json'
        with self.assertRaises(WalletAuthenticationError):
            restore_wallet(self.source, output, 'wrong fixture password')
        self.assertFalse(output.exists())
        for operation in (lambda: create_hd_wallet(self.source, PASSWORD),
                          lambda: recover_hd_wallet(self.source, PASSWORD, MNEMONIC),
                          lambda: restore_wallet(self.source, self.source, PASSWORD)):
            with self.assertRaises(WalletError):
                operation()
        self.assertEqual(self.source.read_bytes(), self.raw)

    def test_v2_network_genesis_path_wordlist_and_metadata_types_reject_before_kdf(self):
        changes = [('network', 'dora'), ('genesis_hash', '00' * 32),
                   ('version', True), ('format', 'dora-single-key-wallet')]
        for name, value in changes:
            changed = deepcopy(self.envelope); changed[name] = value
            self.source.write_text(json.dumps(changed))
            with patch('sumuww.keystore._derive_key', side_effect=AssertionError('KDF must not run')):
                with self.assertRaises(WalletFormatError):
                    load_wallet(self.source, PASSWORD)
        for name, value in (('path', "m/0'/0/0"), ('namespace', 0), ('account', True),
                            ('passphrase', 0), ('wordlist', 'korean'), ('entropy_bits', 128)):
            changed = deepcopy(self.envelope); changed['hd'][name] = value
            self.source.write_text(json.dumps(changed))
            with patch('sumuww.keystore._derive_key', side_effect=AssertionError('KDF must not run')):
                with self.assertRaises(WalletFormatError):
                    load_wallet(self.source, PASSWORD)

    def test_v2_public_key_kdf_salt_nonce_and_ciphertext_are_authenticated(self):
        for field in ('public_key', 'salt', 'nonce', 'ciphertext'):
            changed = deepcopy(self.envelope)
            if field == 'public_key':
                changed[field] = RegtestKey.from_int(3).pubkey.hex()
            else:
                section = changed['kdf'] if field == 'salt' else changed['cipher']
                value = section[field]
                section[field] = ('0' if value[0] != '0' else '1') + value[1:]
            self.source.write_text(json.dumps(changed))
            with self.assertRaises(WalletAuthenticationError):
                load_wallet(self.source, PASSWORD)

    def test_recovery_rejects_bad_count_checksum_extra_passphrase_and_short_password(self):
        for phrase in ('abandon ' * 24, entropy_to_mnemonic(bytes(16)), 'bad ' * 24):
            with self.assertRaises(WalletFormatError):
                recover_hd_wallet(self.root / 'not created.json', PASSWORD, phrase)
        with self.assertRaises(WalletError):
            recover_hd_wallet(self.root / 'not created.json', PASSWORD, MNEMONIC, passphrase='TREZOR')
        with self.assertRaises(WalletError):
            create_hd_wallet(self.root / 'not created.json', 'short')
        self.assertFalse((self.root / 'not created.json').exists())

    def test_v2_exact_json_schema_and_repr_do_not_emit_recovery_secret(self):
        changed = deepcopy(self.envelope); changed['hd']['unexpected'] = 1
        self.source.write_text(json.dumps(changed))
        with self.assertRaises(WalletFormatError):
            load_wallet(self.source, PASSWORD)
        self.assertNotIn(MNEMONIC, repr(self.key))
        self.assertNotIn(ENTROPY.hex(), repr(self.key))
        self.assertIn(self.key.address, repr(self.key))


if __name__ == '__main__':
    unittest.main()
