from dataclasses import FrozenInstanceError, replace
import unittest

from sumuww.block import PROFILE_ID, REGTEST_BITS, genesis_block, mine_header
from sumuww.primitives import REGTEST_POW_LIMIT, UINT256_MAX, check_pow, hash_to_display
from sumuww.profiles import NetworkProfile, REGTEST, RETARGET_LAB, NETWORK_NAMES, get_network


class NetworkProfileTests(unittest.TestCase):
    def test_registered_names_and_identity(self):
        self.assertEqual(NETWORK_NAMES, ('regtest', 'retarget-lab', 'dora', 'sumuww'))
        self.assertIs(get_network('sumuww'), get_network('dora'))
        self.assertEqual(get_network('sumuww').name, 'dora')
        self.assertIs(get_network(), REGTEST)
        for profile in (REGTEST, RETARGET_LAB):
            self.assertIs(get_network(profile.name), profile)
            self.assertIs(get_network(profile), profile)
        self.assertIsInstance(REGTEST, NetworkProfile)

    def test_custom_or_unknown_profiles_are_not_selectable(self):
        for value in ('mainnet', '', True, 0, None, {}, replace(REGTEST),
                      replace(REGTEST, name='unregistered')):
            with self.subTest(type=type(value).__name__), self.assertRaises(ValueError):
                get_network(value)

    def test_profile_is_frozen(self):
        with self.assertRaises(FrozenInstanceError):
            RETARGET_LAB.target_timespan = 600

    def test_regtest_history_and_parameters_are_unchanged(self):
        self.assertEqual(REGTEST.genesis.serialize(), genesis_block().serialize())
        self.assertEqual(hash_to_display(REGTEST.genesis.block_hash()),
                         '51ff452925cf7a4350330ca73abcbf66b4e50d9e0c4641aca6e360dbde838ba0')
        self.assertEqual(REGTEST.profile_id, PROFILE_ID)
        self.assertEqual(REGTEST.initial_bits, REGTEST_BITS)
        self.assertEqual(REGTEST.pow_limit, REGTEST_POW_LIMIT)
        self.assertTrue(REGTEST.no_retarget)
        self.assertEqual((REGTEST.retarget_interval, REGTEST.target_timespan), (2016, 1209600))
        self.assertEqual((REGTEST.address_hrp, REGTEST.message_magic), ('drt', bytes.fromhex('d0524709')))

    def test_laboratory_has_a_distinct_deterministic_genesis(self):
        self.assertEqual(hash_to_display(RETARGET_LAB.genesis.block_hash()),
                         '00364a6e5152bafb1cd74d44e9fc58d2632d7f7b7d0365cab0a86eca40351c51')
        self.assertEqual(RETARGET_LAB.genesis.header.nonce, 43)
        self.assertNotEqual(RETARGET_LAB.genesis.block_hash(), REGTEST.genesis.block_hash())
        self.assertIn(b'DORA independent retarget laboratory 0.11',
                      RETARGET_LAB.genesis.transactions[0].inputs[0].script_sig)
        self.assertFalse(RETARGET_LAB.no_retarget)
        self.assertEqual((RETARGET_LAB.retarget_interval, RETARGET_LAB.target_timespan), (16, 16))
        self.assertEqual((RETARGET_LAB.address_hrp, RETARGET_LAB.message_magic), ('dtl', bytes.fromhex('d052470b')))
        self.assertEqual(RETARGET_LAB.pow_limit, (1 << 248) - 1)
        self.assertLessEqual(RETARGET_LAB.pow_limit * 64, UINT256_MAX)
        self.assertTrue(check_pow(RETARGET_LAB.genesis.block_hash(), 0x2000FFFF, RETARGET_LAB.pow_limit))

    def test_header_mining_accepts_the_selected_limit_and_keeps_default(self):
        self.assertEqual(mine_header(REGTEST.genesis.header), REGTEST.genesis.header)
        self.assertEqual(mine_header(RETARGET_LAB.genesis.header, pow_limit=RETARGET_LAB.pow_limit),
                         RETARGET_LAB.genesis.header)

    def test_bad_profile_parameters_and_genesis_are_rejected(self):
        cases = [
            {'name': ''}, {'name': None}, {'name': 'x' * 33},
            {'profile_id': ''}, {'profile_id': 'x' * 65},
            {'address_hrp': ''}, {'address_hrp': 'BC'}, {'address_hrp': 'dr1'},
            {'message_magic': b''}, {'message_magic': bytearray(4)},
            {'pow_limit': REGTEST_POW_LIMIT}, {'no_retarget': 1},
            {'retarget_interval': 1}, {'target_timespan': 3},
            {'initial_bits': 0}, {'genesis': REGTEST.genesis},
            {'genesis': replace(RETARGET_LAB.genesis, transactions=())},
            {'genesis': replace(RETARGET_LAB.genesis,
                                header=replace(RETARGET_LAB.genesis.header, merkle_root=bytes(32)))},
        ]
        for changes in cases:
            with self.subTest(changes=tuple(changes)), self.assertRaises((ValueError, TypeError)):
                replace(RETARGET_LAB, **changes)


if __name__ == '__main__':
    unittest.main()
