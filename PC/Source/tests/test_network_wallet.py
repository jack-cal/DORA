"""Network-specific address/key metadata and exact v0.10 wallet compatibility.

The compatibility envelope was produced by the preserved v0.10 keystore using
public test scalar 1 and fixed test-only salt/nonce. It contains no live funds.
"""

from copy import deepcopy
from dataclasses import replace
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from coincurve import PrivateKey, PublicKey

from sumuww.address import AddressError, HRP, decode_address, encode_address
from sumuww.keystore import WalletAuthenticationError, WalletFormatError, WalletKey, backup_wallet, create_wallet, load_wallet, restore_wallet
from sumuww.primitives import hash_to_display
from sumuww.profiles import REGTEST, RETARGET_LAB
from sumuww.wallet import RegtestKey

_V10_PASSWORD = "v0.10 compatibility fixture"
_V10_ENVELOPE = {
    "address_hrp": "drt",
    "cipher": {
        "ciphertext": "486ded05fae50902f7405ac37b0f616d2a04e83d83523479713beef01b08ff914c277cc651d296b18caf41c1b32f6178",
        "name": "AES-256-GCM", "nonce": "333333333333333333333333",
    },
    "format": "dora-single-key-wallet",
    "genesis_hash": "51ff452925cf7a4350330ca73abcbf66b4e50d9e0c4641aca6e360dbde838ba0",
    "kdf": {"dklen": 32, "n": 131072, "name": "scrypt", "p": 1, "r": 8, "salt": "55555555555555555555555555555555"},
    "key_type": "secp256k1-p2wpkh", "network": "regtest",
    "profile": "dora-local-regtest-v0.8-p2wpkh",
    "public_key": "0279be667ef9dcbbac55a06295ce870b07029bfcdb2dce28d959f2815b16f81798",
    "version": 1, "witness_version": 0,
}
_V10_RAW = json.dumps(_V10_ENVELOPE, sort_keys=True, separators=(",", ":")).encode("ascii") + b"\n"
_LAB_PASSWORD = "retarget lab wallet test only"


class NetworkAddressTests(unittest.TestCase):
    def setUp(self):
        self.script = RegtestKey.from_int(1).script_pubkey

    def test_regtest_default_keeps_same_hrp_and_encoding(self):
        self.assertEqual(HRP, "drt")
        default = encode_address(self.script)
        self.assertEqual(default, encode_address(self.script, network="regtest"))
        self.assertEqual(default, encode_address(self.script, network=REGTEST))
        self.assertEqual(decode_address(default), self.script)

    def test_lab_address_roundtrip_and_uppercase(self):
        address = encode_address(self.script, network="retarget-lab")
        self.assertTrue(address.startswith("dtl1q"))
        self.assertEqual(address, encode_address(self.script, network=RETARGET_LAB))
        self.assertEqual(decode_address(address, network=RETARGET_LAB), self.script)
        self.assertEqual(decode_address(address.upper(), network="retarget-lab"), self.script)

    def test_cross_network_addresses_are_rejected(self):
        regtest = encode_address(self.script)
        lab = encode_address(self.script, network=RETARGET_LAB)
        with self.assertRaises(AddressError):
            decode_address(regtest, network=RETARGET_LAB)
        with self.assertRaises(AddressError):
            decode_address(lab)
        with self.assertRaises(AddressError):
            decode_address(lab, network=REGTEST)

    def test_unknown_or_unregistered_profile_cannot_change_address_rules(self):
        for network in ("mainnet", "", None, replace(REGTEST), replace(RETARGET_LAB)):
            with self.subTest(network_type=type(network).__name__):
                with self.assertRaises(ValueError):
                    encode_address(self.script, network=network)
                with self.assertRaises(ValueError):
                    decode_address(encode_address(self.script), network=network)

    def test_wallet_key_default_and_registered_network_are_stored(self):
        private = PrivateKey((1).to_bytes(32, "big"))
        default = WalletKey(private)
        lab = WalletKey(private, RETARGET_LAB)
        self.assertIs(default.network, REGTEST)
        self.assertIs(lab.network, RETARGET_LAB)
        self.assertEqual(default.script_pubkey, lab.script_pubkey)
        self.assertTrue(default.address.startswith("drt1"))
        self.assertTrue(lab.address.startswith("dtl1"))
        with self.assertRaises(ValueError):
            WalletKey(private, replace(RETARGET_LAB))


class NetworkWalletTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture_directory = tempfile.TemporaryDirectory(prefix="sumuww-network-wallet-fixture-", dir=os.environ.get("SUMUWW_TEST_WORKDIR"))
        cls.fixture_path = Path(cls.fixture_directory.name) / "lab.json"
        cls.lab_key = create_wallet(cls.fixture_path, _LAB_PASSWORD, network=RETARGET_LAB)
        cls.lab_raw = cls.fixture_path.read_bytes()
        cls.lab_envelope = json.loads(cls.lab_raw)

    @classmethod
    def tearDownClass(cls):
        cls.fixture_directory.cleanup()

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="sumuww-network-wallet-test-", dir=os.environ.get("SUMUWW_TEST_WORKDIR"))
        self.root = Path(self.directory.name)
        self.lab = self.root / "lab.json"
        self.regtest = self.root / "v10-regtest.json"
        self.lab.write_bytes(self.lab_raw)
        self.regtest.write_bytes(_V10_RAW)

    def tearDown(self):
        self.directory.cleanup()

    def test_old_v10_envelope_loads_without_migration(self):
        key = load_wallet(self.regtest, _V10_PASSWORD)
        self.assertIs(key.network, REGTEST)
        self.assertEqual(key.pubkey, RegtestKey.from_int(1).pubkey)
        self.assertEqual(key.address, encode_address(RegtestKey.from_int(1).script_pubkey))
        self.assertEqual(self.regtest.read_bytes(), _V10_RAW)

    def test_lab_create_load_authenticates_exact_profile_metadata(self):
        envelope = self.lab_envelope
        self.assertEqual(envelope["network"], "retarget-lab")
        self.assertEqual(envelope["profile"], RETARGET_LAB.profile_id)
        self.assertEqual(envelope["address_hrp"], "dtl")
        self.assertEqual(envelope["genesis_hash"], hash_to_display(RETARGET_LAB.genesis.block_hash()))
        self.assertNotEqual(envelope["genesis_hash"], _V10_ENVELOPE["genesis_hash"])
        key = load_wallet(self.lab, _LAB_PASSWORD, network="retarget-lab")
        self.assertIs(key.network, RETARGET_LAB)
        self.assertEqual(key.pubkey, self.lab_key.pubkey)
        digest = bytes.fromhex("48" * 32)
        self.assertTrue(PublicKey(key.pubkey).verify(key.sign_digest(digest), digest, hasher=None))
        self.assertNotIn(_LAB_PASSWORD, repr(key))

    def test_lab_backup_restore_preserve_address_and_ciphertext(self):
        backup = self.root / "lab-backup.json"
        restored = self.root / "lab-restored.json"
        backed_up = backup_wallet(self.lab, backup, _LAB_PASSWORD, network="retarget-lab")
        self.lab.unlink()
        recovered = restore_wallet(backup, restored, _LAB_PASSWORD, network=RETARGET_LAB)
        self.assertIs(backed_up.network, RETARGET_LAB)
        self.assertIs(recovered.network, RETARGET_LAB)
        self.assertEqual(recovered.address, self.lab_key.address)
        self.assertEqual(restored.read_bytes(), self.lab_raw)
        self.assertEqual(backup.read_bytes(), self.lab_raw)

    def test_cross_network_load_rejects_before_scrypt(self):
        for source, network, password in ((self.lab, REGTEST, _LAB_PASSWORD), (self.regtest, RETARGET_LAB, _V10_PASSWORD)):
            with self.subTest(network=network.name), patch("sumuww.keystore._derive_key") as derive:
                with self.assertRaises(WalletFormatError):
                    load_wallet(source, password, network=network)
                derive.assert_not_called()
        self.assertEqual(self.lab.read_bytes(), self.lab_raw)
        self.assertEqual(self.regtest.read_bytes(), _V10_RAW)

    def test_cross_network_backup_restore_never_publish_or_replace_files(self):
        for operation in (backup_wallet, restore_wallet):
            for source, network, password in ((self.lab, REGTEST, _LAB_PASSWORD), (self.regtest, RETARGET_LAB, _V10_PASSWORD)):
                for existing in (False, True):
                    destination = self.root / (operation.__name__ + network.name + str(existing) + ".json")
                    if existing:
                        destination.write_bytes(b"keep existing destination")
                    with self.subTest(operation=operation.__name__, network=network.name, existing=existing), patch("sumuww.keystore._derive_key") as derive, patch("sumuww.keystore._publish_exclusively") as publish:
                        with self.assertRaises(WalletFormatError):
                            operation(source, destination, password, network=network)
                        derive.assert_not_called()
                        publish.assert_not_called()
                    if existing:
                        self.assertEqual(destination.read_bytes(), b"keep existing destination")
                    else:
                        self.assertFalse(destination.exists())
        self.assertEqual(self.lab.read_bytes(), self.lab_raw)
        self.assertEqual(self.regtest.read_bytes(), _V10_RAW)

    def test_profile_genesis_and_prefix_tamper_reject_before_scrypt(self):
        for field in ("network", "profile", "genesis_hash", "address_hrp"):
            changed = deepcopy(self.lab_envelope)
            changed[field] = _V10_ENVELOPE[field]
            self.lab.write_text(json.dumps(changed), encoding="utf-8")
            with self.subTest(field=field), patch("sumuww.keystore._derive_key") as derive:
                with self.assertRaises(WalletFormatError):
                    load_wallet(self.lab, _LAB_PASSWORD, network=RETARGET_LAB)
                derive.assert_not_called()

    def test_relabeling_all_network_fields_is_not_a_wallet_migration(self):
        changed = deepcopy(_V10_ENVELOPE)
        changed.update(network=RETARGET_LAB.name, profile=RETARGET_LAB.profile_id,
                       genesis_hash=hash_to_display(RETARGET_LAB.genesis.block_hash()),
                       address_hrp=RETARGET_LAB.address_hrp)
        self.regtest.write_text(json.dumps(changed), encoding="utf-8")
        with self.assertRaises(WalletAuthenticationError):
            load_wallet(self.regtest, _V10_PASSWORD, network=RETARGET_LAB)

    def test_unknown_network_rejected_before_files_or_crypto(self):
        destination = self.root / "absent-directory" / "wallet.json"
        with patch("sumuww.keystore._derive_key") as derive, patch("sumuww.keystore._read_wallet") as read:
            for operation in (
                lambda: create_wallet(destination, _LAB_PASSWORD, network="mainnet"),
                lambda: load_wallet(self.lab, _LAB_PASSWORD, network="mainnet"),
                lambda: backup_wallet(self.lab, destination, _LAB_PASSWORD, network="mainnet"),
                lambda: restore_wallet(self.lab, destination, _LAB_PASSWORD, network="mainnet"),
            ):
                with self.assertRaises(ValueError):
                    operation()
            derive.assert_not_called()
            read.assert_not_called()
        self.assertFalse(destination.parent.exists())
        self.assertEqual(self.lab.read_bytes(), self.lab_raw)


if __name__ == "__main__":
    unittest.main()
