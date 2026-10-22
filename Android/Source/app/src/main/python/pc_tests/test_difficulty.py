"""Context fixtures exercise header ancestry; they are not mined blocks."""

import json
from pathlib import Path
import unittest

from sumuww.difficulty import expected_bits, validate_profile
from sumuww.primitives import (
    BITCOIN_COMPARISON_POW_LIMIT as POW_LIMIT, REGTEST_POW_LIMIT,
    TARGET_TIMESPAN, UINT256_MAX, Header, encode_compact, sha256d,
)

INITIAL_BITS = 0x1C00FFFF
BASE_TIME = 1_700_000_000
ROOT = Path(__file__).resolve().parents[1]


class HeaderFixture:
    def __init__(self, bits=INITIAL_BITS, timestamp=BASE_TIME):
        self.headers = {}
        self.by_height = {}
        self.looked_up = []
        self.append(0, bytes(32), timestamp, bits, b'genesis')

    def append(self, height, parent_hash, timestamp, bits=INITIAL_BITS,
               salt=b'fixture'):
        header = Header(1 if height == 0 else 4, parent_hash,
                        sha256d(salt + height.to_bytes(4, 'little')),
                        timestamp, bits, height)
        digest = header.digest()
        self.headers[digest] = header
        self.by_height[height] = digest
        return digest

    def lookup(self, digest):
        self.looked_up.append(digest)
        return self.headers.get(digest)

    def extend(self, last_height, *, first_height=1, parent_hash=None,
               timestamp_for=None, bits=INITIAL_BITS, salt=b'fixture'):
        previous = self.by_height[first_height - 1] if parent_hash is None else parent_hash
        for height in range(first_height, last_height + 1):
            timestamp = (BASE_TIME + height * 600 if timestamp_for is None
                         else timestamp_for(height))
            previous = self.append(height, previous, timestamp, bits, salt)
        return previous


class ProfileTests(unittest.TestCase):
    def test_safe_public_comparison_profile(self):
        self.assertIsNone(validate_profile(POW_LIMIT, INITIAL_BITS))

    def test_easy_fixture_requires_no_retarget(self):
        with self.assertRaisesRegex(ValueError, 'overflow'):
            validate_profile(REGTEST_POW_LIMIT, 0x207FFFFF)
        self.assertIsNone(validate_profile(REGTEST_POW_LIMIT, 0x207FFFFF,
                                           no_retarget=True))

    def test_exact_overflow_safety_bound(self):
        span = 4
        safe_limit = UINT256_MAX // (span * 4)
        bits = encode_compact(safe_limit)
        validate_profile(safe_limit, bits, target_timespan=span)
        with self.assertRaisesRegex(ValueError, 'overflow'):
            validate_profile(safe_limit + 1, bits, target_timespan=span)

    def test_bad_profile_types_and_ranges(self):
        invalid = [
            {'pow_limit': 0}, {'pow_limit': -1}, {'pow_limit': UINT256_MAX + 1},
            {'pow_limit': True}, {'pow_limit': 1.0},
            {'initial_bits': -1}, {'initial_bits': 1 << 32},
            {'initial_bits': True}, {'initial_bits': '1c00ffff'},
            {'no_retarget': 1}, {'no_retarget': None},
            {'interval': 0}, {'interval': 1}, {'interval': True},
            {'interval': 2.0}, {'interval': 1 << 32},
            {'target_timespan': 3}, {'target_timespan': -1},
            {'target_timespan': 1 << 63}, {'target_timespan': True},
            {'target_timespan': 1209600.0},
        ]
        for change in invalid:
            args = {'pow_limit': POW_LIMIT, 'initial_bits': INITIAL_BITS}
            args.update(change)
            with self.subTest(change=change), self.assertRaises((ValueError, TypeError)):
                validate_profile(**args)

    def test_zero_negative_overflow_above_limit_targets(self):
        for bits in (0, 0x1D80FFFF, 0x23000001, 0x1D010000):
            with self.subTest(bits=bits), self.assertRaises(ValueError):
                validate_profile(POW_LIMIT, bits)

    def test_initial_bits_must_be_canonical(self):
        # Both encode target 1, but only 0x01010000 is the canonical form.
        validate_profile(POW_LIMIT, 0x01010000)
        with self.assertRaisesRegex(ValueError, 'canonical'):
            validate_profile(POW_LIMIT, 0x02000100)


class ContextDifficultyTests(unittest.TestCase):
    def test_next_height_2015_is_not_adjustment(self):
        fixture = HeaderFixture()
        parent = fixture.extend(2014)
        self.assertEqual(expected_bits(2014, parent, fixture.lookup,
                                       POW_LIMIT, INITIAL_BITS), INITIAL_BITS)
        self.assertEqual(fixture.looked_up, [parent])

    def test_next_height_2016_uses_genesis_ancestor(self):
        fixture = HeaderFixture()
        parent = fixture.extend(2015, timestamp_for=lambda h:
                                BASE_TIME + h * TARGET_TIMESPAN // 2015)
        self.assertEqual(expected_bits(2015, parent, fixture.lookup,
                                       POW_LIMIT, INITIAL_BITS), INITIAL_BITS)
        self.assertEqual(len(fixture.looked_up), 2016)
        self.assertEqual(fixture.looked_up[-1], fixture.by_height[0])

    def test_next_height_4032_uses_height_2016_not_genesis(self):
        fixture = HeaderFixture()
        fixture.extend(2015, timestamp_for=lambda h:
                       BASE_TIME + h * TARGET_TIMESPAN // 2015)
        period_start = BASE_TIME + TARGET_TIMESPAN + 600
        parent = fixture.extend(4031, first_height=2016,
                                timestamp_for=lambda h: period_start +
                                (h - 2016) * (TARGET_TIMESPAN // 2) // 2015)
        self.assertEqual(expected_bits(4031, parent, fixture.lookup,
                                       POW_LIMIT, INITIAL_BITS), 0x1B7FFF80)
        self.assertEqual(len(fixture.looked_up), 2016)
        self.assertEqual(fixture.looked_up[-1], fixture.by_height[2016])
        self.assertNotIn(fixture.by_height[2015], fixture.looked_up)

    def test_same_height_side_branches_use_their_own_ancestor_times(self):
        fixture = HeaderFixture()
        common = fixture.extend(2015)
        start_a = BASE_TIME + TARGET_TIMESPAN
        final_time = start_a + TARGET_TIMESPAN
        branch_a = fixture.extend(4031, first_height=2016, parent_hash=common,
                                  timestamp_for=lambda h: start_a +
                                  (h - 2016) * TARGET_TIMESPAN // 2015,
                                  salt=b'branch-a')
        first_a = fixture.by_height[2016]
        start_b = start_a + TARGET_TIMESPAN // 2
        branch_b = fixture.extend(4031, first_height=2016, parent_hash=common,
                                  timestamp_for=lambda h: start_b +
                                  (h - 2016) * (TARGET_TIMESPAN // 2) // 2015,
                                  salt=b'branch-b')
        first_b = fixture.by_height[2016]
        self.assertEqual(fixture.headers[branch_a].timestamp, final_time)
        self.assertEqual(fixture.headers[branch_b].timestamp, final_time)
        self.assertEqual(expected_bits(4031, branch_a, fixture.lookup,
                                       POW_LIMIT, INITIAL_BITS), INITIAL_BITS)
        self.assertEqual(fixture.looked_up[-1], first_a)
        self.assertNotIn(first_b, fixture.looked_up)
        fixture.looked_up.clear()
        self.assertEqual(expected_bits(4031, branch_b, fixture.lookup,
                                       POW_LIMIT, INITIAL_BITS), 0x1B7FFF80)
        self.assertEqual(fixture.looked_up[-1], first_b)
        self.assertNotIn(first_a, fixture.looked_up)

    def test_no_retarget_walks_only_parent_at_boundaries(self):
        fixture = HeaderFixture(bits=0x207FFFFF)
        parent = fixture.extend(2015, bits=0x207FFFFF)
        # The boundary's older context is deliberately unavailable.
        fixture.headers = {parent: fixture.headers[parent]}
        self.assertEqual(expected_bits(2015, parent, fixture.lookup,
                                       REGTEST_POW_LIMIT, 0x207FFFFF,
                                       no_retarget=True), 0x207FFFFF)
        self.assertEqual(fixture.looked_up, [parent])

    def test_historical_comparison_adjustments(self):
        vectors = json.loads((ROOT / 'vectors' / 'consensus_vectors.json').read_text(
            encoding='utf-8'))['bitcoin_comparison_retargets']
        for vector in vectors:
            bits = int(vector['old_bits'], 16)
            fixture = HeaderFixture(bits=bits, timestamp=vector['first_timestamp'])
            parent = fixture.append(1, fixture.by_height[0], vector['last_timestamp'], bits)
            with self.subTest(vector=vector['label']):
                self.assertEqual(expected_bits(1, parent, fixture.lookup,
                                               POW_LIMIT, bits, interval=2),
                                 int(vector['expected_bits'], 16))

    def test_elapsed_clamps_to_quarter_and_four_times(self):
        cases = [(0, 0x1B3FFFC0), (TARGET_TIMESPAN // 4, 0x1B3FFFC0),
                 (TARGET_TIMESPAN * 4, 0x1C03FFFC),
                 (TARGET_TIMESPAN * 5, 0x1C03FFFC)]
        for elapsed, expected in cases:
            fixture = HeaderFixture()
            parent = fixture.append(1, fixture.by_height[0], BASE_TIME + elapsed)
            with self.subTest(elapsed=elapsed):
                self.assertEqual(expected_bits(1, parent, fixture.lookup,
                                               POW_LIMIT, INITIAL_BITS, interval=2), expected)

    def test_negative_elapsed_uses_lower_clamp(self):
        fixture = HeaderFixture()
        parent = fixture.append(1, fixture.by_height[0], BASE_TIME - 1)
        self.assertEqual(expected_bits(1, parent, fixture.lookup, POW_LIMIT,
                                       INITIAL_BITS, interval=2), 0x1B3FFFC0)

    def test_upper_clamp_caps_target_to_pow_limit(self):
        fixture = HeaderFixture(bits=0x1D00FFFF)
        parent = fixture.append(1, fixture.by_height[0], BASE_TIME + TARGET_TIMESPAN * 4,
                                bits=0x1D00FFFF)
        self.assertEqual(expected_bits(1, parent, fixture.lookup, POW_LIMIT,
                                       0x1D00FFFF, interval=2), 0x1D00FFFF)

    def test_height_zero_matches_initial_difficulty(self):
        fixture = HeaderFixture()
        self.assertEqual(expected_bits(0, fixture.by_height[0], fixture.lookup,
                                       POW_LIMIT, INITIAL_BITS), INITIAL_BITS)
        with self.assertRaisesRegex(ValueError, 'Height-zero'):
            expected_bits(0, fixture.by_height[0], fixture.lookup,
                          POW_LIMIT, 0x1D00FFFF)

    def test_missing_parent_or_boundary_ancestor_fails(self):
        fixture = HeaderFixture()
        with self.assertRaisesRegex(ValueError, 'Missing'):
            expected_bits(1, bytes(32), fixture.lookup, POW_LIMIT, INITIAL_BITS)
        parent = fixture.extend(3)
        del fixture.headers[fixture.by_height[1]]
        with self.assertRaisesRegex(ValueError, 'Missing'):
            expected_bits(3, parent, fixture.lookup, POW_LIMIT, INITIAL_BITS,
                          interval=4)

    def test_lookup_hash_mismatch_fails(self):
        fixture = HeaderFixture()
        parent = fixture.extend(1)
        with self.assertRaisesRegex(ValueError, 'match its hash'):
            expected_bits(1, parent, lambda digest: fixture.headers[fixture.by_height[0]],
                          POW_LIMIT, INITIAL_BITS)

    def test_invalid_ancestor_target_fails(self):
        fixture = HeaderFixture()
        broken = fixture.append(1, fixture.by_height[0], BASE_TIME + 600,
                                bits=0x1D80FFFF)
        parent = fixture.append(2, broken, BASE_TIME + 1200)
        parent = fixture.append(3, parent, BASE_TIME + 1800)
        with self.assertRaisesRegex(ValueError, 'target'):
            expected_bits(3, parent, fixture.lookup, POW_LIMIT, INITIAL_BITS,
                          interval=4)

    def test_first_adjustment_rejects_false_genesis_context(self):
        fixture = HeaderFixture()
        fake = fixture.append(0, sha256d(b'not-null-parent'), BASE_TIME,
                              salt=b'false-genesis')
        parent = fixture.append(1, fake, BASE_TIME + TARGET_TIMESPAN)
        with self.assertRaisesRegex(ValueError, 'profile genesis'):
            expected_bits(1, parent, fixture.lookup, POW_LIMIT, INITIAL_BITS,
                          interval=2)

    def test_bad_parent_height_hash_and_lookup_types(self):
        fixture = HeaderFixture()
        parent = fixture.by_height[0]
        for height in (-1, True, 1.0, '0', 1 << 32):
            with self.subTest(height=height), self.assertRaises((ValueError, TypeError)):
                expected_bits(height, parent, fixture.lookup, POW_LIMIT, INITIAL_BITS)
        for digest in (bytes(31), bytes(33), bytearray(32), '00' * 32, None):
            with self.subTest(digest=type(digest)), self.assertRaises(ValueError):
                expected_bits(0, digest, fixture.lookup, POW_LIMIT, INITIAL_BITS)
        with self.assertRaises(TypeError):
            expected_bits(0, parent, {}, POW_LIMIT, INITIAL_BITS)
        with self.assertRaises(TypeError):
            expected_bits(0, parent, lambda digest: {}, POW_LIMIT, INITIAL_BITS)

    def test_header_fields_are_validated_before_hashing(self):
        fixture = HeaderFixture()
        bad = Header(4, bytes(32), bytes(32), 1 << 32, INITIAL_BITS, 0)
        with self.assertRaises(ValueError):
            expected_bits(0, fixture.by_height[0], lambda digest: bad,
                          POW_LIMIT, INITIAL_BITS)

    def test_integer_rounding_can_produce_zero_only_as_an_unmineable_result(self):
        # Matching the comparison calculation, a target of 1 times 1/4 floors
        # to zero.  Returning bits does not waive the separate positive-PoW rule.
        fixture = HeaderFixture(bits=0x01010000)
        parent = fixture.append(1, fixture.by_height[0], BASE_TIME,
                                bits=0x01010000)
        self.assertEqual(expected_bits(1, parent, fixture.lookup, POW_LIMIT,
                                       0x01010000, interval=2), 0)


if __name__ == '__main__':
    unittest.main()
