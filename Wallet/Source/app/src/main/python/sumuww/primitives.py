"""SUMUWW deterministic primitives for specification tests, not a node or wallet.

Bitcoin-like binary conventions are compared with Bitcoin Core v29.0 commit
f490f5562d4b20857ef8d042c050763795fd43da. This module is independently written.
All monetary and work calculations use integers. Hash bytes use internal order;
displayed identifiers reverse those bytes. No public-network genesis is set.
"""

from dataclasses import dataclass
from hashlib import sha256
import re
import struct

# One yugeon is the indivisible SMW amount stored in transaction values.
YUGEON = 1
BASE_UNIT_NAME = "yugeon"
COIN = 100_000_000 * YUGEON
ERA_BLOCKS = 210_000
FIRST_ERA_BLOCKS = 150_000
FIRST_SUBSIDY = 50 * COIN
SECOND_SUBSIDY = 25 * COIN
ZERO_SUBSIDY_HEIGHT = 6_870_000
NOMINAL_SUBSIDY_UNITS = 1_799_999_997_690_000
SPENDABLE_SUBSIDY_UNITS = NOMINAL_SUBSIDY_UNITS - FIRST_SUBSIDY
MAX_MONEY = NOMINAL_SUBSIDY_UNITS
UINT256_MAX = (1 << 256) - 1
TARGET_SPACING = 600
TARGET_TIMESPAN = 1_209_600
RETARGET_INTERVAL = 2_016
# Test comparator limits only. These do not select SUMUWW mainnet launch difficulty.
BITCOIN_COMPARISON_POW_LIMIT = (1 << 224) - 1
REGTEST_POW_LIMIT = (1 << 255) - 1


def require_int(value: int, minimum: int, maximum: int | None = None) -> int:
    if type(value) is not int:
        raise TypeError("Expected an integer, not bool or floating point")
    if value < minimum or (maximum is not None and value > maximum):
        raise ValueError("Integer outside allowed range")
    return value


def subsidy(height: int) -> int:
    """Permitted subsidy in smallest units, including the nominal height-0 era."""
    require_int(height, 0)
    if height < FIRST_ERA_BLOCKS:
        return FIRST_SUBSIDY
    shift = (height - FIRST_ERA_BLOCKS) // ERA_BLOCKS
    # Avoid shifts by attacker-controlled giant values; the result is already zero.
    if shift >= SECOND_SUBSIDY.bit_length():
        return 0
    return SECOND_SUBSIDY >> shift


def scheduled_subsidy_total() -> int:
    """Maximum schedule if every permitted subsidy, including genesis, is claimed."""
    total = FIRST_ERA_BLOCKS * FIRST_SUBSIDY
    reward = SECOND_SUBSIDY
    while reward:
        total += ERA_BLOCKS * reward
        reward //= 2
    return total


def format_amount(units: int) -> str:
    require_int(units, 0, MAX_MONEY)
    whole, fraction = divmod(units, COIN)
    return f"{whole}.{fraction:08d}"


def parse_amount(text: str) -> int:
    """Strict example UI conversion; decimal text is not a consensus wire field."""
    if not isinstance(text, str):
        raise TypeError("Amount must be decimal text")
    match = re.fullmatch(r"(0|[1-9][0-9]*)(?:\.([0-9]{1,8}))?", text)
    if not match:
        raise ValueError("Use unsigned decimal notation with at most 8 decimals")
    units = int(match[1]) * COIN + int((match[2] or "").ljust(8, "0"))
    return require_int(units, 0, MAX_MONEY)


def checked_amount_sum(amounts) -> int:
    total = 0
    for amount in amounts:
        total += require_int(amount, 0, MAX_MONEY)
        require_int(total, 0, MAX_MONEY)
    return total


def transaction_fee(input_amounts, output_amounts) -> int:
    fee = checked_amount_sum(input_amounts) - checked_amount_sum(output_amounts)
    return require_int(fee, 0, MAX_MONEY)


def maximum_coinbase(height: int, block_fees: int) -> int:
    return checked_amount_sum((subsidy(height), block_fees))


def coinbase_is_mature(creation_height: int, spending_height: int) -> bool:
    require_int(creation_height, 0)
    require_int(spending_height, 0)
    return spending_height - creation_height >= 100


def sha256d(data: bytes) -> bytes:
    if not isinstance(data, bytes):
        raise TypeError("Hash input must be bytes")
    return sha256(sha256(data).digest()).digest()


def hash_from_display(text: str) -> bytes:
    if not isinstance(text, str) or not re.fullmatch(r"[0-9a-fA-F]{64}", text):
        raise ValueError("Expected a 64-character hexadecimal identifier")
    return bytes.fromhex(text)[::-1]


def hash_to_display(raw: bytes) -> str:
    if not isinstance(raw, bytes) or len(raw) != 32:
        raise ValueError("Expected exactly 32 hash bytes")
    return raw[::-1].hex()


@dataclass(frozen=True)
class Header:
    version: int
    previous_hash: bytes
    merkle_root: bytes
    timestamp: int
    bits: int
    nonce: int

    def serialize(self) -> bytes:
        require_int(self.version, -(1 << 31), (1 << 31) - 1)
        for raw in (self.previous_hash, self.merkle_root):
            if not isinstance(raw, bytes) or len(raw) != 32:
                raise ValueError("Header hashes must be exactly 32 bytes")
        for field in (self.timestamp, self.bits, self.nonce):
            require_int(field, 0, (1 << 32) - 1)
        return struct.pack("<i", self.version) + self.previous_hash + self.merkle_root + struct.pack("<III", self.timestamp, self.bits, self.nonce)

    @classmethod
    def deserialize(cls, raw: bytes):
        if not isinstance(raw, bytes) or len(raw) != 80:
            raise ValueError("A header has exactly 80 bytes")
        version = struct.unpack("<i", raw[:4])[0]
        timestamp, bits, nonce = struct.unpack("<III", raw[68:80])
        return cls(version, raw[4:36], raw[36:68], timestamp, bits, nonce)

    def digest(self) -> bytes:
        return sha256d(self.serialize())


def decode_compact(bits: int) -> tuple[int, bool, bool]:
    """256-bit target magnitude, sign flag, overflow flag (Bitcoin convention)."""
    require_int(bits, 0, (1 << 32) - 1)
    size = bits >> 24
    mantissa = bits & 0x007FFFFF
    if size <= 3:
        mantissa >>= 8 * (3 - size)
        magnitude = mantissa
    else:
        magnitude = (mantissa << (8 * (size - 3))) & UINT256_MAX
    negative = mantissa != 0 and bool(bits & 0x00800000)
    overflow = mantissa != 0 and (size > 34 or (mantissa > 0xFF and size > 33) or (mantissa > 0xFFFF and size > 32))
    return magnitude, negative, overflow


def encode_compact(target: int) -> int:
    require_int(target, 0, UINT256_MAX)
    size = (target.bit_length() + 7) // 8
    word = target << (8 * (3 - size)) if size <= 3 else target >> (8 * (size - 3))
    if word & 0x00800000:
        word >>= 8
        size += 1
    return word | (size << 24)


def valid_target(bits: int, pow_limit: int) -> int:
    require_int(pow_limit, 1, UINT256_MAX)
    target, negative, overflow = decode_compact(bits)
    if negative or overflow or target == 0 or target > pow_limit:
        raise ValueError("Invalid proof-of-work target")
    return target


def check_pow(raw_hash: bytes, bits: int, pow_limit: int) -> bool:
    if not isinstance(raw_hash, bytes) or len(raw_hash) != 32:
        raise ValueError("Expected exactly 32 hash bytes")
    try:
        target = valid_target(bits, pow_limit)
    except ValueError:
        return False
    return int.from_bytes(raw_hash, "little") <= target


def block_work(bits: int, pow_limit: int) -> int:
    target = valid_target(bits, pow_limit)
    return (1 << 256) // (target + 1)


def retarget(old_bits: int, elapsed_seconds: int, pow_limit: int) -> int:
    """Mainnet-style calculation, without Bitcoin testnet exceptions."""
    old_target = valid_target(old_bits, pow_limit)
    require_int(elapsed_seconds, -(1 << 63), (1 << 63) - 1)
    elapsed = max(TARGET_TIMESPAN // 4, min(elapsed_seconds, TARGET_TIMESPAN * 4))
    # Preserve the bounded arithmetic of the comparison implementation.
    result = ((old_target * elapsed) & UINT256_MAX) // TARGET_TIMESPAN
    return encode_compact(min(result, pow_limit))


def next_work_required(next_height: int, old_bits: int, last_timestamp: int, first_timestamp: int | None, pow_limit: int, *, no_retarget: bool = False) -> int:
    """Caller supplies the branch's timestamp at next_height-2016 at boundaries.

    There is no peer-selected arbitrary target, min-difficulty delay exception,
    or chain lookup in this isolated helper. Full contextual validation is pending.
    """
    require_int(next_height, 1)
    valid_target(old_bits, pow_limit)
    require_int(last_timestamp, 0, (1 << 32) - 1)
    if type(no_retarget) is not bool:
        raise TypeError("no_retarget must be bool")
    if no_retarget or next_height % RETARGET_INTERVAL:
        return old_bits
    require_int(first_timestamp, 0, (1 << 32) - 1)
    return retarget(old_bits, last_timestamp - first_timestamp, pow_limit)


def merkle_root(leaves: list[bytes]) -> tuple[bytes, bool]:
    """Merkle commitment with mutation detection before odd-leaf padding."""
    level = list(leaves)
    for leaf in level:
        if not isinstance(leaf, bytes) or len(leaf) != 32:
            raise ValueError("Merkle leaves must be 32-byte internal-order hashes")
    mutated = False
    while len(level) > 1:
        mutated |= any(level[i] == level[i + 1] for i in range(0, len(level) - 1, 2))
        if len(level) % 2:
            level.append(level[-1])
        level = [sha256d(level[i] + level[i + 1]) for i in range(0, len(level), 2)]
    return (level[0] if level else bytes(32)), mutated


def encode_compact_size(value: int) -> bytes:
    require_int(value, 0, (1 << 64) - 1)
    if value < 253:
        return bytes([value])
    if value <= 0xFFFF:
        return b"\xfd" + struct.pack("<H", value)
    if value <= 0xFFFFFFFF:
        return b"\xfe" + struct.pack("<I", value)
    return b"\xff" + struct.pack("<Q", value)


def decode_compact_size(raw: bytes, maximum: int, offset: int = 0) -> tuple[int, int]:
    """Canonical CompactSize with a caller-chosen object/resource upper bound."""
    if not isinstance(raw, bytes):
        raise TypeError("Input must be bytes")
    require_int(maximum, 0, (1 << 64) - 1)
    require_int(offset, 0, len(raw))
    if offset == len(raw):
        raise ValueError("Truncated CompactSize")
    prefix = raw[offset]
    size = {253: 2, 254: 4, 255: 8}.get(prefix, 0)
    end = offset + 1 + size
    if end > len(raw):
        raise ValueError("Truncated CompactSize")
    value = prefix if not size else int.from_bytes(raw[offset + 1:end], "little")
    minimum = {253: 253, 254: 0x10000, 255: 0x100000000}.get(prefix, 0)
    if value < minimum or value > maximum:
        raise ValueError("Noncanonical or over-limit CompactSize")
    return value, end
