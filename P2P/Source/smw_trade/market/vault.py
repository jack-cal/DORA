"""Dedicated encrypted trade keys; existing wallet files are never modified."""
import base64, hashlib, hmac, secrets, threading
from pathlib import Path
from coincurve import PrivateKey
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from ..vault import _key, _unb64, _read, _write_new, _json
from ..orders import canonical
from sumuww.wallet import RegtestKey
from sumuww.address import encode_address, _bech32_encode, _convert_bits

COINS=('SMW','BTC')
# Accept the previous encrypted format without discarding its inactive keys.
LEGACY_COIN_SETS=({'SMW','BTC','XRP'},{'SMW','BTC','ETH','BNB','XRP'})

class TradeVault:
    def __init__(self,path,network='mainnet'):
        self.path=Path(path);self.network=network;self.mutex=threading.RLock();self.payload=None

    def _decode(self,raw,password):
        e=_json(raw)
        if set(e)!={'format','network','salt','nonce','ciphertext'} or e['format']!='sumuww-trade-vault-v2' or e['network']!=self.network:
            raise ValueError('Wrong encrypted trading wallet or network.')
        key=_key(password,_unb64(e['salt'],16));aad=canonical({k:v for k,v in e.items() if k!='ciphertext'})
        try:p=_json(AESGCM(key).decrypt(_unb64(e['nonce'],12),_unb64(e['ciphertext']),aad))
        except Exception:raise ValueError('Incorrect password or damaged wallet.') from None
        if not isinstance(p,dict) or set(p) not in (set(COINS),*LEGACY_COIN_SETS):raise ValueError('Invalid trading keys.')
        for coin in set(p)-{'XRP'}:PrivateKey(bytes.fromhex(p[coin]))
        # Retired seeds remain opaque encrypted backup data, never signing keys.
        if 'XRP' in p and (not isinstance(p['XRP'],str) or not 1<=len(p['XRP'])<=128):raise ValueError('Invalid legacy key record.')
        return p

    def create(self,password):
        with self.mutex:
            if self.path.exists():raise ValueError('Trading wallet already exists.')
            payload={c:PrivateKey().secret.hex() for c in COINS}
            e={'format':'sumuww-trade-vault-v2','network':self.network,'salt':base64.b64encode(secrets.token_bytes(16)).decode(),'nonce':base64.b64encode(secrets.token_bytes(12)).decode()}
            key=_key(password,_unb64(e['salt'],16))
            e['ciphertext']=base64.b64encode(AESGCM(key).encrypt(_unb64(e['nonce']),canonical(payload),canonical(e))).decode()
            raw=canonical(e);self._decode(raw,password);_write_new(self.path,raw)
            self.payload=payload;return self.state()

    def unlock(self,password):
        with self.mutex:
            self.lock();self.payload=self._decode(_read(self.path),password);return self.state()

    def lock(self):
        with self.mutex:self.payload=None

    def key(self,coin):
        with self.mutex:
            if self.payload is None:raise ValueError('Unlock the trading wallet first.')
            if coin in ('SMW','BTC'):return RegtestKey.from_int(int(self.payload[coin],16))
            raise ValueError('Unsupported coin.')

    def public(self,coin):
        key=self.key(coin)
        if coin=='SMW':return {'address':encode_address(key.script_pubkey,network='dora' if self.network=='mainnet' else 'regtest'),'pubkey':key.pubkey.hex()}
        if coin=='BTC':return {'address':_bech32_encode('bc' if self.network=='mainnet' else 'bcrt',[0]+_convert_bits(key.script_pubkey[2:],8,5,pad=True)),'pubkey':key.pubkey.hex()}

    def secret(self,session):
        with self.mutex:
            self.key('SMW')
            return hmac.new(bytes.fromhex(self.payload['SMW']),b'SUMUWW atomic swap v2\0'+bytes.fromhex(session),hashlib.sha256).digest()

    def state(self):
        with self.mutex:return {'exists':self.path.exists(),'locked':self.payload is None,'network':self.network,'addresses':{} if self.payload is None else {c:self.public(c)['address'] for c in COINS}}

    def seal(self,context,value):
        with self.mutex:
            self.key('SMW')
            key=hmac.new(bytes.fromhex(self.payload['SMW']),b'SUMUWW private journal v2',hashlib.sha256).digest()
            nonce=secrets.token_bytes(12)
            return base64.b64encode(nonce+AESGCM(key).encrypt(nonce,canonical(value),context.encode())).decode()

    def unseal(self,context,value):
        with self.mutex:
            self.key('SMW')
            key=hmac.new(bytes.fromhex(self.payload['SMW']),b'SUMUWW private journal v2',hashlib.sha256).digest()
            raw=base64.b64decode(value,validate=True)
            return _json(AESGCM(key).decrypt(raw[:12],raw[12:],context.encode()))

    def backup(self,destination):
        with self.mutex:
            if Path(destination).resolve()==self.path.resolve():raise ValueError('Choose another backup path.')
            _write_new(destination,_read(self.path));return {'encrypted_backup':True}

    def restore(self,source,password):
        with self.mutex:
            if self.path.exists():raise ValueError('Restore only into a new trading-wallet directory.')
            raw=_read(source);payload=self._decode(raw,password);_write_new(self.path,raw);self.payload=payload
            return self.state()
