"""Shared boundary rules for the PC/Android release candidate.

Only complete signed blocks register connections. The public activation is
9000; historical blocks are never required to acquire retroactive signatures.
No address cache is an eligibility list and no extra approval vote is added.
"""
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache
from hashlib import sha256
import ipaddress
import os
from .boundary_crypto import (BLS, canonical, digest, rawhex, verify_identity, vrf_verify,
                              verify_split, split_signature, valid_bls_membership,
                              valid_bls_signature, valid_bls_aggregate)

ACTIVATION_HEIGHT = 9000
# Transport bounds individual frames, not the number of election respondents.

def require(ok, message):
    if not ok: raise ValueError(message)

def exact(value, names): return type(value) is dict and set(value) == set(names.split())

def network_id(profile):
    return digest({'domain':'sumuww-boundary-network-v1','genesis':profile.genesis.block_hash().hex(),'profile':profile.profile_id})

def draw_input(network, height, parent_hash):
    return {'domain':'sumuww-boundary-draw-v1','network':network,'parentHeight':height,'parentHash':parent_hash,'childHeight':height+1}

def canonical_ip(value):
    address = ipaddress.ip_address(value)
    require('%' not in value, 'Scoped IP is not transferable')
    return str(address.ipv4_mapped) if isinstance(address,ipaddress.IPv6Address) and address.ipv4_mapped else address.exploded

def assignment(ids, ip_sets):
    if len(set(ids)) != len(ids): return None
    used, result = set(), []
    def visit(index):
        if index == len(ids): return True
        for ip in ip_sets.get(ids[index], ()):
            if ip in used: continue
            used.add(ip); result.append({'nodeId':ids[index],'ip':ip})
            if visit(index+1): return True
            result.pop(); used.remove(ip)
        return False
    return result if visit(0) else None

def authenticated(frame, domain):
    require(exact(frame,'payload signature') and type(frame['payload']) is dict, 'Boundary signed frame fields')
    p=frame['payload']
    require(p.get('domain')==domain and verify_identity(p.get('nodeId'),p,frame['signature']), 'Boundary identity signature')
    return p

@lru_cache(maxsize=256)
def _member_cached(encoded):
    import json
    frame=json.loads(encoded)
    p=authenticated(frame,'sumuww-boundary-member-v1')
    require(exact(p,'domain nodeId publicKey pop'),'Boundary member fields')
    pk,pop=rawhex(p['publicKey'],48),rawhex(p['pop'],96)
    require(valid_bls_membership(pk,pop),'Boundary BLS proof of possession')
    return p

def member(frame): return _member_cached(canonical(frame))

def query_context(query, network, height, parent_hash):
    p=authenticated(query,'sumuww-boundary-query-v1')
    require(exact(p,'domain nodeId network parentHeight parentHash nonce') and p['network']==network and
            p['parentHeight']==height and p['parentHash']==parent_hash,'Boundary current query context')
    rawhex(p['nonce'],32)
    return p

def response(frame, query, network, height, parent_hash):
    alpha=canonical(draw_input(network,height,parent_hash))
    return _response(frame,digest(query),alpha,sha256(alpha).hexdigest())


def _response(frame,query_hash,alpha,input_digest):
    encoded=canonical(frame)
    # Reuse only the exact signed response in the exact election context.
    # This stores no caller-owned dictionaries. Large frames remain valid and
    # are checked normally; cache bounds never restrict respondent eligibility.
    if len(encoded)<=8192:
        _response_verified(encoded,query_hash,alpha,input_digest)
        return frame['payload']
    return _validate_response(frame,query_hash,alpha,input_digest)


@lru_cache(maxsize=32768)
def _response_verified(encoded,query_hash,alpha,input_digest):
    import json
    _validate_response(json.loads(encoded),query_hash,alpha,input_digest)


def _validate_response(frame,query_hash,alpha,input_digest):
    p=authenticated(frame,'sumuww-boundary-response-v1')
    require(exact(p,'domain nodeId queryHash revision member ticket neighbors observations') and p['queryHash']==query_hash and
            type(p['revision']) is int and 0<=p['revision']<2**32,'Boundary response query')
    m=member(p['member']); require(m['nodeId']==p['nodeId'],'Boundary response key binding')
    ticket=p['ticket']; require(exact(ticket,'id inputDigest proof output') and ticket['id']==p['nodeId'],'Boundary ticket identity')
    require(ticket['inputDigest']==input_digest,'Boundary seed context')
    require(vrf_verify(rawhex(p['nodeId'],32),rawhex(ticket['proof'],80),alpha)==rawhex(ticket['output'],64),'Boundary ECVRF output')
    peers=p['neighbors']; require(type(peers) is list and peers==sorted(set(peers)) and p['nodeId'] not in peers,'Boundary neighbor records')
    require(type(p['observations']) is list and [e['nodeId'] for e in p['observations']]==peers,'Boundary socket observation set')
    for observation in p['observations']:
        require(exact(observation,'nodeId ips') and type(observation['ips']) is list and observation['ips'] and
                observation['ips']==sorted(set(observation['ips'])),'Boundary socket observations')
        for ip in observation['ips']: require(canonical_ip(ip)==ip,'Noncanonical socket IP')
        rawhex(observation['nodeId'],32)
    return p

def _response_batch(frames,query_hash,alpha,input_digest):
    results=[]
    for frame in frames:
        try:results.append((_response(frame,query_hash,alpha,input_digest),None))
        except Exception as error:
            results.append((None,error));break
    return results


def _validated_responses(frames,query_hash,alpha,input_digest):
    # Independent cryptography only. Graph/election checks and all SQLite
    # operations stay on the calling actor, in the original response order.
    workers=min(4,os.cpu_count() or 1)
    if len(frames)<512 or workers==1:
        for frame in frames:yield _response(frame,query_hash,alpha,input_digest)
        return
    executor=ThreadPoolExecutor(max_workers=workers,thread_name_prefix='boundary-check')
    try:
        chunks=(frames[i:i+64] for i in range(0,len(frames),64))
        def verify(chunk):return _response_batch(chunk,query_hash,alpha,input_digest)
        for results in executor.map(verify,chunks):
            for result,error in results:
                if error is not None:raise error
                yield result
    finally:
        executor.shutdown(wait=True,cancel_futures=True)


def snapshot(bundle,network,height,parent_hash):
    require(exact(bundle,'query responses') and type(bundle['responses']) is list and 3<=len(bundle['responses']),'Boundary response scope')
    query_context(bundle['query'],network,height,parent_hash)
    query_hash=digest(bundle['query'])
    alpha=canonical(draw_input(network,height,parent_hash)); input_digest=sha256(alpha).hexdigest()
    records=OrderedDict()
    validated=_validated_responses(bundle['responses'],query_hash,alpha,input_digest)
    try:
        for p in validated:
            require(p['nodeId'] not in records,'Duplicate responding identity'); records[p['nodeId']]=p
    finally:validated.close()
    require(list(records)==sorted(records),'Boundary response ordering')
    require(bundle['query']['payload']['nodeId'] in records,'Missing discovery requester response')
    ips={node:set() for node in records}
    for node,p in records.items():
        for peer in p['neighbors']:
            require(peer in records and node in records[peer]['neighbors'],'Boundary reported component still responding')
        for observed in p['observations']: ips[observed['nodeId']].update(observed['ips'])
    pending=[next(iter(records))]; seen=set()
    while pending:
        node=pending.pop()
        if node in seen: continue
        seen.add(node); pending.extend(records[node]['neighbors'])
    require(len(seen)==len(records),'Disconnected response groups')
    ips={node:sorted(values) for node,values in ips.items()}
    require(all(ips.values()),'Missing actual observed IP')
    ordered=sorted(records, key=lambda node:(records[node]['ticket']['output'],node))
    team=[]
    for node in ordered:
        if assignment(team+[node],ips): team.append(node)
        if len(team)==3: break
    require(len(team)==3,'Three distinct responding IPs required')
    return {'team':team,'records':records,'ips':ips}

def candidate_message(network,block_hash,start,bundle,m):
    return _candidate_message(network,block_hash,digest(start),digest(bundle),m)


def _candidate_message(network,block_hash,start_hash,election_hash,m):
    return bytes.fromhex(digest({'domain':'sumuww-completed-boundary-signature-v1','network':network,
        'blockHash':block_hash,'startHash':start_hash,'electionHash':election_hash,'nodeId':m['nodeId'],'publicKey':m['publicKey']}))

def replacement_choice(network,height,parent_hash,state,eligible):
    from hashlib import sha256
    ids=sorted(set(eligible)); require(ids,'No current eligible replacement')
    transcript={'domain':'sumuww-boundary-random-replacement-v1','seed':digest(draw_input(network,height,parent_hash)),
                'state':state,'eligible':ids}
    size=2**256; limit=size-size%len(ids)
    for expansion in range(1024):
        h=sha256(canonical({'transcript':transcript,'expansion':expansion})).hexdigest(); number=int(h,16)
        if number<limit: return {'id':ids[number%len(ids)],'eligible':ids,'drawDigest':h}
    raise ValueError('Replacement random expansion exhausted')

def verify_ready(frame,block_hash,bundle):
    p=authenticated(frame,'sumuww-boundary-ready-v1')
    require(exact(p,'domain nodeId blockHash bundleHash challenge') and p['blockHash']==block_hash and p['bundleHash']==digest(bundle),'Boundary current ready response')
    rawhex(p['challenge'],32); return p['nodeId']

def replay(network,height,parent_hash,block_hash,start,bundle,events,aggregate=None):
    view=snapshot(bundle,network,height-1,parent_hash)
    team=list(view['team']); evicted=[]; completed=OrderedDict(); draws=[]
    prepared=None
    def signed_message(m):
        nonlocal prepared
        if prepared is None:prepared=(digest(start),digest(bundle))
        return _candidate_message(network,block_hash,*prepared,m)
    # Replacement never reuses an evicted identity; derive the event bound
    # from the actual response set rather than a fixed participation cutoff.
    require(type(events) is list and len(events)<=len(view['records']),'Boundary event limit')
    for event in events:
        require(type(event) is dict,'Boundary event')
        if event.get('type')=='signature':
            require(exact(event,'type member' if aggregate else 'type member signature'),'Boundary signature event fields')
            m=member(event['member']); node=m['nodeId']
            require(node in team and node not in evicted and node not in completed and
                    event['member']==view['records'][node]['member'],'Boundary current selected signer')
            if not aggregate: require(valid_bls_signature(rawhex(m['publicKey'],48),signed_message(m),rawhex(event['signature'],96)),'Invalid boundary signature')
            completed[node]=event['member']
        elif event.get('type')=='replace':
            require(exact(event,'type observation ready'),'Boundary replacement fields')
            p=authenticated(event['observation'],'sumuww-boundary-replacement-v1')
            require(exact(p,'domain nodeId blockHash bundleHash slot from cause') and
                    p['nodeId']==bundle['query']['payload']['nodeId'] and p['blockHash']==block_hash and p['bundleHash']==digest(bundle) and
                    type(p['slot']) is int and 0<=p['slot']<3 and team[p['slot']]==p['from'] and p['from'] not in completed and
                    p['cause'] in ('NO_REPLY','SOCKET_CLOSED','UNUSABLE_REPLY'),'Boundary replacement context')
            require(type(event['ready']) is list and len(event['ready'])<=len(view['records']),'Boundary current replacement responses')
            ready=[verify_ready(r,block_hash,bundle) for r in event['ready']]
            require(len(ready)==len(set(ready)) and set(ready)<=set(view['records']),'Boundary current replacement responders')
            evicted.append(p['from'])
            eligible=[node for node in ready if node not in team and node not in evicted and
                      assignment([node if i==p['slot'] else old for i,old in enumerate(team)],view['ips'])]
            draw=replacement_choice(network,height-1,parent_hash,{'slot':p['slot'],'team':team,'evicted':evicted,'history':digest(draws)},eligible)
            team[p['slot']]=draw['id']; draws.append({'slot':p['slot'],'from':p['from'],**draw})
        else: raise ValueError('Unknown boundary event')
    if aggregate:
        require(len(completed)==3,'Three complete signatures required')
        members=[member(m) for m in completed.values()]
        require(len({m['publicKey'] for m in members})==3,'Duplicate BLS signer key')
        require(valid_bls_aggregate(tuple(rawhex(m['publicKey'],48) for m in members),
            tuple(signed_message(m) for m in members),rawhex(aggregate,96)), 'Invalid boundary aggregate')
    return {**view,'team':team,'completed':completed,'missing':[n for n in team if n not in completed],'draws':draws}

def certificate(network,height,parent_hash,block_hash,start,bundle,events):
    state=replay(network,height,parent_hash,block_hash,start,bundle,events)
    require(not state['missing'],'Incomplete boundary signatures')
    aggregate=BLS.Aggregate([rawhex(e['signature'],96) for e in events if e['type']=='signature']).hex()
    result={'domain':'sumuww-completed-boundary-certificate-v1','network':network,'blockHash':block_hash,'startHash':digest(start),
            'bundle':bundle,'events':[{k:v for k,v in e.items() if k!='signature'} if e['type']=='signature' else e for e in events],'aggregate':aggregate}
    verify_certificate(network,height,parent_hash,block_hash,start,result)
    return result

def verify_certificate(network,height,parent_hash,block_hash,start,cert):
    require(exact(cert,'domain network blockHash startHash bundle events aggregate') and cert['domain']=='sumuww-completed-boundary-certificate-v1' and
            cert['network']==network and cert['blockHash']==block_hash and cert['startHash']==digest(start),'Boundary certificate context')
    return replay(network,height,parent_hash,block_hash,start,cert['bundle'],cert['events'],cert['aggregate'])

def next_start(parent_hash,parent_certificate):
    a,b=split_signature(rawhex(parent_certificate['aggregate'],96))
    return {'domain':'sumuww-completed-boundary-start-v1','parentHash':parent_hash,
            'parentCertificateHash':digest(parent_certificate),'partA':a.hex(),'partB':b.hex()}

def verify_start(parent_hash,parent_certificate,start):
    require(exact(start,'domain parentHash parentCertificateHash partA partB') and
            start['domain']=='sumuww-completed-boundary-start-v1' and start['parentHash']==parent_hash and
            start['parentCertificateHash']==digest(parent_certificate),'Boundary split context')
    require(verify_split(rawhex(parent_certificate['aggregate'],96),rawhex(start['partA'],96),rawhex(start['partB'],96)),'Boundary split reconstruction')
