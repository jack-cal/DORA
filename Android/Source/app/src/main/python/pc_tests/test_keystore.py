"""Real encryption/signing and bounded, exclusive keystore failure paths.

These tests inject ordinary I/O failures; they do not simulate hardware power
loss or claim process-memory secret erasure or independently audited custody.
"""

from copy import deepcopy
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from coincurve import PublicKey

from sumuww.address import decode_address
from sumuww.keystore import MAX_PASSWORD_BYTES, MAX_WALLET_BYTES, SCRYPT_DKLEN, SCRYPT_MAXMEM, SCRYPT_N, SCRYPT_P, SCRYPT_R, WalletAuthenticationError, WalletError, WalletFormatError, backup_wallet, create_wallet, load_wallet, restore_wallet
from sumuww.transaction import Transaction, TxInput, TxOutput
from sumuww.wallet import RegtestKey, SECP256K1_ORDER, sign_p2wpkh, verify_p2wpkh

PASSWORD = "local wallet password 2026"
PUBLICATION_PRIMITIVE = "sumuww.keystore.os.rename" if os.name == "nt" else "sumuww.keystore.os.link"


class KeystoreTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture_directory = tempfile.TemporaryDirectory(prefix="sumuww-keystore-fixture-", dir=os.environ.get("SUMUWW_TEST_WORKDIR"))
        cls.fixture_path = Path(cls.fixture_directory.name) / "fixture.json"
        cls.fixture_key = create_wallet(cls.fixture_path, PASSWORD)
        cls.fixture_raw = cls.fixture_path.read_bytes()
        cls.fixture_envelope = json.loads(cls.fixture_raw)

    @classmethod
    def tearDownClass(cls):
        cls.fixture_directory.cleanup()

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="sumuww-keystore-test-", dir=os.environ.get("SUMUWW_TEST_WORKDIR"))
        self.root = Path(self.directory.name)
        self.source = self.root / "wallet.json"
        self.source.write_bytes(self.fixture_raw)

    def tearDown(self):
        self.directory.cleanup()

    def write_envelope(self, envelope):
        self.source.write_text(json.dumps(envelope), encoding="utf-8")

    def assert_no_temporary_files(self):
        self.assertEqual(list(self.root.glob(".*wallet-*.tmp")), [])

    def test_load_address_and_real_signature(self):
        key = load_wallet(self.source, PASSWORD)
        self.assertEqual(key.pubkey, self.fixture_key.pubkey)
        self.assertEqual(decode_address(key.address), key.script_pubkey)
        digest = bytes.fromhex("23" * 32)
        self.assertTrue(PublicKey(key.pubkey).verify(key.sign_digest(digest), digest, hasher=None))
        self.assertIn(key.address, repr(key))
        self.assertNotIn("PrivateKey", repr(key))
        self.assertNotIn(PASSWORD, repr(key))

    def test_wallet_key_signs_existing_p2wpkh_transaction(self):
        key = load_wallet(self.source, PASSWORD)
        spent = TxOutput(5_000_000_000, key.script_pubkey)
        tx = Transaction(2, (TxInput(bytes.fromhex("41" * 32), 0),), (TxOutput(4_999_990_000, RegtestKey.from_int(2).script_pubkey),))
        signed = sign_p2wpkh(tx, 0, spent, key)
        self.assertTrue(verify_p2wpkh(signed, 0, spent))
        self.assertEqual(signed.txid(), tx.txid())

    def test_new_wallets_use_distinct_random_keys_salts_and_nonces(self):
        first_path, second_path = self.root / "a.json", self.root / "b.json"
        first = create_wallet(first_path, PASSWORD)
        second = create_wallet(second_path, PASSWORD)
        a, b = json.loads(first_path.read_bytes()), json.loads(second_path.read_bytes())
        self.assertNotEqual(first.pubkey, second.pubkey)
        self.assertNotEqual(a["kdf"]["salt"], b["kdf"]["salt"])
        self.assertNotEqual(a["cipher"]["nonce"], b["cipher"]["nonce"])
        self.assertEqual(load_wallet(first_path, PASSWORD).pubkey, first.pubkey)
        self.assertEqual(load_wallet(second_path, PASSWORD).pubkey, second.pubkey)

    def test_random_scalar_range_and_no_plaintext_secret_written(self):
        path = self.root / "known-key.json"
        with patch("sumuww.keystore.secrets.randbelow", return_value=0) as random_scalar:
            key = create_wallet(path, PASSWORD)
        random_scalar.assert_called_once_with(SECP256K1_ORDER - 1)
        self.assertEqual(key.pubkey, RegtestKey.from_int(1).pubkey)
        raw = path.read_bytes()
        self.assertNotIn((1).to_bytes(32, "big"), raw)
        self.assertNotIn((1).to_bytes(32, "big").hex().encode("ascii"), raw)
        self.assertNotIn(PASSWORD.encode(), raw)
        self.assertNotIn("0000000000000000000000000000000000000000000000000000000000000001", repr(key))
        self.assert_no_temporary_files()

    def test_actual_scrypt_parameters_are_fixed(self):
        import hashlib
        original = hashlib.scrypt
        with patch("sumuww.keystore.hashlib.scrypt", wraps=original) as derive:
            load_wallet(self.source, PASSWORD)
        self.assertEqual(derive.call_args.kwargs["n"], SCRYPT_N)
        self.assertEqual(derive.call_args.kwargs["r"], SCRYPT_R)
        self.assertEqual(derive.call_args.kwargs["p"], SCRYPT_P)
        self.assertEqual(derive.call_args.kwargs["dklen"], SCRYPT_DKLEN)
        self.assertEqual(derive.call_args.kwargs["maxmem"], SCRYPT_MAXMEM)
        self.assertEqual(len(derive.call_args.kwargs["salt"]), 16)

    def test_wrong_password_does_not_reveal_inputs_or_change_file(self):
        wrong = "wrong wallet password 123"
        with self.assertRaises(WalletAuthenticationError) as caught:
            load_wallet(self.source, wrong)
        self.assertNotIn(wrong, str(caught.exception))
        self.assertNotIn(PASSWORD, str(caught.exception))
        self.assertIsNone(caught.exception.__cause__)
        self.assertEqual(self.source.read_bytes(), self.fixture_raw)

    def test_ciphertext_salt_nonce_and_public_key_are_authenticated(self):
        mutations = []
        for section, field in (("cipher", "ciphertext"), ("cipher", "nonce"), ("kdf", "salt")):
            changed = deepcopy(self.fixture_envelope)
            value = bytearray.fromhex(changed[section][field])
            value[0] ^= 1
            changed[section][field] = value.hex()
            mutations.append(changed)
        changed = deepcopy(self.fixture_envelope)
        changed["public_key"] = RegtestKey.from_int(2).pubkey.hex()
        mutations.append(changed)
        for number, changed in enumerate(mutations):
            with self.subTest(mutation=number):
                self.write_envelope(changed)
                with self.assertRaises(WalletAuthenticationError):
                    load_wallet(self.source, PASSWORD)

    def test_network_genesis_type_and_version_rejected_before_kdf(self):
        mutations = {"format": "another-wallet", "version": 2, "network": "mainnet", "profile": "different-profile", "genesis_hash": "00" * 32, "address_hrp": "bc", "key_type": "secp256k1-p2tr", "witness_version": 1}
        for field, value in mutations.items():
            changed = deepcopy(self.fixture_envelope)
            changed[field] = value
            self.write_envelope(changed)
            with self.subTest(field=field), patch("sumuww.keystore._derive_key") as derive:
                with self.assertRaises(WalletFormatError):
                    load_wallet(self.source, PASSWORD)
                derive.assert_not_called()

    def test_kdf_parameter_downgrade_and_resource_attacks_rejected(self):
        for field, value in (("name", "pbkdf2"), ("n", 2), ("n", 1 << 60), ("r", 1), ("p", 100000), ("dklen", 64), ("n", True), ("r", 8.0)):
            changed = deepcopy(self.fixture_envelope)
            changed["kdf"][field] = value
            self.write_envelope(changed)
            with self.subTest(field=field, value=value), patch("sumuww.keystore._derive_key") as derive:
                with self.assertRaises(WalletFormatError):
                    load_wallet(self.source, PASSWORD)
                derive.assert_not_called()

    def test_exact_schema_and_duplicate_fields_rejected(self):
        changes = []
        for section in (None, "kdf", "cipher"):
            changed = deepcopy(self.fixture_envelope)
            target = changed if section is None else changed[section]
            target["extra"] = "unsupported"
            changes.append(changed)
            changed = deepcopy(self.fixture_envelope)
            target = changed if section is None else changed[section]
            target.pop(next(iter(target)))
            changes.append(changed)
        for changed in changes:
            self.write_envelope(changed)
            with patch("sumuww.keystore._derive_key") as derive:
                with self.assertRaises(WalletFormatError):
                    load_wallet(self.source, PASSWORD)
                derive.assert_not_called()
        for raw in (b'{"version":1,"version":1}', self.fixture_raw.replace(b'"name":"scrypt"', b'"name":"scrypt","name":"scrypt"')):
            self.source.write_bytes(raw)
            with self.assertRaises(WalletFormatError):
                load_wallet(self.source, PASSWORD)

    def test_binary_field_lengths_hex_types_and_pubkey_validity(self):
        for section, field, value in (("kdf", "salt", "00" * 15), ("cipher", "nonce", "00" * 13), ("cipher", "ciphertext", "00" * 47), ("kdf", "salt", "ff " * 16), ("kdf", "salt", "FF" * 16), ("cipher", "nonce", 123), (None, "public_key", "00" * 33), (None, "public_key", "04" + "00" * 32)):
            changed = deepcopy(self.fixture_envelope)
            target = changed if section is None else changed[section]
            target[field] = value
            self.write_envelope(changed)
            with self.subTest(field=field), patch("sumuww.keystore._derive_key") as derive:
                with self.assertRaises(WalletFormatError):
                    load_wallet(self.source, PASSWORD)
                derive.assert_not_called()

    def test_json_and_file_size_bounds(self):
        for raw in (b"", b"x" * (MAX_WALLET_BYTES + 1), b"\xff", b"[]", b"null", b"true", b"{}", b"{", b"\xef\xbb\xbf" + self.fixture_raw):
            self.source.write_bytes(raw)
            with self.subTest(size=len(raw)), patch("sumuww.keystore._derive_key") as derive:
                with self.assertRaises(WalletFormatError):
                    load_wallet(self.source, PASSWORD)
                derive.assert_not_called()
        self.source.write_bytes(self.fixture_raw + b" " * (MAX_WALLET_BYTES - len(self.fixture_raw)))
        self.assertEqual(load_wallet(self.source, PASSWORD).pubkey, self.fixture_key.pubkey)

    def test_create_password_validation_does_not_create_file(self):
        path = self.root / "invalid.json"
        for password in ("", "short", '\ud55c' * 11, "a" * (MAX_PASSWORD_BYTES + 1), '\ud55c' * 342, "\ud800" * 12, None, b"password-not-text"):
            with self.subTest(password_type=type(password).__name__), self.assertRaises(WalletError):
                create_wallet(path, password)
            self.assertFalse(path.exists())

    def test_unicode_password_exact_utf8_roundtrip(self):
        path = self.root / "unicode.json"
        password = '\ub3c4\ub77c\uac1c\uc778\ud0a4\uc9c0\uac11\uc554\ud638\uc5f4\ub450\uae00\uc790'
        key = create_wallet(path, password)
        self.assertEqual(load_wallet(path, password).pubkey, key.pubkey)

    def test_load_password_empty_oversized_invalid_type_rejected(self):
        for password in ("", "a" * 1025, "\ud800", None, b"not text"):
            with self.subTest(password_type=type(password).__name__), self.assertRaises(WalletError):
                load_wallet(self.source, password)

    def test_backup_and_restore_verify_and_preserve_ciphertext(self):
        backup = self.root / "backup.json"
        restored = self.root / "restored.json"
        self.assertEqual(backup_wallet(self.source, backup, PASSWORD).pubkey, self.fixture_key.pubkey)
        self.source.unlink()
        self.assertEqual(restore_wallet(backup, restored, PASSWORD).address, self.fixture_key.address)
        self.assertEqual(backup.read_bytes(), self.fixture_raw)
        self.assertEqual(restored.read_bytes(), self.fixture_raw)
        self.assertEqual(load_wallet(restored, PASSWORD).pubkey, self.fixture_key.pubkey)
        self.assert_no_temporary_files()

    def test_backup_restore_wrong_password_do_not_publish_destination(self):
        for operation in (backup_wallet, restore_wallet):
            destination = self.root / "rejected.json"
            with self.assertRaises(WalletAuthenticationError):
                operation(self.source, destination, "incorrect-password")
            self.assertFalse(destination.exists())
            self.assertEqual(self.source.read_bytes(), self.fixture_raw)
            self.assert_no_temporary_files()

    def test_existing_destination_is_never_overwritten(self):
        destination = self.root / "existing.json"
        destination.write_bytes(b"preserve these bytes")
        with self.assertRaises(WalletError):
            create_wallet(destination, PASSWORD)
        for operation in (backup_wallet, restore_wallet):
            with self.assertRaises(WalletError):
                operation(self.source, destination, PASSWORD)
        self.assertEqual(destination.read_bytes(), b"preserve these bytes")
        self.assert_no_temporary_files()

    def test_write_fsync_failure_leaves_no_destination_or_temporary_file(self):
        destination = self.root / "failed.json"
        with patch("sumuww.keystore.os.fsync", side_effect=OSError("injected fsync failure")):
            with self.assertRaises(OSError):
                backup_wallet(self.source, destination, PASSWORD)
        self.assertFalse(destination.exists())
        self.assert_no_temporary_files()
        self.assertEqual(self.source.read_bytes(), self.fixture_raw)

    def test_publication_failure_leaves_no_destination_or_temporary_file(self):
        destination = self.root / "failed.json"
        with patch(PUBLICATION_PRIMITIVE, side_effect=OSError("injected publication failure")):
            with self.assertRaises(OSError):
                backup_wallet(self.source, destination, PASSWORD)
        self.assertFalse(destination.exists())
        self.assert_no_temporary_files()
        self.assertEqual(self.source.read_bytes(), self.fixture_raw)

    def test_close_failure_leaves_no_destination_or_temporary_file(self):
        destination = self.root / "failed.json"
        original_fdopen = os.fdopen
        class FailingClose:
            def __init__(self, descriptor, mode):
                self.output = original_fdopen(descriptor, mode)
            def __enter__(self):
                return self.output
            def __exit__(self, *ignored):
                self.output.close()
                raise OSError("injected close failure")
        with patch("sumuww.keystore.os.fdopen", side_effect=FailingClose):
            with self.assertRaises(OSError):
                backup_wallet(self.source, destination, PASSWORD)
        self.assertFalse(destination.exists())
        self.assert_no_temporary_files()

    def test_publication_race_preserves_other_writer(self):
        publish = os.rename if os.name == "nt" else os.link
        def other_writer(source, target):
            Path(target).write_bytes(b"other writer won")
            publish(source, target)
        for operation in (backup_wallet, restore_wallet):
            destination = self.root / (operation.__name__ + "-raced.json")
            with self.subTest(operation=operation.__name__), patch(PUBLICATION_PRIMITIVE, side_effect=other_writer):
                with self.assertRaises(WalletError):
                    operation(self.source, destination, PASSWORD)
            self.assertEqual(destination.read_bytes(), b"other writer won")
            self.assertEqual(self.source.read_bytes(), self.fixture_raw)
            self.assert_no_temporary_files()

    def test_source_and_destination_alias_do_not_replace_source(self):
        with self.assertRaises(WalletError):
            backup_wallet(self.source, self.source, PASSWORD)
        self.assertEqual(self.source.read_bytes(), self.fixture_raw)
        self.assert_no_temporary_files()

    def test_existing_dangling_symlink_is_not_replaced_where_supported(self):
        destination = self.root / "dangling.json"
        try:
            destination.symlink_to(self.root / "missing.json")
        except (OSError, NotImplementedError):
            self.skipTest("symlink creation unavailable for this account")
        with self.assertRaises(WalletError):
            create_wallet(destination, PASSWORD)
        self.assertTrue(destination.is_symlink())

    def test_signing_digest_bounds_do_not_echo_input(self):
        for digest in (b"", bytes(31), bytes(33), "secret-like-text", bytearray(32)):
            with self.subTest(digest_type=type(digest).__name__), self.assertRaises(WalletError) as caught:
                self.fixture_key.sign_digest(digest)
            self.assertNotIn("secret-like-text", str(caught.exception))

    def test_authenticated_invalid_secret_and_mismatched_pubkey_rejected(self):
        # Constructing an envelope requires the password; this verifies the
        # unlocked material checks separately from GCM's corruption detection.
        from sumuww.keystore import _aad, _derive_key
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        changed = deepcopy(self.fixture_envelope)
        aes_key = _derive_key(PASSWORD.encode(), bytes.fromhex(changed["kdf"]["salt"]))
        for secret in (bytes(32), SECP256K1_ORDER.to_bytes(32, "big"), (2).to_bytes(32, "big")):
            changed["cipher"]["ciphertext"] = AESGCM(aes_key).encrypt(bytes.fromhex(changed["cipher"]["nonce"]), secret, _aad(changed)).hex()
            self.write_envelope(changed)
            with self.assertRaises(WalletFormatError):
                load_wallet(self.source, PASSWORD)


if __name__ == "__main__":
    unittest.main()
