"""Immutable signed advertisements, atomic full-order reservations and history.

Advertisements do not prove balances. Settlement must independently inspect both
chains. Cancellation never deletes a reservation or a recovery record.
"""
from contextlib import contextmanager
from pathlib import Path
import hashlib, json, secrets, sqlite3, time
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from ..orders import Identity, canonical, valid_hex
from .amounts import QUOTES, quote_total, show

DOMAIN = 'sumuww-market-v2'

def identifier(body):
    return hashlib.sha256(canonical(body)).hexdigest()

def authenticate(packet, network):
    if not isinstance(packet, dict) or set(packet) != {'body','signature'}:
        raise ValueError('Invalid signed envelope.')
    body = packet['body']
    if not isinstance(body, dict) or body.get('domain') != DOMAIN or body.get('network') != network:
        raise ValueError('Different market network.')
    if not valid_hex(body.get('maker'),32) or not valid_hex(packet['signature'],64):
        raise ValueError('Invalid signing identity.')
    Ed25519PublicKey.from_public_bytes(bytes.fromhex(body['maker'])).verify(bytes.fromhex(packet['signature']),canonical(body))
    return body

class Board:
    def __init__(self, directory, network='mainnet', clock=time.time):
        if network not in ('mainnet','test'):
            raise ValueError('Unknown market network.')
        self.directory=Path(directory);self.directory.mkdir(parents=True,exist_ok=True)
        self.identity=Identity(self.directory/'market-identity.key')
        self.database=self.directory/'market.sqlite';self.network=network;self.clock=clock
        with self.connect() as c:
            c.executescript('''
              CREATE TABLE IF NOT EXISTS market_config (id INTEGER PRIMARY KEY CHECK(id=1),network TEXT NOT NULL);
              CREATE TABLE IF NOT EXISTS posts (id TEXT PRIMARY KEY,packet TEXT NOT NULL);
              CREATE TABLE IF NOT EXISTS closures (post TEXT PRIMARY KEY,packet TEXT NOT NULL);
              CREATE TABLE IF NOT EXISTS reservations (id TEXT PRIMARY KEY,post TEXT UNIQUE NOT NULL,packet TEXT NOT NULL);
              CREATE TABLE IF NOT EXISTS swaps (id TEXT PRIMARY KEY,state TEXT NOT NULL);
              CREATE TABLE IF NOT EXISTS events (seq INTEGER PRIMARY KEY AUTOINCREMENT,packet TEXT UNIQUE NOT NULL);
            ''')
            c.execute('INSERT OR IGNORE INTO market_config VALUES(1,?)',(network,))
            if c.execute('SELECT network FROM market_config WHERE id=1').fetchone()[0]!=network:
                raise ValueError('Use a separate directory for each market network.')
            c.execute('INSERT OR IGNORE INTO events(packet) SELECT packet FROM posts ORDER BY rowid')
            c.execute('INSERT OR IGNORE INTO events(packet) SELECT packet FROM closures ORDER BY rowid')

    @contextmanager
    def connect(self):
        c=sqlite3.connect(self.database,timeout=15,isolation_level=None)
        c.row_factory=sqlite3.Row
        c.execute('PRAGMA journal_mode=WAL');c.execute('PRAGMA synchronous=FULL')
        try:yield c
        finally:c.close()

    def sign(self,kind,**values):
        return self.identity.sign({'domain':DOMAIN,'network':self.network,'maker':self.identity.public,'kind':kind,**values})

    def validate_post(self,packet,live=False):
        b=authenticate(packet,self.network)
        fields={'domain','network','maker','kind','side','coin','quantity','price','smw_units','quote_units','title','note','created','expires','nonce'}
        if set(b)!=fields or b['kind']!='post' or b['side'] not in ('buy','sell') or b['coin'] not in QUOTES:
            raise ValueError('Invalid advertisement.')
        smw,total,price=quote_total(b['quantity'],b['price'],b['coin'])
        if type(b['smw_units']) is not int or type(b['quote_units']) is not int or (smw,total,price)!=(b['smw_units'],b['quote_units'],b['price']):
            raise ValueError('Signed price and quantity disagree.')
        if show(smw,'SMW')!=b['quantity'] or not valid_hex(b['nonce'],16):
            raise ValueError('Noncanonical advertisement.')
        for key,maximum in (('title',100),('note',2000)):
            if not isinstance(b[key],str) or len(b[key])>maximum or any(ord(ch)<32 and ch not in '\n\t' for ch in b[key]):
                raise ValueError('Invalid advertisement text.')
        if type(b['created']) is not int or type(b['expires']) is not int or not 60<=b['expires']-b['created']<=30*86400 or b['created']>self.clock()+120:
            raise ValueError('Invalid advertisement lifetime.')
        if live and b['expires']<=self.clock():raise ValueError('Advertisement expired.')
        return b

    def create(self,side,coin,quantity,price,title='',note='',lifetime=86400):
        if type(lifetime) is not int:raise ValueError('Invalid lifetime.')
        smw,total,canonical_price=quote_total(quantity,price,coin)
        now=int(self.clock())
        p=self.sign('post',side=side,coin=coin,quantity=show(smw,'SMW'),price=canonical_price,smw_units=smw,quote_units=total,title=title.strip(),note=note.strip(),created=now,expires=now+lifetime,nonce=secrets.token_hex(16))
        self.import_packet(p);return p

    def post(self,oid):
        with self.connect() as c:row=c.execute('SELECT packet FROM posts WHERE id=?',(oid,)).fetchone()
        if not row:raise ValueError('Unknown advertisement.')
        return self.validate_post(json.loads(row[0]))

    def validate_request(self,p,oid,live=False):
        b=authenticate(p,self.network)
        if set(b)!={'domain','network','maker','kind','post','nonce','expires'} or b['kind']!='request' or b['post']!=oid or not valid_hex(b['nonce'],16) or type(b['expires']) is not int:
            raise ValueError('Invalid reservation request.')
        if live and not self.clock()<b['expires']<=self.clock()+300:raise ValueError('Reservation request expired.')
        return b

    def request(self,oid):
        post=self.post(oid)
        if post['maker']==self.identity.public:raise ValueError('Cannot trade with your own order identity.')
        return self.sign('request',post=oid,nonce=secrets.token_hex(16),expires=int(self.clock())+180)

    def reserve(self,request):
        oid=request.get('body',{}).get('post');r=self.validate_request(request,oid,live=True)
        with self.connect() as c:
            c.execute('BEGIN IMMEDIATE')
            row=c.execute('SELECT packet FROM posts WHERE id=?',(oid,)).fetchone()
            if not row:raise ValueError('Unknown advertisement.')
            post=self.validate_post(json.loads(row[0]),live=True)
            if post['maker']!=self.identity.public or r['maker']==self.identity.public:raise ValueError('Wrong reservation participants.')
            existing=c.execute('SELECT packet FROM closures WHERE post=?',(oid,)).fetchone()
            if existing:
                packet=json.loads(existing[0]);b=authenticate(packet,self.network)
                if b['kind']=='reserved' and b['request']==request:return packet
                raise ValueError('Advertisement is already closed or reserved.')
            packet=self.sign('reserved',post=oid,request=request,session=identifier(r))
            c.execute('INSERT INTO closures VALUES(?,?)',(oid,canonical(packet).decode()))
            c.execute('INSERT INTO reservations VALUES(?,?,?)',(identifier(r),oid,canonical(packet).decode()))
            c.execute('INSERT INTO events(packet) VALUES(?)',(canonical(packet).decode(),))
            c.execute('COMMIT');return packet

    def cancel(self,oid):
        with self.connect() as c:
            c.execute('BEGIN IMMEDIATE')
            post=self.post(oid)
            if post['maker']!=self.identity.public:raise ValueError('Only the author can cancel this advertisement.')
            if c.execute('SELECT 1 FROM closures WHERE post=?',(oid,)).fetchone():raise ValueError('Already closed or reserved. Use trade cancellation/refund for a reservation.')
            p=self.sign('canceled',post=oid)
            c.execute('INSERT INTO closures VALUES(?,?)',(oid,canonical(p).decode()))
            c.execute('INSERT INTO events(packet) VALUES(?)',(canonical(p).decode(),));c.execute('COMMIT');return p

    def import_packet(self,p):
        b=authenticate(p,self.network)
        with self.connect() as c:
            if b.get('kind')=='post':
                self.validate_post(p)
                c.execute('BEGIN IMMEDIATE')
                added=c.execute('INSERT OR IGNORE INTO posts VALUES(?,?)',(identifier(b),canonical(p).decode())).rowcount>0
                if added:c.execute('INSERT INTO events(packet) VALUES(?)',(canonical(p).decode(),))
                c.execute('COMMIT');return added
            oid=b.get('post');post=self.post(oid)
            if b['maker']!=post['maker']:raise ValueError('Only the author can close the advertisement.')
            if b.get('kind')=='canceled':
                if set(b)!={'domain','network','maker','kind','post'}:raise ValueError('Invalid cancellation.')
            elif b.get('kind')=='reserved':
                if set(b)!={'domain','network','maker','kind','post','request','session'}:raise ValueError('Invalid reservation.')
                r=self.validate_request(b['request'],oid)
                if b['session']!=identifier(r) or r['maker']==post['maker']:raise ValueError('Invalid reservation parties.')
            else:raise ValueError('Unknown advertisement event.')
            c.execute('BEGIN IMMEDIATE')
            old=c.execute('SELECT packet FROM closures WHERE post=?',(oid,)).fetchone()
            if old:
                if json.loads(old[0])!=p:raise ValueError('Conflicting signed closure; keep existing record.')
                c.execute('COMMIT');return False
            c.execute('INSERT INTO closures VALUES(?,?)',(oid,canonical(p).decode()))
            c.execute('INSERT INTO events(packet) VALUES(?)',(canonical(p).decode(),))
            if b['kind']=='reserved':c.execute('INSERT INTO reservations VALUES(?,?,?)',(b['session'],oid,canonical(p).decode()))
            c.execute('COMMIT');return True

    def terms(self,session):
        with self.connect() as c:row=c.execute('SELECT packet FROM reservations WHERE id=?',(session,)).fetchone()
        if not row:raise ValueError('Reserve the advertisement first.')
        reservation=authenticate(json.loads(row[0]),self.network);p=self.post(reservation['post'])
        taker=reservation['request']['body']['maker']
        seller=p['maker'] if p['side']=='sell' else taker
        buyer=taker if p['side']=='sell' else p['maker']
        if self.identity.public not in (seller,buyer):raise ValueError('Not a party to this reservation.')
        return {'session':session,'post':reservation['post'],'seller':seller,'buyer':buyer,'coin':p['coin'],'smw_units':p['smw_units'],'quote_units':p['quote_units'],'price':p['price'],'network':self.network}

    def listing(self,coin=None):
        with self.connect() as c:rows=c.execute('SELECT p.id,p.packet,c.packet AS closure FROM posts p LEFT JOIN closures c ON c.post=p.id ORDER BY p.rowid DESC').fetchall()
        result=[]
        for row in rows:
            packet=json.loads(row['packet'])
            if packet['body'].get('coin') in ('ETH','BNB','XRP'):continue
            b=self.validate_post(packet)
            if coin and b['coin']!=coin:continue
            state=json.loads(row['closure'])['body']['kind'] if row['closure'] else 'expired' if b['expires']<=self.clock() else 'active'
            result.append({**b,'id':row['id'],'status':state,'mine':b['maker']==self.identity.public,'total':show(b['quote_units'],b['coin'])})
        return result

    def sessions(self):
        with self.connect() as c:ids=[r[0] for r in c.execute('SELECT id FROM reservations ORDER BY rowid DESC')]
        result=[]
        for session in ids:
            try:result.append(self.terms(session))
            except ValueError:pass
        return result

    def export(self,offset=0):
        if type(offset) is not int or offset<0:raise ValueError('Invalid history cursor.')
        with self.connect() as c:
            # Retired records stay on disk, but do not enter the active feed.
            rows=c.execute('''SELECT e.packet FROM events e
                JOIN posts p ON p.id=COALESCE(json_extract(e.packet,'$.body.post'),
                    (SELECT id FROM posts WHERE packet=e.packet))
                WHERE json_extract(p.packet,'$.body.coin')='BTC'
                ORDER BY e.seq LIMIT 64 OFFSET ?''',(offset,)).fetchall()
        return [json.loads(r[0]) for r in rows]
