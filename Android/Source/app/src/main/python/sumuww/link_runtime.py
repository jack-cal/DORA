"""Nonblocking connection proof jobs on the existing PC/Android TCP transport."""
import asyncio
import json
import secrets
import time
from collections import OrderedDict
from cryptography.exceptions import InvalidSignature
from .link_crypto import (POLICY,Identity,canonical,digest,require,verify_frame,producer,
                         message,slot,sample,compress,verify,proof_selected,PROOF_SELECTION_DENOMINATOR)
from . import link_beacon as beacon
from .boundary_transport import PartReceiver
from .link_recovery import BeaconRecovery
from . import link_selection as selection

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
        self.selection_votes=set()
        self.tasks=set();self.jobs={};self.retry_after={};self.tick=None;self.started=time.monotonic();self.last_error=None
        self.proposed=set();self.omit_beacon=False;self.omit_witness=False;self.signature_delay=0
        self.omit_dkg=False;self.omit_dkg_probe=False;self.recovery=BeaconRecovery(self)
        self.metrics={'completed':0,'rejected':0,'skipped':0,'pending':0,'lotteries':[]}
        self._job_count_cache=None
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
                'completed_links':self.metrics['completed'],'beacon_recovery':self.recovery.info(),
                'selection_activation_height':self.state.selection_activation,
                'selection_upgrade_active':self.state.selection_required(self.node.chain._row(self.node.chain.tip_hash)[2]),
                'stored_complete_proofs':self.node.chain.connection.execute('SELECT COUNT(*) FROM link_proofs').fetchone()[0],
                'lottery_jobs':self.job_counts()}

    def job_counts(self):
        """Do not confuse a nonselected finished lottery with a complete proof."""
        token=self.keys.db.total_changes
        if self._job_count_cache is not None and self._job_count_cache[0]==token:
            return dict(self._job_count_cache[1])
        counts={'total':0,'not_selected':0,'awaiting_lottery':0,'selected_pending':0,'selected_complete':0}
        for done,selected in self.keys.db.execute("SELECT json_extract(value,'$.done'),json_type(value,'$.message') FROM link_private WHERE name GLOB 'job:*'"):
            counts['total']+=1
            counts[('selected_complete' if done else 'selected_pending') if selected=='object' else
                   ('not_selected' if done else 'awaiting_lottery')]+=1
        self._job_count_cache=(token,counts)
        return dict(counts)

    def job_details(self,limit=100):
        """Public progress only: never export signatures, contacts or key material."""
        rows=[]
        for name,value in self.keys.db.execute("SELECT name,value FROM link_private WHERE name GLOB 'job:*' AND COALESCE(json_extract(value,'$.done'),0)=0"):
            saved=json.loads(value)
            try:height=self.node.chain._row(bytes.fromhex(name[4:]))[2]
            except (KeyError,ValueError):continue
            rows.append({'height':height,'phase':saved.get('phase','participants'),
                         'received':len(saved.get('pieces',{})),
                         'candidates':saved.get('responsive_candidates',0),
                         'approvals':saved.get('approvals',0),'required_approvals':saved.get('required_approvals',0),
                         'attempts':saved.get('attempts',0),'last_attempt':saved.get('last_attempt'),
                         'last_progress':saved.get('last_progress'),'next_retry':saved.get('next_retry'),
                         'last_error':saved.get('last_error')})
        return sorted(rows,key=lambda r:r['height'],reverse=True)[:max(0,min(100,int(limit)))]

    async def responsive_candidates(self):
        """Probe the entire discovery inventory through relays, before sampling.

        A failed probe does not delete a contact or restrict future discovery.
        The existing signed nonce echo works with previous v2 peers as well.
        These are local availability observations, not consensus membership.
        """
        candidates=tuple(sorted(self.contacts));nonce=secrets.token_hex(32)
        async def probe(node_id):
            try:
                response=await self.request(node_id,'dkg_probe',{'nonce':nonce})
                return node_id if response==nonce else None
            except (ValueError,TimeoutError,OSError):return None
        responses=await asyncio.gather(*(probe(i) for i in candidates))
        return [i for i in responses if i is not None]

    async def activity_records(self,ctx):
        async def probe(node_id):
            try:
                record=await self.request(node_id,'link_activity',ctx)
                require(selection.check_activity(record,ctx)==node_id,'Activity responder identity')
                return record
            except (ValueError,TimeoutError,OSError,KeyError,InvalidSignature):return None
        values=await asyncio.gather(*(probe(i) for i in tuple(sorted(self.contacts))))
        return [v for v in values if v is not None]

    async def candidate_certificate(self,a,b,progress=None):
        ctx=selection.context(self.state,a,b,self.node.chain.tip_hash,secrets.token_hex(32))
        if progress:progress('activity',{})
        records=await self.activity_records(ctx)
        proposed=selection.proposal(ctx,records)
        ids,electorate=selection.check_proposal(self.state,proposed,fresh=True)
        if progress:progress('candidate_quorum',{'responsive_candidates':len(ids),'approvals':0,'required_approvals':beacon.quorum(len(electorate))})
        async def approve(node_id):
            try:return await self.request(node_id,'link_candidates',proposed,timeout=45)
            except (ValueError,TimeoutError,OSError,KeyError,InvalidSignature):return None
        votes=await asyncio.gather(*(approve(i) for i in electorate))
        approvals=sorted((v for v in votes if v is not None),key=lambda v:v['payload']['nodeId'])
        if progress:progress('candidate_quorum',{'approvals':len(approvals)})
        return {'proposal':proposed,'approvals':approvals}
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
        # Page the entire inventory; byte budgets never truncate candidates.
        page={'contacts':[],'proofs':[]};size=0
        for kind,values in (('contacts',tuple(self.contacts.values())),('proofs',self.state.all_proofs())):
            for value in values:
                amount=len(canonical(value))
                if size and size+amount>256*1024:
                    await self.node._send(session,'bcall',canonical(self.frame('sync',page)))
                    page={'contacts':[],'proofs':[]};size=0
                page[kind].append(value);size+=amount
        if size:await self.node._send(session,'bcall',canonical(self.frame('sync',page)))
        # DKG messages are public commitments/encrypted shares, never private
        # key material. Replay them to a peer which missed the initial gossip.
        path=self.node.chain._path(self.node.chain.tip_hash)
        for row in tuple(self.contexts.values()):
            try:self.state.check_setup_context(row['context'],path)
            except (ValueError,KeyError,TypeError):continue
            for kind in ('deal','ready'):
                for value in tuple(row[kind+'s' if kind=='deal' else 'ready'].values()):
                    await self.node._send(session,'bcall',canonical(self.frame('dkg',{'context':row['context'],kind:value})))
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
            self.state.check_setup_context(ctx,self.node.chain._path(self.node.chain.tip_hash))
            for c in ctx['members']:self.add_contact(c)
            cid=digest(ctx);row=self.contexts.setdefault(cid,{'context':ctx,'deals':{},'ready':{},'dealing':False,'recovering':False})
            if 'deal' in body:
                await asyncio.to_thread(beacon.verify_deal,ctx,body['deal'])
                dealer=body['deal']['payload']['nodeId'];old=row['deals'].get(dealer)
                require(old in (None,body['deal']),'Conflicting DKG contribution');row['deals'][dealer]=body['deal']
            if 'ready' in body:
                r=verify_frame(body['ready']);require(r['nodeId'] in ids and r['domain']=='sumuww-dkg-ready-v1','Invalid ready identity')
                row['ready'][r['nodeId']]=body['ready']
            if self.keys.node_id in ids and not row['dealing'] and not self.omit_dkg:
                row['dealing']=True;self.spawn(self.deal(row))
            if len(row['deals'])==len(ids) and not row['recovering'] and not self.omit_dkg:
                row['recovering']=True;self.spawn(self.ready(row))
            self.spawn(self.try_setup(row))
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
        try:ready=await self.crypto(beacon.recover,m)
        except beacon.InvalidDealer as error:
            # Only this recipient's own authenticated failure affects its next
            # proposal. Unproved third-party accusations never remove contacts.
            self.recovery.excluded[error.dealer]=time.monotonic()+self.recovery.cooldown
            self.recovery.active=None;self.recovery.next_check=0
            return
        await self.publish('dkg',{'context':row['context'],'ready':ready})
    async def try_setup(self,row):
        if row.get('checking'):return
        ids=beacon.check_context(row['context'])
        if len(row['deals'])!=len(ids) or len(row['ready'])<beacon.quorum(len(ids)):return
        m=beacon.manifest(row['context'],list(row['deals'].values()))
        ready=[r for _,r in sorted(row['ready'].items()) if r['payload']['manifest']==digest(m)]
        if len(ready)<beacon.quorum(len(ids)):return
        setup={'manifest':m,'ready':ready};row['checking']=True
        try:await asyncio.to_thread(beacon.verify_setup,setup)
        finally:row['checking']=False
        path=self.node.chain._path(self.node.chain.tip_hash)
        try:self.state.check_setup_context(row['context'],path)
        except ValueError:return # Completed after a different generation won PoW.
        if any(self.recovery.excluded.get(i,0)>time.monotonic() for i in ids):return
        current=self.state.prepared_setup(path)
        def rank(candidate):
            ctx=candidate['manifest']['context']
            height=self.node.chain._row(bytes.fromhex(ctx['round']))[2] if 'round' in ctx else -1
            return height,len(ctx['members']),digest(candidate['manifest'])
        if current is None or rank(setup)>rank(current):
            self.state.set_local('ready_setup',setup)
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
        if (method in ('beacon','beacon_health') and self.omit_beacon) or (method in ('sign','link_activity') and self.omit_witness) or (method in ('dkg_probe','selection_probe') and self.omit_dkg_probe):return
        try:
            if self.signature_delay and method in ('sign','beacon'):await asyncio.sleep(self.signature_delay)
            if method=='dkg_probe':
                from .link_crypto import raw
                raw(body['nonce'],32);value=body['nonce']
            elif method=='selection_probe':
                from .link_crypto import raw
                raw(body['nonce'],32)
                value={'nonce':body['nonce'],'policy':selection.SELECTION_POLICY,'activation_height':selection.PUBLIC_ACTIVATION_HEIGHT}
            elif method=='link_activity':
                require(self.state.selection_required(self.node.chain._row(self.node.chain.tip_hash)[2]),'Certified selection upgrade is not activated')
                electorate=selection.check_context(self.state,body,fresh=True)
                author=producer(self.node.chain.get_block(bytes.fromhex(body['source'])))
                require(request['requester']==author or request['requester'] in electorate,'Activity requester is not a producer or anchored voter')
                value=selection.activity(self.keys,body,self.contact)
            elif method=='link_candidates':
                require(self.state.selection_required(self.node.chain._row(self.node.chain.tip_hash)[2]),'Certified selection upgrade is not activated')
                ids,electorate=selection.check_proposal(self.state,body,fresh=True)
                author=producer(self.node.chain.get_block(bytes.fromhex(body['context']['source'])))
                require(request['requester']==author,'Candidate proposal must be signed by the source producer')
                require(self.keys.node_id in electorate,'Not an anchored selection voter')
                for record in body['responders']:self.add_contact(record['contact'])
                # Independently query the entire discovered inventory. A
                # producer cannot get an honest vote for a chosen subset.
                edge=(body['context']['source'],body['context']['target'])
                require(edge not in self.selection_votes and len(self.selection_votes)<8,'Candidate observation is busy; retry later')
                self.selection_votes.add(edge)
                try:
                    observed=await self.activity_records(body['context'])
                    responsive=sorted(selection.check_activity(r,body['context']) for r in observed)
                    require(responsive==ids,'Candidate set differs from independently observed active nodes')
                    value=selection.vote(self.keys,body)
                finally:self.selection_votes.discard(edge)
            elif method=='beacon_health':
                from .link_crypto import block_beacon,raw
                raw(body['nonce'],32)
                anchor=bytes.fromhex(body['anchor']);setup=block_beacon(self.node.chain.get_block(anchor))
                require(setup is not None,'Health anchor is not a beacon block')
                challenge=digest(['SUMUWW-BEACON-HEALTH',self.network,body['anchor'],body['nonce']])
                value=await self.crypto(beacon.partial,setup,challenge)
            elif method=='block':
                value=self.node.chain.get_block(bytes.fromhex(body['hash'])).serialize().hex()
            elif method=='beacon':
                a=bytes.fromhex(body['source']);row=self.node.chain._row(a);found=self.state.anchor(self.node.chain._path(row[1]))
                require(found is not None,'Beacon not anchored')
                expected=slot(self.network,row[2],row[1].hex());require(body['slot']==expected,'Beacon slot mismatch')
                value=await self.crypto(beacon.partial,found[1],expected)
            elif method=='sign':
                certificate=body.get('selection') if 'message' in body else None
                m=body['message'] if 'message' in body else body
                ar=self.node.chain._row(bytes.fromhex(m['source']));br=self.node.chain._row(bytes.fromhex(m['target']))
                require(self.state.enabled(ar[2]) and br[1]==ar[0] and producer(self.node.chain.get_block(ar[0]))==request['requester'],'Signature source producer mismatch')
                require(len(m['signers'])==3 and len(set(m['signers']))==3 and self.keys.node_id in m['signers'],'Signature team')
                found=self.state.anchor(self.node.chain._path(ar[1]));require(found is not None,'Beacon missing')
                expected=slot(self.network,ar[2],ar[1].hex());random=await asyncio.to_thread(beacon.verify_beacon,found[1],expected,m['beacon'])
                selection_id=None
                if certificate is not None:
                    require(self.state.selection_required(self.node.chain._row(self.node.chain.tip_hash)[2]),'Certified selection upgrade is not activated')
                    require(selection.verify_certificate(self.state,certificate,random,fresh=True)==m['signers'],'Wrong certified witnesses')
                    ctx=certificate['proposal']['context']
                    require(ctx['source']==m['source'] and ctx['target']==m['target'],'Selection connection mismatch')
                    selection_id=digest(certificate)
                else:require(not self.state.selection_required(ar[2]),'Active candidate certificate is required')
                require(proof_selected(random) and m==message(self.network,ar[0].hex(),br[0].hex(),ar[2],ar[1].hex(),m['signers'],m['beacon'],selection_id),'Unselected or mismatched signature request')
                lock=selection.witness_lock(m) if certificate is not None else expected
                signature=bytes.fromhex(self.keys.sign_once(lock,m));value={'left':signature[:32].hex(),'right':signature[32:].hex()}
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
                if 'selection' in body:
                    require(self.state.selection_required(self.node.chain._row(self.node.chain.tip_hash)[2]),'Certified selection upgrade is not activated')
                    ar=self.node.chain._row(a.block_hash());found=self.state.anchor(self.node.chain._path(ar[1]))
                    random=beacon.verify_beacon(found[1],slot(self.network,ar[2],ar[1].hex()),m['beacon'])
                    require(selection.verify_certificate(self.state,body['selection'],random,fresh=True)==m['signers'],'Wrong attachment candidate selection')
                    ctx=body['selection']['proposal']['context']
                    require(ctx['source']==m['source'] and ctx['target']==m['target'] and m.get('selection')==digest(body['selection']),'Attachment selection binding')
                else:require(not self.state.selection_required(m['height']),'Active candidate certificate is required')
                value=self.keys.sign({'domain':'sumuww-target-attachment-v1','source_attachment':digest(source_body),'source_receipt':body['source_receipt']})
            else:raise ValueError('Unknown link request method')
            reply={'request':key,'ok':True,'value':value}
        except Exception as error:reply={'request':key,'ok':False,'error':str(error)}
        await self.publish('reply',reply)
    async def obtain_beacon(self,a,setup,s):
        ids=beacon.check_context(setup['manifest']['context']);needed=beacon.threshold(len(ids))
        async def response(i):
            value=await self.request(i,'beacon',{'source':a,'slot':s})
            require(value['nodeId']==i,'Beacon responder identity mismatch')
            return value
        tasks=[asyncio.create_task(response(i)) for i in ids];partials=[]
        try:
            for task in asyncio.as_completed(tasks):
                try:
                    value=await task;await asyncio.to_thread(beacon.verify_partial,setup,s,value);partials.append(value)
                    if len(partials)>=needed:return await asyncio.to_thread(beacon.combine,setup,s,partials)
                except Exception:continue
            found=self.state.anchor(self.node.chain._path(self.node.chain._row(bytes.fromhex(a))[1]))
            self.recovery.failure(found[0],set(ids)-{v['nodeId'] for v in partials})
            raise ValueError('Insufficient valid beacon responses; mining continues')
        finally:
            for task in tasks:task.cancel()
            await asyncio.gather(*tasks,return_exceptions=True)
    async def link(self,a,b):
        ar=self.node.chain._row(a);found=self.state.anchor(self.node.chain._path(ar[1]));setup=found[1]
        saved=self.keys.get('job:'+a.hex()) or {'target':b.hex()};self.keys.put('job:'+a.hex(),saved)
        b=bytes.fromhex(saved['target'])
        if saved.get('done'):return
        def persist(phase=None):
            if phase is not None:saved['phase']=phase
            self.keys.put('job:'+a.hex(),saved)
        saved['attempts']=saved.get('attempts',0)+1
        saved['last_attempt']=int(time.time())
        try:
            if 'message' not in saved:
                persist('participants')
                candidates=await self.responsive_candidates()
                saved['responsive_candidates']=len(candidates)
                require(len(candidates)>=3,'Fewer than three discovered participants replied; mining continues')
                saved['candidates']=candidates;persist('beacon')
                s=slot(self.network,ar[2],ar[1].hex());signature=await self.obtain_beacon(a.hex(),setup,s)
                random=beacon.verify_beacon(setup,s,signature)
                if not proof_selected(random):
                    saved['done']=True;persist('not_selected');self.metrics['skipped']+=1;return
                signers=sample(random,candidates)
                saved['message']=message(self.network,a.hex(),b.hex(),ar[2],ar[1].hex(),signers,signature)
                persist('witnesses')
                self.metrics['lotteries'].append({'source':a.hex(),'candidate_count':len(candidates),'signers':signers})
            strict=(self.state.selection_required(ar[2]) or
                    self.state.selection_required(self.node.chain._row(self.node.chain.tip_hash)[2]) or
                    'selection' in saved.get('message',{}))
            if strict:
                current=saved.get('selection')
                if current is not None:
                    try:selection.check_context(self.state,current['proposal']['context'],fresh=True)
                    except (ValueError,KeyError):current=None
                if current is None or saved.get('renew_selection'):
                    def progress(phase,values):
                        saved.update(values);persist(phase)
                    certificate=await self.candidate_certificate(a,b,progress)
                    signature=saved['message']['beacon']
                    random=beacon.verify_beacon(setup,slot(self.network,ar[2],ar[1].hex()),signature)
                    signers=selection.verify_certificate(self.state,certificate,random,fresh=True)
                    old=saved['message']
                    self.keys.put('job-round:'+a.hex()+':'+digest(old),
                                  {'message':old,'pieces':saved.get('pieces',{}),'last_error':saved.get('last_error')})
                    saved['message']=message(self.network,a.hex(),b.hex(),ar[2],ar[1].hex(),signers,signature,digest(certificate))
                    saved['selection']=certificate;saved['pieces']={};saved['renew_selection']=False
                    saved['candidates']=[r['response']['payload']['nodeId'] for r in certificate['proposal']['responders']]
                    saved['responsive_candidates']=len(saved['candidates']);persist('witnesses')
            m=saved['message']
            # Keep legacy A/B/team messages intact. Never erase a signature lock
            # or silently ask a witness to sign another message for the slot.
            def validate_piece(signer,piece):
                require(type(piece) is dict and set(piece)=={'left','right'},'Invalid witness response')
                left=bytes.fromhex(piece['left']);right=bytes.fromhex(piece['right'])
                require(len(left)==32 and len(right)==32,'Invalid witness signature halves')
                verify(signer,m,(left+right).hex())
            pieces={}
            for signer,piece in saved.get('pieces',{}).items():
                if signer not in m['signers']:continue
                try:validate_piece(signer,piece)
                except (ValueError,TypeError,KeyError,InvalidSignature):continue
                pieces[signer]=piece
            saved['pieces']=pieces;persist('witnesses')
            missing=[i for i in m['signers'] if i not in pieces]
            errors={}
            async def collect(signer):
                try:
                    request={'message':m,'selection':saved['selection']} if 'selection' in m else m
                    piece=await self.request(signer,'sign',request)
                    validate_piece(signer,piece)
                    pieces[signer]=piece
                    saved['last_progress']=int(time.time());saved['failures']=0
                    persist() # Retain each valid reply, even if others fail.
                except Exception as error:
                    errors[signer]=str(error) or type(error).__name__
            await asyncio.gather(*(collect(i) for i in missing))
            saved['waiting_for']=[i for i in m['signers'] if i not in pieces]
            saved['witness_errors']=errors
            if saved['waiting_for'] and strict:saved['renew_selection']=True
            require(not saved['waiting_for'],f"Waiting for {len(saved['waiting_for'])} of 3 original witnesses; valid replies are saved")
            ordered=[pieces[i] for i in m['signers']]
            proof={'message':m,'left':compress(b''.join(bytes.fromhex(p['left']) for p in ordered)),
                   'right':compress(b''.join(bytes.fromhex(p['right']) for p in ordered))}
            source_body={'domain':'sumuww-source-attachment-v1',**proof}
            proof['source_receipt']=self.keys.sign(source_body)
            if 'selection' in m:proof['selection']=saved['selection']
            persist('target_receipt')
            proof['target_receipt']=await self.request(producer(self.node.chain.get_block(b)),'attach',proof)
            persist('verification')
            self.state.add_proof(proof);saved['done']=True;saved['last_error']=None;saved['failures']=0;persist('complete')
            self.metrics['completed']+=1;await self.publish('proof',proof)
        except Exception as error:
            saved['last_error']=str(error) or type(error).__name__;saved['failures']=saved.get('failures',0)+1;persist()
            raise
        finally:
            self.jobs.pop(a,None)
            delay=min(900,30*2**min(saved.get('failures',0),5))
            saved['next_retry']=None if saved.get('done') else int(time.time()+delay);persist()
            self.retry_after[a]=time.monotonic()+delay
    async def refresh(self):
        if self.closed:return
        if self.tick is None or self.tick.done():self.tick=self.spawn(self.background())
    async def fetch_support(self,key,proof):
        from .block import Block
        try:
            target=bytes.fromhex(proof['selection']['proposal']['context']['round'] if 'selection' in proof else proof['message']['target']);pending=[];seen=set()
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
            await asyncio.sleep(0)
            m=proof.get('message',{})
            try:
                required=[m['source'],m['target']]
                if 'selection' in proof:required.append(proof['selection']['proposal']['context']['round'])
                if any(not self.node.chain.has_block(bytes.fromhex(h)) for h in required):
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
        self.recovery.schedule(path)
        # Discovery continues regardless of activation, setup and job progress.
        rows=self.node.chain.connection.execute('SELECT hash FROM blocks WHERE height>=? ORDER BY height',(self.state.activation,)).fetchall()
        for (a,) in rows:
            # Let TCP readers, keepalives and mining control run between jobs.
            await asyncio.sleep(0)
            if a in self.jobs or time.monotonic()<self.retry_after.get(a,0):continue
            block=self.node.chain.get_block(a)
            if producer(block)!=self.keys.node_id:continue
            saved=self.keys.get('job:'+a.hex())
            if saved and saved.get('done'):continue
            if saved and (saved.get('next_retry') or 0)>time.time():continue
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
