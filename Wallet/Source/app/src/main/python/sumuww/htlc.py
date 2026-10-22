"""Exact-template witness HTLCs; real secp256k1 signatures, BIP143 digests.

This exact template is enabled by Chain only at its configured activation height.
No general-purpose script interpreter or private-key arithmetic is implemented.
"""
from dataclasses import dataclass, replace
import hashlib
import struct
from coincurve import PublicKey, ecdsa
from .transaction import Transaction, TxOutput
from .primitives import sha256d, encode_compact_size
from .wallet import verify_p2wpkh, is_strict_der
from .errors import InvalidTransaction, UnsupportedFeature

def push(raw):
    if not 1 <= len(raw) <= 75:
        raise ValueError('Only canonical short pushes are used')
    return bytes([len(raw)]) + raw

def script_number(number):
    if type(number) is not int or not 17 <= number < 500_000_000:
        raise ValueError('Refund height must be in [17, 500000000)')
    raw = number.to_bytes((number.bit_length() + 7) // 8, 'little')
    return raw + (b'\0' if raw[-1] & 128 else b'')

@dataclass(frozen=True)
class Contract:
    secret_hash: bytes
    receiver_pubkey: bytes
    refund_pubkey: bytes
    refund_height: int

    def __post_init__(self):
        if not isinstance(self.secret_hash, bytes) or len(self.secret_hash) != 32:
            raise ValueError('Expected SHA256 commitment')
        for key in (self.receiver_pubkey, self.refund_pubkey):
            if len(key) != 33 or PublicKey(key).format() != key:
                raise ValueError('Compressed secp256k1 key required')
        script_number(self.refund_height)
        if self.receiver_pubkey == self.refund_pubkey:
            raise ValueError('Counterparties must have different keys')

    @property
    def script(self):
        # IF SHA256 <hash> EQUALVERIFY <receiver> CHECKSIG ELSE
        # <height> CHECKLOCKTIMEVERIFY DROP <refund> CHECKSIG ENDIF
        return (b'\x63\xa8' + push(self.secret_hash) + b'\x88' + push(self.receiver_pubkey)
                + b'\xac\x67' + push(script_number(self.refund_height))
                + b'\xb1\x75' + push(self.refund_pubkey) + b'\xac\x68')

    @property
    def script_pubkey(self):
        return b'\x00\x20' + hashlib.sha256(self.script).digest()

    @classmethod
    def parse(cls, raw):
        pos = 0
        def exact(value):
            nonlocal pos
            if raw[pos:pos+len(value)] != value:
                raise InvalidTransaction('Unsupported HTLC script template')
            pos += len(value)
        def take(length=None):
            nonlocal pos
            if pos >= len(raw): raise InvalidTransaction('Truncated script')
            count = raw[pos]
            pos += 1
            if not 1 <= count <= 75 or (length is not None and count != length) or pos + count > len(raw):
                raise InvalidTransaction('Noncanonical script push')
            value = raw[pos:pos+count]
            pos += count
            return value
        exact(b'\x63\xa8'); commitment = take(32); exact(b'\x88')
        receiver = take(33); exact(b'\xac\x67'); height = take()
        if len(height) > 4 or height[-1] & 128:
            raise InvalidTransaction('Invalid refund height')
        exact(b'\xb1\x75'); refund = take(33); exact(b'\xac\x68')
        try:
            contract = cls(commitment, receiver, refund, int.from_bytes(height, 'little'))
        except ValueError as exc:
            raise InvalidTransaction(str(exc)) from exc
        if pos != len(raw) or contract.script != raw:
            raise InvalidTransaction('Noncanonical HTLC script')
        return contract

def digest(tx, index, spent_output, witness_script):
    if not 0 <= index < len(tx.inputs): raise ValueError('Input index')
    item = tx.inputs[index]
    return sha256d(b''.join((
        struct.pack('<I', tx.version),
        sha256d(b''.join(i.outpoint() for i in tx.inputs)),
        sha256d(b''.join(struct.pack('<I', i.sequence) for i in tx.inputs)),
        item.outpoint(), encode_compact_size(len(witness_script)), witness_script,
        struct.pack('<q', spent_output.value), struct.pack('<I', item.sequence),
        sha256d(b''.join(o.serialize() for o in tx.outputs)),
        struct.pack('<I', tx.lock_time), struct.pack('<I', 1))))

def verify_spend(tx, index, spent_output):
    if len(spent_output.script_pubkey) != 34 or spent_output.script_pubkey[:2] != b'\x00\x20':
        return verify_p2wpkh(tx, index, spent_output)
    item = tx.inputs[index]
    if item.script_sig or len(item.witness) not in (3, 4): return False
    raw = item.witness[-1]
    if b'\x00\x20' + hashlib.sha256(raw).digest() != spent_output.script_pubkey: return False
    contract = Contract.parse(raw)
    if len(item.witness) == 4:
        signature, secret, branch, _ = item.witness
        if branch != b'\x01' or len(secret) != 32 or hashlib.sha256(secret).digest() != contract.secret_hash:
            return False
        pubkey = contract.receiver_pubkey
    else:
        signature, branch, _ = item.witness
        if branch != b'' or not contract.refund_height <= tx.lock_time < 500_000_000 or item.sequence == 0xFFFFFFFF:
            return False
        pubkey = contract.refund_pubkey
    if not is_strict_der(signature) or signature[-1] != 1: return False
    try:
        _, normalized = ecdsa.signature_normalize(ecdsa.der_to_cdata(signature[:-1]))
        return PublicKey(pubkey).verify(ecdsa.cdata_to_der(normalized), digest(tx, index, spent_output, raw), hasher=None)
    except ValueError:
        return False

def sign_spend(tx, index, spent_output, contract, key, *, secret=None):
    if spent_output.script_pubkey != contract.script_pubkey:
        raise ValueError('Contract does not match locked output')
    claiming = secret is not None
    expected = contract.receiver_pubkey if claiming else contract.refund_pubkey
    if key.pubkey != expected: raise ValueError('Wrong spending key')
    signature = key.sign_digest(digest(tx, index, spent_output, contract.script)) + b'\x01'
    witness = (signature, secret, b'\x01', contract.script) if claiming else (signature, b'', contract.script)
    items = list(tx.inputs)
    items[index] = replace(items[index], witness=witness)
    signed = replace(tx, inputs=tuple(items))
    if not verify_spend(signed, index, spent_output): raise ValueError('Invalid locally signed HTLC spend')
    return signed
