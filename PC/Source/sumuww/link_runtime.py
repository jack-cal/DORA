"""Nonblocking connection proof jobs on the existing PC/Android TCP transport."""
import asyncio
import json
import secrets
import time
from collections import OrderedDict
from .link_crypto import (POLICY,Identity,canonical,digest,require,verify_frame,producer,
                         message,slot,sample,compress,verify,proof_selected,PROOF_SELECTION_DENOMINATOR)
from . import link_beacon as beacon
from .boundary_transport import PartReceiver

class LinkRuntime:
    def __init__(self,node):
        self.node=node;self.state=node.chain.boundary;self.network=self.state.network
        self.key_path=node.database.with_name(node.database.name+'.link-keys.sqlite')
        self.keys=Identity(self.key_path);self.closed=False;self.parts=PartReceiver()
        self.contact=self.keys.signed({'domain':'sumuww-link-contact-v1','network':self.network,
                                      'nodeId':self.keys.node_id,'encryption':self.keys.encryption_key})
        self.contacts={c['payload']['nodeId']:c for c in (self.state.local('contacts') or [])}
        self.contacts[self.keys.node_id]=self.contact
        self.seen=OrderedDict();self.proofs={};self.deferred={};self.calls={};self.contexts={}
        self.providers={};self.support_tasks={}
        self.tasks=set();self.jobs={};self.tick=None;self.started=time.monotonic();self.last_error=None
        self.proposed=set();self.omit_beacon=False;self.omit_witness=False;self.signature_delay=0
        self.metrics={'completed':0,'rejected':0,'skipped':0,'pending':0,'lotteries':[]}
    def spawn(self,awaitable):
        task=asyncio.create_task(awaitable);self.tasks.add(task)
        def finished(t):
            self.tasks.discard(t)
            if not t.cancelled() and t.exception():self.last_error=str(t.exception())
        task.add_done_callback(finished);return task
    async def crypto(self,method,*args):
        def run():
            identity=Identity(self.key_path)
            try:return method(identity,*args)
            finally:identity.close()
        return await asyncio.to_thread(run)
    def sessions(self):
        return [s for s in self.node._sessions.values() if s.ready and s.boundary_id and s.boundary_policy==POLICY and not s.writer.is_closing()]
    def info(self):
        return {'activation_height':self.state.activation,'block_policy':POLICY,'signing_node_id':self.keys.node_id,
                'authenticated_connected_nodes':len(self.sessions()),'discovered_nodes':len(self.contacts),
                'pending_links':len(self.jobs),'last_error':self.last_error,'selection_probability':1/PROOF_SELECTION_DENOMINATOR,
                'completed_links':self.metrics['completed']}
    async def hello(self,session,**kwargs):
        if session.boundary_hello_sent:return
        session.boundary_hello_sent=True
        p={'domain':'sumuww-link-hello-v1','network':self.network,'nodeId':self.keys.node_id,
           'ownNonce':str(self.node.nonce),'peerNonce':str(session.nonce),'blockPolicy':POLICY,'contact':self.contact}
        await self.node._send(session,'bhello',canonical(self.keys.signed(p)))
    async def broadcast(self,frame,exclude=None):
        data=canonical(frame)
        async def send(session):
            try:await self.node._send(session,'bcall',data)
            except (OSError,TimeoutError,ValueError):pass
        await asyncio.gather(*(send(s) for s in self.sessions() if s is not exclude))
    def frame(self,kind,body):
        return self.keys.signed({'domain':'sumuww-link-gossip-v1','network':self.network,'nodeId':self.keys.node_id,
                                 'kind':kind,'nonce':secrets.token_hex(16),'body':body})
    async def publish(self,kind,body):await self.receive(self.frame(kind,body),None)
    def add_contact(self,c):
        p=verify_frame(c)
        require(set(p)=={'domain','network','nodeId','encryption'} and p['domain']=='sumuww-link-contact-v1' and p['network']==self.network,'Contact context')
        require(len(bytes.fromhex(p['encryption']))==32,'Contact encryption key')
        old=self.contacts.get(p['nodeId']);require(old in (None,c),'Identity changed encryption key')
        if old is None:
            self.contacts[p['nodeId']]=c;self.state.set_local('contacts',list(self.contacts.values()))
    async def sync(self,session):
        # Full identity/evidence inventory is framed by the existing multipart
        # transport. This is not a truncated lottery candidate prefix.
        await self.node._send(session,'bcall',canonical(self.frame('sync',{'contacts':list(self.contacts.values()),'proofs':self.state.all_proofs()})))
    async def handle(self,session,command,payload):
        from .boundary_runtime import decode_json,decode_block,BoundaryPolicyMismatch
        if command=='bpart':
            complete=self.parts.receive(session,payload)
            if complete is not None:await self.handle(session,*complete)
            return
        if command=='bhello':
            p=verify_frame(decode_json(payload))
            if p.get('blockPolicy')!=POLICY:raise BoundaryPolicyMismatch('Previous signing policy; native transport only')
            require(p['domain']=='sumuww-link-hello-v1' and p['network']==self.network and p['ownNonce']==str(session.nonce) and p['peerNonce']==str(self.node.nonce),'Link handshake binding')
            require(p['contact']['payload']['nodeId']==p['nodeId'],'Contact handshake identity')
            self.add_contact(p['contact']);session.boundary_id=p['nodeId'];session.boundary_policy=POLICY
            await self.hello(session);self.spawn(self.sync(session));self.spawn(self.publish('contact',p['contact']));return
        require(session.boundary_id and session.boundary_policy==POLICY,'Link handshake required')
        if command=='bblock':
            raw,envelope=decode_block(payload)
            if envelope.get('policy')==POLICY:
                for proof in envelope['links']:
                    key=digest(proof);self.deferred[key]=proof;self.providers[key]=session.boundary_id
            await self.node._received_block(session,raw);return
        if command=='bcall':
            # Verification/DKG jobs are independent of the block receiver and
            # mining worker. A slow recipient never owns the next-block path.
            self.spawn(self.receive(decode_json(payload,None),session));return
        raise ValueError('Unsupported link command')
    async def receive(self,frame,source):
        p=verify_frame(frame)
        require(p['domain']=='sumuww-link-gossip-v1' and p['network']==self.network,'Link gossip context')
        key=digest(frame)
        if key in self.seen:return
        self.seen[key]=True
        if len(self.seen)>16384:self.seen.popitem(last=False)
        kind=p['kind'];body=p['body']
        if kind=='contact':self.add_contact(body)
        elif kind=='sync':
            for c in body['contacts']:self.add_contact(c)
            for proof in body['proofs']:
                key=digest(proof);self.deferred[key]=proof;self.providers[key]=p['nodeId']
        elif kind=='dkg':
            ctx=body['context'];ids=beacon.check_context(ctx)
            require(ctx['network']==self.network,'DKG network mismatch')
            for c in ctx['members']:self.add_contact(c)
            cid=digest(ctx);row=self.contexts.setdefault(cid,{'context':ctx,'deals':{},'ready':{},'dealing':False,'recovering':False})
            if 'deal' in body:
                await asyncio.to_thread(beacon.verify_deal,ctx,body['deal'])
                dealer=body['deal']['payload']['nodeId'];old=row['deals'].get(dealer)
                require(old in (None,body['deal']),'Conflicting DKG contribution');row['deals'][dealer]=body['deal']
            if 'ready' in body:
                r=verify_frame(body['ready']);require(r['nodeId'] in ids and r['domain']=='sumuww-dkg-ready-v1','Invalid ready identity')
                row['ready'][r['nodeId']]=body['ready']
            if self.keys.node_id in ids and not row['dealing']:
                row['dealing']=True;self.spawn(self.deal(row))
            if len(row['deals'])==len(ids) and not row['recovering']:
                row['recovering']=True;self.spawn(self.ready(row))
            self.try_setup(row)
        elif kind=='request':
            require(p['nodeId']==body['requester'],'Request signer mismatch')
            if body['target']==self.keys.node_id:self.spawn(self.execute(key,body))
        elif kind=='reply':
            pending=self.calls.get(body['request'])
            if pending and p['nodeId']==pending[0] and not pending[1].done():pending[1].set_result(body)
        elif kind=='proof':
            key=digest(body);self.deferred[key]=body;self.providers[key]=p['nodeId']
        else:raise ValueError('Unknown link gossip type')
        await self.broadcast(frame,source)
    async def deal(self,row):
        deal=await self.crypto(beacon.make_deal,row['context'])
        await self.publish('dkg',{'context':row['context'],'deal':deal})
    async def ready(self,row):
        if self.keys.node_id not in beacon.check_context(row['context']):return
        m=beacon.manifest(row['context'],list(row['deals'].values()))
        ready=await self.crypto(beacon.recover,m)
        await self.publish('dkg',{'context':row['context'],'ready':ready})
    def try_setup(self,row):
        ids=beacon.check_context(row['context'])
        if len(row['deals'])!=len(ids) or len(row['ready'])<beacon.quorum(len(ids)):return
        m=beacon.manifest(row['context'],list(row['deals'].values()))
        ready=[r for _,r in sorted(row['ready'].items()) if r['payload']['manifest']==digest(m)]
        if len(ready)<beacon.quorum(len(ids)):return
        setup={'manifest':m,'ready':ready};beacon.verify_setup(setup)
        current=self.state.local('ready_setup')
        if current is None or len(ids)>len(current['manifest']['context']['members']):self.state.set_local('ready_setup',setup)
    async def request(self,target,method,body,timeout=20):
        frame=self.frame('request',{'requester':self.keys.node_id,'target':target,'method':method,'body':body})
        key=digest(frame);future=asyncio.get_running_loop().create_future();self.calls[key]=(target,future)
        try:
            await self.receive(frame,None)
            result=await asyncio.wait_for(future,timeout)
            require(result['ok'],result.get('error','Request failed'));return result['value']
        finally:self.calls.pop(key,None)
    async def execute(self,key,request):
        method=request['method'];body=request['body']
        if (method=='beacon' and self.omit_beacon) or (method=='sign' and self.omit_witness):return
        try:
            if self.signature_delay and method in ('sign','beacon'):await asyncio.sleep(self.signature_delay)
            if method=='block':
                value=self.node.chain.get_block(bytes.fromhex(body['hash'])).serialize().hex()
            elif method=='beacon':
                a=bytes.fromhex(body['source']);row=self.node.chain._row(a);found=self.state.anchor(self.node.chain._path(row[1]))
                require(found is not None,'Beacon not anchored')
                expected=slot(self.network,row[2],row[1].hex());require(body['slot']==expected,'Beacon slot mismatch')
                value=await self.crypto(beacon.partial,found[1],expected)
            elif method=='sign':
                m=body;ar=self.node.chain._row(bytes.fromhex(m['source']));br=self.node.chain._row(bytes.fromhex(m['target']))
                require(self.state.enabled(ar[2]) and br[1]==ar[0] and producer(self.node.chain.get_block(ar[0]))==request['requester'],'Signature source producer mismatch')
                require(len(m['signers'])==3 and len(set(m['signers']))==3 and self.keys.node_id in m['signers'],'Signature team')
                found=self.state.anchor(self.node.chain._path(ar[1]));require(found is not None,'Beacon missing')
                expected=slot(self.network,ar[2],ar[1].hex());random=await asyncio.to_thread(beacon.verify_beacon,found[1],expected,m['beacon'])
                require(proof_selected(random) and m==message(self.network,ar[0].hex(),br[0].hex(),ar[2],ar[1].hex(),m['signers'],m['beacon']),'Unselected or mismatched signature request')
                signature=bytes.fromhex(self.keys.sign_once(expected,m));value={'left':signature[:32].hex(),'right':signature[32:].hex()}
            elif method=='attach':
                m=body['message'];a=self.node.chain.get_block(bytes.fromhex(m['source']));b=self.node.chain.get_block(bytes.fromhex(m['target']))
                require(b.header.previous_hash==a.block_hash() and producer(b)==self.keys.node_id and producer(a)==request['requester'],'Attachment producer mismatch')
                source_body={'domain':'sumuww-source-attachment-v1','message':m,'left':body['left'],'right':body['right']}
                verify(request['requester'],source_body,body['source_receipt'])
                # Validate all three reconstructed witness signatures before
                # signing the target receipt (same verifier as final ingestion).
                from .link_crypto import decompress
                l=decompress(body['left'],96);r=decompress(body['right'],96)
                for i,signer in enumerate(m['signers']):verify(signer,m,(l[32*i:32*i+32]+r[32*i:32*i+32]).hex())
                value=self.keys.sign({'domain':'sumuww-target-attachment-v1','source_attachment':digest(source_body),'source_receipt':body['source_receipt']})
            else:raise ValueError('Unknown link request method')
            reply={'request':key,'ok':True,'value':value}
        except Exception as error:reply={'request':key,'ok':False,'error':str(error)}
        await self.publish('reply',reply)
    async def obtain_beacon(self,a,setup,s):
        ids=beacon.check_context(setup['manifest']['context']);needed=beacon.threshold(len(ids))
        tasks=[asyncio.create_task(self.request(i,'beacon',{'source':a,'slot':s})) for i in ids];partials=[]
        try:
            for task in asyncio.as_completed(tasks):
                try:
                    value=await task;await asyncio.to_thread(beacon.verify_partial,setup,s,value);partials.append(value)
                    if len(partials)>=needed:return await asyncio.to_thread(beacon.combine,setup,s,partials)
                except Exception:continue
            raise ValueError('Insufficient valid beacon responses; mining continues')
        finally:
            for task in tasks:task.cancel()
            await asyncio.gather(*tasks,return_exceptions=True)
    async def link(self,a,b):
        ar=self.node.chain._row(a);found=self.state.anchor(self.node.chain._path(ar[1]));setup=found[1]
        saved=self.keys.get('job:'+a.hex()) or {'target':b.hex()};self.keys.put('job:'+a.hex(),saved)
        b=bytes.fromhex(saved['target'])
        try:
            if 'message' not in saved:
                s=slot(self.network,ar[2],ar[1].hex());signature=await self.obtain_beacon(a.hex(),setup,s)
                random=beacon.verify_beacon(setup,s,signature)
                if not proof_selected(random):
                    saved['done']=True;self.keys.put('job:'+a.hex(),saved);self.metrics['skipped']+=1;return
                signers=sample(random,self.contacts)
                saved['message']=message(self.network,a.hex(),b.hex(),ar[2],ar[1].hex(),signers,signature)
                saved['candidates']=sorted(self.contacts);self.keys.put('job:'+a.hex(),saved)
                self.metrics['lotteries'].append({'source':a.hex(),'candidate_count':len(self.contacts),'signers':signers})
            m=saved['message']
            pieces=await asyncio.gather(*(self.request(i,'sign',m) for i in m['signers']))
            proof={'message':m,'left':compress(b''.join(bytes.fromhex(p['left']) for p in pieces)),
                   'right':compress(b''.join(bytes.fromhex(p['right']) for p in pieces))}
            source_body={'domain':'sumuww-source-attachment-v1',**proof}
            proof['source_receipt']=self.keys.sign(source_body)
            proof['target_receipt']=await self.request(producer(self.node.chain.get_block(b)),'attach',proof)
            self.state.add_proof(proof);saved['done']=True;self.keys.put('job:'+a.hex(),saved)
            self.metrics['completed']+=1;await self.publish('proof',proof)
        finally:self.jobs.pop(a,None)
    async def refresh(self):
        if self.closed:return
        if self.tick is None or self.tick.done():self.tick=self.spawn(self.background())
    async def fetch_support(self,key,proof):
        from .block import Block
        try:
            target=bytes.fromhex(proof['message']['target']);pending=[];seen=set()
            while not self.node.chain.has_block(target):
                require(target not in seen,'Cyclic proof ancestry');seen.add(target)
                encoded=await self.request(self.providers[key],'block',{'hash':target.hex()})
                block=Block.deserialize(bytes.fromhex(encoded));require(block.block_hash()==target,'Proof history hash mismatch')
                pending.append(block);target=block.header.previous_hash
            for block in reversed(pending):self.node.chain.accept_block(block)
        finally:self.support_tasks.pop(key,None)
    async def background(self):
        self.parts.expire(max(60,self.node.timeout))
        for key,proof in tuple(self.deferred.items()):
            m=proof.get('message',{})
            try:
                if not self.node.chain.has_block(bytes.fromhex(m['source'])) or not self.node.chain.has_block(bytes.fromhex(m['target'])):
                    # Native sync supplies the common history. Missing side
                    # branches are then fetched and fully validated too, so a
                    # late node sees the same conflicting-slot evidence.
                    if key in self.providers and key not in self.support_tasks and self.node.chain._row(self.node.chain.tip_hash)[2]>=m['height']-1:
                        self.support_tasks[key]=self.spawn(self.fetch_support(key,proof))
                    continue
                changed=self.state.add_proof(proof);self.deferred.pop(key,None)
                # A peer can finish its handshake while this node is still
                # downloading a proof's side branch. Its initial inventory
                # then lacks that proof. Announce newly validated attachments
                # again from this now-complete provider so it cannot miss them.
                if changed:self.spawn(self.publish('proof',proof))
            except Exception as error:
                self.metrics['rejected']+=1;self.last_error=str(error);self.deferred.pop(key,None)
        path=self.node.chain._path(self.node.chain.tip_hash);root=self.state.root(path)
        if root is None:return
        if self.state.anchor(path) is None and len(self.contacts)>=3 and root not in self.proposed and time.monotonic()-self.started>2:
            self.proposed.add(root)
            self.spawn(self.publish('dkg',{'context':beacon.context(self.network,root,list(self.contacts.values()))}))
        # Discovery continues regardless of activation, setup and job progress.
        rows=self.node.chain.connection.execute('SELECT hash FROM blocks WHERE height>=? ORDER BY height',(self.state.activation,)).fetchall()
        for (a,) in rows:
            if a in self.jobs:continue
            block=self.node.chain.get_block(a)
            if producer(block)!=self.keys.node_id:continue
            saved=self.keys.get('job:'+a.hex())
            if saved and saved.get('done'):continue
            if self.state.anchor(self.node.chain._path(block.header.previous_hash)) is None:continue
            children=self.node.chain.connection.execute('SELECT hash FROM blocks WHERE parent=? ORDER BY hash',(a,)).fetchall()
            if not children:continue
            # Persist the exact A/B target. A late reply never moves to a later block.
            b=bytes.fromhex(saved['target']) if saved else children[0][0]
            self.jobs[a]=self.spawn(self.link(a,b))
    def pending_candidate(self):return None
    async def close(self):
        self.closed=True;self.parts.close()
        tasks=tuple(self.tasks)
        for task in tasks:task.cancel()
        await asyncio.gather(*tasks,return_exceptions=True)
        self.keys.close()
