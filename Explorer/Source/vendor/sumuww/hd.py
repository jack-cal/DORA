"""BIP32 key derivation and BIP39 English mnemonics for local SUMUWW wallets.

Algorithms: https://github.com/bitcoin/bips/blob/master/bip-0032.mediawiki
and https://github.com/bitcoin/bips/blob/master/bip-0039.mediawiki.
HMAC, PBKDF2 and hashes use Python/OpenSSL; EC operations use libsecp256k1
through coincurve. No cipher or elliptic-curve primitive is implemented here.
Extended Bitcoin xpub/xprv encodings are an explicit interchange primitive;
their version bytes do not identify a SUMUWW network or promise wallet support
by another application. Secret exports require explicit method calls.
"""

from dataclasses import dataclass, field
from functools import lru_cache
import hashlib
import hmac
from pathlib import Path
import re
import sys
import unicodedata

from coincurve import PrivateKey, PublicKey

from .wallet import SECP256K1_ORDER, hash160

HARDENED = 1 << 31
SUMUWW_NAMESPACE = 0x444F5241
WORDLIST_SHA256 = '2f5eed53a4727b4bf8880d8f3f199efc90e58503646d9ff8eff3a2ed3b24dbda'
_ALPHABET = '123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz'
_VERSIONS = {False: (0x0488B21E, 0x0488ADE4), True: (0x043587CF, 0x04358394)}


class HDKeyError(ValueError):
    """Safe error that never includes a seed, mnemonic or private key."""


def _integer(value, minimum, maximum, message):
    if type(value) is not int or not minimum <= value <= maximum:
        raise HDKeyError(message)
    return value


def _hmac(key, data):
    return hmac.new(key, data, hashlib.sha512).digest()


def _metadata(chain_code, depth, fingerprint, child_number):
    if type(chain_code) is not bytes or len(chain_code) != 32:
        raise HDKeyError('HD chain code must contain exactly 32 bytes')
    _integer(depth, 0, 255, 'HD depth is outside the supported range')
    _integer(child_number, 0, 0xFFFFFFFF, 'HD child index is outside the supported range')
    if type(fingerprint) is not bytes or len(fingerprint) != 4:
        raise HDKeyError('HD parent fingerprint must contain exactly 4 bytes')
    if depth == 0 and (fingerprint != bytes(4) or child_number != 0):
        raise HDKeyError('HD master metadata is invalid')


def parse_path(path):
    if type(path) is not str or len(path) > 512:
        raise HDKeyError('HD derivation path is invalid')
    components = path.split('/')
    if components[0] != 'm' or len(components) > 256:
        raise HDKeyError('HD derivation path is invalid')
    result = []
    for part in components[1:]:
        if not re.fullmatch(r'(0|[1-9][0-9]{0,9})([\'hH]?)', part):
            raise HDKeyError('HD derivation path is invalid')
        hardened = part[-1:] in ("'", 'h', 'H')
        value = int(part[:-1] if hardened else part)
        _integer(value, 0, HARDENED - 1, 'HD derivation index is outside the supported range')
        result.append(value + (HARDENED if hardened else 0))
    return tuple(result)


def _base58(raw):
    value = int.from_bytes(raw, 'big')
    encoded = ''
    while value:
        value, index = divmod(value, 58)
        encoded = _ALPHABET[index] + encoded
    return '1' * (len(raw) - len(raw.lstrip(b'\0'))) + encoded


def _extended(node, key_data, private, testnet):
    if type(testnet) is not bool:
        raise HDKeyError('HD extended-key network flag must be boolean')
    version = _VERSIONS[testnet][int(private)]
    raw = (version.to_bytes(4, 'big') + bytes([node.depth]) + node.parent_fingerprint
           + node.child_number.to_bytes(4, 'big') + node.chain_code + key_data)
    checksum = hashlib.sha256(hashlib.sha256(raw).digest()).digest()[:4]
    return _base58(raw + checksum)


@dataclass(frozen=True, repr=False)
class HDPublicNode:
    _public_key: PublicKey = field(repr=False)
    chain_code: bytes = field(repr=False)
    depth: int = 0
    parent_fingerprint: bytes = bytes(4)
    child_number: int = 0

    def __post_init__(self):
        if not isinstance(self._public_key, PublicKey):
            raise HDKeyError('HD public key is invalid')
        _metadata(self.chain_code, self.depth, self.parent_fingerprint, self.child_number)

    @property
    def pubkey(self):
        return self._public_key.format(compressed=True)

    @property
    def fingerprint(self):
        return hash160(self.pubkey)[:4]

    def derive_child(self, index, *, skip_invalid=True):
        _integer(index, 0, HARDENED - 1, 'Public HD derivation cannot use a hardened index')
        if type(skip_invalid) is not bool or self.depth == 255:
            raise HDKeyError('HD child derivation is unavailable')
        for _ in range(16):
            material = _hmac(self.chain_code, self.pubkey + index.to_bytes(4, 'big'))
            if int.from_bytes(material[:32], 'big') < SECP256K1_ORDER:
                try:
                    public = self._public_key.add(material[:32], update=False)
                    return HDPublicNode(public, material[32:], self.depth + 1, self.fingerprint, index)
                except ValueError:
                    pass
            if not skip_invalid or index == HARDENED - 1:
                break
            index += 1
        raise HDKeyError('HD child derivation produced an invalid key')

    def to_extended_public(self, *, testnet=False):
        return _extended(self, self.pubkey, False, testnet)

    def __repr__(self):
        return f'HDPublicNode(depth={self.depth}, child_number={self.child_number})'


@dataclass(frozen=True, repr=False)
class HDNode:
    _private_key: PrivateKey = field(repr=False)
    chain_code: bytes = field(repr=False)
    depth: int = 0
    parent_fingerprint: bytes = bytes(4)
    child_number: int = 0

    def __post_init__(self):
        if not isinstance(self._private_key, PrivateKey):
            raise HDKeyError('HD private key is invalid')
        _metadata(self.chain_code, self.depth, self.parent_fingerprint, self.child_number)

    @classmethod
    def from_seed(cls, seed):
        if type(seed) is not bytes or not 16 <= len(seed) <= 64:
            raise HDKeyError('HD seed must contain 16 to 64 bytes')
        material = _hmac(b'Bitcoin seed', seed)
        if not 1 <= int.from_bytes(material[:32], 'big') < SECP256K1_ORDER:
            raise HDKeyError('HD seed produced an invalid master key')
        return cls(PrivateKey(material[:32]), material[32:])

    @property
    def pubkey(self):
        return self._private_key.public_key.format(compressed=True)

    @property
    def fingerprint(self):
        return hash160(self.pubkey)[:4]

    def derive_child(self, index, *, skip_invalid=True):
        _integer(index, 0, 0xFFFFFFFF, 'HD child index is outside the supported range')
        if type(skip_invalid) is not bool or self.depth == 255:
            raise HDKeyError('HD child derivation is unavailable')
        for _ in range(16):
            data = ((b'\0' + self._private_key.secret) if index >= HARDENED else self.pubkey)
            material = _hmac(self.chain_code, data + index.to_bytes(4, 'big'))
            if int.from_bytes(material[:32], 'big') < SECP256K1_ORDER:
                try:
                    private = self._private_key.add(material[:32], update=False)
                    return HDNode(private, material[32:], self.depth + 1, self.fingerprint, index)
                except ValueError:
                    pass
            if not skip_invalid or index == 0xFFFFFFFF:
                break
            index += 1
        raise HDKeyError('HD child derivation produced an invalid key')

    def derive_path(self, path, *, skip_invalid=True):
        node = self
        for index in parse_path(path):
            node = node.derive_child(index, skip_invalid=skip_invalid)
        return node

    def neuter(self):
        return HDPublicNode(self._private_key.public_key, self.chain_code, self.depth,
                            self.parent_fingerprint, self.child_number)

    def to_extended_public(self, *, testnet=False):
        return _extended(self, self.pubkey, False, testnet)

    def to_extended_private(self, *, testnet=False):
        """Explicit secret export primitive; never called by normal wallet display."""
        return _extended(self, b'\0' + self._private_key.secret, True, testnet)

    def __repr__(self):
        return f'HDNode(depth={self.depth}, child_number={self.child_number})'


def import_extended_key(encoded):
    """Import standard xpub/xprv/tpub/tprv encodings with strict metadata checks."""
    if type(encoded) is not str or not 1 <= len(encoded) <= 120:
        raise HDKeyError('HD extended key is invalid')
    value = 0
    for character in encoded:
        try:
            digit = _ALPHABET.index(character)
        except ValueError:
            raise HDKeyError('HD extended key is invalid') from None
        value = value * 58 + digit
    raw = b'\0' * (len(encoded) - len(encoded.lstrip('1'))) + value.to_bytes((value.bit_length() + 7) // 8, 'big')
    if len(raw) != 82 or _base58(raw) != encoded:
        raise HDKeyError('HD extended key is invalid')
    body, checksum = raw[:-4], raw[-4:]
    if not hmac.compare_digest(hashlib.sha256(hashlib.sha256(body).digest()).digest()[:4], checksum):
        raise HDKeyError('HD extended key checksum is invalid')
    version = int.from_bytes(body[:4], 'big')
    private_versions = {item[1] for item in _VERSIONS.values()}
    public_versions = {item[0] for item in _VERSIONS.values()}
    depth, fingerprint, index, chain = body[4], body[5:9], int.from_bytes(body[9:13], 'big'), body[13:45]
    try:
        if version in private_versions and body[45] == 0:
            return HDNode(PrivateKey(body[46:78]), chain, depth, fingerprint, index)
        if version in public_versions and body[45] in (2, 3):
            return HDPublicNode(PublicKey(body[45:78]), chain, depth, fingerprint, index)
    except ValueError:
        raise HDKeyError('HD extended key material or metadata is invalid') from None
    raise HDKeyError('HD extended key type is invalid')


@lru_cache(maxsize=1)
def _wordlist():
    root = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent.parent))
    path = root / 'assets' / 'bip39' / 'english.txt'
    try:
        with path.open('rb') as source:
            raw = source.read(16385)
    except OSError:
        raise HDKeyError('BIP39 English wordlist is unavailable') from None
    if len(raw) > 16384 or hashlib.sha256(raw).hexdigest() != WORDLIST_SHA256:
        raise HDKeyError('BIP39 English wordlist does not match the approved bytes')
    words = tuple(raw.decode('ascii').splitlines())
    if len(words) != 2048 or len(set(words)) != 2048:
        raise HDKeyError('BIP39 English wordlist is invalid')
    return words


def entropy_to_mnemonic(entropy):
    """Explicitly encode BIP39 entropy; caller is responsible for secret display."""
    if type(entropy) is not bytes or len(entropy) not in (16, 20, 24, 28, 32):
        raise HDKeyError('BIP39 entropy must contain 16, 20, 24, 28 or 32 bytes')
    checksum_bits = len(entropy) // 4
    value = (int.from_bytes(entropy, 'big') << checksum_bits) | (hashlib.sha256(entropy).digest()[0] >> (8 - checksum_bits))
    words = _wordlist()
    count = (len(entropy) * 8 + checksum_bits) // 11
    return ' '.join(words[(value >> (11 * (count - index - 1))) & 2047] for index in range(count))


def mnemonic_to_entropy(mnemonic):
    if type(mnemonic) is not str or not 1 <= len(mnemonic) <= 1024:
        raise HDKeyError('BIP39 recovery words are invalid')
    try:
        phrase = unicodedata.normalize('NFKD', mnemonic)
        words = phrase.split()
        if len(words) not in (12, 15, 18, 21, 24):
            raise HDKeyError('BIP39 recovery word count is invalid')
        lookup = {word: index for index, word in enumerate(_wordlist())}
        value = 0
        for word in words:
            if word not in lookup:
                raise HDKeyError('BIP39 recovery words are not in the English wordlist')
            value = (value << 11) | lookup[word]
        entropy_bits = len(words) * 11 * 32 // 33
        checksum_bits = entropy_bits // 32
        entropy = (value >> checksum_bits).to_bytes(entropy_bits // 8, 'big')
        expected = hashlib.sha256(entropy).digest()[0] >> (8 - checksum_bits)
        if (value & ((1 << checksum_bits) - 1)) != expected:
            raise HDKeyError('BIP39 recovery word checksum is invalid')
        return entropy
    except UnicodeError:
        raise HDKeyError('BIP39 recovery words are invalid') from None


def mnemonic_to_seed(mnemonic, passphrase=''):
    entropy = mnemonic_to_entropy(mnemonic)
    canonical = entropy_to_mnemonic(entropy)
    if type(passphrase) is not str or len(passphrase) > 1024:
        raise HDKeyError('BIP39 passphrase is invalid')
    try:
        password = unicodedata.normalize('NFKD', canonical).encode('utf-8')
        salt = ('mnemonic' + unicodedata.normalize('NFKD', passphrase)).encode('utf-8')
    except UnicodeError:
        raise HDKeyError('BIP39 recovery phrase or passphrase is invalid') from None
    if len(salt) > 4096:
        raise HDKeyError('BIP39 passphrase is invalid')
    return hashlib.pbkdf2_hmac('sha512', password, salt, 2048, dklen=64)
