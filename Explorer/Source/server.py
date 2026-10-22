"""SUMUWW explorer. Source chain is always opened mode=ro; index is separate."""
from __future__ import annotations
import argparse
import csv
import errno
from contextlib import closing
from datetime import datetime,timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer as _ThreadingHTTPServer
import json
import io
import os
from pathlib import Path
import re
import secrets
import sqlite3
import socket
import sys
import threading
import time
import weakref
import webbrowser
from urllib.parse import parse_qs, unquote, urlsplit
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'vendor'))
from witness_address import AddressError, decode_address, encode_address
from sumuww.block import Block
from sumuww.transaction import Transaction
from sumuww.profiles import SUMUWW
from sumuww.errors import UnsupportedFeature
from sumuww.primitives import MAX_MONEY, Header, hash_to_display, valid_target, subsidy, merkle_root, sha256d
from analytics import AdvancedExplorer, FILTER_KEYS, rate

HASH = re.compile(r'^[0-9a-fA-F]{64}$')
VERSION = '0.4.6'
INDEX_ID = 0x53574D45
MAX_HEIGHT = 0x7fffffff

class DataUnavailable(RuntimeError):
    """A source/index failure, never a malformed search request."""

class SnapshotChanged(RuntimeError):
    pass

class ExplorerHTTPServer(_ThreadingHTTPServer):
    # Windows SO_REUSEADDR permits a second process to bind an active HTTP port.
    # Exclusivity prevents two explorers from intermittently answering one URL.
    allow_reuse_address = os.name != 'nt'
    daemon_threads = True

    def server_bind(self):
        if os.name == 'nt' and hasattr(socket,'SO_EXCLUSIVEADDRUSE'):
            self.socket.setsockopt(socket.SOL_SOCKET,socket.SO_EXCLUSIVEADDRUSE,1)
        super().server_bind()

def bounded(value, maximum=MAX_HEIGHT):
    if type(value) is not int or not 0 <= value <= maximum:
        raise ValueError('Page value is outside the supported range')
    return value

def query_integer(text, maximum=MAX_HEIGHT):
    if not re.fullmatch(r'[0-9]{1,10}', text):
        raise ValueError('Invalid page value')
    return bounded(int(text), maximum)

def release_index_lock(stream):
    try:
        stream.seek(0)
        if os.name == 'nt':
            import msvcrt
            msvcrt.locking(stream.fileno(),msvcrt.LK_UNLCK,1)
        else:
            import fcntl
            fcntl.flock(stream.fileno(),fcntl.LOCK_UN)
    finally:
        stream.close()

def amount(units):
    sign = '-' if units < 0 else ''
    value = abs(units)
    return f'{sign}{value // 100000000}.{value % 100000000:08d}'

def verify_merkle_proof(proof):
    """Verify TXID membership against the included 80-byte header, not chain finality."""
    try:
        if not isinstance(proof,dict) or proof.get('format') != 'SUMUWW-txid-merkle-v1':
            return False
        total,index=proof['transaction_count'],proof['transaction_index']
        if type(total) is not int or not 1<=total<=1000000 or type(index) is not int or not 0<=index<total:
            return False
        def digest(text):
            if not isinstance(text,str) or HASH.fullmatch(text) is None:
                raise ValueError('Invalid proof hash')
            return bytes.fromhex(text)[::-1]
        header=Header.deserialize(bytes.fromhex(proof['header_hex']))
        if hash_to_display(header.digest()) != proof['block_hash'] or hash_to_display(header.merkle_root) != proof['merkle_root']:
            return False
        node=digest(proof['txid'])
        branch=proof['siblings']
        if not isinstance(branch,list) or len(branch)>20:
            return False
        position=0
        while total>1:
            if position>=len(branch):return False
            sibling=digest(branch[position]);position+=1
            if index==total-1 and total%2 and sibling!=node:return False
            node=sha256d(sibling+node if index%2 else node+sibling)
            index//=2;total=(total+1)//2
        return position==len(branch) and node==header.merkle_root
    except (ValueError,TypeError,KeyError,IndexError):
        return False

def csv_file(filename,fields,rows):
    stream=io.StringIO(newline='');writer=csv.writer(stream)
    writer.writerow(fields);writer.writerows(rows)
    return {'filename':filename,'content_type':'text/csv; charset=utf-8','data':stream.getvalue().encode('utf-8-sig')}

def address(script):
    try:
        return encode_address(script, network=SUMUWW)
    except AddressError:
        return None

def default_database():
    local = os.environ.get('LOCALAPPDATA')
    current = Path(local) / 'SUMUWW' if local else Path.home() / '.sumuww'
    legacy = Path(local) / 'DORA' if local else Path.home() / '.dora'
    base = current
    if not (current / 'active-node.json').exists() and not (current / 'data/node.sqlite').exists():
        if (legacy / 'active-node.json').exists() or (legacy / 'data/node.sqlite').exists():
            base = legacy
    marker = base / 'active-node.json'
    override = os.environ.get('SUMUWW_DATA_DIR') or os.environ.get('DORA_DATA_DIR')
    if override:
        return Path(override).expanduser() / 'node.sqlite'
    if marker.is_file():
        if marker.stat().st_size > 4096:
            raise ValueError('Invalid active-node path file. Specify --database.')
        value = json.loads(marker.read_text(encoding='utf-8'))
        if not isinstance(value,dict) or set(value) != {'directory'} or not isinstance(value['directory'],str) or not value['directory'].strip():
            raise ValueError('Invalid active-node path file. Specify --database.')
        return Path(value['directory']).expanduser() / 'node.sqlite'
    return base / 'data/node.sqlite'

class NotFound(ValueError):
    pass

class Explorer(AdvancedExplorer):
    def __init__(self, database, index):
        self.database = Path(database).resolve()
        self.index = Path(index).resolve()
        protected = [self.database] + [Path(str(self.database)+suffix) for suffix in ('-wal','-shm','-journal')]
        def is_protected(path):
            return any(path == target or (path.exists() and target.exists() and path.samefile(target)) for target in protected)
        if is_protected(self.index):
            raise ValueError('Explorer index must be separate from the chain database')
        if not self.database.is_file():
            raise ValueError('Node database does not exist. Specify --database.')
        self.index.parent.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self.closed = False
        lock_path = self.index.with_name(self.index.name+'.lock')
        if is_protected(lock_path):
            raise ValueError('Index lock must be separate from the chain database')
        stream = lock_path.open('a+b')
        try:
            if stream.seek(0,2) == 0:
                stream.write(b'0');stream.flush()
            stream.seek(0)
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(stream.fileno(),msvcrt.LK_NBLCK,1)
            else:
                import fcntl
                fcntl.flock(stream.fileno(),fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            stream.close()
            raise ValueError('This explorer index is already in use. Close the other explorer or use a separate --index.') from None
        self._release = weakref.finalize(self,release_index_lock,stream)
        self.tip = None
        self.snapshot = None
        self.updated = 0
        self.last_error = None
        self.pool = {}
        self.coins = []
        try:
            self.initialize_index()
            self.refresh(force=True)
        except BaseException:
            self.close()
            raise

    def close(self):
        with self.lock:
            if not self.closed:
                self.closed = True
                self._release()

    def initialize_index(self):
        with closing(self.connect_index()) as c, c:
            existing = {r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")}
            expected = {
                'blocks':['hash','height','parent','timestamp','bits','nonce','version','merkle','work','size','weight','tx_count','reward','subsidy'],
                'txs':['txid','blockhash','position','coinbase','size','weight','version','locktime'],
                'outputs':['txid','n','value','address','script'], 'inputs':['txid','n','previous','previous_n']}
            optional = {'observations':['parent','observed_at','txids','template'],
                        'block_audits':['blockhash','observed_at','expected','actual','observed','captured_at']}
            # Upgrade only recognized explorer schemas; never adopt another database.
            identity = c.execute('PRAGMA application_id').fetchone()[0]
            if existing and (not set(expected)<=existing or existing-set(expected)-set(optional) or identity not in (0,INDEX_ID)
                             or any([r[1] for r in c.execute('PRAGMA table_info('+table+')')] != columns for table,columns in {**expected,**{k:v for k,v in optional.items() if k in existing}}.items())):
                raise ValueError('Selected index is not a SUMUWW Explorer index. Choose a separate --index.')
            if c.execute('PRAGMA quick_check').fetchone()[0] != 'ok':
                raise DataUnavailable('Explorer index is damaged. Use a new --index path to rebuild it.')
            c.executescript('''
            CREATE TABLE IF NOT EXISTS blocks(hash TEXT PRIMARY KEY, height INTEGER UNIQUE,
              parent TEXT, timestamp INTEGER, bits INTEGER, nonce INTEGER, version INTEGER,
              merkle TEXT, work TEXT, size INTEGER, weight INTEGER, tx_count INTEGER,
              reward INTEGER, subsidy INTEGER);
            CREATE TABLE IF NOT EXISTS txs(txid TEXT PRIMARY KEY, blockhash TEXT REFERENCES blocks(hash) ON DELETE CASCADE,
              position INTEGER, coinbase INTEGER, size INTEGER, weight INTEGER, version INTEGER, locktime INTEGER);
            CREATE TABLE IF NOT EXISTS outputs(txid TEXT REFERENCES txs(txid) ON DELETE CASCADE,
              n INTEGER, value INTEGER, address TEXT, script TEXT, PRIMARY KEY(txid,n));
            CREATE TABLE IF NOT EXISTS inputs(txid TEXT REFERENCES txs(txid) ON DELETE CASCADE,
              n INTEGER, previous TEXT, previous_n INTEGER, PRIMARY KEY(txid,n));
            CREATE INDEX IF NOT EXISTS outputs_address ON outputs(address);
            CREATE INDEX IF NOT EXISTS inputs_previous ON inputs(previous,previous_n);
            CREATE INDEX IF NOT EXISTS txs_block ON txs(blockhash,position);
            CREATE INDEX IF NOT EXISTS txs_kind ON txs(coinbase,blockhash,position);
            CREATE TABLE IF NOT EXISTS observations(parent TEXT PRIMARY KEY REFERENCES blocks(hash) ON DELETE CASCADE,
              observed_at REAL,txids TEXT,template TEXT);
            CREATE TABLE IF NOT EXISTS block_audits(blockhash TEXT PRIMARY KEY REFERENCES blocks(hash) ON DELETE CASCADE,
              observed_at REAL,expected TEXT,actual TEXT,observed TEXT,captured_at REAL);
            ''')
            c.execute(f'PRAGMA application_id={INDEX_ID}')
            if c.execute('PRAGMA user_version').fetchone()[0] < 3:
                for row in c.execute("SELECT txid,n,script FROM outputs WHERE address IS NULL AND length(script)=68 AND substr(script,1,4)='0020'").fetchall():
                    decoded=address(bytes.fromhex(row['script']))
                    if decoded is not None:
                        c.execute('UPDATE outputs SET address=? WHERE txid=? AND n=?',(decoded,row['txid'],row['n']))
            c.execute('PRAGMA user_version=3')
            if c.execute('PRAGMA foreign_key_check').fetchone() is not None:
                raise DataUnavailable('Explorer index has inconsistent references. Use a new --index path.')
            rows = list(c.execute('SELECT height,hash,parent FROM blocks ORDER BY height'))
            for height,row in enumerate(rows):
                if row['height'] != height or (height == 0 and row['hash'] != hash_to_display(SUMUWW.genesis.block_hash())) or (height>0 and row['parent'] != rows[height-1]['hash']):
                    raise DataUnavailable('Explorer index has an incomplete chain. Use a new --index path.')

    def connect_index(self):
        c = sqlite3.connect(self.index, timeout=10)
        c.row_factory = sqlite3.Row
        c.execute('PRAGMA foreign_keys=ON')
        return c

    def source(self):
        c = sqlite3.connect(self.database.as_uri() + '?mode=ro', uri=True, timeout=3)
        try:
            c.execute('PRAGMA query_only=ON')
            c.execute('BEGIN')
        except BaseException:
            c.close()
            raise
        return c

    def refresh(self, force=False):
        with self.lock:
            if self.closed:
                raise DataUnavailable('Explorer is closed')
            if not force and time.monotonic() - getattr(self,'_refreshed',0) < 3:
                return
            try:
                self._refresh_snapshot()
            except (sqlite3.Error,OSError,ValueError,TypeError,KeyError,IndexError,OverflowError,UnsupportedFeature) as error:
                raise DataUnavailable('Unable to read a consistent node snapshot. Check the database and retry.') from error

    def _refresh_snapshot(self):
        with closing(self.source()) as source:
            meta = dict(source.execute('SELECT name,value FROM metadata'))
            if (meta.get('profile') != SUMUWW.profile_id or meta.get('schema') != '1'
                    or meta.get('genesis') != SUMUWW.genesis.block_hash()):
                raise ValueError('Database is not the supported SUMUWW main chain')
            tip = hash_to_display(meta['tip'])
            tip_row = source.execute('SELECT height FROM blocks WHERE hash=?',(meta['tip'],)).fetchone()
            if tip_row is None or type(tip_row[0]) is not int or not 0<=tip_row[0]<=MAX_HEIGHT:
                raise ValueError('Missing or invalid active tip')
            pool = {}
            for digest, raw in source.execute('SELECT txid,raw FROM mempool ORDER BY id'):
                tx = Transaction.deserialize(raw)
                if tx.txid() != digest or tx.is_coinbase():
                    raise ValueError('Mempool bytes differ from the node index')
                pool[hash_to_display(digest)] = tx
            coins = list(source.execute('SELECT txid,idx,value,script,height,coinbase FROM utxos'))
            for digest,n,value,script,height,coinbase in coins:
                if (not isinstance(digest,bytes) or len(digest)!=32 or type(n) is not int or not 0<=n<=0xffffffff
                        or type(value) is not int or not 0<=value<=MAX_MONEY or not isinstance(script,bytes)
                        or type(height) is not int or not 0<=height<=tip_row[0] or type(coinbase) is not int or coinbase not in (0,1)):
                    raise ValueError('Invalid UTXO record')
            with closing(self.connect_index()) as index, index:
                path = []
                current = meta['tip']
                seen = set()
                expected_height = None
                ancestor = -1
                while current != bytes(32):
                    if current in seen:
                        raise ValueError('Cyclic active chain')
                    seen.add(current)
                    row = source.execute('SELECT hash,parent,height,work FROM blocks WHERE hash=?',(current,)).fetchone()
                    if row is None or type(row[2]) is not int or row[2] < 0 or (expected_height is not None and row[2] != expected_height):
                        raise ValueError('Incomplete or inconsistent active chain')
                    known = index.execute('SELECT height FROM blocks WHERE hash=?',(hash_to_display(current),)).fetchone()
                    if known is not None:
                        if known[0] != row[2]:
                            raise ValueError('Index height differs from the source')
                        ancestor = known[0]
                        break
                    path.append(row)
                    expected_height = row[2]-1
                    current = row[1]
                path.reverse()
                if ancestor == -1 and (not path or path[0][0] != SUMUWW.genesis.block_hash() or path[0][2] != 0):
                    raise ValueError('Active chain does not reach the SUMUWW genesis')
                if tip != self.tip:
                    index.execute('DELETE FROM blocks WHERE height>?',(ancestor,))
                for row in path:
                    raw = source.execute('SELECT raw FROM blocks WHERE hash=?', (row[0],)).fetchone()[0]
                    block = Block.deserialize(raw)
                    if block.block_hash() != row[0] or block.header.previous_hash != row[1]:
                        raise ValueError('Block bytes differ from the node index')
                    root,mutated = merkle_root([tx.txid() for tx in block.transactions])
                    if root != block.header.merkle_root or mutated:
                        raise ValueError('Block transaction commitment differs from its header')
                    self.insert_block(index, row, block, len(raw))
                self.record_observation(index,path,pool,coins,tip)
                # Commit the index only after every part of the same source
                # snapshot has been read and checked successfully.
        changed = self.snapshot is None or tip != self.tip or pool != self.pool or coins != self.coins
        self.pool, self.coins, self.tip = pool, coins, tip
        if changed:
            self.snapshot = secrets.token_hex(32)
        self.updated = time.time()
        self._refreshed = time.monotonic()
        self.last_error = None

    def insert_block(self, c, row, block, size):
        h = block.header
        valid_target(h.bits,SUMUWW.pow_limit)
        digest = hash_to_display(row[0])
        reward = sum(o.value for o in block.transactions[0].outputs)
        c.execute('INSERT INTO blocks VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                  (digest, row[2], hash_to_display(row[1]), h.timestamp, h.bits, h.nonce, h.version,
                   hash_to_display(h.merkle_root), row[3], size, block.weight(), len(block.transactions),
                   reward, subsidy(row[2])))
        for position, tx in enumerate(block.transactions):
            txid = hash_to_display(tx.txid())
            c.execute('INSERT INTO txs VALUES (?,?,?,?,?,?,?,?)',
                      (txid, digest, position, tx.is_coinbase(), len(tx.serialize()), tx.weight(), tx.version, tx.lock_time))
            c.executemany('INSERT INTO outputs VALUES (?,?,?,?,?)',
                          [(txid, n, o.value, address(o.script_pubkey), o.script_pubkey.hex()) for n, o in enumerate(tx.outputs)])
            if not tx.is_coinbase():
                c.executemany('INSERT INTO inputs VALUES (?,?,?,?)',
                              [(txid, n, hash_to_display(i.prev_txid), i.prev_index) for n, i in enumerate(tx.inputs)])

    def run(self, operation, *args, snapshot=None):
        with self.lock:
            self.refresh()
            if snapshot is not None and snapshot != self.snapshot:
                raise SnapshotChanged('Chain changed while reading this page. Retry the page.')
            with closing(self.connect_index()) as c:
                result = getattr(self, operation)(c, *args)
                result['snapshot'] = self.snapshot
                result['chain_tip'] = self.tip
                result['updated_at'] = self.updated
                return result

    def block_row(self, c, key):
        if str(key).isdigit() and len(str(key)) <= 10:
            row = c.execute('SELECT * FROM blocks WHERE height=?', (int(key),)).fetchone()
        elif HASH.fullmatch(str(key)):
            row = c.execute('SELECT * FROM blocks WHERE hash=?', (str(key).lower(),)).fetchone()
        else:
            raise ValueError('Enter a block height or a 64-character hash')
        if row is None:
            raise NotFound('Block not found in this node’s active chain')
        return row

    def tip_height(self, c):
        return c.execute('SELECT height FROM blocks WHERE hash=?', (self.tip,)).fetchone()[0]

    def view_block(self, c, row):
        result = dict(row)
        result['confirmations'] = self.tip_height(c) - row['height'] + 1
        result['reward'] = amount(row['reward'])
        result['subsidy'] = amount(row['subsidy'])
        result['bits'] = f'{row["bits"]:08x}'
        result['target'] = f'{valid_target(row["bits"], SUMUWW.pow_limit):064x}'
        result['algorithm'] = 'DGW v3' if row['height'] >= SUMUWW.dgw_activation_height else '2016-block retarget'
        return result

    def overview(self, c, before=None):
        if before is not None:
            bounded(before)
        height = self.tip_height(c)
        start = height + 1 if before is None else before
        blocks = [self.view_block(c, row) for row in c.execute('SELECT * FROM blocks WHERE height<? ORDER BY height DESC LIMIT 20', (start,))]
        latest = c.execute('SELECT * FROM blocks ORDER BY height DESC LIMIT 25').fetchall()
        interval = (latest[0]['timestamp'] - latest[-1]['timestamp']) / (len(latest)-1) if len(latest)>1 else None
        pool = [self.pending_summary(txid, tx) for txid, tx in list(self.pool.items())[:20]]
        counts = c.execute('SELECT count(*),coalesce(sum(coinbase),0) FROM txs').fetchone()
        return {'height': height, 'tip': self.tip, 'updated_at': self.updated,
                'version':VERSION,'last_block_age_seconds':max(0,int(time.time()-latest[0]['timestamp'])),
                'last_block_time': latest[0]['timestamp'], 'transactions': counts[0],
                'coinbase_transactions':counts[1], 'ordinary_transactions':counts[0]-counts[1],
                'utxos': len(self.coins), 'mempool_count': len(self.pool), 'mempool': pool,
                'interval': interval, 'algorithm': 'DGW v3' if height >= SUMUWW.dgw_activation_height else '2016-block retarget',
                'activation_height': SUMUWW.dgw_activation_height, 'blocks': blocks,
                'next_before': blocks[-1]['height'] if blocks and blocks[-1]['height'] > 0 else None,
                'source': 'Local node database', 'network_status': 'not_observed'}

    def block(self, c, key, offset=0):
        bounded(offset,1000000)
        row = self.block_row(c, key)
        result = self.view_block(c, row)
        result['transactions'] = [self.tx_summary(c, tx) for tx in c.execute('SELECT t.*,b.height FROM txs t JOIN blocks b ON b.hash=t.blockhash WHERE blockhash=? ORDER BY position LIMIT 50 OFFSET ?', (row['hash'], offset))]
        result['offset'] = offset
        nxt = c.execute('SELECT hash FROM blocks WHERE height=?', (row['height']+1,)).fetchone()
        result['next'] = nxt[0] if nxt else None
        return result

    def mempool(self, c, offset=0):
        bounded(offset,1000000)
        return {'total': len(self.pool), 'offset': offset,
                'transactions': [self.pending_summary(txid,tx) for txid,tx in list(self.pool.items())[offset:offset+25]]}

    def transactions(self,c,kind='ordinary',offset=0,filters=None):
        return self.filtered_transactions(c,kind,offset,filters)

    def tx_summary(self, c, row):
        result = dict(row)
        result['output_total'] = amount(c.execute('SELECT coalesce(sum(value),0) FROM outputs WHERE txid=?', (row['txid'],)).fetchone()[0])
        fee=self.financials(c,row['txid'],row['coinbase']);vsize=(row['weight']+3)//4
        result.update(vsize=vsize,fee=amount(fee) if fee is not None else None,fee_rate=rate(fee,vsize))
        return result

    def pending_summary(self, txid, tx):
        return {'txid': txid, 'coinbase': tx.is_coinbase(), 'size': len(tx.serialize()), 'weight': tx.weight(),
                'version': tx.version, 'locktime': tx.lock_time, 'confirmations': 0, 'pending': True,
                'output_total': amount(sum(o.value for o in tx.outputs))}

    def pending_view(self, txid, tx):
        return {**self.pending_summary(txid,tx),
                'inputs': [{'previous': hash_to_display(i.prev_txid), 'previous_n': i.prev_index} for i in tx.inputs],
                'outputs': [{'n': n, 'value': amount(o.value), 'address': address(o.script_pubkey), 'script': o.script_pubkey.hex()} for n, o in enumerate(tx.outputs)]}

    def address_summary(self,c,row,canonical):
        result=self.tx_summary(c,row)
        received=c.execute('SELECT coalesce(sum(value),0) FROM outputs WHERE txid=? AND address=?',(row['txid'],canonical)).fetchone()[0]
        spent=c.execute('''SELECT coalesce(sum(o.value),0) FROM inputs i JOIN outputs o ON o.txid=i.previous AND o.n=i.previous_n
                           WHERE i.txid=? AND o.address=?''',(row['txid'],canonical)).fetchone()[0]
        result.update(received=amount(received),spent=amount(spent),net_change=amount(received-spent))
        return result

    def address_pending_summary(self,c,txid,tx,script):
        result=self.pending_summary(txid,tx)
        received=sum(o.value for o in tx.outputs if o.script_pubkey==script)
        spent=0;resolved=True
        for item in tx.inputs:
            parent=self.pool.get(hash_to_display(item.prev_txid))
            if parent is not None and item.prev_index<len(parent.outputs):
                output=parent.outputs[item.prev_index]
                if output.script_pubkey==script:spent+=output.value
            else:
                output=c.execute('SELECT value,script FROM outputs WHERE txid=? AND n=?',(hash_to_display(item.prev_txid),item.prev_index)).fetchone()
                if output is None:resolved=False
                elif bytes.fromhex(output['script'])==script:spent+=output['value']
        result.update(received=amount(received),spent=amount(spent) if resolved else None,
                      net_change=amount(received-spent) if resolved else None)
        return result

    def transaction(self, c, txid):
        if not HASH.fullmatch(txid):
            raise ValueError('Invalid transaction ID')
        txid = txid.lower()
        row = c.execute('SELECT t.*,b.height,b.timestamp FROM txs t JOIN blocks b ON b.hash=t.blockhash WHERE txid=?', (txid,)).fetchone()
        if row is None:
            if txid in self.pool:
                data=self.pending_view(txid, self.pool[txid]);model=self.pool_model(c)[txid]
                data.update({key:model[key] for key in ('fee','fee_rate','vsize','effective_fee_rate')})
                return data
            raise NotFound('Transaction not found in the active chain or local mempool')
        result = self.tx_summary(c, row)
        result['confirmations'] = self.tip_height(c) - row['height'] + 1
        result['pending'] = False
        inputs = [dict(r) for r in c.execute('''SELECT i.n,i.previous,i.previous_n,o.value,o.address FROM inputs i
                  LEFT JOIN outputs o ON o.txid=i.previous AND o.n=i.previous_n WHERE i.txid=? ORDER BY i.n''', (txid,))]
        outputs = [dict(r) for r in c.execute('''SELECT o.n,o.value,o.address,o.script,i.txid AS spent_by FROM outputs o
                   LEFT JOIN inputs i ON i.previous=o.txid AND i.previous_n=o.n WHERE o.txid=? ORDER BY o.n''', (txid,))]
        total_in = sum(i['value'] for i in inputs if i['value'] is not None)
        total_out = sum(o['value'] for o in outputs)
        result['fee'] = amount(total_in - total_out) if not row['coinbase'] and all(i['value'] is not None for i in inputs) else None
        for item in inputs + outputs:
            if item.get('value') is not None:
                item['value'] = amount(item['value'])
        for item in outputs:
            item['unspendable'] = row['height'] == 0 or item['script'].startswith('6a')
        result['inputs'], result['outputs'] = inputs, outputs
        return result

    def address(self, c, text, offset=0):
        bounded(offset,1000000)
        script = decode_address(text, network=SUMUWW)
        canonical = encode_address(script, network=SUMUWW)
        coins = [coin for coin in self.coins if coin[3] == script]
        height = self.tip_height(c)
        spent_pending = {(i.prev_txid, i.prev_index) for tx in self.pool.values() for i in tx.inputs}
        confirmed = sum(coin[2] for coin in coins)
        immature = sum(coin[2] for coin in coins if coin[5] and height + 1 - coin[4] < 100)
        available = sum(coin[2] for coin in coins if (coin[0],coin[1]) not in spent_pending and (not coin[5] or height+1-coin[4]>=100))
        history_sql = '''SELECT txid FROM outputs WHERE address=? UNION
            SELECT i.txid FROM inputs i JOIN outputs o ON o.txid=i.previous AND o.n=i.previous_n WHERE o.address=?'''
        total = c.execute('SELECT count(*) FROM (' + history_sql + ')', (canonical,canonical)).fetchone()[0]
        history = c.execute('SELECT t.*,b.height,b.timestamp FROM txs t JOIN blocks b ON b.hash=t.blockhash WHERE t.txid IN (' + history_sql + ') ORDER BY b.height DESC,t.position DESC LIMIT 25 OFFSET ?', (canonical,canonical,offset))
        pending = []
        known_outputs = {(r['txid'], r['n']) for r in c.execute('SELECT txid,n FROM outputs WHERE address=?', (canonical,))}
        pending_entries = [(bytes.fromhex(txid)[::-1],tx) for txid,tx in self.pool.items()]
        pending_outputs = {(digest,n) for digest,tx in pending_entries for n,o in enumerate(tx.outputs) if o.script_pubkey == script}
        for txid, tx in self.pool.items():
            if any(o.script_pubkey == script for o in tx.outputs) or any((hash_to_display(i.prev_txid),i.prev_index) in known_outputs or (i.prev_txid,i.prev_index) in pending_outputs for i in tx.inputs):
                pending.append(self.address_pending_summary(c,txid,tx,script))
        pending_received = sum(o.value for digest,tx in pending_entries for n,o in enumerate(tx.outputs)
                               if o.script_pubkey==script and (digest,n) not in spent_pending)
        return {'address': canonical, 'height': height, 'confirmed': amount(confirmed), 'immature': amount(immature),
                'available': amount(available), 'pending_received': amount(pending_received),
                'utxo_count': len(coins), 'total_transactions': total, 'offset': offset,
                'transactions': [self.address_summary(c,r,canonical) for r in history], 'pending': pending,
                'utxos': [{'txid': hash_to_display(r[0]), 'n': r[1], 'value': amount(r[2]), 'height': r[4],
                           'coinbase': bool(r[5]), 'mature': not r[5] or height+1-r[4]>=100,
                           'pending_spent': (r[0],r[1]) in spent_pending} for r in coins[:100]]}

    def stored_block(self,c,key):
        row=self.block_row(c,key)
        with closing(self.source()) as source:
            stored=source.execute('SELECT raw FROM blocks WHERE hash=?',(bytes.fromhex(row['hash'])[::-1],)).fetchone()
        if stored is None:raise DataUnavailable('The block bytes are no longer available')
        raw=stored[0]
        try:block=Block.deserialize(raw)
        except (ValueError,TypeError,UnsupportedFeature) as error:raise DataUnavailable('Stored block bytes are invalid') from error
        root,mutated=merkle_root([tx.txid() for tx in block.transactions])
        if hash_to_display(block.block_hash())!=row['hash'] or hash_to_display(block.header.previous_hash)!=row['parent'] or root!=block.header.merkle_root or mutated:
            raise DataUnavailable('Stored block bytes do not match the indexed block')
        return row,block,raw

    def raw_block(self,c,key):
        row,_,raw=self.stored_block(c,key)
        return {'filename':f'SUMUWW-block-{row["height"]}-{row["hash"]}.bin','content_type':'application/octet-stream','data':raw}

    def transaction_bytes(self,c,txid):
        if not HASH.fullmatch(txid):raise ValueError('Invalid transaction ID')
        txid=txid.lower()
        row=c.execute('SELECT blockhash,position FROM txs WHERE txid=?',(txid,)).fetchone()
        if row is None:
            if txid in self.pool:return None,None,self.pool[txid]
            raise NotFound('Transaction not found')
        blockrow,block,_=self.stored_block(c,row['blockhash'])
        if not 0<=row['position']<len(block.transactions):raise DataUnavailable('Invalid transaction position')
        tx=block.transactions[row['position']]
        if hash_to_display(tx.txid())!=txid:raise DataUnavailable('Transaction index differs from block bytes')
        return blockrow,block,tx

    def raw_transaction(self,c,txid):
        _,_,tx=self.transaction_bytes(c,txid)
        return {'filename':'SUMUWW-transaction-'+hash_to_display(tx.txid())+'.bin','content_type':'application/octet-stream','data':tx.serialize()}

    def proof(self,c,txid):
        row,block,tx=self.transaction_bytes(c,txid)
        if block is None:raise NotFound('A pending transaction has no block inclusion proof')
        leaves=[item.txid() for item in block.transactions]
        original=leaves.index(tx.txid());index=original;siblings=[];level=leaves
        while len(level)>1:
            sibling=index^1
            siblings.append(hash_to_display(level[sibling] if sibling<len(level) else level[index]))
            if len(level)%2:level=level+[level[-1]]
            level=[sha256d(level[n]+level[n+1]) for n in range(0,len(level),2)]
            index//=2
        result={'format':'SUMUWW-txid-merkle-v1','txid':hash_to_display(tx.txid()),'block_hash':row['hash'],
                'block_height':row['height'],'merkle_root':hash_to_display(block.header.merkle_root),
                'header_hex':block.header.serialize().hex(),'transaction_index':original,
                'transaction_count':len(leaves),'siblings':siblings,
                'scope':'TXID inclusion in this header; not chain finality, witness-data verification or consensus validation'}
        result['proof_valid']=verify_merkle_proof(result)
        if not result['proof_valid']:raise DataUnavailable('Unable to construct a valid Merkle proof')
        return result

    def statistics(self,c,limit=144):
        bounded(limit,2016)
        if limit<1:raise ValueError('Statistics require at least one block')
        rows=list(c.execute('SELECT * FROM blocks ORDER BY height DESC LIMIT ?',(limit+1,)))
        rows.reverse();previous=rows[0] if len(rows)>limit else None
        sample=rows[-limit:];points=[]
        initial=valid_target(SUMUWW.initial_bits,SUMUWW.pow_limit)
        for row in sample:
            interval=row['timestamp']-previous['timestamp'] if previous is not None else None
            points.append({'height':row['height'],'hash':row['hash'],'timestamp':row['timestamp'],
                           'interval_seconds':interval,'difficulty_ratio':initial/valid_target(row['bits'],SUMUWW.pow_limit),
                           'transactions':row['tx_count'],'ordinary_transactions':row['tx_count']-1,
                           'size':row['size'],'reward':amount(row['reward'])})
            previous=row
        intervals=[point['interval_seconds'] for point in points if point['interval_seconds'] is not None]
        return {'limit':limit,'block_count':len(points),'from_height':points[0]['height'],'to_height':points[-1]['height'],
                'average_interval_seconds':sum(intervals)/len(intervals) if intervals else None,
                'ordinary_transactions':sum(p['ordinary_transactions'] for p in points),
                'total_claimed_rewards':amount(sum(row['reward'] for row in sample)),'points':points,
                'difficulty_reference':'SUMUWW initial target / block target',
                'interval_reference':'Consecutive block timestamps; individual differences may be negative'}

    def export_blocks(self,c,limit=1000):
        bounded(limit,10000)
        if limit<1:raise ValueError('Export requires at least one block')
        rows=list(c.execute('SELECT height,hash,timestamp,tx_count,size,bits,reward FROM blocks ORDER BY height DESC LIMIT ?',(limit,)))
        return csv_file(f'SUMUWW-blocks-{rows[0][0]}-{rows[-1][0]}.csv',
                        ['height','block_hash','timestamp_utc','transactions_including_coinbase','bytes','bits','claimed_reward_SMW'],
                        [(r[0],r[1],datetime.fromtimestamp(r[2],timezone.utc).isoformat(),r[3],r[4],f'{r[5]:08x}',amount(r[6])) for r in rows])

    def export_address(self,c,text,limit=1000,offset=0):
        bounded(limit,10000);bounded(offset,1000000)
        if limit<1:raise ValueError('Export requires at least one transaction')
        canonical=encode_address(decode_address(text,network=SUMUWW),network=SUMUWW)
        rows=c.execute('''SELECT t.*,b.height,b.timestamp FROM txs t JOIN blocks b ON b.hash=t.blockhash WHERE t.txid IN
            (SELECT txid FROM outputs WHERE address=? UNION SELECT i.txid FROM inputs i JOIN outputs o ON o.txid=i.previous AND o.n=i.previous_n WHERE o.address=?)
            ORDER BY b.height DESC,t.position DESC LIMIT ? OFFSET ?''',(canonical,canonical,limit,offset))
        records=[self.address_summary(c,row,canonical) for row in rows]
        return csv_file(f'SUMUWW-address-{canonical}-{offset}.csv',
                        ['address','txid','height','timestamp_utc','coinbase','received_outputs_SMW','spent_inputs_SMW','net_change_SMW'],
                        [(canonical,r['txid'],r['height'],datetime.fromtimestamp(r['timestamp'],timezone.utc).isoformat(),int(r['coinbase']),r['received'],r['spent'],r['net_change']) for r in records])

    def export_statistics(self,c,limit=144):
        data=self.statistics(c,limit)
        return csv_file(f'SUMUWW-statistics-{data["from_height"]}-{data["to_height"]}.csv',
                        ['height','block_hash','timestamp_utc','difficulty_relative_to_initial','timestamp_interval_seconds','transactions_including_coinbase','ordinary_transactions','bytes','claimed_reward_SMW'],
                        [(p['height'],p['hash'],datetime.fromtimestamp(p['timestamp'],timezone.utc).isoformat(),format(p['difficulty_ratio'],'.12g'),p['interval_seconds'],p['transactions'],p['ordinary_transactions'],p['size'],p['reward']) for p in data['points']])

    def search(self, c, query):
        query = query.strip()
        if query.isdigit() and len(query)<=10:
            row = self.block_row(c,query)
            return {'type': 'block', 'key': row['hash']}
        if HASH.fullmatch(query):
            if c.execute('SELECT 1 FROM blocks WHERE hash=?', (query.lower(),)).fetchone():
                return {'type': 'block', 'key': query.lower()}
            self.transaction(c,query)
            return {'type': 'transaction', 'key': query.lower()}
        script = decode_address(query,network=SUMUWW)
        return {'type': 'address', 'key': encode_address(script,network=SUMUWW)}

class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def respond(self, status, data, content_type='application/json; charset=utf-8',filename=None):
        raw = json.dumps(data,ensure_ascii=False).encode() if content_type.startswith('application/json') else data
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(raw)))
        self.send_header('Cache-Control', 'no-store')
        if filename is not None:
            self.send_header('Content-Disposition','attachment; filename="'+filename+'"')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Referrer-Policy', 'no-referrer')
        self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
        self.end_headers()
        if self.command != 'HEAD':
            self.wfile.write(raw)

    def do_GET(self):
        try:
            # Numeric loopback Host prevents DNS rebinding to this local service.
            expected = f'127.0.0.1:{self.server.server_port}'
            if self.headers.get('Host') != expected:
                return self.respond(403, {'error': 'Use the printed loopback URL'})
            if self.headers.get('Sec-Fetch-Site') == 'cross-site':
                return self.respond(403, {'error': 'Cross-site requests are not allowed'})
            if self.headers.get('Origin') not in (None,'http://'+expected):
                return self.respond(403, {'error': 'Cross-origin requests are not allowed'})
            if len(self.path)>2048:
                return self.respond(414, {'error': 'Request too long'})
            url = urlsplit(self.path)
            query = parse_qs(url.query,keep_blank_values=True,max_num_fields=32)
            path = unquote(url.path)
            allowed = ({'before','snapshot'} if path == '/api/overview' else
                       FILTER_KEYS|{'kind','offset','snapshot','lang'} if path in ('/api/transactions','/api/report/transactions','/api/export/transactions.csv') else
                       {'limit','snapshot'} if path == '/api/mining' else
                       {'snapshot'} if path == '/api/fees' or path.endswith('/audit') or path.endswith('/related') else
                       {'lang','snapshot'} if path.endswith('/receipt') else
                       {'at_height','snapshot'} if path.endswith('/balance') else
                       {'date_from','date_to','min_height','max_height','offset','lang','snapshot'} if path.endswith('/history') or path.endswith('/report') else
                       {'q','snapshot'} if path == '/api/search' else
                       {'limit','snapshot'} if path in ('/api/statistics','/api/statistics/export','/api/export/blocks.csv') else
                       {'limit','offset','snapshot'} if path.startswith('/api/export/address/') else
                       {'download','snapshot'} if path.startswith('/api/transaction/') and path.endswith('/proof') else
                       {'snapshot'} if path.endswith('/raw') else {'offset','snapshot'})
            if set(query)-allowed or any(len(values)!=1 for values in query.values()):
                raise ValueError('Unknown or repeated query parameter')
            offset = query_integer(query.get('offset',['0'])[0],1000000)
            snapshot = query.get('snapshot',[None])[0]
            if snapshot is not None and HASH.fullmatch(snapshot) is None:
                raise ValueError('Invalid snapshot identifier')
            explorer = self.server.explorer
            filters={key:query[key][0] for key in FILTER_KEYS if key in query}
            language=query.get('lang',['en'])[0]
            if path == '/api/overview':
                before = query.get('before',[None])[0]
                result = explorer.run('overview',query_integer(before) if before is not None else None,snapshot=snapshot)
            elif path == '/api/mempool':
                result = explorer.run('mempool',offset,snapshot=snapshot)
            elif path == '/api/transactions':
                result = explorer.run('transactions',query.get('kind',['ordinary'])[0],offset,filters,snapshot=snapshot)
            elif path == '/api/fees':
                result = explorer.run('fee_analysis',snapshot=snapshot)
            elif path == '/api/mining':
                result = explorer.run('mining_analysis',query_integer(query.get('limit',['144'])[0],2016),snapshot=snapshot)
            elif path in ('/api/report/transactions','/api/export/transactions.csv'):
                result = explorer.run('transaction_report',query.get('kind',['all'])[0],filters,language,snapshot=snapshot)
                if path.endswith('.csv'):
                    result=csv_file('SUMUWW-transactions.csv',['txid','height','coinbase','output_SMW','fee_SMW','smallest_units_per_vB'],
                        [(r['txid'],r['height'],r['coinbase'],r['output_total'],r['fee'],r['fee_rate']) for r in result['transactions']])
            elif path.startswith('/api/address/') and path.endswith('/history'):
                result = explorer.run('ledger',path[len('/api/address/'):-len('/history')],filters,offset,snapshot=snapshot)
            elif path.startswith('/api/address/') and path.endswith('/balance'):
                result = explorer.run('past_balance',path[len('/api/address/'):-len('/balance')],query_integer(query.get('at_height',['0'])[0]),snapshot=snapshot)
            elif path.startswith('/api/address/') and path.endswith('/report'):
                result = explorer.run('address_report',path[len('/api/address/'):-len('/report')],filters,language,snapshot=snapshot)
            elif path.startswith('/api/transaction/') and path.endswith('/receipt'):
                result = explorer.run('receipt',path[len('/api/transaction/'):-len('/receipt')],language,snapshot=snapshot)
            elif path.startswith('/api/transaction/') and path.endswith('/related'):
                result = explorer.run('related',path[len('/api/transaction/'):-len('/related')],snapshot=snapshot)
            elif path.startswith('/api/block/') and path.endswith('/audit'):
                result = explorer.run('block_audit',path[len('/api/block/'):-len('/audit')],snapshot=snapshot)
            elif path == '/api/statistics':
                result = explorer.run('statistics',query_integer(query.get('limit',['144'])[0],2016),snapshot=snapshot)
            elif path == '/api/statistics/export':
                result = explorer.run('export_statistics',query_integer(query.get('limit',['144'])[0],2016),snapshot=snapshot)
            elif path == '/api/export/blocks.csv':
                result = explorer.run('export_blocks',query_integer(query.get('limit',['1000'])[0],10000),snapshot=snapshot)
            elif path.startswith('/api/export/address/'):
                result = explorer.run('export_address',path[len('/api/export/address/'):],query_integer(query.get('limit',['1000'])[0],10000),offset,snapshot=snapshot)
            elif path.startswith('/api/block/') and path.endswith('/raw'):
                result = explorer.run('raw_block',path[len('/api/block/'):-len('/raw')],snapshot=snapshot)
            elif path.startswith('/api/transaction/') and path.endswith('/raw'):
                result = explorer.run('raw_transaction',path[len('/api/transaction/'):-len('/raw')],snapshot=snapshot)
            elif path.startswith('/api/transaction/') and path.endswith('/proof'):
                result = explorer.run('proof',path[len('/api/transaction/'):-len('/proof')],snapshot=snapshot)
                download=query.get('download',['0'])[0]
                if download not in ('0','1'):raise ValueError('Invalid download value')
                if download=='1':
                    return self.respond(200,json.dumps(result,indent=2).encode(),'application/octet-stream',filename='SUMUWW-proof-'+result['txid']+'.json')
            elif path.startswith('/api/block/'):
                result = explorer.run('block',path[len('/api/block/'):],offset,snapshot=snapshot)
            elif path.startswith('/api/transaction/'):
                result = explorer.run('transaction',path[len('/api/transaction/'):],snapshot=snapshot)
            elif path.startswith('/api/address/'):
                result = explorer.run('address',path[len('/api/address/'):],offset,snapshot=snapshot)
            elif path == '/api/search':
                result = explorer.run('search',query.get('q',[''])[0],snapshot=snapshot)
            elif path in ('/', '/index.html','/app.js','/advanced.js','/languages.js','/style.css'):
                name = 'index.html' if path in ('/','/index.html') else path[1:]
                mime = {'index.html': 'text/html; charset=utf-8','app.js':'text/javascript; charset=utf-8','advanced.js':'text/javascript; charset=utf-8','languages.js':'text/javascript; charset=utf-8','style.css':'text/css; charset=utf-8'}[name]
                return self.respond(200,(ROOT/'dist'/name).read_bytes(),mime)
            else:
                return self.respond(404, {'error':'Not found'})
            if 'report_kind' in result:
                from reports import make_pdf
                return self.respond(200,make_pdf(result),'application/pdf',filename='SUMUWW-'+result['report_kind']+'.pdf')
            if 'content_type' in result:
                return self.respond(200,result['data'],result['content_type'],filename=result['filename'])
            self.respond(200,result)
        except NotFound as error:
            self.respond(404,{'error':str(error),'code':'not_found'})
        except SnapshotChanged as error:
            self.respond(409,{'error':str(error),'code':'snapshot_changed'})
        except DataUnavailable:
            self.respond(503,{'error':'Node/index data is unavailable or inconsistent. Retry after checking the database.','code':'data_unavailable'})
        except (ValueError,AddressError) as error:
            self.respond(400,{'error':str(error),'code':'invalid_request'})
        except (BrokenPipeError,ConnectionResetError,ConnectionAbortedError):
            # A canceled browser request must not trigger a second response.
            return
        except (sqlite3.Error,OSError):
            self.respond(503,{'error':'Node data is temporarily unavailable. Retry shortly.','code':'data_unavailable'})
        except Exception:
            self.respond(500,{'error':'Unable to read chain data'})

    def do_POST(self):
        self.respond(405,{'error':'Explorer is read-only'})

    do_PUT = do_DELETE = do_PATCH = do_OPTIONS = do_POST
    do_HEAD = do_GET

    def setup(self):
        self.request.settimeout(15)
        super().setup()

def running_explorer(port):
    """Recognize an existing local explorer without starting another indexer."""
    try:
        with urlopen(f'http://127.0.0.1:{port}/api/overview',timeout=5) as response:
            if response.status != 200:
                return False
            data=json.loads(response.read(65537))
        return (isinstance(data,dict) and data.get('source')=='Local node database'
                and data.get('network_status')=='not_observed'
                and isinstance(data.get('version'),str)
                and re.fullmatch(r'[0-9]+\.[0-9]+\.[0-9]+',data['version']) is not None
                and HASH.fullmatch(str(data.get('tip',''))) is not None
                and type(data.get('height')) is int and data['height']>=0)
    except (OSError,ValueError,TypeError):
        return False

def open_explorer_browser(port):
    url=f'http://127.0.0.1:{port}'
    try:
        opened=webbrowser.open(url)
    except Exception:
        opened=False
    if not opened:
        print('Open this address in your browser: '+url,flush=True)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--version',action='version',version='SUMUWW Explorer '+VERSION)
    parser.add_argument('--database',type=Path)
    parser.add_argument('--verify-proof',type=Path,help='Verify a downloaded Merkle proof without opening the node database')
    runtime_root = Path(sys.executable).resolve().parent if getattr(sys,'frozen',False) else ROOT
    parser.add_argument('--index',type=Path,default=runtime_root/'data/explorer.sqlite')
    parser.add_argument('--port',type=int,default=8770)
    browser_options=parser.add_mutually_exclusive_group()
    browser_options.add_argument('--open-browser',action='store_true',default=None,help='Open the explorer, reusing a running local instance when possible')
    browser_options.add_argument('--no-browser',dest='open_browser',action='store_false',help='Run without opening a browser')
    options=parser.parse_args()
    open_browser=options.open_browser if options.open_browser is not None else bool(getattr(sys,'frozen',False) and len(sys.argv)==1)
    server = explorer = observer = None
    stop_observer=threading.Event()
    try:
        if options.verify_proof is not None:
            if options.verify_proof.stat().st_size>65536:raise ValueError('Proof file is too large')
            proof=json.loads(options.verify_proof.read_text(encoding='utf-8-sig'))
            if not verify_merkle_proof(proof):raise ValueError('Invalid Merkle proof')
            print('Valid TXID inclusion proof for '+proof['txid']+' in header '+proof['block_hash']+'. This does not verify chain finality or consensus rules.',flush=True)
            return 0
        if not 0<=options.port<=65535:
            raise ValueError('Port must be between 0 and 65535')
        # Refuse duplicate ports before opening or modifying the explorer index.
        try:
            server=ExplorerHTTPServer(('127.0.0.1',options.port),Handler)
        except OSError as error:
            if (open_browser and options.database is None and options.index==runtime_root/'data/explorer.sqlite'
                    and (error.errno==errno.EADDRINUSE or getattr(error,'winerror',None)==10048)
                    and running_explorer(options.port)):
                print(f'SUMUWW Explorer is already running: http://127.0.0.1:{options.port}',flush=True)
                open_explorer_browser(options.port)
                return 0
            raise
        explorer=Explorer(options.database or default_database(),options.index)
        server.explorer=explorer
        print(f'SUMUWW Explorer {VERSION}: http://127.0.0.1:{server.server_port}',flush=True)
        print(f'Read-only source indexed. Height {explorer.run("overview")["height"]}.',flush=True)
        if open_browser:
            open_explorer_browser(server.server_port)
        def observe():
            while not stop_observer.wait(3):
                try:explorer.refresh()
                except DataUnavailable as error:explorer.last_error=str(error)
        observer=threading.Thread(target=observe,name='explorer-observation',daemon=True)
        observer.start()
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    except (ValueError,OSError,sqlite3.Error,DataUnavailable,RecursionError) as error:
        print('Explorer could not start: '+str(error),file=sys.stderr,flush=True)
        return 1
    finally:
        stop_observer.set()
        if observer is not None:observer.join(timeout=5)
        if server is not None:
            server.server_close()
        if explorer is not None:
            explorer.close()
    return 0

if __name__=='__main__':
    raise SystemExit(main())
