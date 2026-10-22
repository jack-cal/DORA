"""Local public test-scalar fixtures; no production keys or network access."""

from dataclasses import replace
import unittest

from coincurve import PublicKey, ecdsa

from sumuww.errors import InvalidTransaction, UnsupportedFeature
from sumuww.transaction import Transaction, TxInput, TxOutput, bip143_sighash_all
from sumuww.wallet import (
    RegtestKey,
    SECP256K1_ORDER,
    hash160,
    is_strict_der,
    p2wpkh_script,
    sign_p2wpkh,
    verify_p2wpkh,
)


class WalletTests(unittest.TestCase):
    def setUp(self):
        self.alice = RegtestKey.from_int(1)
        self.bob = RegtestKey.from_int(2)
        self.spent = TxOutput(5_000_000_000, self.alice.script_pubkey)
        self.unsigned = Transaction(
            2,
            (TxInput(b"\x11" * 32, 0, sequence=0xFFFFFFFE),),
            (TxOutput(4_999_990_000, self.bob.script_pubkey),),
            lock_time=7,
        )

    def signed(self):
        return sign_p2wpkh(self.unsigned, 0, self.spent, self.alice)

    def with_witness(self, tx, witness):
        return replace(tx, inputs=(replace(tx.inputs[0], witness=witness),))

    def test_compressed_generator_key_hash_and_script_vector(self):
        expected = bytes.fromhex(
            "0279be667ef9dcbbac55a06295ce870b07029bfcdb2dce28d959f2815b16f81798"
        )
        self.assertEqual(self.alice.pubkey, expected)
        self.assertEqual(hash160(expected).hex(), "751e76e8199196d454941c45d1b3a323f1433bd6")
        self.assertEqual(
            self.alice.script_pubkey.hex(), "0014751e76e8199196d454941c45d1b3a323f1433bd6"
        )

    def test_signs_locally_without_mutating_unsigned_transaction(self):
        signed = self.signed()
        self.assertEqual(self.unsigned.inputs[0].witness, ())
        self.assertTrue(verify_p2wpkh(signed, 0, self.spent))
        self.assertEqual(signed.inputs[0].witness[1], self.alice.pubkey)
        self.assertEqual(signed.inputs[0].witness[0][-1], 1)
        self.assertEqual(signed.txid(), self.unsigned.txid())
        self.assertNotEqual(signed.wtxid(), signed.txid())
        self.assertEqual(Transaction.deserialize(signed.serialize()), signed)

    def test_commits_to_spent_amount_outputs_version_locktime_and_sequence(self):
        signed = self.signed()
        mutations = (
            replace(signed, outputs=(replace(signed.outputs[0], value=4_999_990_001),)),
            replace(signed, outputs=(replace(signed.outputs[0], script_pubkey=self.alice.script_pubkey),)),
            replace(signed, version=1),
            replace(signed, lock_time=8),
            replace(signed, inputs=(replace(signed.inputs[0], sequence=0xFFFFFFFD),)),
            replace(signed, inputs=(replace(signed.inputs[0], prev_index=1),)),
            replace(signed, inputs=(replace(signed.inputs[0], prev_txid=b"\x12" * 32),)),
        )
        for changed in mutations:
            with self.subTest(transaction=changed):
                self.assertFalse(verify_p2wpkh(changed, 0, self.spent))
        self.assertFalse(verify_p2wpkh(signed, 0, replace(self.spent, value=self.spent.value - 1)))

    def test_wrong_witness_key_or_spent_key_hash_fails(self):
        signed = self.signed()
        signature, _ = signed.inputs[0].witness
        changed = self.with_witness(signed, (signature, self.bob.pubkey))
        self.assertFalse(verify_p2wpkh(changed, 0, self.spent))
        wrong = TxOutput(self.spent.value, self.bob.script_pubkey)
        self.assertFalse(verify_p2wpkh(signed, 0, wrong))

    def test_high_s_is_consensus_valid_after_normalizing_for_library(self):
        signed = self.signed()
        signature, pubkey = signed.inputs[0].witness
        compact = ecdsa.serialize_compact(ecdsa.der_to_cdata(signature[:-1]))
        s = int.from_bytes(compact[32:], "big")
        self.assertLessEqual(s, SECP256K1_ORDER // 2)
        high_compact = compact[:32] + (SECP256K1_ORDER - s).to_bytes(32, "big")
        high_der = ecdsa.cdata_to_der(ecdsa.deserialize_compact(high_compact))
        digest = bip143_sighash_all(signed, 0, self.spent.script_pubkey, self.spent.value)
        self.assertFalse(PublicKey(pubkey).verify(high_der, digest, hasher=None))
        changed = self.with_witness(signed, (high_der + b"\x01", pubkey))
        self.assertTrue(is_strict_der(changed.inputs[0].witness[0]))
        self.assertTrue(verify_p2wpkh(changed, 0, self.spent))

    def test_uncompressed_witness_key_not_rejected_as_compressed_policy(self):
        pubkey = self.alice.public_key_bytes(compressed=False)
        self.assertEqual(len(pubkey), 65)
        spent = TxOutput(self.spent.value, p2wpkh_script(pubkey))
        digest = bip143_sighash_all(self.unsigned, 0, spent.script_pubkey, spent.value)
        signature = self.alice.sign_digest(digest) + b"\x01"
        signed = self.with_witness(self.unsigned, (signature, pubkey))
        self.assertTrue(verify_p2wpkh(signed, 0, spent))

    def test_strict_der_structural_edge_vectors(self):
        malformed = (
            "", "310602010102010101", "300702010102010101",
            "300603010102010101", "300602000202010101",
            "300602018102010101", "30070202000102010101",
            "300602010102018101", "30070201010202000101",
            "30060201010201010100", "300602ff0102010101",
            "300602010102ff0101",
        )
        for item in malformed:
            with self.subTest(encoding=item):
                self.assertFalse(is_strict_der(bytes.fromhex(item)))
        # Structural validity does not imply a mathematically valid signature.
        self.assertTrue(is_strict_der(bytes.fromhex("300602010102010101")))
        self.assertTrue(is_strict_der(bytes.fromhex("30070202008002010101")))
        self.assertTrue(is_strict_der(bytes.fromhex("300602010002010001")))

    def test_redundant_r_padding_rejected_before_normalization(self):
        signed = self.signed()
        signature, pubkey = signed.inputs[0].witness
        der = signature[:-1]
        padded = bytes([der[0], der[1] + 1, der[2], der[3] + 1]) + b"\x00" + der[4:]
        changed = self.with_witness(signed, (padded + b"\x01", pubkey))
        self.assertFalse(is_strict_der(changed.inputs[0].witness[0]))
        self.assertFalse(verify_p2wpkh(changed, 0, self.spent))

    def test_empty_extra_witness_and_nonempty_native_script_sig_fail(self):
        signed = self.signed()
        sig, pub = signed.inputs[0].witness
        for witness in ((), (sig,), (sig, pub, b""), (b"", pub)):
            with self.subTest(witness=witness):
                self.assertFalse(verify_p2wpkh(self.with_witness(signed, witness), 0, self.spent))
        changed = replace(signed, inputs=(replace(signed.inputs[0], script_sig=b"\x00"),))
        self.assertFalse(verify_p2wpkh(changed, 0, self.spent))

    def test_unsupported_script_and_sighash_do_not_claim_consensus_invalidity(self):
        signed = self.signed()
        for script in (b"\x51", b"\x00\x20" + b"\x22" * 32):
            with self.subTest(script=script):
                with self.assertRaises(UnsupportedFeature):
                    verify_p2wpkh(signed, 0, TxOutput(self.spent.value, script))
        sig, pub = signed.inputs[0].witness
        for flag in (0x02, 0x03, 0x81):
            with self.subTest(flag=flag):
                changed = self.with_witness(signed, (sig[:-1] + bytes([flag]), pub))
                with self.assertRaises(UnsupportedFeature):
                    verify_p2wpkh(changed, 0, self.spent)

    def test_multiple_inputs_sign_independently_and_bind_other_outpoints(self):
        spent_bob = TxOutput(3_000_000_000, self.bob.script_pubkey)
        tx = replace(
            self.unsigned,
            inputs=self.unsigned.inputs + (TxInput(b"\x22" * 32, 1),),
            outputs=(TxOutput(7_999_980_000, self.alice.script_pubkey),),
        )
        once = sign_p2wpkh(tx, 0, self.spent, self.alice)
        signed = sign_p2wpkh(once, 1, spent_bob, self.bob)
        self.assertEqual(once.inputs[0].witness, signed.inputs[0].witness)
        self.assertTrue(verify_p2wpkh(signed, 0, self.spent))
        self.assertTrue(verify_p2wpkh(signed, 1, spent_bob))
        changed = replace(
            signed, inputs=(signed.inputs[0], replace(signed.inputs[1], prev_index=2))
        )
        self.assertFalse(verify_p2wpkh(changed, 0, self.spent))

    def test_explicit_test_key_bounds_signer_ownership_and_index(self):
        for scalar in (0, -1, SECP256K1_ORDER, True, "1"):
            with self.subTest(scalar=scalar):
                with self.assertRaises(ValueError):
                    RegtestKey.from_int(scalar)
        self.assertEqual(repr(self.alice), "RegtestKey(test_only=True)")
        with self.assertRaises(InvalidTransaction):
            sign_p2wpkh(self.unsigned, 0, self.spent, self.bob)
        for index in (-1, 1, True):
            with self.subTest(index=index):
                with self.assertRaises(InvalidTransaction):
                    sign_p2wpkh(self.unsigned, index, self.spent, self.alice)

    def test_invalid_serialized_public_key_and_zero_scalars_fail(self):
        with self.assertRaises(InvalidTransaction):
            p2wpkh_script(b"\x02" + b"\xff" * 32)
        signed = self.signed()
        _, pubkey = signed.inputs[0].witness
        zero = bytes.fromhex("300602010002010001")
        changed = self.with_witness(signed, (zero, pubkey))
        self.assertTrue(is_strict_der(zero))
        self.assertFalse(verify_p2wpkh(changed, 0, self.spent))


if __name__ == "__main__":
    unittest.main()
