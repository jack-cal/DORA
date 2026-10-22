import json
from pathlib import Path
import random
import unittest

from sumuww.primitives import (
    COIN, ERA_BLOCKS, FIRST_ERA_BLOCKS, FIRST_SUBSIDY, MAX_MONEY, NOMINAL_SUBSIDY_UNITS,
    SPENDABLE_SUBSIDY_UNITS, UINT256_MAX, TARGET_TIMESPAN,
    BITCOIN_COMPARISON_POW_LIMIT as POW_LIMIT, REGTEST_POW_LIMIT,
    Header, subsidy, scheduled_subsidy_total, parse_amount, format_amount,
    checked_amount_sum, transaction_fee, maximum_coinbase, coinbase_is_mature,
    sha256d, hash_from_display, hash_to_display, decode_compact, encode_compact,
    valid_target, check_pow, block_work, retarget, next_work_required,
    merkle_root, encode_compact_size, decode_compact_size,
)

ROOT = Path(__file__).resolve().parents[1]
VECTORS = json.loads((ROOT / 'vectors' / 'consensus_vectors.json').read_text(encoding='utf-8'))


class MonetaryTests(unittest.TestCase):
    def test_explicit_subsidy_boundaries(self):
        for vector in VECTORS['sumuww_subsidies']:
            with self.subTest(height=vector['height']):
                self.assertEqual(subsidy(vector['height']), vector['units'])

    def test_terminal_supply_independent_integer_identity(self):
        n = 2_500_000_000
        independently_summed = FIRST_ERA_BLOCKS * FIRST_SUBSIDY + ERA_BLOCKS * (2 * n - n.bit_count())
        self.assertEqual(independently_summed, 1_799_999_997_690_000)
        self.assertEqual(scheduled_subsidy_total(), independently_summed)
        self.assertEqual(NOMINAL_SUBSIDY_UNITS, independently_summed)
        self.assertEqual(SPENDABLE_SUBSIDY_UNITS, independently_summed - 50 * COIN)
        self.assertEqual(format_amount(NOMINAL_SUBSIDY_UNITS), '17999999.97690000')
        self.assertEqual(format_amount(SPENDABLE_SUBSIDY_UNITS), '17999949.97690000')

    def test_genesis_nominal_reward_and_first_drop(self):
        self.assertEqual(subsidy(0), 5_000_000_000)
        self.assertEqual(subsidy(150_000) * 2, subsidy(149_999))
        self.assertEqual(subsidy(6_660_000), 1)
        self.assertEqual(subsidy(6_869_999), 1)
        self.assertEqual(subsidy(6_870_000), 0)

    def test_invalid_height_types_and_giant_height(self):
        for value in (-1, 1.0, True, '210000'):
            with self.assertRaises((ValueError, TypeError)):
                subsidy(value)
        self.assertEqual(subsidy(10**100), 0)

    def test_decimal_text_preserves_smallest_units(self):
        for text, units in [('0', 0), ('0.00000001', 1), ('6.25', 625_000_000), ('50', 5_000_000_000), ('17999999.97690000', MAX_MONEY)]:
            self.assertEqual(parse_amount(text), units)
            self.assertEqual(parse_amount(format_amount(units)), units)

    def test_bad_amounts_and_bounds(self):
        for text in ['-1', '1e-8', 'NaN', '1.000000001', ' 1', '1 ', '01', '', '.1', '1.', '17999999.97690001']:
            with self.subTest(text=text), self.assertRaises(ValueError):
                parse_amount(text)
        for value in [1.0, True, None]:
            with self.assertRaises(TypeError):
                parse_amount(value)
        for values in [[-1], [MAX_MONEY + 1], [MAX_MONEY, 1], [1.0], [True]]:
            with self.assertRaises((ValueError, TypeError)):
                checked_amount_sum(values)

    def test_fee_example_and_value_creation_rejection(self):
        self.assertEqual(transaction_fee([10 * COIN], [3 * COIN, 699_900_000]), 100_000)
        with self.assertRaises(ValueError):
            transaction_fee([1], [2])
        self.assertEqual(maximum_coinbase(210_000, 100_000), 2_500_100_000)
        with self.assertRaises(ValueError):
            maximum_coinbase(1, -1)

    def test_coinbase_maturity_exact_spending_height(self):
        self.assertFalse(coinbase_is_mature(1, 100))
        self.assertTrue(coinbase_is_mature(1, 101))
        self.assertFalse(coinbase_is_mature(100, 99))


class HeaderAndHashTests(unittest.TestCase):
    def test_known_bitcoin_genesis_header_not_sumuww_anchor(self):
        fixture = VECTORS['bitcoin_comparison_genesis']
        header = Header(fixture['version'], hash_from_display(fixture['previous_hash']), hash_from_display(fixture['merkle_root']), fixture['timestamp'], int(fixture['bits'], 16), fixture['nonce'])
        self.assertEqual(header.serialize().hex(), fixture['header_hex'])
        self.assertEqual(len(header.serialize()), 80)
        self.assertEqual(hash_to_display(header.digest()), fixture['hash'])
        self.assertTrue(check_pow(header.digest(), header.bits, POW_LIMIT))
        self.assertEqual(Header.deserialize(header.serialize()), header)

    def test_hash_input_is_bytes_and_identifier_order(self):
        raw = bytes(range(32))
        self.assertEqual(hash_from_display(hash_to_display(raw)), raw)
        self.assertEqual(hash_to_display(raw), raw[::-1].hex())
        with self.assertRaises(TypeError):
            sha256d('text')
        for text in ['0' * 63, '0' * 65, 'z' * 64]:
            with self.assertRaises(ValueError):
                hash_from_display(text)

    def test_header_rejects_truncation_trailing_bytes_and_field_overflow(self):
        for raw in [bytes(79), bytes(81)]:
            with self.assertRaises(ValueError):
                Header.deserialize(raw)
        for header in [Header(1, bytes(31), bytes(32), 0, 0, 0), Header(1, bytes(32), bytes(32), 1 << 32, 0, 0), Header(1 << 31, bytes(32), bytes(32), 0, 0, 0), Header(True, bytes(32), bytes(32), 0, 0, 0)]:
            with self.assertRaises((ValueError, TypeError)):
                header.serialize()


class WorkAndTargetTests(unittest.TestCase):
    def test_compact_target_fixtures(self):
        for vector in VECTORS['compact_targets']:
            with self.subTest(bits=vector['bits']):
                self.assertEqual(decode_compact(int(vector['bits'], 16)), (int(vector['target_hex'], 16), vector['negative'], vector['overflow']))

    def test_compact_encoding_boundaries(self):
        for target, bits in [(0, 0), (1, 0x01010000), (128, 0x02008000), (0x123456, 0x03123456), (0x80FFFF, 0x040080FF)]:
            self.assertEqual(encode_compact(target), bits)
        self.assertEqual(encode_compact(POW_LIMIT), 0x1D00FFFF)
        self.assertEqual(encode_compact(REGTEST_POW_LIMIT), 0x207FFFFF)

    def test_target_quantization_properties(self):
        rng = random.Random(1701)
        for _ in range(200):
            target = rng.randrange(1, UINT256_MAX)
            bits = encode_compact(target)
            decoded, negative, overflow = decode_compact(bits)
            self.assertFalse(negative or overflow)
            self.assertLessEqual(decoded, target)
            self.assertEqual(encode_compact(decoded), bits)

    def test_pow_equal_target_valid_and_above_target_invalid(self):
        bits = 0x1D00FFFF
        target = valid_target(bits, POW_LIMIT)
        self.assertTrue(check_pow(target.to_bytes(32, 'little'), bits, POW_LIMIT))
        self.assertFalse(check_pow((target + 1).to_bytes(32, 'little'), bits, POW_LIMIT))
        for bits in [0, 0x1D80FFFF, 0x23000001, 0x1D010000]:
            self.assertFalse(check_pow(bytes(32), bits, POW_LIMIT))

    def test_fixed_historical_retarget_vectors(self):
        for vector in VECTORS['bitcoin_comparison_retargets']:
            with self.subTest(label=vector['label']):
                actual = retarget(int(vector['old_bits'], 16), vector['last_timestamp'] - vector['first_timestamp'], POW_LIMIT)
                self.assertEqual(actual, int(vector['expected_bits'], 16))

    def test_boundary_and_regtest_no_retarget(self):
        self.assertEqual(next_work_required(2015, 0x1D00FFFF, 100, None, POW_LIMIT), 0x1D00FFFF)
        self.assertEqual(next_work_required(2016, 0x1D00FFFF, TARGET_TIMESPAN, 0, POW_LIMIT), 0x1D00FFFF)
        with self.assertRaises(TypeError):
            next_work_required(2016, 0x1D00FFFF, 100, None, POW_LIMIT)
        self.assertEqual(next_work_required(2016, 0x207FFFFF, 100, None, REGTEST_POW_LIMIT, no_retarget=True), 0x207FFFFF)
        self.assertEqual(retarget(0x1C05A3F4, -1, POW_LIMIT), retarget(0x1C05A3F4, TARGET_TIMESPAN // 4, POW_LIMIT))
        self.assertEqual(retarget(0x1C387F6F, TARGET_TIMESPAN * 5, POW_LIMIT), retarget(0x1C387F6F, TARGET_TIMESPAN * 4, POW_LIMIT))

    def test_work_and_shorter_harder_chain(self):
        self.assertEqual(block_work(0x1D00FFFF, POW_LIMIT), 4_295_032_833)
        self.assertEqual(block_work(0x207FFFFF, REGTEST_POW_LIMIT), 2)
        self.assertGreater(2 * block_work(0x1C00FFFF, POW_LIMIT), 10 * block_work(0x1D00FFFF, POW_LIMIT))

    def test_large_target_preserves_comparison_256bit_intermediate(self):
        # Deliberately unsafe for public retarget parameters; diagnostic only.
        self.assertEqual(retarget(0x207FFFFF, 1_209_600, REGTEST_POW_LIMIT), 0x1E0CDEBB)


class MerkleAndSizeTests(unittest.TestCase):
    def test_single_and_empty_merkle(self):
        leaf = sha256d(b'A')
        self.assertEqual(merkle_root([]), (bytes(32), False))
        self.assertEqual(merkle_root([leaf]), (leaf, False))

    def test_odd_padding_is_not_mutation_but_duplicate_tail_is(self):
        a, b, c = (sha256d(bytes([i])) for i in range(3))
        root_three, mutated_three = merkle_root([a, b, c])
        root_four, mutated_four = merkle_root([a, b, c, c])
        self.assertEqual(root_three, root_four)
        self.assertFalse(mutated_three)
        self.assertTrue(mutated_four)

    def test_internal_level_mutation(self):
        leaves = [sha256d(bytes([i])) for i in range(6)]
        normal_root, normal_mutated = merkle_root(leaves)
        altered_root, altered_mutated = merkle_root(leaves + leaves[-2:])
        self.assertEqual(normal_root, altered_root)
        self.assertFalse(normal_mutated)
        self.assertTrue(altered_mutated)

    def test_malformed_leaf(self):
        with self.assertRaises(ValueError):
            merkle_root([bytes(31)])

    def test_compact_size_fixed_wire_vectors(self):
        for number, wire in [(0, '00'), (252, 'fc'), (253, 'fdfd00'), (65535, 'fdffff'), (65536, 'fe00000100'), (4294967295, 'feffffffff'), (4294967296, 'ff0000000001000000')]:
            self.assertEqual(encode_compact_size(number).hex(), wire)
            self.assertEqual(decode_compact_size(bytes.fromhex(wire), 1 << 63), (number, len(bytes.fromhex(wire))))

    def test_compact_size_noncanonical_truncated_over_limit(self):
        for wire in ['', 'fd', 'fd01', 'fdfc00', 'feffff0000', 'ffffffffff00000000']:
            with self.subTest(wire=wire), self.assertRaises(ValueError):
                decode_compact_size(bytes.fromhex(wire), (1 << 64) - 1)
        with self.assertRaises(ValueError):
            decode_compact_size(bytes.fromhex('fdfd00'), 252)
        self.assertEqual(decode_compact_size(bytes.fromhex('00fdfd0000'), 1000, 1), (253, 4))


if __name__ == '__main__':
    unittest.main()
