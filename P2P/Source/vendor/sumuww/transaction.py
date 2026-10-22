"""Bounded Bitcoin-style transaction bytes for the local SUMUWW development profile.

This independently written codec does not execute scripts or validate UTXOs,
coinbase maturity, locks, fees, duplicate inputs, or block commitments. The
chainstate validator must perform those checks. Unsupported spending features
must not be treated as valid or cached as consensus-invalid.

Wire comparison: Bitcoin Core v29.0, commit
f490f5562d4b20857ef8d042c050763795fd43da, src/primitives/transaction.h.
Digest reference: https://github.com/bitcoin/bips/blob/master/bip-0143.mediawiki
Weight reference: https://github.com/bitcoin/bips/blob/master/bip-0141.mediawiki
"""

from dataclasses import dataclass, replace
import struct

from .errors import InvalidTransaction, UnsupportedFeature
from .primitives import MAX_MONEY, decode_compact_size, encode_compact_size, sha256d

MAX_TRANSACTION_WEIGHT = 4_000_000
MAX_TRANSACTION_BYTES = 4_000_000
UINT32_MAX = (1 << 32) - 1
NULL_TXID = bytes(32)
SIGHASH_ALL = 1
# Every base byte contributes four weight units, even for witness transactions.
MAX_INPUT_COUNT = MAX_TRANSACTION_WEIGHT // (41 * 4)
MAX_OUTPUT_COUNT = MAX_TRANSACTION_WEIGHT // (9 * 4)


def _integer(value: int, minimum: int, maximum: int, name: str) -> int:
    if type(value) is not int or not minimum <= value <= maximum:
        raise InvalidTransaction(f"{name} is outside its integer range")
    return value


def _bytes(value: bytes, name: str, maximum: int = MAX_TRANSACTION_BYTES) -> bytes:
    if not isinstance(value, bytes) or len(value) > maximum:
        raise InvalidTransaction(f"{name} must be bounded immutable bytes")
    return value


def _compact_length(value: int) -> int:
    if value < 253:
        return 1
    if value <= 0xffff:
        return 3
    if value <= UINT32_MAX:
        return 5
    return 9


def _blob(raw: bytes) -> bytes:
    return encode_compact_size(len(raw)) + raw


@dataclass(frozen=True)
class TxInput:
    """prev_txid is the 32 raw hash bytes, not display-order hexadecimal."""

    prev_txid: bytes
    prev_index: int
    script_sig: bytes = b""
    sequence: int = UINT32_MAX
    witness: tuple[bytes, ...] = ()

    def __post_init__(self):
        _bytes(self.prev_txid, "prev_txid", 32)
        if len(self.prev_txid) != 32:
            raise InvalidTransaction("prev_txid must have exactly 32 bytes")
        _integer(self.prev_index, 0, UINT32_MAX, "prev_index")
        _bytes(self.script_sig, "script_sig")
        _integer(self.sequence, 0, UINT32_MAX, "sequence")
        if type(self.witness) is not tuple or len(self.witness) > MAX_TRANSACTION_BYTES:
            raise InvalidTransaction("witness must be a bounded tuple")
        witness_bytes = _compact_length(len(self.witness))
        for item in self.witness:
            _bytes(item, "witness item")
            witness_bytes += _compact_length(len(item)) + len(item)
            if witness_bytes > MAX_TRANSACTION_BYTES:
                raise InvalidTransaction("witness exceeds the byte budget")

    def outpoint(self) -> bytes:
        return self.prev_txid + struct.pack("<I", self.prev_index)

    def serialize(self) -> bytes:
        """Input base serialization; the transaction writes witness separately."""
        return self.outpoint() + _blob(self.script_sig) + struct.pack("<I", self.sequence)


@dataclass(frozen=True)
class TxOutput:
    value: int
    script_pubkey: bytes

    def __post_init__(self):
        _integer(self.value, 0, MAX_MONEY, "output value")
        _bytes(self.script_pubkey, "script_pubkey")

    def serialize(self) -> bytes:
        # Nonnegative values have the same bytes as the signed int64 wire field.
        return struct.pack("<q", self.value) + _blob(self.script_pubkey)


class _Reader:
    """One-transaction byte and weight budget, without declared-count allocation."""

    def __init__(self, raw: bytes, offset: int):
        _bytes(raw, "serialized buffer", maximum=len(raw) if isinstance(raw, bytes) else 0)
        _integer(offset, 0, len(raw), "offset")
        self.raw = raw
        self.offset = offset
        self.start = offset
        self.weight = 0

    def available(self, witness: bool = False) -> int:
        scale = 1 if witness else 4
        return min(len(self.raw) - self.offset,
                   (MAX_TRANSACTION_WEIGHT - self.weight) // scale,
                   MAX_TRANSACTION_BYTES - (self.offset - self.start))

    def _advance(self, count: int, witness: bool = False):
        if count > self.available(witness):
            raise InvalidTransaction("Truncated transaction or exceeded byte/weight budget")
        self.offset += count
        self.weight += count * (1 if witness else 4)

    def take(self, count: int, witness: bool = False) -> bytes:
        begin = self.offset
        self._advance(count, witness)
        return self.raw[begin:self.offset]

    def compact(self, maximum: int, witness: bool = False) -> int:
        try:
            value, end = decode_compact_size(self.raw, maximum=maximum, offset=self.offset)
        except (TypeError, ValueError) as exc:
            raise InvalidTransaction("Invalid or unbounded CompactSize") from exc
        self._advance(end - self.offset, witness)
        return value

    def blob(self, witness: bool = False) -> bytes:
        count = self.compact(self.available(witness), witness)
        return self.take(count, witness)


@dataclass(frozen=True)
class Transaction:
    # The frozen v29.0 comparison source uses uint32_t for transaction version.
    version: int
    inputs: tuple[TxInput, ...]
    outputs: tuple[TxOutput, ...]
    lock_time: int = 0

    def __post_init__(self):
        _integer(self.version, 0, UINT32_MAX, "transaction version")
        _integer(self.lock_time, 0, UINT32_MAX, "lock_time")
        if type(self.inputs) is not tuple or len(self.inputs) > MAX_INPUT_COUNT:
            raise InvalidTransaction("inputs must be a bounded tuple")
        if type(self.outputs) is not tuple or len(self.outputs) > MAX_OUTPUT_COUNT:
            raise InvalidTransaction("outputs must be a bounded tuple")
        if any(not isinstance(item, TxInput) for item in self.inputs):
            raise InvalidTransaction("inputs must contain TxInput objects")
        if any(not isinstance(item, TxOutput) for item in self.outputs):
            raise InvalidTransaction("outputs must contain TxOutput objects")
        base, total = self._sizes()
        if total > MAX_TRANSACTION_BYTES or base * 3 + total > MAX_TRANSACTION_WEIGHT:
            raise InvalidTransaction("Transaction exceeds the byte/weight budget")

    def has_witness(self) -> bool:
        # A stack containing one empty item is nonempty witness data.
        return any(item.witness for item in self.inputs)

    def _sizes(self) -> tuple[int, int]:
        base = 8 + _compact_length(len(self.inputs)) + _compact_length(len(self.outputs))
        base += sum(40 + _compact_length(len(item.script_sig)) + len(item.script_sig)
                    for item in self.inputs)
        base += sum(8 + _compact_length(len(item.script_pubkey)) + len(item.script_pubkey)
                    for item in self.outputs)
        if not self.has_witness():
            return base, base
        witness_bytes = 2
        for item in self.inputs:
            witness_bytes += _compact_length(len(item.witness))
            witness_bytes += sum(_compact_length(len(part)) + len(part) for part in item.witness)
        return base, base + witness_bytes

    def serialize(self, include_witness: bool = True) -> bytes:
        if type(include_witness) is not bool:
            raise InvalidTransaction("include_witness must be bool")
        use_witness = include_witness and self.has_witness()
        pieces = [struct.pack("<I", self.version)]
        if use_witness:
            pieces.append(b"\x00\x01")
        pieces.append(encode_compact_size(len(self.inputs)))
        pieces.extend(item.serialize() for item in self.inputs)
        pieces.append(encode_compact_size(len(self.outputs)))
        pieces.extend(item.serialize() for item in self.outputs)
        if use_witness:
            for item in self.inputs:
                pieces.append(encode_compact_size(len(item.witness)))
                pieces.extend(_blob(part) for part in item.witness)
        pieces.append(struct.pack("<I", self.lock_time))
        return b"".join(pieces)

    @classmethod
    def deserialize_from(cls, raw: bytes, offset: int = 0) -> tuple["Transaction", int]:
        """Read one canonical transaction; return the first unconsumed byte offset."""
        reader = _Reader(raw, offset)
        version = struct.unpack("<I", reader.take(4))[0]
        input_count = reader.compact(min(MAX_INPUT_COUNT, reader.available() // 41))
        flags = 0
        if input_count == 0:
            # 00/00 represents empty vin/vout. Any nonzero flag is extended form.
            flags = reader.take(1, witness=True)[0]
            if flags not in (0, 1):
                raise InvalidTransaction("Unknown transaction optional-data flags")
            if flags:
                # The first zero count was a witness marker, not part of the base.
                reader.weight -= 3
                input_count = reader.compact(min(MAX_INPUT_COUNT, reader.available() // 41))
            else:
                # With no extension, this byte is the empty output-count byte.
                reader.weight += 3
        inputs = []
        for _ in range(input_count):
            prev_txid = reader.take(32)
            prev_index = struct.unpack("<I", reader.take(4))[0]
            script_sig = reader.blob()
            sequence = struct.unpack("<I", reader.take(4))[0]
            inputs.append(TxInput(prev_txid, prev_index, script_sig, sequence))
        outputs = []
        if input_count or flags:
            output_count = reader.compact(min(MAX_OUTPUT_COUNT, reader.available() // 9))
            for _ in range(output_count):
                value = struct.unpack("<q", reader.take(8))[0]
                outputs.append(TxOutput(value, reader.blob()))
        if flags:
            has_witness = False
            for index, item in enumerate(inputs):
                item_count = reader.compact(reader.available(witness=True), witness=True)
                witness = tuple(reader.blob(witness=True) for _ in range(item_count))
                has_witness |= bool(witness)
                inputs[index] = replace(item, witness=witness)
            if not has_witness:
                raise InvalidTransaction("Superfluous all-empty witness record")
        lock_time = struct.unpack("<I", reader.take(4))[0]
        tx = cls(version, tuple(inputs), tuple(outputs), lock_time)
        return tx, reader.offset

    @classmethod
    def deserialize(cls, raw: bytes) -> "Transaction":
        _bytes(raw, "serialized transaction")
        tx, end = cls.deserialize_from(raw)
        if end != len(raw):
            raise InvalidTransaction("Trailing bytes after transaction")
        return tx

    def txid(self) -> bytes:
        return sha256d(self.serialize(include_witness=False))

    def wtxid(self) -> bytes:
        """Actual hash; witness merkle construction separately uses zero for coinbase."""
        return sha256d(self.serialize(include_witness=True))

    def weight(self) -> int:
        base, total = self._sizes()
        return base * 3 + total

    def is_coinbase(self) -> bool:
        return (len(self.inputs) == 1 and self.inputs[0].prev_txid == NULL_TXID
                and self.inputs[0].prev_index == UINT32_MAX)


def coinbase_height_prefix(height: int) -> bytes:
    """CScript << nonnegative block height, including OP_0 and OP_1..OP_16.

    This creates only the BIP34 prefix. A coinbase scriptSig still needs total
    length 2..100 bytes and block-context validation in the chainstate layer.
    """
    _integer(height, 0, (1 << 31) - 1, "coinbase height")
    if height == 0:
        return b"\x00"
    if height <= 16:
        return bytes([0x50 + height])
    raw = height.to_bytes((height.bit_length() + 7) // 8, "little")
    if raw[-1] & 0x80:
        raw += b"\x00"
    return bytes([len(raw)]) + raw


def bip143_sighash_all(tx: Transaction, input_index: int,
                      prev_script_pubkey: bytes, prev_value: int) -> bytes:
    """BIP143 SIGHASH_ALL for a native version-0 P2WPKH prevout only.

    This function computes a digest, not a signature validity decision. The
    caller must match the witness public key and prevout hash and enforce the
    signature's final sighash byte as 01. Other scripts/sighash modes require a
    separately implemented verifier; they must fail closed in this prototype.
    """
    if not isinstance(tx, Transaction):
        raise InvalidTransaction("Expected a Transaction")
    _integer(input_index, 0, len(tx.inputs) - 1, "input_index")
    _bytes(prev_script_pubkey, "previous script_pubkey")
    _integer(prev_value, 0, MAX_MONEY, "previous output value")
    if len(prev_script_pubkey) != 22 or prev_script_pubkey[:2] != b"\x00\x14":
        raise UnsupportedFeature("Only native P2WPKH BIP143 SIGHASH_ALL is implemented")
    item = tx.inputs[input_index]
    script_code = b"\x76\xa9\x14" + prev_script_pubkey[2:] + b"\x88\xac"
    preimage = b"".join((
        struct.pack("<I", tx.version),
        sha256d(b"".join(part.outpoint() for part in tx.inputs)),
        sha256d(b"".join(struct.pack("<I", part.sequence) for part in tx.inputs)),
        item.outpoint(), _blob(script_code), struct.pack("<q", prev_value),
        struct.pack("<I", item.sequence),
        sha256d(b"".join(part.serialize() for part in tx.outputs)),
        struct.pack("<I", tx.lock_time), struct.pack("<I", SIGHASH_ALL),
    ))
    return sha256d(preimage)
