"""Canonical local block objects and a distinct, fixed development genesis."""

from dataclasses import dataclass
from hashlib import sha256
import struct

from .errors import MiningExhausted, ValidationError
from .primitives import Header, REGTEST_POW_LIMIT, decode_compact_size, encode_compact_size, merkle_root, require_int, sha256d, subsidy, valid_target
from .transaction import Transaction, TxInput, TxOutput, coinbase_height_prefix

MAX_BLOCK_WEIGHT = 4_000_000
REGTEST_BITS = 0x207FFFFF
GENESIS_TIME = 1_700_000_000
GENESIS_MESSAGE = b'DORA independent local-regtest prototype 0.8'
PROFILE_ID = 'dora-local-regtest-v0.8-p2wpkh'


@dataclass(frozen=True)
class Block:
    header: Header
    transactions: tuple[Transaction, ...]

    def serialize(self, include_witness=True) -> bytes:
        return self.header.serialize() + encode_compact_size(len(self.transactions)) + b''.join(t.serialize(include_witness=include_witness) for t in self.transactions)

    @classmethod
    def deserialize(cls, raw: bytes):
        if not isinstance(raw, bytes) or not 81 <= len(raw) <= MAX_BLOCK_WEIGHT:
            raise ValidationError('Block byte length outside development profile bounds')
        header = Header.deserialize(raw[:80])
        try:
            count, offset = decode_compact_size(raw, MAX_BLOCK_WEIGHT // 10, 80)
            if count == 0:
                raise ValidationError('Empty block')
            transactions = []
            for _ in range(count):
                transaction, offset = Transaction.deserialize_from(raw, offset)
                transactions.append(transaction)
            if offset != len(raw):
                raise ValidationError('Trailing block bytes')
            return cls(header, tuple(transactions))
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc

    def block_hash(self) -> bytes:
        return self.header.digest()

    def weight(self) -> int:
        return len(self.serialize(False)) * 3 + len(self.serialize(True))


def has_witness(transaction: Transaction) -> bool:
    return any(item.witness for item in transaction.inputs)


def witness_commitment(transactions: tuple[Transaction, ...], reserved: bytes) -> bytes:
    if len(reserved) != 32:
        raise ValidationError('Witness reserved value must have 32 bytes')
    root, _ = merkle_root([bytes(32)] + [t.wtxid() for t in transactions[1:]])
    return sha256d(root + reserved)


def build_coinbase(height: int, pay_script: bytes, fees: int = 0, extra_nonce: int = 0, witness_reserved: bytes | None = None, commitment: bytes | None = None) -> Transaction:
    script = coinbase_height_prefix(height) + b'\x04' + struct.pack('<I', extra_nonce)
    witness = () if witness_reserved is None else (witness_reserved,)
    inputs = (TxInput(bytes(32), 0xFFFFFFFF, script, 0xFFFFFFFF, witness),)
    outputs = [TxOutput(subsidy(height) + fees, pay_script)]
    if commitment is not None:
        if len(commitment) != 32:
            raise ValidationError('Invalid witness commitment length')
        outputs.append(TxOutput(0, b'\x6a\x24\xaa\x21\xa9\xed' + commitment))
    return Transaction(2, inputs, tuple(outputs), 0)


def mine_header(header: Header, max_attempts: int = 1_000_000, *, pow_limit: int = REGTEST_POW_LIMIT, cancel_check=None) -> Header:
    """Search nonce 0 upward with identical header bytes and optional cancellation.

    Reuse SHA256's immutable 76-byte header prefix and instantiate a Header only
    for a winning nonce. This changes mining cost, never proof-of-work rules.
    """
    require_int(max_attempts, 1, 1 << 32)
    if not isinstance(header, Header):
        raise TypeError('Expected a Header for mining')
    if cancel_check is not None and not callable(cancel_check):
        raise TypeError('Mining cancellation check must be callable')
    target = valid_target(header.bits, pow_limit)
    prefix = sha256(header.serialize()[:76])
    for nonce in range(max_attempts):
        if cancel_check is not None and (nonce & 4095) == 0 and cancel_check():
            raise RuntimeError('Mining cancelled')
        first = prefix.copy()
        first.update(struct.pack('<I', nonce))
        digest = sha256(first.digest()).digest()
        if int.from_bytes(digest, 'little') <= target:
            return Header(header.version, header.previous_hash, header.merkle_root,
                          header.timestamp, header.bits, nonce)
    raise MiningExhausted('Local proof-of-work search exhausted its bounded attempt budget')


def genesis_block() -> Block:
    # The fixed genesis has no spendable UTXO and no developer allocation.
    tx = Transaction(1, (TxInput(bytes(32), 0xFFFFFFFF, b'\x00' + GENESIS_MESSAGE),), (TxOutput(subsidy(0), b'\x6a' + bytes([len(GENESIS_MESSAGE)]) + GENESIS_MESSAGE),), 0)
    root, _ = merkle_root([tx.txid()])
    header = mine_header(Header(1, bytes(32), root, GENESIS_TIME, REGTEST_BITS, 0))
    return Block(header, (tx,))
