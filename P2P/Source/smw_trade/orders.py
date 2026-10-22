"""Signed public regtest orders, durable cancellations and atomic reservations."""
from contextlib import contextmanager
from decimal import Decimal, InvalidOperation
import hashlib, json, os, secrets, sqlite3, time
from pathlib import Path
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat, PrivateFormat, NoEncryption

DOMAIN = 'sumuww-p2p-regtest-v1'
MAX_ATOMS = 1_800_000_000_000_000

def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True, allow_nan=False).encode()

def atoms(text):
    if not isinstance(text, str) or len(text) > 32:
        raise ValueError('Amount must be a decimal string')
    try:
        n = Decimal(text)
        scaled = n * 100_000_000
        if not n.is_finite() or not 0 < scaled <= MAX_ATOMS or scaled != scaled.to_integral_value():
            raise ValueError('Amount must be positive with at most eight decimals')
        return int(scaled)
    except InvalidOperation as exc:
        raise ValueError('Invalid amount') from exc

def amount(value):
    return f'{value // 100_000_000}.{value % 100_000_000:08d}'

def valid_hex(text, size):
    return isinstance(text, str) and len(text) == size * 2 and all(c in '0123456789abcdef' for c in text)

class Identity:
    """Order identity only. Never used to hold or sign SMW/BTC funds."""
    def __init__(self, path):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.is_symlink(): raise ValueError('Identity symlink refused')
        try:
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError:
            raw = path.read_bytes()
        else:
            raw = secrets.token_bytes(32)
            with os.fdopen(fd, 'wb') as out:
                out.write(raw); out.flush(); os.fsync(out.fileno())
        self.key = Ed25519PrivateKey.from_private_bytes(raw)
        self.public = self.key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw).hex()

    def sign(self, body):
        return {'body': body, 'signature': self.key.sign(canonical(body)).hex()}

def authenticate(packet):
    if not isinstance(packet, dict) or set(packet) != {'body', 'signature'}:
        raise ValueError('Malformed signed envelope')
    body = packet['body']
    if not isinstance(body, dict) or body.get('domain') != DOMAIN or not valid_hex(body.get('maker'), 32):
        raise ValueError('Wrong domain or identity')
    if not valid_hex(packet['signature'], 64): raise ValueError('Malformed signature')
    Ed25519PublicKey.from_public_bytes(bytes.fromhex(body['maker'])).verify(bytes.fromhex(packet['signature']), canonical(body))
    return body

def order_id(body):
    return hashlib.sha256(canonical(body)).hexdigest()

class Store:
    def __init__(self, directory, clock=time.time):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.identity = Identity(self.directory / 'order-identity.key')
        self.db = self.directory / 'orders.sqlite'
        self.clock = clock
        with self.connect() as c:
            c.executescript('''
              CREATE TABLE IF NOT EXISTS orders (id TEXT PRIMARY KEY, packet TEXT NOT NULL);
              CREATE TABLE IF NOT EXISTS events (order_id TEXT PRIMARY KEY, packet TEXT NOT NULL, status TEXT NOT NULL);
              CREATE TABLE IF NOT EXISTS agreements (id TEXT PRIMARY KEY, order_id TEXT NOT NULL UNIQUE,
                request TEXT NOT NULL, maker_confirmation TEXT NOT NULL);
              CREATE TABLE IF NOT EXISTS journal (session TEXT PRIMARY KEY, state TEXT NOT NULL, evidence TEXT NOT NULL);
            ''')

    @contextmanager
    def connect(self):
        c = sqlite3.connect(self.db, timeout=10, isolation_level=None)
        c.row_factory = sqlite3.Row
        c.execute('PRAGMA journal_mode=WAL'); c.execute('PRAGMA synchronous=FULL')
        try: yield c
        finally: c.close()

    def _validate_order(self, packet, *, require_live):
        b = authenticate(packet)
        fields = {'domain','kind','maker','side','smw_atoms','btc_sats','created_at','expires_at','nonce'}
        if set(b) != fields or b['kind'] != 'order' or b['side'] not in ('sell','buy'):
            raise ValueError('Invalid order schema')
        for field in ('smw_atoms','btc_sats'):
            if type(b[field]) is not int or not 0 < b[field] <= MAX_ATOMS: raise ValueError('Invalid amount')
        if not valid_hex(b['nonce'], 16): raise ValueError('Invalid nonce')
        if (type(b['created_at']) is not int or type(b['expires_at']) is not int
                or not b['created_at'] < b['expires_at'] or b['created_at'] > self.clock() + 120):
            raise ValueError('Invalid order lifetime')
        if require_live and b['expires_at'] <= self.clock(): raise ValueError('Expired order')
        return b

    def create(self, side, smw, btc, lifetime=3600):
        if type(lifetime) is not int or lifetime <= 0: raise ValueError('Invalid lifetime')
        now = int(self.clock())
        packet = self.identity.sign({'domain':DOMAIN,'kind':'order','maker':self.identity.public,'side':side,
            'smw_atoms':atoms(smw),'btc_sats':atoms(btc),'created_at':now,'expires_at':now+lifetime,'nonce':secrets.token_hex(16)})
        self.import_order(packet)
        return packet

    def import_order(self, packet):
        b = self._validate_order(packet, require_live=True)
        oid = order_id(b)
        with self.connect() as c:
            c.execute('INSERT OR IGNORE INTO orders VALUES (?,?)',(oid,canonical(packet).decode()))
        return oid

    def import_event(self, packet):
        b = authenticate(packet)
        if set(b) != {'domain','kind','maker','order_id','session'} or b['kind'] not in ('cancel','reserve'):
            raise ValueError('Invalid order event')
        if not valid_hex(b['order_id'],32): raise ValueError('Invalid order ID')
        if b['kind'] == 'reserve' and not valid_hex(b['session'],32): raise ValueError('Invalid session')
        if b['kind'] == 'cancel' and b['session'] != '': raise ValueError('Invalid cancellation')
        with self.connect() as c:
            row = c.execute('SELECT packet FROM orders WHERE id=?',(b['order_id'],)).fetchone()
            if not row or json.loads(row[0])['body']['maker'] != b['maker']: raise ValueError('Not order owner')
            # Terminal notice is never overwritten by replay of an old order.
            c.execute('INSERT OR IGNORE INTO events VALUES (?,?,?)',
                (b['order_id'],canonical(packet).decode(),'canceled' if b['kind']=='cancel' else 'reserved'))

    def cancel(self, oid):
        with self.connect() as c:
            c.execute('BEGIN IMMEDIATE')
            row = c.execute('SELECT packet FROM orders WHERE id=?',(oid,)).fetchone()
            if not row or json.loads(row[0])['body']['maker'] != self.identity.public: raise ValueError('Not your order')
            if c.execute('SELECT 1 FROM events WHERE order_id=?',(oid,)).fetchone(): raise ValueError('Order is already closed or reserved')
            packet = self.identity.sign({'domain':DOMAIN,'kind':'cancel','maker':self.identity.public,'order_id':oid,'session':''})
            c.execute('INSERT INTO events VALUES (?,?,?)',(oid,canonical(packet).decode(),'canceled'))
            c.execute('COMMIT')
        return packet

    def acceptance_request(self, oid):
        return self.identity.sign({'domain':DOMAIN,'kind':'accept','maker':self.identity.public,
            'order_id':oid,'nonce':secrets.token_hex(16),'expires_at':int(self.clock())+120})

    def reserve(self, request):
        b = authenticate(request)
        if set(b) != {'domain','kind','maker','order_id','nonce','expires_at'} or b['kind'] != 'accept':
            raise ValueError('Invalid acceptance request')
        if (not valid_hex(b['order_id'],32) or not valid_hex(b['nonce'],16) or type(b['expires_at']) is not int
                or not self.clock() < b['expires_at'] <= self.clock()+180): raise ValueError('Expired or invalid request')
        session = order_id(b)
        with self.connect() as c:
            c.execute('BEGIN IMMEDIATE')
            old = c.execute('SELECT maker_confirmation FROM agreements WHERE id=?',(session,)).fetchone()
            if old: return json.loads(old[0])  # Idempotent retry of exact signed request.
            row = c.execute('SELECT packet FROM orders WHERE id=?',(b['order_id'],)).fetchone()
            if not row: raise ValueError('Unknown order')
            order = self._validate_order(json.loads(row[0]), require_live=True)
            if order['maker'] != self.identity.public or order['maker'] == b['maker']: raise ValueError('Wrong counterparty')
            if c.execute('SELECT 1 FROM events WHERE order_id=?',(b['order_id'],)).fetchone(): raise ValueError('Order unavailable')
            confirmation = self.identity.sign({'domain':DOMAIN,'kind':'reserve','maker':self.identity.public,
                'order_id':b['order_id'],'session':session})
            c.execute('INSERT INTO agreements VALUES (?,?,?,?)',(session,b['order_id'],canonical(request).decode(),canonical(confirmation).decode()))
            c.execute('INSERT INTO events VALUES (?,?,?)',(b['order_id'],canonical(confirmation).decode(),'reserved'))
            c.execute('COMMIT')
            return confirmation

    def export(self):
        with self.connect() as c:
            return {'orders':[json.loads(r[0]) for r in c.execute('SELECT packet FROM orders')],
                    'events':[json.loads(r[0]) for r in c.execute('SELECT packet FROM events')]}

    def has_packet(self, packet):
        b=packet['body']
        with self.connect() as c:
            if b['kind']=='order':
                return c.execute('SELECT 1 FROM orders WHERE id=?',(order_id(b),)).fetchone() is not None
            return c.execute('SELECT 1 FROM events WHERE order_id=?',(b['order_id'],)).fetchone() is not None

    def listing(self):
        with self.connect() as c:
            rows = c.execute('SELECT o.id,o.packet,e.status FROM orders o LEFT JOIN events e ON o.id=e.order_id').fetchall()
        result=[]
        for r in rows:
            b=json.loads(r['packet'])['body']
            state=r['status'] or ('expired' if b['expires_at']<=self.clock() else 'active')
            result.append({'id':r['id'],**b,'status':state,'mine':b['maker']==self.identity.public,
                'smw':amount(b['smw_atoms']),'btc':amount(b['btc_sats'])})
        return result

    def checkpoint(self, session, state, evidence):
        # Called by the local chain-observing runner, never by a remote peer/UI.
        with self.connect() as c:
            c.execute('INSERT INTO journal VALUES (?,?,?) ON CONFLICT(session) DO UPDATE SET state=excluded.state,evidence=excluded.evidence',
                (session,state,canonical(evidence).decode()))

    def history(self):
        with self.connect() as c:
            return [{'session':r[0],'state':r[1],'evidence':json.loads(r[2])} for r in c.execute('SELECT * FROM journal ORDER BY rowid')]
