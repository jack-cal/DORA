"""Local test-key helpers for the v0.8 native P2WPKH/SIGHASH_ALL profile.

This is not an HD wallet, keystore, backup system, or production custody API.
RegtestKey deliberately takes an explicit test scalar: demo keys are public test
fixtures and must never be used to receive valuable assets. ECDSA operations use
coincurve/libsecp256k1; no elliptic-curve or nonce implementation is provided here.

The signer creates compressed public keys and low-S signatures. Verification
does not promote those local choices into consensus restrictions: valid high-S
and uncompressed public-key witnesses remain acceptable in this supported path.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
import hashlib

from coincurve import PrivateKey, PublicKey, ecdsa

from .errors import InvalidTransaction, UnsupportedFeature
from .transaction import Transaction, TxOutput, bip143_sighash_all


SECP256K1_ORDER = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141
SIGHASH_ALL = 0x01


def hash160(data: bytes) -> bytes:
    """RIPEMD160(SHA256(data)), using the runtime's reviewed hash primitives."""
    if not isinstance(data, bytes):
        raise TypeError("hash160 input must be bytes")
    return hashlib.new("ripemd160", hashlib.sha256(data).digest()).digest()


def p2wpkh_script(pubkey: bytes) -> bytes:
    """Build native witness-v0 pubkey-hash script for a valid serialized key.

    RegtestKey emits compressed keys; accepting an uncompressed key here avoids
    treating compressed-only relay policy as a new block-validity restriction.
    """
    if not isinstance(pubkey, bytes):
        raise TypeError("public key must be bytes")
    try:
        PublicKey(pubkey)
    except ValueError as exc:
        raise InvalidTransaction("invalid secp256k1 public key") from exc
    return b"\x00\x14" + hash160(pubkey)


def is_strict_der(signature_with_hashtype: bytes) -> bool:
    """Check BIP66's structural DER rules, including the final sighash byte.

    This does not check the sighash value, low-S policy, scalar ranges, or ECDSA
    truth. The bounded length/index checks are independent of libsecp's parser.
    """
    sig = signature_with_hashtype
    if not isinstance(sig, bytes) or not 9 <= len(sig) <= 73:
        return False
    if sig[0] != 0x30 or sig[1] != len(sig) - 3:
        return False
    rlen = sig[3]
    if 5 + rlen >= len(sig):
        return False
    slen = sig[5 + rlen]
    if rlen + slen + 7 != len(sig):
        return False
    if sig[2] != 0x02 or rlen == 0 or sig[4] & 0x80:
        return False
    if rlen > 1 and sig[4] == 0 and not sig[5] & 0x80:
        return False
    if sig[rlen + 4] != 0x02 or slen == 0 or sig[rlen + 6] & 0x80:
        return False
    if slen > 1 and sig[rlen + 6] == 0 and not sig[rlen + 7] & 0x80:
        return False
    return True


@dataclass(frozen=True, repr=False)
class RegtestKey:
    """Explicit local test key; not a secure key-generation/storage interface."""

    _private_key: PrivateKey = field(repr=False)

    @classmethod
    def from_int(cls, scalar: int) -> "RegtestKey":
        if type(scalar) is not int or not 1 <= scalar < SECP256K1_ORDER:
            raise ValueError("test scalar must be an integer in secp256k1 range")
        return cls(PrivateKey(scalar.to_bytes(32, "big")))

    @property
    def pubkey(self) -> bytes:
        return self._private_key.public_key.format(compressed=True)

    @property
    def script_pubkey(self) -> bytes:
        return p2wpkh_script(self.pubkey)

    def public_key_bytes(self, *, compressed: bool = True) -> bytes:
        return self._private_key.public_key.format(compressed=compressed)

    def sign_digest(self, digest: bytes) -> bytes:
        """DER ECDSA of an already computed 32-byte digest, without rehashing."""
        if not isinstance(digest, bytes) or len(digest) != 32:
            raise ValueError("signature digest must be exactly 32 bytes")
        return self._private_key.sign(digest, hasher=None)

    def __repr__(self) -> str:
        return "RegtestKey(test_only=True)"


def _require_supported_output(spent_output: TxOutput) -> None:
    script = spent_output.script_pubkey
    if len(script) != 22 or script[:2] != b"\x00\x14":
        raise UnsupportedFeature("v0.8 supports only native P2WPKH spending")


def _require_input_index(tx: Transaction, input_index: int) -> None:
    if type(input_index) is not int or not 0 <= input_index < len(tx.inputs):
        raise InvalidTransaction("input index is outside the transaction")


def sign_p2wpkh(
    tx: Transaction,
    input_index: int,
    spent_output: TxOutput,
    key: RegtestKey,
) -> Transaction:
    """Return a new transaction with one native P2WPKH input signed locally."""
    _require_supported_output(spent_output)
    _require_input_index(tx, input_index)
    if tx.inputs[input_index].script_sig:
        raise InvalidTransaction("native P2WPKH scriptSig must be empty")
    if spent_output.script_pubkey != key.script_pubkey:
        raise InvalidTransaction("test key does not own the spent output")
    digest = bip143_sighash_all(tx, input_index, spent_output.script_pubkey, spent_output.value)
    signature = key.sign_digest(digest) + bytes([SIGHASH_ALL])
    inputs = list(tx.inputs)
    inputs[input_index] = replace(inputs[input_index], witness=(signature, key.pubkey))
    signed = replace(tx, inputs=tuple(inputs))
    if not verify_p2wpkh(signed, input_index, spent_output):
        raise InvalidTransaction("locally generated signature failed verification")
    return signed


def verify_p2wpkh(tx: Transaction, input_index: int, spent_output: TxOutput) -> bool:
    """Verify the supported witness spend, using the actual spent output amount.

    Unsupported script/sighash paths raise UnsupportedFeature and must not be
    cached as consensus-invalid. False denotes a failed supported P2WPKH spend.
    UTXO availability, maturity, amount totals, and transaction/block resource
    limits remain the node's responsibility, rather than being wallet decisions.
    """
    _require_supported_output(spent_output)
    _require_input_index(tx, input_index)
    txin = tx.inputs[input_index]
    if txin.script_sig or len(txin.witness) != 2:
        return False
    signature, pubkey = txin.witness
    if not isinstance(signature, bytes) or not isinstance(pubkey, bytes):
        return False
    if not is_strict_der(signature):
        return False
    if signature[-1] != SIGHASH_ALL:
        raise UnsupportedFeature("v0.8 supports only BIP143 SIGHASH_ALL")
    if hash160(pubkey) != spent_output.script_pubkey[2:]:
        return False
    digest = bip143_sighash_all(tx, input_index, spent_output.script_pubkey, spent_output.value)
    try:
        public_key = PublicKey(pubkey)
        original = ecdsa.der_to_cdata(signature[:-1])
        # libsecp's verification API requires low-S. Normalize only after strict
        # original DER checks; never reject a valid high-S block witness as policy.
        _, normalized = ecdsa.signature_normalize(original)
        return public_key.verify(ecdsa.cdata_to_der(normalized), digest, hasher=None)
    except ValueError:
        return False

