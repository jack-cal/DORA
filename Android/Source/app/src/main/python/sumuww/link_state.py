"""Additive SQLite migration and proof-based equal-work fork choice."""
from contextlib import contextmanager
from dataclasses import replace
import json
from .errors import InvalidBlock,StorageError
from .link_crypto import (POLICY,Identity,canonical,digest,require,producer,producer_output,
                         block_beacon,beacon_outputs,decompress,verify,slot,message,proof_selected)
from . import link_beacon as beacon

class LinkState:
    def __init__(self,chain,activation):
        self.chain=chain;self.activation=activation;self.pending=None;self.anchor_cache={}
        self._producer_id=None;self._template_extras=None
        self.network=chain.network.genesis.block_hash().hex()
        if activation is None:return
        c=chain.connection
        c.execute('BEGIN IMMEDIATE')
        try:
            c.execute('CREATE TABLE IF NOT EXISTS link_upgrade (one INTEGER PRIMARY KEY, policy TEXT NOT NULL, activation INTEGER NOT NULL)')
            old=c.execute('SELECT policy,activation FROM link_upgrade WHERE one=1').fetchone()
            if old is None:
                # Never silently reinterpret a different rule's post-activation history.
                if c.execute('SELECT 1 FROM blocks WHERE height>=? LIMIT 1',(activation,)).fetchone():
                    raise StorageError('Existing post-9000 history needs an explicit migration review; original data is preserved')
                c.execute('INSERT INTO link_upgrade VALUES (1,?,?)',(POLICY,activation))
            elif old!=(POLICY,activation):
                if (old==('sumuww-postpow-links-9000-v1',activation) and
                        not c.execute('SELECT 1 FROM blocks WHERE height>=? LIMIT 1',(activation,)).fetchone()):
                    # A preactivation update changes no accepted block or proof.
                    c.execute('UPDATE link_upgrade SET policy=? WHERE one=1',(POLICY,))
                else:raise StorageError('Link activation configuration mismatch; post-activation history is preserved')
            c.execute('CREATE TABLE IF NOT EXISTS link_proofs (id TEXT PRIMARY KEY, source BLOB NOT NULL, target BLOB NOT NULL, slot TEXT NOT NULL, body BLOB NOT NULL)')
            c.execute('CREATE INDEX IF NOT EXISTS link_proof_source ON link_proofs(source)')
            c.execute('CREATE INDEX IF NOT EXISTS link_proof_target ON link_proofs(target)')
            c.execute('CREATE TABLE IF NOT EXISTS link_local (name TEXT PRIMARY KEY, body BLOB NOT NULL)')
            c.execute('COMMIT')
        except BaseException:
            c.execute('ROLLBACK');raise
    def enabled(self,height):return self.activation is not None and height>=self.activation
    def required(self,height,parent_hash=None):return False # A proof is never a mining/acceptance prerequisite.
    def assert_registered(self,*args,**kwargs):pass # No arrival-order finality locks.
    def store(self,*args):pass
    def previous_trace(self,*args):return None
    @contextmanager
    def submission(self,block,envelope):yield
    def identity(self):
        return Identity(self.chain.database.with_name(self.chain.database.name+'.link-keys.sqlite'))
    def local(self,name):
        if self.activation is None:return None
        row=self.chain.connection.execute('SELECT body FROM link_local WHERE name=?',(name,)).fetchone()
        return json.loads(row[0]) if row else None
    def set_local(self,name,value):
        self.chain.connection.execute('INSERT OR REPLACE INTO link_local VALUES (?,?)',(name,canonical(value)))
    def root(self,path):
        if self.activation is None or len(path)<self.activation:return None
        return path[self.activation-1][0][0].hex()
    def anchor(self,path):
        if not path or self.activation is None:return None
        key=path[-1][0][0]
        if key in self.anchor_cache:return self.anchor_cache[key]
        result=None
        for row,block in path[self.activation:]:
            setup=block_beacon(block)
            if setup is not None:
                result=(row[0],setup);break
        # Eviction bounds only a derived cache, never identities or discovery.
        if len(self.anchor_cache)>256:self.anchor_cache.clear()
        self.anchor_cache[key]=result
        return result
    def template_coinbase(self,coinbase,path):
        if not self.enabled(len(path)):return coinbase
        if self._producer_id is None:
            identity=self.identity()
            try:self._producer_id=identity.node_id
            finally:identity.close()
        outputs=coinbase.outputs+(producer_output(self._producer_id),)
        setup=self.local('ready_setup')
        if setup is not None and self.anchor(path) is None and setup['manifest']['context']['root']==self.root(path):
            beacon.verify_setup(setup)
            key=(path[-1][0][0],digest(setup))
            if self._template_extras is None or self._template_extras[0]!=key:
                self._template_extras=(key,beacon_outputs(setup))
            extra=self._template_extras[1]
            # If a transcript cannot fit, omit it and keep mining normally.
            if sum(len(o.script_pubkey) for o in extra)<800_000:outputs+=extra
        return replace(coinbase,outputs=outputs)
    def validate(self,block,path):
        if not self.enabled(len(path)):return
        try:
            producer(block);setup=block_beacon(block)
            if setup is not None:
                require(self.anchor(path) is None,'Beacon already anchored on this branch')
                ctx=setup['manifest']['context']
                require(ctx['network']==self.network and ctx['root']==self.root(path),'Beacon activation ancestry mismatch')
                beacon.verify_setup(setup)
        except Exception as error:
            if isinstance(error,StorageError):raise
            raise InvalidBlock('Link commitment: '+str(error)) from error
    def proof(self,block_hash):
        if self.activation is None:return None
        rows=self.chain.connection.execute('SELECT body FROM link_proofs WHERE source=? OR target=? ORDER BY id',(block_hash,block_hash)).fetchall()
        return {'policy':POLICY,'links':[json.loads(r[0]) for r in rows]} if rows else None
    def all_proofs(self):
        return [json.loads(r[0]) for r in self.chain.connection.execute('SELECT body FROM link_proofs ORDER BY id')]
    def verify_proof(self,proof):
        require(type(proof) is dict and set(proof)=={'message','left','right','source_receipt','target_receipt'},'Complete paired link required')
        m=proof['message'];a=bytes.fromhex(m['source']);b=bytes.fromhex(m['target'])
        ar=self.chain._row(a);br=self.chain._row(b)
        require(self.enabled(ar[2]) and br[1]==a and br[2]==ar[2]+1,'Link must bind a direct child after activation')
        source=self.chain.get_block(a);target=self.chain.get_block(b)
        found=self.anchor(self.chain._path(ar[1]));require(found is not None,'Prior PoW-anchored beacon required')
        setup=found[1];expected_slot=slot(self.network,ar[2],ar[1].hex())
        random=beacon.verify_beacon(setup,expected_slot,m['beacon'])
        require(proof_selected(random),'This random event does not request a link')
        signers=m['signers'];require(type(signers) is list and len(signers)==3 and len(set(signers))==3,'Three distinct witnesses required')
        require(m==message(self.network,a.hex(),b.hex(),ar[2],ar[1].hex(),signers,m['beacon']),'Link message context')
        left=decompress(proof['left'],96);right=decompress(proof['right'],96)
        for i,signer in enumerate(signers):verify(signer,m,(left[i*32:(i+1)*32]+right[i*32:(i+1)*32]).hex())
        body={'domain':'sumuww-source-attachment-v1','message':m,'left':proof['left'],'right':proof['right']}
        verify(producer(source),body,proof['source_receipt'])
        verify(producer(target),{'domain':'sumuww-target-attachment-v1','source_attachment':digest(body),'source_receipt':proof['source_receipt']},proof['target_receipt'])
        return a,b,m['slot']
    def add_proof(self,proof):
        a,b,s=self.verify_proof(proof);key=digest(proof);c=self.chain.connection
        c.execute('BEGIN IMMEDIATE')
        try:
            changed=c.execute('INSERT OR IGNORE INTO link_proofs VALUES (?,?,?,?,?)',(key,a,b,s,canonical(proof))).rowcount>0
            if changed:self.reselect(in_transaction=True)
            c.execute('COMMIT')
        except BaseException:
            c.execute('ROLLBACK');raise
        return changed
    def ingest(self,envelope):
        if envelope is None:return
        require(type(envelope) is dict and set(envelope)=={'policy','links'} and envelope['policy']==POLICY,'Unsupported attachment envelope')
        for proof in envelope['links']:self.add_proof(proof)
    def scores(self):
        slots={}
        for a,b,s in self.chain.connection.execute('SELECT source,target,slot FROM link_proofs'):
            slots.setdefault(s,set()).add((a,b))
        edges={next(iter(edges)) for edges in slots.values() if len(edges)==1}
        return edges,sum(len(edges)>1 for edges in slots.values())
    def score(self,path):
        edges,_=self.scores();ids={row[0] for row,_ in path}
        return sum(a in ids and b in ids for a,b in edges)
    def prefer(self,path,old_path):
        work=int(path[-1][0][3]);old_work=int(old_path[-1][0][3])
        if work!=old_work:return work>old_work
        if not self.enabled(max(path[-1][0][2],old_path[-1][0][2])):return False
        return (self.score(path),-int.from_bytes(path[-1][0][0],'big'))>(self.score(old_path),-int.from_bytes(old_path[-1][0][0],'big'))
    def reselect(self,in_transaction=False):
        c=self.chain.connection;old_path=self.chain._path(self.chain.tip_hash);best=old_path
        for (key,) in c.execute('SELECT hash FROM blocks WHERE hash NOT IN (SELECT parent FROM blocks)'):
            path=self.chain._path(key)
            if self.prefer(path,best):best=path
        if best[-1][0][0]==old_path[-1][0][0]:return False
        state,_=self.chain._state_for(best[-1][0][0]);ids={r[0] for r,_ in best}
        disconnected=[t for r,b in old_path if r[0] not in ids for t in b.transactions[1:]]
        confirmed={t.txid() for _,b in best for t in b.transactions}
        self.chain._replace_utxos(state)
        c.execute("UPDATE metadata SET value=? WHERE name='tip'",(best[-1][0][0],))
        self.chain._rebuild_mempool(disconnected,confirmed,state=state.copy(),path=best)
        self.chain._indexed_path_cache=None;self.chain._validated_branch_cache=None
        return True
    def verify_storage(self):
        if self.activation is None:return
        for proof in self.all_proofs():self.verify_proof(proof)
