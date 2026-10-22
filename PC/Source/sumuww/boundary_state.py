"""Atomic boundary proof and registered-connection state in the real chain DB."""
from collections import OrderedDict
from contextlib import contextmanager
import json
from .errors import InvalidBlock, StorageError

class BoundaryState:
    def __init__(self, chain, activation):
        self.chain=chain; self.activation=activation; self.pending=None; self.checked=OrderedDict()
        if activation is None: return
        from .boundary import network_id
        self.network=network_id(chain.network)
        from .random_boundary import POLICY,NUMERATOR,DENOMINATOR
        self.config={'domain':'sumuww-boundary-activation-v1','network':self.network,'activationHeight':activation,
            'blockSelection':POLICY,'numerator':NUMERATOR,'denominator':DENOMINATOR}
        from .boundary_crypto import canonical
        c=chain.connection
        c.execute('BEGIN IMMEDIATE')
        try:
            c.execute('CREATE TABLE IF NOT EXISTS boundary_config (one INTEGER PRIMARY KEY CHECK(one=1), config BLOB NOT NULL)')
            c.execute('CREATE TABLE IF NOT EXISTS boundary_proofs (hash BLOB PRIMARY KEY, envelope BLOB NOT NULL)')
            c.execute('CREATE TABLE IF NOT EXISTS boundary_tails (parent BLOB PRIMARY KEY, child BLOB NOT NULL, part_a TEXT NOT NULL)')
            c.execute('CREATE TABLE IF NOT EXISTS boundary_registered (height INTEGER PRIMARY KEY, hash BLOB NOT NULL, parent BLOB NOT NULL, proof TEXT NOT NULL)')
            old=c.execute('SELECT config FROM boundary_config WHERE one=1').fetchone()
            if old is None: c.execute('INSERT INTO boundary_config VALUES (1,?)',(canonical(self.config),))
            elif old[0]!=canonical(self.config):
                legacy={'domain':'sumuww-boundary-activation-v1','network':self.network,'activationHeight':activation}
                # Before either policy can have applied, preserve the same
                # verified history/UTXOs and update only this local rule marker.
                # Never reinterpret any post-activation block or signed record.
                untouched=(not c.execute('SELECT 1 FROM blocks WHERE height>=? LIMIT 1',(activation,)).fetchone()
                    and not any(c.execute('SELECT 1 FROM '+table+' LIMIT 1').fetchone()
                        for table in ('boundary_proofs','boundary_tails','boundary_registered')))
                if old[0]==canonical(legacy) and untouched:
                    c.execute('UPDATE boundary_config SET config=? WHERE one=1',(canonical(self.config),))
                else:raise StorageError('Boundary activation configuration mismatch')
            c.execute('COMMIT')
        except BaseException:
            c.execute('ROLLBACK'); raise

    def required(self,height,parent_hash=None):
        if self.activation is None or height<self.activation:return False
        if parent_hash is None:
            parent_hash=self.chain.tip_hash
            if self.chain._row(parent_hash)[2]+1!=height:raise ValueError('Explicit parent required for historical selection')
        from .random_boundary import selected
        return selected(self.network,height,parent_hash.hex())

    def previous_trace(self,parent_hash):
        """Latest selected ancestor; ordinary PoW blocks do not create traces."""
        if self.activation is None:return None
        current=parent_hash
        while True:
            row=self.chain._row(current)
            if row[2]<self.activation:return None
            if self.required(row[2],row[1]):
                proof=self.proof(current)
                if proof is None:raise StorageError('Selected ancestor proof missing')
                return current,proof
            current=row[1]

    def proof(self, digest):
        if self.activation is None: return None
        row=self.chain.connection.execute('SELECT envelope FROM boundary_proofs WHERE hash=?',(digest,)).fetchone()
        if row is None: return None
        envelope=json.loads(row[0])
        if envelope['start'] is not None:
            parent=bytes.fromhex(envelope['start']['parentHash'])
            tail=self.chain.connection.execute('SELECT child,part_a FROM boundary_tails WHERE parent=?',(parent,)).fetchone()
            if not tail or tail[0]!=digest: raise StorageError('Boundary parent tail missing or attached to another child')
            envelope['start']['partA']=tail[1]
        return envelope

    @contextmanager
    def submission(self, block, envelope):
        if self.pending is not None: raise InvalidBlock('Reentrant boundary submission')
        from .boundary_crypto import canonical
        if envelope is not None:
            encoded=canonical(envelope)
            envelope=json.loads(encoded)
        self.pending=(block.block_hash(),envelope)
        try: yield
        finally: self.pending=None

    def _envelope(self, digest):
        return self.pending[1] if self.pending and self.pending[0]==digest else self.proof(digest)

    def _registration_identity(self, envelope):
        from .boundary_crypto import digest
        c=envelope['certificate']
        return digest({'start':envelope['start'],'bundle':c['bundle'],'aggregate':c['aggregate'],
            'members':sorted([e['member'] for e in c['events'] if e['type']=='signature'],key=lambda m:m['payload']['nodeId'])})

    def validate(self, block, path):
        height=len(path)
        if self.activation is None: return
        envelope=self._envelope(block.block_hash())
        if not self.required(height,block.header.previous_hash):
            if envelope is not None: raise InvalidBlock('Unexpected boundary proof on an unselected block')
            self.assert_registered(block,path)
            return
        try:
            from .boundary import exact, verify_certificate, verify_start
            from .boundary_crypto import digest
            if not exact(envelope,'start certificate'): raise ValueError('Complete boundary proof required')
            parent_hash=block.header.previous_hash
            previous=self.previous_trace(parent_hash)
            if previous is None:
                if envelope['start'] is not None: raise ValueError('First selected block has no earlier trace')
            else:
                trace_hash,parent=previous
                verify_start(trace_hash.hex(),parent['certificate'],envelope['start'])
            key=digest({'height':height,'block':block.block_hash().hex(),'proof':envelope})
            if key not in self.checked:
                verify_certificate(self.network,height,parent_hash.hex(),block.block_hash().hex(),envelope['start'],envelope['certificate'])
                self.checked[key]=True
                if len(self.checked)>256: self.checked.popitem(last=False)
            self.assert_registered(block,path,envelope)
        except (ValueError,TypeError,KeyError,AssertionError) as error:
            raise InvalidBlock('Boundary validation: '+str(error)) from error

    def assert_registered(self, block, path, envelope=None, *, activating=False):
        if self.activation is None: return
        rows=self.chain.connection.execute('SELECT height,hash,parent,proof FROM boundary_registered ORDER BY height').fetchall()
        if not rows:return
        height=len(path); ancestry={row[2]:row[0] for row,_ in path}; ancestry[height]=block.block_hash()
        for registered_height,digest,parent,proof in rows:
            if registered_height in ancestry and ancestry[registered_height]!=digest:
                raise InvalidBlock('REGISTERED_CONNECTION_CONFLICT at '+str(registered_height))
            if registered_height==height and envelope is not None and (parent!=block.header.previous_hash or proof!=self._registration_identity(envelope)):
                raise InvalidBlock('REGISTERED_CONNECTION_CONFLICT at '+str(registered_height))
        if activating and rows and height<rows[-1][0]:
            raise InvalidBlock('REGISTERED_CONNECTION_CONFLICT: candidate truncates registered descendants')

    def store(self, block, height):
        if not self.required(height,block.header.previous_hash): return
        from .boundary_crypto import canonical
        envelope=self._envelope(block.block_hash())
        if envelope is None: raise InvalidBlock('Cannot persist an unsigned activated block')
        encoded=json.loads(canonical(envelope)); start=encoded['start']; c=self.chain.connection
        if start is not None:
            parent=bytes.fromhex(start['parentHash'])
            old=c.execute('SELECT child,part_a FROM boundary_tails WHERE parent=?',(parent,)).fetchone()
            if old and (old[0]!=block.block_hash() or old[1]!=start['partA']): raise InvalidBlock('Boundary parent tail already connected')
            if not old: c.execute('INSERT INTO boundary_tails VALUES (?,?,?)',(parent,block.block_hash(),start['partA']))
            del start['partA']
        c.execute('INSERT INTO boundary_proofs VALUES (?,?)',(block.block_hash(),canonical(encoded)))
        c.execute('INSERT INTO boundary_registered VALUES (?,?,?,?)',(height,block.block_hash(),block.header.previous_hash,self._registration_identity(envelope)))
        self.chain._stage('after_boundary_proof_saved')

    def verify_storage(self):
        if self.activation is None: return
        c=self.chain.connection
        activated=c.execute('SELECT hash,height,raw FROM blocks WHERE height>=? ORDER BY height',(self.activation,)).fetchall()
        from .block import Block
        for hash,height,raw in activated:
            block=Block.deserialize(raw); path=self.chain._path(block.header.previous_hash)
            self.validate(block,path)
            row=c.execute('SELECT hash FROM boundary_registered WHERE height=?',(height,)).fetchone()
            if self.required(height,block.header.previous_hash):
                if not row or row[0]!=hash: raise StorageError('Persisted signed boundary registration missing')
            elif row is not None:raise StorageError('Unexpected registration on unselected block')
        dangling=c.execute('SELECT COUNT(*) FROM boundary_registered r LEFT JOIN blocks b ON b.hash=r.hash WHERE b.hash IS NULL').fetchone()[0]
        if dangling: raise StorageError('Boundary registration without original block')
