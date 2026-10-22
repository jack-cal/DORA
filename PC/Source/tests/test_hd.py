"""Published BIP32/39 vectors and malformed input; all seeds are public fixtures."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import unicodedata

from coincurve import PrivateKey
from sumuww.hd import (HARDENED, HDKeyError, HDNode, HDPublicNode, _wordlist,
                     entropy_to_mnemonic, import_extended_key, mnemonic_to_entropy,
                     mnemonic_to_seed, parse_path)
from sumuww.wallet import SECP256K1_ORDER

ROOT = Path(__file__).resolve().parents[1]
VECTORS = json.loads((ROOT / 'vectors' / 'hd_standard_vectors.json').read_text())
SEED = bytes.fromhex(VECTORS['bip32'][0]['seed_hex'])


class HDPrimitiveTests(unittest.TestCase):
    def test_all_official_bip32_vectors_include_leading_zero_derivations(self):
        for suite in VECTORS['bip32']:
            master = HDNode.from_seed(bytes.fromhex(suite['seed_hex']))
            for row in suite['keys']:
                with self.subTest(path=row['path']):
                    child = master.derive_path(row['path'])
                    self.assertEqual(child.to_extended_public(), row['xpub'])
                    self.assertEqual(child.to_extended_private(), row['xprv'])
                    self.assertEqual(import_extended_key(row['xpub']).pubkey, child.pubkey)
                    self.assertEqual(import_extended_key(row['xprv']).pubkey, child.pubkey)

    def test_official_invalid_extended_keys_rejected(self):
        self.assertEqual(len(VECTORS['bip32_invalid_extended']), 14)
        for encoded in VECTORS['bip32_invalid_extended']:
            with self.assertRaises(HDKeyError):
                import_extended_key(encoded)

    def test_all_official_english_bip39_vectors_and_master_xprv(self):
        self.assertEqual(len(VECTORS['bip39_english']), 24)
        for entropy_hex, mnemonic, seed_hex, master_xprv in VECTORS['bip39_english']:
            entropy = bytes.fromhex(entropy_hex)
            self.assertEqual(entropy_to_mnemonic(entropy), mnemonic)
            self.assertEqual(mnemonic_to_entropy(mnemonic), entropy)
            seed = mnemonic_to_seed(mnemonic, 'TREZOR')
            self.assertEqual(seed.hex(), seed_hex)
            self.assertEqual(HDNode.from_seed(seed).to_extended_private(), master_xprv)

    def test_private_and_public_nonhardened_children_match(self):
        master = HDNode.from_seed(SEED).derive_child(HARDENED)
        child = master.derive_child(7)
        public = master.neuter().derive_child(7)
        self.assertEqual(child.pubkey, public.pubkey)
        self.assertEqual(child.chain_code, public.chain_code)
        self.assertEqual(child.parent_fingerprint, master.fingerprint)
        with self.assertRaises(HDKeyError):
            master.neuter().derive_child(HARDENED)

    def test_testnet_extended_encodings_roundtrip_without_changing_keys(self):
        node = HDNode.from_seed(SEED).derive_child(3)
        for encoded in (node.to_extended_public(testnet=True), node.to_extended_private(testnet=True)):
            self.assertEqual(import_extended_key(encoded).pubkey, node.pubkey)
        for wrong in ('bad', '', None, 1, '0' * 111, node.to_extended_public() + '1'):
            with self.assertRaises(HDKeyError):
                import_extended_key(wrong)

    def test_path_parser_strict_types_indices_and_hardening(self):
        self.assertEqual(parse_path("m/0'/1/2h/3H"), (HARDENED, 1, HARDENED + 2, HARDENED + 3))
        for path in ('', 'M/0', 'm/', 'm/-1', 'm/01', 'm/2147483648', 'm/1.0', ' m/0', 3, None):
            with self.assertRaises(HDKeyError):
                parse_path(path)
        node = HDNode.from_seed(SEED)
        for index in (-1, 1 << 32, True, 1.0, None):
            with self.assertRaises(HDKeyError):
                node.derive_child(index)

    def test_invalid_master_keys_do_not_leak_seed(self):
        for left in (bytes(32), SECP256K1_ORDER.to_bytes(32, 'big')):
            with patch('sumuww.hd._hmac', return_value=left + bytes(32)):
                with self.assertRaises(HDKeyError) as error:
                    HDNode.from_seed(SEED)
                self.assertNotIn(SEED.hex(), str(error.exception))

    def test_invalid_child_uses_next_index_or_exact_path_rejects(self):
        node = HDNode.from_seed(SEED)
        invalid = SECP256K1_ORDER.to_bytes(32, 'big') + b'\x11' * 32
        valid = (1).to_bytes(32, 'big') + b'\x22' * 32
        with patch('sumuww.hd._hmac', side_effect=(invalid, valid)):
            child = node.derive_child(9)
            self.assertEqual(child.child_number, 10)
            self.assertEqual(child.chain_code, b'\x22' * 32)
        with patch('sumuww.hd._hmac', return_value=invalid) as mocked:
            with self.assertRaises(HDKeyError):
                node.derive_child(9, skip_invalid=False)
            self.assertEqual(mocked.call_count, 1)
        with patch('sumuww.hd._hmac', return_value=invalid) as mocked:
            with self.assertRaises(HDKeyError):
                node.derive_child(9)
            self.assertEqual(mocked.call_count, 16)

    def test_zero_child_private_key_and_infinity_public_key_are_skipped(self):
        node = HDNode.from_seed(SEED)
        tweak = SECP256K1_ORDER - int.from_bytes(node._private_key.secret, 'big')
        invalid = tweak.to_bytes(32, 'big') + b'\x33' * 32
        valid = (1).to_bytes(32, 'big') + b'\x44' * 32
        with patch('sumuww.hd._hmac', side_effect=(invalid, valid)):
            self.assertEqual(node.derive_child(0).child_number, 1)
        with patch('sumuww.hd._hmac', side_effect=(invalid, valid)):
            self.assertEqual(node.neuter().derive_child(0).child_number, 1)

    def test_zero_tweak_valid_and_depth_limit_rejected(self):
        node = HDNode.from_seed(SEED)
        with patch('sumuww.hd._hmac', return_value=bytes(32) + b'\x55' * 32):
            self.assertEqual(node.derive_child(0).pubkey, node.pubkey)
            self.assertEqual(node.neuter().derive_child(0).pubkey, node.pubkey)
        leaf = HDNode(node._private_key, node.chain_code, 255, node.fingerprint, 1)
        with self.assertRaises(HDKeyError):
            leaf.derive_child(0)

    def test_seed_entropy_mnemonic_bounds_and_checksum_errors_are_safe(self):
        for seed in (b'', bytes(15), bytes(65), bytearray(32), 'private fixture text'):
            with self.assertRaises(HDKeyError):
                HDNode.from_seed(seed)
        for entropy in (b'', bytes(17), bytes(33), 'private fixture text'):
            with self.assertRaises(HDKeyError):
                entropy_to_mnemonic(entropy)
        for phrase in ('abandon ' * 24, 'not-a-secret-fixture ' * 24, 'abandon ' * 11, None, 12, 'a' * 1025):
            with self.assertRaises(HDKeyError) as error:
                mnemonic_to_entropy(phrase)
            self.assertNotIn('not-a-secret-fixture', str(error.exception))

    def test_nfkd_passphrase_and_transcription_whitespace(self):
        phrase = entropy_to_mnemonic(bytes(32))
        spaced = '\n\t' + '\u3000'.join(phrase.split()) + '\n'
        self.assertEqual(mnemonic_to_seed(spaced), mnemonic_to_seed(phrase))
        composed = '\u00e9'
        self.assertEqual(mnemonic_to_seed(phrase, composed), mnemonic_to_seed(phrase, unicodedata.normalize('NFKD', composed)))
        self.assertNotEqual(mnemonic_to_seed(phrase), mnemonic_to_seed(phrase, ' '))

    def test_source_and_frozen_asset_bytes_match_and_tampering_rejected(self):
        with tempfile.TemporaryDirectory(prefix='hd-wordlist-') as temporary:
            root = Path(temporary); assets = root / 'assets' / 'bip39'; assets.mkdir(parents=True)
            data = (ROOT / 'assets' / 'bip39' / 'english.txt').read_bytes()
            (assets / 'english.txt').write_bytes(data)
            try:
                with patch('sumuww.hd.sys._MEIPASS', str(root), create=True):
                    _wordlist.cache_clear()
                    self.assertEqual(len(_wordlist()), 2048)
                    (assets / 'english.txt').write_bytes(data + b'changed\n')
                    _wordlist.cache_clear()
                    with self.assertRaises(HDKeyError):
                        _wordlist()
            finally:
                _wordlist.cache_clear()

    def test_reprs_do_not_reveal_private_key_or_chain_code(self):
        node = HDNode.from_seed(SEED)
        self.assertNotIn(node._private_key.secret.hex(), repr(node))
        self.assertNotIn(node.chain_code.hex(), repr(node))
        self.assertNotIn(node.chain_code.hex(), repr(node.neuter()))


if __name__ == '__main__':
    unittest.main()
