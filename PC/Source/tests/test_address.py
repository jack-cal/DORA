"""BIP173 official vectors plus the intentionally narrow local SUMUWW profile."""

import unittest

from sumuww.address import AddressError, HRP, _bech32_decode, _bech32_encode, _convert_bits, decode_address, encode_address
from sumuww.wallet import RegtestKey


class Bech32VectorTests(unittest.TestCase):
    # Source: https://github.com/bitcoin/bips/blob/master/bip-0173.mediawiki
    def test_official_valid_bech32_checksums(self):
        vectors = (
            "A12UEL5L", "a12uel5l",
            "an83characterlonghumanreadablepartthatcontainsthenumber1andtheexcludedcharactersbio1tt5tgs",
            "abcdef1qpzry9x8gf2tvdw0s3jn54khce6mua7lmqqqxw",
            "11qqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqc8247j",
            "split1checkupstagehandshakeupstreamerranterredcaperred2y9e3w",
            "?1ezyfcl",
        )
        for text in vectors:
            with self.subTest(address=text):
                hrp, data = _bech32_decode(text)
                self.assertEqual(_bech32_encode(hrp, data), text.lower())

    def test_official_invalid_bech32_checksums(self):
        vectors = (
            "\x201nwldj5", "\x7f1axkwrx", "\x801eym55h",
            "an84characterslonghumanreadablepartthatcontainsthenumber1andtheexcludedcharactersbio1569pvx",
            "pzry9x0s0muk", "1pzry9x0s0muk", "x1b4n0q5v", "li1dgmt3",
            "de1lg7wt\xff", "A1G7SGD8", "10a06t8", "1qzzfhee",
        )
        for text in vectors:
            with self.subTest(address=text), self.assertRaises(AddressError):
                _bech32_decode(text)

    def test_official_p2wpkh_script_encoding_vector(self):
        script = bytes.fromhex("0014751e76e8199196d454941c45d1b3a323f1433bd6")
        data = [0] + _convert_bits(script[2:], 8, 5, pad=True)
        self.assertEqual(_bech32_encode("bc", data), "bc1qw508d6qejxtdg4y5r3zarvary0c5xw7kv8f3t4")
        self.assertEqual(_bech32_encode("tb", data), "tb1qw508d6qejxtdg4y5r3zarvary0c5xw7kxpjzsx")
        hrp, decoded = _bech32_decode("BC1QW508D6QEJXTDG4Y5R3ZARVARY0C5XW7KV8F3T4")
        self.assertEqual(hrp, "bc")
        self.assertEqual(decoded[0], 0)
        self.assertEqual(bytes(_convert_bits(decoded[1:], 5, 8, pad=False)), script[2:])

    def test_official_invalid_padding_vectors(self):
        for text in (
            "bc1zw508d6qejxtdg4y5r3zarvaryvqyzf3du",
            "tb1qrp33g0q5c5txsp9arysrx4k6zdkfs4nce4xj0gdcccefvpysxf3pjxtptv",
        ):
            with self.subTest(address=text):
                _, data = _bech32_decode(text)
                with self.assertRaises(AddressError):
                    _convert_bits(data[1:], 5, 8, pad=False)


class SumuwwAddressTests(unittest.TestCase):
    def setUp(self):
        self.script = RegtestKey.from_int(1).script_pubkey
        self.address = encode_address(self.script)

    def test_regtest_roundtrip_and_uppercase(self):
        self.assertTrue(self.address.startswith("drt1q"))
        self.assertEqual(len(self.address), 43)
        self.assertEqual(self.address, self.address.lower())
        self.assertEqual(decode_address(self.address), self.script)
        self.assertEqual(decode_address(self.address.upper()), self.script)
        for scalar in (2, 3, 100, 1 << 128):
            script = RegtestKey.from_int(scalar).script_pubkey
            self.assertEqual(decode_address(encode_address(script)), script)

    def test_other_networks_rejected_even_with_valid_checksum(self):
        data = [0] + _convert_bits(self.script[2:], 8, 5, pad=True)
        for hrp in ("bc", "tb", "bcrt", "dora", "dm"):
            with self.subTest(hrp=hrp), self.assertRaises(AddressError):
                decode_address(_bech32_encode(hrp, data))

    def test_checksum_rejects_each_single_character_substitution(self):
        for position in range(len(self.address)):
            replacement = "q" if self.address[position] != "q" else "p"
            corrupted = self.address[:position] + replacement + self.address[position + 1:]
            with self.subTest(position=position), self.assertRaises(AddressError):
                decode_address(corrupted)

    def test_mixed_case_whitespace_and_non_ascii_rejected(self):
        for text in ("D" + self.address[1:], self.address + "\n", " " + self.address, self.address + " ", self.address + '\ud55c', self.address.replace("q", "Q", 1)):
            with self.subTest(address=text), self.assertRaises(AddressError):
                decode_address(text)

    def test_version_and_program_length_restrictions(self):
        for version, program in ((1, bytes(20)), (16, bytes(20)), (0, bytes(32)), (0, bytes(19)), (0, bytes(21)), (0, b"")):
            address = _bech32_encode(HRP, [version] + _convert_bits(program, 8, 5, pad=True))
            with self.subTest(version=version, length=len(program)), self.assertRaises(AddressError):
                decode_address(address)
        with self.assertRaises(AddressError):
            decode_address(_bech32_encode(HRP, []))

    def test_excessive_zero_padding_and_nonzero_padding_rejected(self):
        data = [0] + _convert_bits(self.script[2:], 8, 5, pad=True)
        for invalid in (data + [0], data + [1]):
            with self.assertRaises(AddressError):
                decode_address(_bech32_encode(HRP, invalid))

    def test_only_supported_script_is_encodable(self):
        for script in (b"", b"\x51\x14" + bytes(20), b"\x00\x20" + bytes(32), self.script[:-1], self.script + b"\x00", bytearray(self.script), "0014"):
            with self.subTest(script_type=type(script).__name__), self.assertRaises(AddressError):
                encode_address(script)

    def test_bounded_input_length_and_types(self):
        for text in (None, b"drt1q", "", "drt1", "d" * 91, "d" * 100_000):
            with self.subTest(input_type=type(text).__name__), self.assertRaises(AddressError):
                decode_address(text)

    def test_bit_conversion_rejects_invalid_values(self):
        for value in (-1, 32, True, 1.0):
            with self.subTest(value=value), self.assertRaises(AddressError):
                _convert_bits([value], 5, 8, pad=False)


if __name__ == "__main__":
    unittest.main()
