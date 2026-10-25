"""Background, permissionless replacement of unavailable beacon generations.

Timeouts decide only what this node proposes. PoW ancestry and the validated
public DKG transcript decide which generation every verifier actually uses.
No wallet key or old witness signature is redistributed.
"""
import asyncio
import secrets
import time

from . import link_beacon as beacon
from .link_crypto import digest


class BeaconRecovery:
    def __init__(self,runtime):
        self.runtime=runtime
        self.task=None
        self.active=None
        self.next_check=0.0
        self.interval=60.0
        self.request_timeout=20.0
        self.setup_timeout=120.0
        self.cooldown=300.0
        self.excluded={}
        self.failed_anchor=None
        self.status='discovering'
        self.attempts=0
        self.timeouts=0

    def failure(self,anchor,missing):
        r=self.runtime
        current=r.state.anchor(r.node.chain._path(r.node.chain.tip_hash))
        if current is None or current[0]!=anchor:return
        self.failed_anchor=anchor.hex()
        until=time.monotonic()+self.cooldown
        for node_id in missing:self.excluded[node_id]=until
        self.next_check=0.0

    def schedule(self,path):
        """Called by the housekeeping task; never awaited by mining/sync."""
        r=self.runtime
        if r.closed or (self.task and not self.task.done()):return
        if r.state.root(path) is None or time.monotonic()-r.started<2:return
        if time.monotonic()<self.next_check:return
        self.task=r.spawn(self.step())

    async def step(self):
        r=self.runtime;now=time.monotonic()
        self.next_check=now+self.interval
        path=r.node.chain._path(r.node.chain.tip_hash)
        root=r.state.root(path)
        if root is None:return
        current=r.state.anchor(path)
        previous=current[0].hex() if current else beacon.NO_PREVIOUS
        if r.state.prepared_setup(path) is not None:self.active=None
        if self.active:
            cid,started=self.active;row=r.contexts.get(cid)
            if row:
                try:r.state.check_setup_context(row['context'],path)
                except ValueError:row=None
            if row and now-started<self.setup_timeout:
                self.status='preparing distributed key'
                # Retransmit public data after packet loss or a reconnect.
                await r.publish('dkg',{'context':row['context']})
                for kind,values in (('deal',row['deals']),('ready',row['ready'])):
                    if r.keys.node_id in values:
                        await r.publish('dkg',{'context':row['context'],kind:values[r.keys.node_id]})
                return
            if row:
                ids=set(beacon.check_context(row['context']))
                missing=ids-set(row['deals'])
                if not missing:missing=ids-set(row['ready'])
                for node_id in missing:self.excluded[node_id]=now+self.cooldown
                self.timeouts+=1
            self.active=None
        if current and path[-1][0][2]<r.node.chain._row(current[0])[2]+beacon.MIN_GENERATION_BLOCKS:
            self.status='active; next recovery window not reached'
            return
        self.excluded={k:v for k,v in self.excluded.items() if v>now}
        # Probe *all* discovered contacts through gossip, including non-neighbors.
        # No fixed-size shortlist or IP quota is used. A probe is not admission.
        self.status='checking discovered participants'
        nonce=secrets.token_hex(32)
        certified=r.state.selection_required(path[-1][0][2])
        async def probe(node_id):
            try:
                method='selection_probe' if certified else 'dkg_probe'
                value=await r.request(node_id,method,{'nonce':nonce},timeout=self.request_timeout)
                if certified:
                    from .link_selection import SELECTION_POLICY,PUBLIC_ACTIVATION_HEIGHT
                    if value=={'nonce':nonce,'policy':SELECTION_POLICY,'activation_height':PUBLIC_ACTIVATION_HEIGHT}:return node_id
                elif value==nonce:return node_id
            except (ValueError,TimeoutError,OSError):pass
            return None
        results=await asyncio.gather(*(probe(i) for i in tuple(r.contacts)))
        live={i for i in results if i is not None}
        if current:
            old=set(beacon.check_context(current[1]['manifest']['context']))
            # A signed contact reply alone does not show that the old shares
            # are usable. Verify actual threshold shares on a fresh challenge.
            challenge=digest(['SUMUWW-BEACON-HEALTH',r.network,previous,nonce])
            async def health(node_id):
                try:
                    value=await r.request(node_id,'beacon_health',{'anchor':previous,'nonce':nonce},timeout=self.request_timeout)
                    if value['nodeId']!=node_id:return None
                    await asyncio.to_thread(beacon.verify_partial,current[1],challenge,value)
                    return node_id
                except (ValueError,KeyError,TimeoutError,OSError):return None
            healthy={i for i in await asyncio.gather(*(health(i) for i in old & live)) if i is not None}
            if len(healthy)<beacon.threshold(len(old)):
                for node_id in old-healthy:self.excluded[node_id]=time.monotonic()+self.cooldown
            prepared=r.state.prepared_setup(path)
            if prepared:
                proposed=set(beacon.check_context(prepared['manifest']['context']))
                if not proposed<=live or proposed & self.excluded.keys():
                    r.state.set_local('ready_setup',None)
                else:
                    self.status='prepared; awaiting an ordinary mined block'
                    return
            if len(healthy)>=beacon.threshold(len(old)) and live==old and self.failed_anchor!=previous and not self.excluded:
                self.status='active'
                return
        else:
            prepared=r.state.prepared_setup(path)
            if prepared:
                proposed=set(beacon.check_context(prepared['manifest']['context']))
                if proposed<=live and not proposed & self.excluded.keys():
                    self.status='prepared; awaiting an ordinary mined block'
                    return
                r.state.set_local('ready_setup',None)
        members=[r.contacts[i] for i in sorted(live) if i not in self.excluded]
        if len(members)<3:
            self.status='waiting for three responsive DKG participants; mining continues'
            return
        # Re-read after network/crypto awaits: a concurrent anchor or reorg
        # invalidates the old proposal; it must never overwrite the new one.
        path=r.node.chain._path(r.node.chain.tip_hash)
        found=r.state.anchor(path)
        if (found[0].hex() if found else beacon.NO_PREVIOUS)!=previous:return
        ctx=beacon.recovery_context(r.network,root,members,previous,path[-1][0][0].hex())
        r.state.check_setup_context(ctx,path)
        self.active=(digest(ctx),time.monotonic());self.attempts+=1
        self.status='preparing distributed key'
        await r.publish('dkg',{'context':ctx})

    def info(self):
        return {'status':self.status,'attempts':self.attempts,'timed_out_setups':self.timeouts}
