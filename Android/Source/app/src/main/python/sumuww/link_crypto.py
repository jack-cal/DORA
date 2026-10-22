"""Post-PoW connection attachments. Wallet keys and old block bytes are untouched."""
import hashlib
import json
import secrets
import sqlite3
import zlib
from pathlib import Path
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

POLICY = 'sumuww-postpow-links-9000-v2'
PROOF_SELECTION_DENOMINATOR = 5
PROOF_SELECTION_THRESHOLD = (1 << 256) // PROOF_SELECTION_DENOMINATOR
PRODUCER_TAG = b'SMWL\x01'
BEACON_TAG = b'SMWB\x01'

def canonical(value):
    # Reuse the existing strict, integer-only canonical format.
    from .boundary_crypto import canonical as encode
    return encode(value)

def digest(value): return hashlib.sha256(canonical(value)).hexdigest()
def require(condition, message):
    if not condition: raise ValueError(message)

def raw(value, length):
    require(type(value) is str and len(value) == length*2 and value == value.lower(), 'Invalid link hex')
    result = bytes.fromhex(value)
    require(len(result) == length and result.hex() == value, 'Invalid link bytes')
    return result

def verify(node_id, message, signature):
    Ed25519PublicKey.from_public_bytes(raw(node_id,32)).verify(raw(signature,64),canonical(message))

def proof_selected(seed):
    """20% event from the verified beacon; integer consensus, never a schedule."""
    return int.from_bytes(raw(seed,32),'big') < PROOF_SELECTION_THRESHOLD

def verify_frame(frame):
    require(type(frame) is dict and set(frame) == {'payload','signature'}, 'Invalid signed frame')
    verify(frame['payload']['nodeId'], frame['payload'], frame['signature'])
    return frame['payload']

class Identity:
    def __init__(self, path):
        Path(path).parent.mkdir(parents=True,exist_ok=True)
        self.db = sqlite3.connect(str(path),isolation_level=None,timeout=10)
        self.db.execute('PRAGMA synchronous=FULL')
        self.db.execute('CREATE TABLE IF NOT EXISTS identity (one INTEGER PRIMARY KEY, seed BLOB NOT NULL, encryption BLOB NOT NULL)')
        self.db.execute('CREATE TABLE IF NOT EXISTS link_locks (slot TEXT PRIMARY KEY, message BLOB NOT NULL, signature TEXT NOT NULL)')
        self.db.execute('CREATE TABLE IF NOT EXISTS link_private (name TEXT PRIMARY KEY, value BLOB NOT NULL)')
        self.db.execute('INSERT OR IGNORE INTO identity VALUES (1,?,?)',(secrets.token_bytes(32),secrets.token_bytes(32)))
        seed, enc = self.db.execute('SELECT seed,encryption FROM identity WHERE one=1').fetchone()
        self.ed = Ed25519PrivateKey.from_private_bytes(seed)
        self.encryption = X25519PrivateKey.from_private_bytes(enc)
        self.node_id = self.ed.public_key().public_bytes(Encoding.Raw,PublicFormat.Raw).hex()
        self.encryption_key = self.encryption.public_key().public_bytes(Encoding.Raw,PublicFormat.Raw).hex()
    def sign(self, message): return self.ed.sign(canonical(message)).hex()
    def signed(self, message): return {'payload':message,'signature':self.sign(message)}
    def sign_once(self, slot, message):
        body = canonical(message)
        self.db.execute('BEGIN IMMEDIATE')
        try:
            old = self.db.execute('SELECT message,signature FROM link_locks WHERE slot=?',(slot,)).fetchone()
            if old:
                require(old[0] == body, 'Conflicting connection signature')
                signature = old[1]
            else:
                signature = self.sign(message)
                self.db.execute('INSERT INTO link_locks VALUES (?,?,?)',(slot,body,signature))
            self.db.execute('COMMIT')
            return signature
        except BaseException:
            self.db.execute('ROLLBACK'); raise
    def get(self,name):
        row=self.db.execute('SELECT value FROM link_private WHERE name=?',(name,)).fetchone()
        return json.loads(row[0]) if row else None
    def put(self,name,value):
        self.db.execute('INSERT OR REPLACE INTO link_private VALUES (?,?)',(name,canonical(value)))
    def close(self): self.db.close()

def compress(data):
    packed=zlib.compress(data)
    return {'codec':'zlib','data':packed.hex()} if len(packed)<len(data) else {'codec':'raw','data':data.hex()}

def decompress(bundle, length):
    require(type(bundle) is dict and set(bundle)=={'codec','data'},'Invalid compressed bundle')
    require(type(bundle['data']) is str and len(bundle['data'])<=2*(length+128),'Oversized compressed bundle')
    data=bytes.fromhex(bundle['data'])
    if bundle['codec']=='zlib':
        decoder=zlib.decompressobj();data=decoder.decompress(data,length+1)
        require(decoder.eof and not decoder.unused_data and not decoder.unconsumed_tail,'Noncanonical compressed bundle')
    else:require(bundle['codec']=='raw','Unknown compression')
    require(len(data)==length,'Invalid decompressed length')
    return data

def sample(seed, candidates):
    # Rejection sampling over the entire locally discovered set. No IP quota,
    # neighbor filter, prefix, fixed pool size, or discovery-hop limit.
    pool=sorted(set(candidates));require(len(pool)>=3,'Three discovered identities needed')
    output=[];counter=0
    while len(output)<3:
        n=len(pool);limit=(1<<256)-((1<<256)%n)
        value=int.from_bytes(hashlib.sha256(bytes.fromhex(seed)+counter.to_bytes(8,'big')).digest(),'big');counter+=1
        if value<limit:output.append(pool.pop(value%n))
    return output

def slot(network, height, parent): return digest([POLICY,network,height,parent])
def message(network, a, b, height, parent, signers, beacon):
    return {'domain':POLICY,'network':network,'source':a,'target':b,'height':height,
            'slot':slot(network,height,parent),'signers':signers,'beacon':beacon}

def producer(block):
    values=[]
    for output in block.transactions[0].outputs:
        script=output.script_pubkey
        if script.startswith(b'\x6a\x25'+PRODUCER_TAG):
            require(output.value==0 and len(script)==39,'Invalid producer commitment')
            values.append(script[7:].hex())
    require(len(values)==1,'Exactly one producer commitment required')
    return values[0]

def producer_output(node_id):
    from .transaction import TxOutput
    return TxOutput(0,b'\x6a\x25'+PRODUCER_TAG+raw(node_id,32))

def beacon_outputs(setup):
    from .transaction import TxOutput
    data=zlib.compress(canonical(setup));key=bytes.fromhex(digest(setup));parts=[data[i:i+8000] for i in range(0,len(data),8000)]
    # This is transport framing only, not a participant-count bound.
    result=[]
    for i,part in enumerate(parts):
        body=BEACON_TAG+key+i.to_bytes(4,'big')+len(parts).to_bytes(4,'big')+part
        result.append(TxOutput(0,b'\x6a\x4d'+len(body).to_bytes(2,'little')+body))
    return tuple(result)

def block_beacon(block):
    parts=[];key=None;total=None
    for output in block.transactions[0].outputs:
        s=output.script_pubkey
        if s.startswith(b'\x6a\x4d') and s[4:9]==BEACON_TAG:
            require(output.value==0 and int.from_bytes(s[2:4],'little')==len(s)-4 and len(s)>=49,'Invalid beacon commitment')
            k=s[9:41];i=int.from_bytes(s[41:45],'big');n=int.from_bytes(s[45:49],'big')
            require(i==len(parts) and n>0 and (key is None or (key==k and total==n)),'Beacon part order')
            key=k;total=n;parts.append(s[49:])
    if not parts:return None
    require(len(parts)==total,'Incomplete beacon commitment')
    decoder=zlib.decompressobj();data=decoder.decompress(b''.join(parts),4_000_001)
    require(len(data)<=4_000_000 and decoder.eof and not decoder.unused_data and not decoder.unconsumed_tail,'Beacon expansion exceeds block limit')
    setup=json.loads(data)
    require(canonical(setup)==data and digest(setup)==key.hex(),'Beacon commitment digest')
    return setup
