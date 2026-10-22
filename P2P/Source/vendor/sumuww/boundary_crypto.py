"""Portable boundary cryptography, with independent wallet-free node keys.

ECVRF suite 0x03 is RFC 9381 EDWARDS25519-SHA512-TAI. Secret
Edwards/scalar operations use libsodium, not Python curve multiplication.
BLS12-381 uses py_ecc's real POP ciphersuite. No mock signatures or test seeds.
"""
from hashlib import sha256, sha512
from functools import lru_cache
import hmac
import json
from pathlib import Path
import secrets
import sqlite3

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from nacl.bindings import (
    crypto_core_ed25519_add as point_add, crypto_core_ed25519_sub as point_sub,
    crypto_core_ed25519_is_valid_point as valid_point,
    crypto_core_ed25519_scalar_reduce as reduce_scalar,
    crypto_core_ed25519_scalar_mul as scalar_mul, crypto_core_ed25519_scalar_add as scalar_add,
    crypto_scalarmult_ed25519_noclamp as multiply_point,
    crypto_scalarmult_ed25519_base_noclamp as multiply_base,
)
from py_ecc.bls import G2ProofOfPossession as BLS
from py_ecc.bls.g2_primitives import G2_to_signature, signature_to_G2, subgroup_check
from py_ecc.optimized_bls12_381 import G2, add, neg, multiply, curve_order, is_inf, eq

IDENTITY = b'\x01' + bytes(31)
P = 2**255-19
D = (-121665*pow(121666, P-2, P)) % P
L = 2**252+27742317777372353535851937790883648493

@lru_cache(maxsize=4096)
def valid_bls_membership(public_key, proof_of_possession):
    # Cache this cryptographic statement only. Signed identity/IP bindings
    # remain separately authenticated; cache eviction never excludes nodes.
    return BLS.KeyValidate(public_key) and BLS.PopVerify(public_key, proof_of_possession)


@lru_cache(maxsize=4096)
def valid_bls_signature(public_key, message, signature):
    # Exact immutable cryptographic statements only; all election/history
    # rules are still evaluated by replay on every invocation.
    return BLS.Verify(public_key, message, signature)


@lru_cache(maxsize=4096)
def valid_bls_aggregate(public_keys, messages, signature):
    return BLS.AggregateVerify(public_keys, messages, signature)

def canonical(value):
    def validate(item):
        if item is None or type(item) in (str, bool): return
        if type(item) is int and -(2**53-1) <= item <= 2**53-1: return
        if type(item) is list:
            for child in item: validate(child)
            return
        if type(item) is dict and all(type(k) is str for k in item):
            for child in item.values(): validate(child)
            return
        raise ValueError('Noncanonical boundary data')
    validate(value)
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode('utf-8')

def digest(value): return sha256(canonical(value)).hexdigest()

def rawhex(value, length):
    if type(value) is not str or len(value) != length*2 or value != value.lower():
        raise ValueError('Noncanonical boundary hex')
    raw = bytes.fromhex(value)
    if len(raw) != length or raw.hex() != value: raise ValueError('Boundary hex length')
    return raw

def verify_identity(node_id, value, signature):
    try:
        Ed25519PublicKey.from_public_bytes(rawhex(node_id, 32)).verify(rawhex(signature, 64), canonical(value))
        return True
    except (ValueError, TypeError, Exception) as error:
        # cryptography's InvalidSignature is deliberately a rejected signature.
        return False

def _decode_public_point(encoded):
    """ZIP-215 public input decoding, matching the existing TAI implementation."""
    if len(encoded) != 32: raise ValueError('Edwards point length')
    number = int.from_bytes(encoded, 'little'); sign = number >> 255; y = (number & (2**255-1)) % P
    y2 = y*y % P
    x2 = (y2-1)*pow(D*y2+1, P-2, P) % P
    x = pow(x2, (P+3)//8, P)
    if x*x % P != x2: x = x*pow(2, (P-1)//4, P) % P
    if x*x % P != x2: raise ValueError('Not an Edwards point')
    if x % 2 != sign: x = P-x
    return (y | ((x & 1) << 255)).to_bytes(32, 'little')

def _cofactor_point(encoded):
    number = int.from_bytes(encoded, 'little')
    candidate = (((number & (2**255-1)) % P) | (number & (1 << 255))).to_bytes(32, 'little')
    for _ in range(3): candidate = point_add(candidate, candidate)
    return candidate


def _hash_to_point(public_key, alpha):
    for counter in range(256):
        try:
            encoded = sha512(b'\x03\x01'+public_key+alpha+bytes([counter, 0])).digest()[:32]
            # Preserve the existing ZIP-215 y reduction and sign bit. Sodium's
            # point addition performs the curve decoding in native code; the
            # same three doublings still clear the cofactor exactly as before.
            candidate = _cofactor_point(encoded)
            if candidate != IDENTITY and valid_point(candidate): return candidate
        except (ValueError, RuntimeError): pass
    raise ValueError('ECVRF hash-to-curve exhausted')

def _scalar(value): return value.to_bytes(32, 'little')
def _mul(scalar, point): return IDENTITY if scalar == bytes(32) else multiply_point(scalar, point)
def _base(scalar): return IDENTITY if scalar == bytes(32) else multiply_base(scalar)
def _challenge(y, h, gamma, u, v): return sha512(b'\x03\x02'+y+h+gamma+u+v+b'\x00').digest()[:16]
def _vrf_output(gamma):
    for _ in range(3): gamma = point_add(gamma, gamma)
    return sha512(b'\x03\x03'+gamma+b'\x00').digest()

def vrf_prove(seed, alpha):
    if type(seed) is not bytes or len(seed) != 32 or type(alpha) is not bytes: raise ValueError('ECVRF input')
    expanded = sha512(seed).digest(); clamped = bytearray(expanded[:32]); clamped[0] &= 248; clamped[31] &= 127; clamped[31] |= 64
    x = reduce_scalar(bytes(clamped)+bytes(32)); y = _base(x); h = _hash_to_point(y, alpha)
    gamma = _mul(x, h); k = reduce_scalar(sha512(expanded[32:]+h).digest())
    c = _challenge(y, h, gamma, _base(k), _mul(k, h))
    s = scalar_add(k, scalar_mul(c+bytes(16), x))
    proof = gamma+c+s
    return proof, vrf_verify(y, proof, alpha)

def vrf_verify(public_key, proof, alpha):
    # Cache only a successfully verified, immutable cryptographic statement.
    # Every byte of the key, proof and seed context is part of the cache key.
    # Eviction changes cost only; it never excludes an election respondent.
    if all(type(value) is bytes for value in (public_key, proof, alpha)) and len(alpha) <= 4096:
        return _vrf_verified(public_key, proof, alpha)
    return _vrf_verify_uncached(public_key, proof, alpha)


@lru_cache(maxsize=65536)
def _vrf_verified(public_key, proof, alpha):
    return _vrf_verify_uncached(public_key, proof, alpha)


def _vrf_verify_uncached(public_key, proof, alpha):
    if len(public_key) != 32 or len(proof) != 80 or type(alpha) is not bytes or not valid_point(public_key):
        raise ValueError('Invalid ECVRF key/proof')
    gamma, c, s = proof[:32], proof[32:48], proof[48:]
    if not valid_point(gamma) or int.from_bytes(s, 'little') >= L: raise ValueError('Invalid ECVRF proof point/scalar')
    h = _hash_to_point(public_key, alpha); c_scalar = c+bytes(16)
    u = point_sub(_base(s), _mul(c_scalar, public_key)); v = point_sub(_mul(s, h), _mul(c_scalar, gamma))
    if not hmac.compare_digest(c, _challenge(public_key, h, gamma, u, v)): raise ValueError('Invalid ECVRF challenge')
    return _vrf_output(gamma)

def split_signature(signature):
    original = signature_to_G2(signature)
    if is_inf(original) or not subgroup_check(original): raise ValueError('Invalid completed BLS signature')
    while True:
        a = multiply(G2, secrets.randbelow(curve_order-1)+1)
        b = add(original, neg(a))
        if not is_inf(b): return G2_to_signature(a), G2_to_signature(b)

def verify_split(signature, part_a, part_b):
    try:
        original, a, b = map(signature_to_G2, (signature, part_a, part_b))
        return all(not is_inf(p) and subgroup_check(p) for p in (original, a, b)) and eq(add(a, b), original)
    except (ValueError, TypeError, AssertionError): return False

class NodeKeys:
    """Random per-install node keys; unrelated to any wallet signing key."""
    def __init__(self, database, network):
        path = Path(database); path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path, isolation_level=None, timeout=10)
        self.db.executescript('PRAGMA journal_mode=WAL; PRAGMA synchronous=FULL; CREATE TABLE IF NOT EXISTS boundary_identity (one INTEGER PRIMARY KEY CHECK(one=1), network TEXT, seed BLOB, bls TEXT); CREATE TABLE IF NOT EXISTS boundary_signatures (slot TEXT PRIMARY KEY, message BLOB, signature BLOB);')
        self.db.execute('BEGIN IMMEDIATE')
        try:
            row = self.db.execute('SELECT network,seed,bls FROM boundary_identity WHERE one=1').fetchone()
            if row is None:
                row = (network, secrets.token_bytes(32), str(BLS.KeyGen(secrets.token_bytes(32))))
                self.db.execute('INSERT INTO boundary_identity VALUES (1,?,?,?)', row)
            if row[0] != network: raise ValueError('Boundary key network mismatch')
            self.db.execute('COMMIT')
        except BaseException:
            self.db.execute('ROLLBACK'); self.db.close(); raise
        self._seed, self._bls = bytes(row[1]), int(row[2]); self._ed = Ed25519PrivateKey.from_private_bytes(self._seed)
        self.node_id = self._ed.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw).hex()
        self.public_key = BLS.SkToPk(self._bls); self.pop = BLS.PopProve(self._bls)
        try: path.chmod(0o600)
        except OSError: pass

    def sign(self, payload): return self._ed.sign(canonical(payload)).hex()
    def signed(self, payload): return {'payload':payload, 'signature':self.sign(payload)}
    def ticket(self, alpha):
        proof, output = vrf_prove(self._seed, alpha)
        return {'id':self.node_id, 'inputDigest':sha256(alpha).hexdigest(), 'proof':proof.hex(), 'output':output.hex()}
    def sign_once(self, slot, message):
        self.db.execute('BEGIN IMMEDIATE')
        try:
            old = self.db.execute('SELECT message,signature FROM boundary_signatures WHERE slot=?', (slot,)).fetchone()
            if old:
                if old[0] != message: raise ValueError('Boundary conflicting private signature')
                self.db.execute('COMMIT'); return bytes(old[1])
            signature = BLS.Sign(self._bls, message)
            self.db.execute('INSERT INTO boundary_signatures VALUES (?,?,?)', (slot, message, signature))
            self.db.execute('COMMIT'); return signature
        except BaseException:
            if self.db.in_transaction: self.db.execute('ROLLBACK')
            raise
    def close(self): self.db.close()
