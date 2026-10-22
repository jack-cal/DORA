"""Public BIP143 fixture plus adversarial transaction-codec boundary cases.

Reference fixture: https://github.com/bitcoin/bips/blob/master/bip-0143.mediawiki
Native P2WPKH example. It is a wire/digest test, not a SUMUWW chain anchor.
"""

from dataclasses import FrozenInstanceError, replace
import struct
import unittest

from sumuww.errors import InvalidTransaction, UnsupportedFeature
from sumuww.primitives import MAX_MONEY, encode_compact_size
from sumuww.transaction import (
    MAX_TRANSACTION_WEIGHT, NULL_TXID, UINT32_MAX, Transaction, TxInput, TxOutput,
    bip143_sighash_all, coinbase_height_prefix,
)


UNSIGNED = bytes.fromhex("""
0100000002
fff7f7881a8099afa6940d42d1e7f6362bec38171ea3edf433541db4e4ad969f0000000000eeffffff
ef51e1b804cc89d182d279655c3aa89e815b1b309fe287d9b2b55d57b90ec68a0100000000ffffffff
02
202cb206000000001976a9148280b37df378db99f66f85c95a783a76ac7a6d5988ac
9093510d000000001976a9143bde42dbee7e4dbe6a21b2d50ce2f0167faa815988ac
11000000
""")

SIGNED = bytes.fromhex("""
01000000000102
fff7f7881a8099afa6940d42d1e7f6362bec38171ea3edf433541db4e4ad969f00000000
494830450221008b9d1dc26ba6a9cb62127b02742fa9d754cd3bebf337f7a55d114c8e5cdd30be
022040529b194ba3f9281a99f2b1c0a19c0489bc22ede944ccf4ecbab4cc618ef3ed01eeffffff
ef51e1b804cc89d182d279655c3aa89e815b1b309fe287d9b2b55d57b90ec68a0100000000ffffffff
02
202cb206000000001976a9148280b37df378db99f66f85c95a783a76ac7a6d5988ac
9093510d000000001976a9143bde42dbee7e4dbe6a21b2d50ce2f0167faa815988ac
00
0247304402203609e17b84f6a7d30c80bfa610b5b4542f32a8a0d5447a12fb1366d7f01cc44a
0220573a954c4518331561406f90300e8f3358f51928d43c212a8caed02de67eebee01
21025476c2e83188368da1ff3e292e7acafcdb3566bb0ad253f62fc70f07aeee6357
11000000
""")

# Independently double-SHA256-hashed fixture serialization, in raw byte order.
UNSIGNED_TXID = "4302c449ad95afbf3241fe001f3712e9c80594b412dee807540cf20daeff3533"
SIGNED_TXID = "09462d604a3102fae083ada369c795855a28db4bdd3d05358a361cf32a1a15e8"
SIGNED_WTXID = "62b709c9126ae7782ea86576b338f39211199d149dced92423df070937386cc3"
PREV_P2WPKH = bytes.fromhex("00141d0f172a0ecb48aee1be1f2687d2963ae33f71a1")
BIP143_SIGHASH = "c37af31116d1b27caf68aae9e3ac82f1477929014d5b917657d0eb49478cb670"


def simple_tx(witness=()):
    return Transaction(2, (TxInput(bytes(range(32)), 3, witness=witness),),
                       (TxOutput(1234, b""),), 0)


class TransactionTests(unittest.TestCase):
    def test_public_unsigned_fixture(self):
        tx = Transaction.deserialize(UNSIGNED)
        self.assertEqual(tx.serialize(), UNSIGNED)
        self.assertEqual(tx.txid().hex(), UNSIGNED_TXID)
        self.assertEqual(tx.wtxid(), tx.txid())
        self.assertEqual(tx.version, 1)
        self.assertEqual(tx.lock_time, 17)
        self.assertEqual(len(tx.inputs), 2)
        self.assertEqual([item.value for item in tx.outputs], [112_340_000, 223_450_000])
        self.assertEqual(tx.weight(), 640)

    def test_public_signed_fixture(self):
        tx = Transaction.deserialize(SIGNED)
        self.assertEqual(tx.serialize(), SIGNED)
        self.assertEqual(tx.txid().hex(), SIGNED_TXID)
        self.assertEqual(tx.wtxid().hex(), SIGNED_WTXID)
        self.assertEqual(len(tx.serialize(False)), 233)
        self.assertEqual(len(tx.serialize()), 343)
        self.assertEqual(tx.weight(), 1042)
        self.assertEqual(tx.inputs[0].witness, ())
        self.assertEqual(len(tx.inputs[1].witness), 2)
        self.assertEqual(tx.inputs[1].witness[1].hex(),
                         "025476c2e83188368da1ff3e292e7acafcdb3566bb0ad253f62fc70f07aeee6357")

    def test_published_bip143_sighash(self):
        for raw in (UNSIGNED, SIGNED):
            tx = Transaction.deserialize(raw)
            self.assertEqual(bip143_sighash_all(tx, 1, PREV_P2WPKH, 600_000_000).hex(),
                             BIP143_SIGHASH)

    def test_bip143_commits_to_amount(self):
        tx = Transaction.deserialize(UNSIGNED)
        self.assertNotEqual(bip143_sighash_all(tx, 1, PREV_P2WPKH, 600_000_001).hex(),
                            BIP143_SIGHASH)

    def test_bip143_commits_to_every_output_and_sequence(self):
        tx = Transaction.deserialize(UNSIGNED)
        changed_output = replace(tx.outputs[0], value=tx.outputs[0].value + 1)
        tx2 = replace(tx, outputs=(changed_output, tx.outputs[1]))
        changed_input = replace(tx.inputs[0], sequence=UINT32_MAX)
        tx3 = replace(tx, inputs=(changed_input, tx.inputs[1]))
        for changed in (tx2, tx3):
            self.assertNotEqual(bip143_sighash_all(changed, 1, PREV_P2WPKH, 600_000_000).hex(),
                                BIP143_SIGHASH)

    def test_bip143_unsupported_scripts_fail_closed(self):
        tx = simple_tx()
        for script in (b"", b"\x51", b"\x00\x20" + bytes(32),
                       b"\x51\x20" + bytes(32), b"\xa9\x14" + bytes(20) + b"\x87"):
            with self.subTest(script=script.hex()), self.assertRaises(UnsupportedFeature):
                bip143_sighash_all(tx, 0, script, 1234)

    def test_bip143_input_and_amount_bounds(self):
        tx = simple_tx()
        for index in (-1, 1, True):
            with self.subTest(index=index), self.assertRaises(InvalidTransaction):
                bip143_sighash_all(tx, index, PREV_P2WPKH, 1)
        for value in (-1, MAX_MONEY + 1, 1.0, True):
            with self.subTest(value=value), self.assertRaises(InvalidTransaction):
                bip143_sighash_all(tx, 0, PREV_P2WPKH, value)

    def test_witness_changes_wtxid_only(self):
        tx = simple_tx((b"signature", b"pubkey"))
        changed = replace(tx, inputs=(replace(tx.inputs[0], witness=(b"other", b"pubkey")),))
        self.assertEqual(tx.txid(), changed.txid())
        self.assertNotEqual(tx.wtxid(), changed.wtxid())
        self.assertEqual(Transaction.deserialize(tx.serialize(False)).txid(), tx.txid())

    def test_empty_stack_item_is_a_real_witness(self):
        tx = simple_tx((b"",))
        raw = tx.serialize()
        self.assertEqual(raw[4:6], b"\x00\x01")
        self.assertEqual(tx.weight(), 244)
        self.assertEqual(Transaction.deserialize(raw), tx)

    def test_no_witness_omits_marker(self):
        tx = simple_tx()
        self.assertEqual(tx.serialize(True), tx.serialize(False))
        self.assertEqual(tx.serialize()[4], 1)
        self.assertEqual(tx.weight(), 240)

    def test_stream_offsets_do_not_consume_next_transaction(self):
        tx = simple_tx((b"",))
        raw1 = tx.serialize()
        raw2 = UNSIGNED
        buffer = b"prefix!" + raw1 + raw2 + b"tail"
        parsed1, end1 = Transaction.deserialize_from(buffer, 7)
        parsed2, end2 = Transaction.deserialize_from(buffer, end1)
        self.assertEqual(parsed1, tx)
        self.assertEqual(parsed2.serialize(), raw2)
        self.assertEqual(end1, 7 + len(raw1))
        self.assertEqual(buffer[end2:], b"tail")

    def test_trailing_bytes_are_rejected(self):
        with self.assertRaises(InvalidTransaction):
            Transaction.deserialize(UNSIGNED + b"\x00")

    def test_all_truncations_are_rejected(self):
        for raw in (UNSIGNED, SIGNED):
            for cut in range(len(raw)):
                with self.subTest(length=len(raw), cut=cut), self.assertRaises(InvalidTransaction):
                    Transaction.deserialize(raw[:cut])

    def test_unknown_optional_flags_rejected(self):
        raw = simple_tx((b"",)).serialize()
        for flag in (2, 3, 255):
            with self.subTest(flag=flag), self.assertRaises(InvalidTransaction):
                Transaction.deserialize(raw[:5] + bytes([flag]) + raw[6:])

    def test_superfluous_all_empty_witness_rejected(self):
        base = simple_tx().serialize()
        raw = base[:4] + b"\x00\x01" + base[4:-4] + b"\x00" + base[-4:]
        with self.assertRaises(InvalidTransaction):
            Transaction.deserialize(raw)

    def test_noncanonical_input_count_rejected(self):
        base = simple_tx().serialize()
        with self.assertRaises(InvalidTransaction):
            Transaction.deserialize(base[:4] + b"\xfd\x01\x00" + base[5:])

    def test_noncanonical_output_count_rejected(self):
        base = simple_tx().serialize()
        with self.assertRaises(InvalidTransaction):
            Transaction.deserialize(base[:46] + b"\xfd\x01\x00" + base[47:])

    def test_noncanonical_script_length_rejected(self):
        base = simple_tx().serialize()
        for position in (41, 55):
            with self.subTest(position=position), self.assertRaises(InvalidTransaction):
                Transaction.deserialize(base[:position] + b"\xfd\x00\x00" + base[position + 1:])

    def test_noncanonical_witness_count_and_item_length_rejected(self):
        raw = simple_tx((b"",)).serialize()
        for position, value in ((58, 1), (59, 0)):
            with self.subTest(position=position), self.assertRaises(InvalidTransaction):
                Transaction.deserialize(raw[:position] + b"\xfd" + struct.pack("<H", value)
                                        + raw[position + 1:])

    def test_declared_huge_input_output_counts_rejected(self):
        base = simple_tx().serialize()
        huge = b"\xff" + bytes.fromhex("ffffffffffffffff")
        cases = (base[:4] + huge + base[5:], base[:46] + huge + base[47:])
        for raw in cases:
            with self.assertRaises(InvalidTransaction):
                Transaction.deserialize(raw)

    def test_declared_huge_script_or_witness_rejected(self):
        huge = b"\xfe\xff\xff\xff\xff"
        base = simple_tx().serialize()
        witnessed = simple_tx((b"",)).serialize()
        cases = (base[:41] + huge + base[42:], base[:55] + huge + base[56:],
                 witnessed[:58] + huge + witnessed[59:],
                 witnessed[:59] + huge + witnessed[60:])
        for raw in cases:
            with self.assertRaises(InvalidTransaction):
                Transaction.deserialize(raw)

    def test_output_value_outside_money_range_rejected(self):
        base = simple_tx().serialize()
        for value in (-1, MAX_MONEY + 1, (1 << 63) - 1):
            with self.subTest(value=value), self.assertRaises(InvalidTransaction):
                Transaction.deserialize(base[:47] + struct.pack("<q", value) + base[55:])

    def test_version_is_uint32_in_frozen_comparison_profile(self):
        for version in (0, 0x80000000, UINT32_MAX):
            tx = replace(simple_tx(), version=version)
            self.assertEqual(tx.serialize()[:4], struct.pack("<I", version))
            self.assertEqual(Transaction.deserialize(tx.serialize()), tx)
        for version in (-1, 1 << 32, True, 2.0):
            with self.subTest(version=version), self.assertRaises(InvalidTransaction):
                replace(simple_tx(), version=version)

    def test_other_integer_ranges_reject_bool_float_and_overflow(self):
        for bad in (-1, 1 << 32, True, 1.0):
            for name in ("prev_index", "sequence"):
                with self.subTest(name=name, bad=bad), self.assertRaises(InvalidTransaction):
                    replace(simple_tx().inputs[0], **{name: bad})
            with self.assertRaises(InvalidTransaction):
                replace(simple_tx(), lock_time=bad)

    def test_fields_are_immutable(self):
        tx = simple_tx()
        with self.assertRaises(FrozenInstanceError):
            tx.lock_time = 5
        with self.assertRaises(InvalidTransaction):
            replace(tx, inputs=list(tx.inputs))
        with self.assertRaises(InvalidTransaction):
            replace(tx.inputs[0], witness=[b"mutable"])
        with self.assertRaises(InvalidTransaction):
            replace(tx.inputs[0], script_sig=bytearray())
        with self.assertRaises(InvalidTransaction):
            replace(tx.outputs[0], script_pubkey=bytearray())

    def test_txid_length_is_exact(self):
        for raw in (bytes(31), bytes(33), bytearray(32)):
            with self.subTest(raw=type(raw)), self.assertRaises(InvalidTransaction):
                replace(simple_tx().inputs[0], prev_txid=raw)

    def test_stream_offset_and_raw_type_bounds(self):
        for offset in (-1, len(UNSIGNED) + 1, True):
            with self.subTest(offset=offset), self.assertRaises(InvalidTransaction):
                Transaction.deserialize_from(UNSIGNED, offset)
        with self.assertRaises(InvalidTransaction):
            Transaction.deserialize(bytearray(UNSIGNED))
        with self.assertRaises(InvalidTransaction):
            Transaction.deserialize(bytes(4_000_001))

    def test_legacy_weight_exact_boundary_and_one_byte_over(self):
        # Base size = 64 + script length once its CompactSize needs five bytes.
        size = 1_000_000 - 64
        tx = replace(simple_tx(), inputs=(replace(simple_tx().inputs[0], script_sig=b"x" * size),))
        self.assertEqual(tx.weight(), MAX_TRANSACTION_WEIGHT)
        self.assertEqual(Transaction.deserialize(tx.serialize()), tx)
        with self.assertRaises(InvalidTransaction):
            replace(tx, inputs=(replace(tx.inputs[0], script_sig=b"x" * (size + 1)),))
        raw = tx.serialize()
        # Raise the declared and actual script by one without constructing an invalid object.
        oversized = raw[:41] + encode_compact_size(size + 1) + b"x" * (size + 1) + raw[46 + size:]
        with self.assertRaises(InvalidTransaction):
            Transaction.deserialize(oversized)

    def test_witness_weight_exact_boundary_and_one_byte_over(self):
        # Base=60, marker/flag=2, stack count=1, item length=5 => weight=248+item.
        size = MAX_TRANSACTION_WEIGHT - 248
        tx = simple_tx((b"x" * size,))
        self.assertEqual(tx.weight(), MAX_TRANSACTION_WEIGHT)
        self.assertEqual(Transaction.deserialize(tx.serialize()), tx)
        with self.assertRaises(InvalidTransaction):
            simple_tx((b"x" * (size + 1),))
        raw = tx.serialize()
        oversized = raw[:59] + encode_compact_size(size + 1) + b"x" * (size + 1) + raw[64 + size:]
        with self.assertRaises(InvalidTransaction):
            Transaction.deserialize(oversized)

    def test_empty_transaction_is_only_a_codec_object(self):
        # Chainstate must reject empty vin/vout; allowing construction tests that layer.
        raw = bytes.fromhex("02000000000000000000")
        tx = Transaction.deserialize(raw)
        self.assertEqual(tx.inputs, ())
        self.assertEqual(tx.outputs, ())
        self.assertEqual(tx.serialize(), raw)

    def test_coinbase_identity_checks_both_null_fields(self):
        tx = Transaction(2, (TxInput(NULL_TXID, UINT32_MAX, b"\x51\x00"),),
                         (TxOutput(5_000_000_000, b"\x51"),))
        self.assertTrue(tx.is_coinbase())
        self.assertFalse(replace(tx, inputs=(replace(tx.inputs[0], prev_index=0),)).is_coinbase())
        self.assertFalse(replace(tx, inputs=(replace(tx.inputs[0], prev_txid=b"x" * 32),)).is_coinbase())
        self.assertFalse(replace(tx, inputs=tx.inputs * 2).is_coinbase())

    def test_coinbase_height_minimal_prefix_vectors(self):
        expected = {
            0: "00", 1: "51", 16: "60", 17: "0111", 127: "017f", 128: "028000",
            255: "02ff00", 256: "020001", 32767: "02ff7f", 32768: "03008000",
            8388607: "03ffff7f", 8388608: "0400008000", 2147483647: "04ffffff7f",
        }
        for height, raw in expected.items():
            with self.subTest(height=height):
                self.assertEqual(coinbase_height_prefix(height).hex(), raw)
        for bad in (-1, 1 << 31, True, 1.0):
            with self.subTest(bad=bad), self.assertRaises(InvalidTransaction):
                coinbase_height_prefix(bad)


if __name__ == "__main__":
    unittest.main()
