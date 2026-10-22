"""Password-encrypted, regtest-only local signing keys. No public wallet import."""
import base64, json, os, secrets, threading
from pathlib import Path
from coincurve import PrivateKey
from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt
from sumuww.wallet import RegtestKey
from sumuww.address import _bech32_encode, _convert_bits
from .orders import canonical, valid_hex
FORMAT = 'sumuww-p2p-regtest-vault'
KDF = 'scrypt-n32768-r8-p1'

def _password(password):
    if not isinstance(password, str) or not 12 <= len(password) <= 1024:
        raise ValueError('Enter a password between 12 and 1024 characters.')
    return password.encode('utf8')

def _key(password, salt):
    return Scrypt(salt=salt, length=32, n=32768, r=8, p=1).derive(_password(password))

def _unb64(value, size=None):
    try:
        raw = base64.b64decode(value, validate=True)
    except (ValueError, TypeError):
        raise ValueError('Invalid encrypted vault format.') from None
    if size is not None and len(raw) != size:
        raise ValueError('Invalid encrypted vault length.')
    return raw

def _json(raw):

    def pairs(items):
        result = {}
        for k, v in items:
            if k in result:
                raise ValueError('Duplicate vault field.')
            result[k] = v
        return result
    return json.loads(raw, object_pairs_hook=pairs)

def _read(path):
    path = Path(path)
    if path.is_symlink() or not 0 < path.stat().st_size <= 65536:
        raise ValueError('Unsupported vault file.')
    return path.read_bytes()

def _envelope(raw):
    try:
        b = _json(raw)
        if not isinstance(b, dict) or set(b) != {'format', 'version', 'network', 'wallet_id', 'kdf', 'salt', 'nonce', 'ciphertext'}:
            raise ValueError('Invalid schema')
        if b['format'] != FORMAT or type(b['version']) is not int or b['version'] != 1 or (b['network'] != 'regtest-only') or (b['kdf'] != KDF) or (not valid_hex(b['wallet_id'], 16)):
            raise ValueError('Invalid profile')
        _unb64(b['salt'], 16)
        _unb64(b['nonce'], 12)
        if not 16 < len(_unb64(b['ciphertext'])) < 8192:
            raise ValueError('Invalid ciphertext')
        return b
    except (KeyError, TypeError, UnicodeError, json.JSONDecodeError, ValueError):
        raise ValueError('This is not an encrypted regtest vault for this application.') from None

def _aad(envelope):
    return canonical({k: v for k, v in envelope.items() if k != 'ciphertext'})

def _decrypt(envelope, key):
    try:
        raw = AESGCM(key).decrypt(_unb64(envelope['nonce'], 12), _unb64(envelope['ciphertext']), _aad(envelope))
        b = _json(raw)
        if not isinstance(b, dict) or set(b) != {'network', 'wallet_id', 'smw', 'btc'} or b['network'] != 'regtest-only' or (b['wallet_id'] != envelope['wallet_id']) or (not valid_hex(b['smw'], 32)) or (not valid_hex(b['btc'], 32)):
            raise ValueError('Invalid encrypted payload')
        PrivateKey(bytes.fromhex(b['smw']))
        PrivateKey(bytes.fromhex(b['btc']))
        if b['smw'] == b['btc']:
            raise ValueError('Repeated coin key')
        return b
    except (InvalidTag, ValueError, TypeError, KeyError, UnicodeError):
        raise ValueError('Incorrect password or damaged vault file.') from None

def _write_new(path, raw):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink():
        raise ValueError('Vault symlink files are not supported.')
    temp = path.with_name('.' + path.name + '.' + secrets.token_hex(12) + '.tmp')
    fd = os.open(temp, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 384)
    try:
        with os.fdopen(fd, 'wb') as f:
            f.write(raw)
            f.flush()
            os.fsync(f.fileno())
        if os.name == 'nt':
            os.rename(temp, path)
        else:
            os.link(temp, path)
    finally:
        temp.unlink(missing_ok=True)

def _address(key, coin):
    return _bech32_encode('drt' if coin == 'smw' else 'bcrt', [0] + _convert_bits(key.script_pubkey[2:], 8, 5, pad=True))

class Vault:

    def __init__(self, path):
        self.path = Path(path)
        self.mutex = threading.RLock()
        self._secrets = {}
        self._aes = None
        self._id = None
        self._public = {}

    def _load(self, envelope, key, payload):
        self.lock()
        self._aes = bytearray(key)
        self._id = envelope['wallet_id']
        self._secrets = {coin: bytearray.fromhex(payload[coin]) for coin in ('smw', 'btc')}
        self._public = {coin: _address(RegtestKey.from_int(int.from_bytes(value, 'big')), coin) for coin, value in self._secrets.items()}

    def state(self):
        with self.mutex:
            return {'exists': self.path.exists(), 'locked': not bool(self._secrets), 'network': 'regtest-only', 'wallet_id': self._id, 'addresses': dict(self._public), 'public_wallet_connected': False}

    def create(self, password):
        with self.mutex:
            if self.path.exists():
                raise ValueError('A vault already exists. Unlock the existing vault.')
            _password(password)
            b = {'network': 'regtest-only', 'wallet_id': secrets.token_hex(16), 'smw': PrivateKey().secret.hex(), 'btc': PrivateKey().secret.hex()}
            envelope = {'format': FORMAT, 'version': 1, 'network': 'regtest-only', 'wallet_id': b['wallet_id'], 'kdf': KDF, 'salt': base64.b64encode(secrets.token_bytes(16)).decode(), 'nonce': base64.b64encode(secrets.token_bytes(12)).decode()}
            derived = _key(password, _unb64(envelope['salt']))
            envelope['ciphertext'] = base64.b64encode(AESGCM(derived).encrypt(_unb64(envelope['nonce']), canonical(b), _aad(envelope))).decode()
            raw = canonical(envelope)
            _decrypt(envelope, derived)
            _write_new(self.path, raw)
            self._load(envelope, derived, b)
            return self.state()

    def unlock(self, password):
        with self.mutex:
            self.lock()
            envelope = _envelope(_read(self.path))
            derived = _key(password, _unb64(envelope['salt']))
            payload = _decrypt(envelope, derived)
            self._load(envelope, derived, payload)
            return self.state()

    def lock(self):
        with self.mutex:
            for value in [*self._secrets.values(), *([self._aes] if self._aes is not None else [])]:
                value[:] = bytes(len(value))
            self._secrets = {}
            self._aes = None
            self._id = None
            self._public = {}

    def keys(self):
        with self.mutex:
            if not self._secrets:
                raise ValueError('Unlock the test vault first.')
            try:
                envelope = _envelope(_read(self.path))
                payload = _decrypt(envelope, bytes(self._aes))
                if payload['wallet_id'] != self._id:
                    raise ValueError('The file does not match the unlocked vault.')
            except Exception:
                self.lock()
                raise
            return {coin: RegtestKey.from_int(int(value, 16)) for coin, value in ((c, payload[c]) for c in ('smw', 'btc'))}

    def backup(self, destination):
        with self.mutex:
            self.keys()
            destination = Path(destination)
            if destination.resolve() == self.path.resolve():
                raise ValueError('Choose a different backup path.')
            _write_new(destination, _read(self.path))
            return {'encrypted_backup': True, 'network': 'regtest-only'}

    def signing_material(self):
        with self.mutex:
            return {'keys': self.keys(), 'public': self.state()}

    def restore(self, source, password):
        with self.mutex:
            if self.path.exists():
                raise ValueError('Existing vaults are not overwritten. Restore into an empty data directory.')
            raw = _read(source)
            envelope = _envelope(raw)
            derived = _key(password, _unb64(envelope['salt']))
            payload = _decrypt(envelope, derived)
            _write_new(self.path, raw)
            self._load(envelope, derived, payload)
            return self.state()
