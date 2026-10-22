"""Native ABI equivalence and failure/concurrency tests using public fixtures."""
from concurrent.futures import ThreadPoolExecutor
import hashlib,json
from pathlib import Path
import unittest
from coincurve import PrivateKey,PublicKey,ecdsa

class NativeAdapterTests(unittest.TestCase):
    def test_desktop_signature_bytes_and_public_keys_match(self):
        rows=json.loads(Path(__file__).with_name('signing_oracle.json').read_text())['rows']
        for row in rows:
            key=PrivateKey(row['public_test_scalar'].to_bytes(32,'big'))
            digest=bytes.fromhex(row['digest']);signature=key.sign(digest,hasher=None)
            self.assertEqual(key.public_key.format().hex(),row['public_key'])
            self.assertEqual(key.public_key.format(False).hex(),row['uncompressed'])
            self.assertEqual(signature.hex(),row['der'])
            self.assertTrue(key.public_key.verify(signature,digest,hasher=None))
    def test_invalid_scalars_points_der_and_digest_fail_closed(self):
        order=0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141
        for scalar in [bytes(32),order.to_bytes(32,'big'),b'\xff'*32,b'a'*31,b'a'*33]:
            with self.assertRaises(ValueError):PrivateKey(scalar)
        for public in [b'',bytes(33),bytes(65),b'\x02'+b'\xff'*32]:
            with self.assertRaises(ValueError):PublicKey(public)
        key=PrivateKey((1).to_bytes(32,'big'))
        for digest in [b'',b'a'*31,b'a'*33]:
            with self.assertRaises(ValueError):key.sign(digest,hasher=None)
        for invalid in [b'',b'\x30',bytes(80),b'\x30\x06\x02\x01\x00\x02\x01\x00']:
            self.assertFalse(key.public_key.verify(invalid,bytes(32),hasher=None))
    def test_parallel_signing_and_verification(self):
        def owned(index):
            key=PrivateKey((index+1).to_bytes(32,'big'))
            digest=hashlib.sha256(str(index).encode()).digest()
            signature=key.sign(digest,hasher=None)
            return key.public_key.verify(signature,digest,hasher=None)
        with ThreadPoolExecutor(max_workers=8) as pool:
            self.assertTrue(all(pool.map(owned,range(64))))
    def test_compact_signature_bounds(self):
        for raw in [b'',b'x'*63,b'x'*65,b'\xff'*64]:
            with self.assertRaises(ValueError):ecdsa.deserialize_compact(raw)
