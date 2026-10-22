"""Checksummed addresses for the single supported local SUMUWW output type.

The Bech32 format follows BIP173 (https://github.com/bitcoin/bips/blob/master/
bip-0173.mediawiki). Only witness version 0 and 20-byte P2WPKH programs are
accepted. Registered development profiles use distinct address prefixes; no
public-network prefix is selected.
"""

from __future__ import annotations

from .profiles import SUMUWW, REGTEST, get_network

# Preserve the regtest constant used by v0.10 callers and vector tests.
HRP = REGTEST.address_hrp
_CHARSET = "qpzry9x8gf2tvdw0s3jn54khce6mua7l"
_VALUES = {character: index for index, character in enumerate(_CHARSET)}
_GENERATORS = (0x3B6A57B2, 0x26508E6D, 0x1EA119FA, 0x3D4233DD, 0x2A1462B3)


class AddressError(ValueError):
    """An address is malformed or outside the supported local profile."""


def _polymod(values) -> int:
    state = 1
    for value in values:
        top = state >> 25
        state = ((state & 0x1FFFFFF) << 5) ^ value
        for bit, generator in enumerate(_GENERATORS):
            if top & (1 << bit):
                state ^= generator
    return state


def _hrp_values(hrp: str) -> list[int]:
    return [ord(character) >> 5 for character in hrp] + [0] + [ord(character) & 31 for character in hrp]


def _bech32_encode(hrp: str, data: list[int]) -> str:
    """Internal general Bech32 encoder, also used for official vector tests."""
    if not isinstance(hrp, str) or not 1 <= len(hrp) <= 83 or any(not 33 <= ord(c) <= 126 for c in hrp):
        raise AddressError("invalid address prefix")
    if hrp != hrp.lower() or any(type(value) is not int or not 0 <= value < 32 for value in data):
        raise AddressError("invalid address encoding data")
    remainder = _polymod(_hrp_values(hrp) + data + [0] * 6) ^ 1
    checksum = [(remainder >> (5 * position)) & 31 for position in range(5, -1, -1)]
    result = hrp + "1" + "".join(_CHARSET[value] for value in data + checksum)
    if len(result) > 90:
        raise AddressError("address exceeds 90 characters")
    return result


def _bech32_decode(text: str) -> tuple[str, list[int]]:
    if not isinstance(text, str) or not 8 <= len(text) <= 90:
        raise AddressError("address length is outside supported bounds")
    if any(not 33 <= ord(character) <= 126 for character in text):
        raise AddressError("address contains an invalid character")
    if text != text.lower() and text != text.upper():
        raise AddressError("address must not mix uppercase and lowercase")
    normalized = text.lower()
    separator = normalized.rfind("1")
    if not 1 <= separator <= 83 or len(normalized) - separator - 1 < 6:
        raise AddressError("address separator or checksum is missing")
    hrp = normalized[:separator]
    try:
        values = [_VALUES[character] for character in normalized[separator + 1:]]
    except KeyError:
        raise AddressError("address contains an invalid data character") from None
    if _polymod(_hrp_values(hrp) + values) != 1:
        raise AddressError("address checksum does not match")
    return hrp, values[:-6]


def _convert_bits(values, source_bits: int, target_bits: int, *, pad: bool) -> list[int]:
    accumulator = 0
    bit_count = 0
    result = []
    mask = (1 << target_bits) - 1
    accumulator_mask = (1 << (source_bits + target_bits - 1)) - 1
    for value in values:
        if type(value) is not int or not 0 <= value < 1 << source_bits:
            raise AddressError("invalid address data value")
        accumulator = ((accumulator << source_bits) | value) & accumulator_mask
        bit_count += source_bits
        while bit_count >= target_bits:
            bit_count -= target_bits
            result.append((accumulator >> bit_count) & mask)
    if pad:
        if bit_count:
            result.append((accumulator << (target_bits - bit_count)) & mask)
    elif bit_count >= source_bits or (accumulator << (target_bits - bit_count)) & mask:
        raise AddressError("address has invalid padding")
    return result


def encode_address(script_pubkey: bytes, *, network="regtest") -> str:
    """Encode native P2WPKH using the explicitly selected registered profile."""
    profile = get_network(network)
    if not isinstance(script_pubkey, bytes) or len(script_pubkey) != 22 or script_pubkey[:2] != b"\x00\x14":
        raise AddressError("only native witness-v0 P2WPKH scripts are supported")
    return _bech32_encode(profile.address_hrp, [0] + _convert_bits(script_pubkey[2:], 8, 5, pad=True))


def decode_address(text: str, *, network="regtest") -> bytes:
    """Verify prefix, checksum and supported witness type before returning script."""
    profile = get_network(network)
    hrp, data = _bech32_decode(text)
    accepted = (profile.address_hrp, 'dora') if profile is SUMUWW else (profile.address_hrp,)
    if hrp not in accepted:
        raise AddressError("address belongs to a different network")
    if not data or data[0] != 0:
        raise AddressError("only witness version 0 is supported")
    program = bytes(_convert_bits(data[1:], 5, 8, pad=False))
    if len(program) != 20:
        raise AddressError("only 20-byte P2WPKH programs are supported")
    return b"\x00\x14" + program
