"""Feldman DKG and unique threshold BLS for the height-9000 attachment engine.

The completed public setup is committed inside an ordinary PoW coinbase before
it can authorize a link. No new genesis or trusted randomness server is used.
This experimental DKG is not an audited, production beacon implementation.
"""
from functools import lru_cache
from hashlib import sha256
import secrets
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PublicKey
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from py_ecc.bls import G2ProofOfPossession as BLS
from py_ecc.bls.g2_primitives import pubkey_to_G1,G1_to_pubkey,signature_to_G2,G2_to_signature,subgroup_check
from py_ecc.optimized_bls12_381 import G1,Z1,Z2,add,multiply,curve_order as Q,is_inf,eq
from .link_crypto import canonical,digest,raw,require,verify_frame

# Consensus spacing between key generations, not a witness/candidate limit.
# Recovery runs in the background; no block is required to include a setup.
MIN_GENERATION_BLOCKS = 12
RECOVERY_DOMAIN = 'sumuww-dkg-recovery-v1'
NO_PREVIOUS = '00'*32

class InvalidDealer(ValueError):
    """A recipient could not authenticate or verify this dealer's own share."""
    def __init__(self,dealer):
        self.dealer=dealer
        super().__init__('Invalid encrypted DKG share from '+dealer)

def threshold(n): return max(2,(n-1)//3+1)
def quorum(n): return (2*n)//3+1
def scalar(): return secrets.randbelow(Q-1)+1
def public(s): return G1_to_pubkey(multiply(G1,s)).hex()
def evaluate(coefficients,x):
    value=0
    for coefficient in reversed(coefficients):value=(value*x+coefficient)%Q
    return value
def point(encoded):
    p=pubkey_to_G1(raw(encoded,48));require(not is_inf(p) and subgroup_check(p),'Invalid beacon G1');return p
def evaluate_public(commitments,x):
    p=Z1
    for c in reversed(commitments):p=add(multiply(p,x),point(c))
    return p
def context(network,root,members):
    return {'domain':'sumuww-dkg-9000-v1','network':network,'root':root,
            'members':sorted(members,key=lambda m:m['payload']['nodeId'])}
def recovery_context(network,root,members,previous,round_hash):
    ctx=context(network,root,members)
    ctx.update(domain=RECOVERY_DOMAIN,previous=previous,round=round_hash)
    return ctx
def check_context(ctx):
    if ctx.get('domain')==RECOVERY_DOMAIN:
        require(set(ctx)=={'domain','network','root','members','previous','round'},'Recovery context fields')
        raw(ctx['previous'],32);raw(ctx['round'],32)
    else:
        require(set(ctx)=={'domain','network','root','members'} and ctx['domain']=='sumuww-dkg-9000-v1','DKG context')
    raw(ctx['network'],32);raw(ctx['root'],32)
    require(type(ctx['members']) is list and len(ctx['members'])>=3,'DKG needs at least three identities')
    ids=[]
    for member in ctx['members']:
        p=verify_frame(member)
        require(set(p)=={'domain','network','nodeId','encryption'} and p['domain']=='sumuww-link-contact-v1' and p['network']==ctx['network'],'DKG member context')
        raw(p['nodeId'],32);raw(p['encryption'],32);ids.append(p['nodeId'])
    require(ids==sorted(set(ids)),'DKG duplicate or unsorted member')
    return ids
def make_deal(identity,ctx):
    ids=check_context(ctx);key=digest(ctx);require(identity.node_id in ids,'Not a DKG participant')
    stored=identity.get('dkg:'+key)
    if stored:return stored['deal']
    coefficients=[scalar() for _ in range(threshold(len(ids)))]
    body={'context':key,'nodeId':identity.node_id,'commitments':[public(c) for c in coefficients]}
    pop=BLS.Sign(coefficients[0],canonical(body)).hex()
    encrypted=[]
    for i,member in enumerate(ctx['members'],1):
        p=member['payload'];aad=canonical([key,identity.node_id,p['nodeId']])
        shared=identity.encryption.exchange(X25519PublicKey.from_public_bytes(raw(p['encryption'],32)))
        encryption_key=sha256(b'SUMUWW-DKG-9000'+shared+aad).digest();nonce=secrets.token_bytes(12)
        ciphertext=AESGCM(encryption_key).encrypt(nonce,evaluate(coefficients,i).to_bytes(32,'big'),aad)
        encrypted.append({'recipient':p['nodeId'],'nonce':nonce.hex(),'ciphertext':ciphertext.hex()})
    deal=identity.signed({'domain':'sumuww-dkg-deal-v1','nodeId':identity.node_id,'body':body,'pop':pop,'encrypted':encrypted})
    identity.put('dkg:'+key,{'deal':deal})
    return deal

@lru_cache(maxsize=256)
def _verify_deal(encoded_context,encoded_deal):
    import json
    ctx=json.loads(encoded_context);deal=json.loads(encoded_deal);ids=check_context(ctx);p=verify_frame(deal);b=p['body']
    require(set(p)=={'domain','nodeId','body','pop','encrypted'} and p['domain']=='sumuww-dkg-deal-v1','DKG deal fields')
    require(b['context']==digest(ctx) and b['nodeId']==p['nodeId'] and p['nodeId'] in ids,'DKG deal context')
    require(len(b['commitments'])==threshold(len(ids)),'DKG polynomial degree')
    for c in b['commitments']:point(c)
    require(BLS.Verify(raw(b['commitments'][0],48),canonical(b),raw(p['pop'],96)),'DKG knowledge proof')
    require([e['recipient'] for e in p['encrypted']]==ids,'DKG encrypted recipients')
    for e in p['encrypted']:raw(e['nonce'],12);raw(e['ciphertext'],48)
    return True
def verify_deal(ctx,deal):return _verify_deal(canonical(ctx),canonical(deal))
def manifest(ctx,deals):return {'context':ctx,'deals':sorted(deals,key=lambda d:d['payload']['nodeId'])}

@lru_cache(maxsize=128)
def _group(encoded):
    import json
    setup=json.loads(encoded);ctx=setup['context'];ids=check_context(ctx);deals=setup['deals']
    require([d['payload']['nodeId'] for d in deals]==ids,'Complete DKG dealer set required')
    key=Z1
    for d in deals:
        verify_deal(ctx,d);key=add(key,point(d['payload']['body']['commitments'][0]))
    require(not is_inf(key),'Zero beacon key')
    return G1_to_pubkey(key).hex()
def group(setup):return _group(canonical(setup))
def verification_share(setup,node_id):
    ids=check_context(setup['context']);x=ids.index(node_id)+1;p=Z1
    for deal in setup['deals']:p=add(p,evaluate_public(deal['payload']['body']['commitments'],x))
    require(not is_inf(p),'Zero verification share');return G1_to_pubkey(p).hex()
def recover(identity,setup):
    group(setup);ctx=setup['context'];ids=check_context(ctx);x=ids.index(identity.node_id)+1;value=0
    key=digest(ctx)
    for deal in setup['deals']:
        p=deal['payload'];member=next(m['payload'] for m in ctx['members'] if m['payload']['nodeId']==p['nodeId'])
        encrypted=p['encrypted'][x-1];aad=canonical([key,p['nodeId'],identity.node_id])
        shared=identity.encryption.exchange(X25519PublicKey.from_public_bytes(raw(member['encryption'],32)))
        encryption_key=sha256(b'SUMUWW-DKG-9000'+shared+aad).digest()
        try:
            share=int.from_bytes(AESGCM(encryption_key).decrypt(raw(encrypted['nonce'],12),raw(encrypted['ciphertext'],48),aad),'big')
            require(0<share<Q and eq(multiply(G1,share),evaluate_public(p['body']['commitments'],x)),'Inconsistent DKG share')
        except Exception as error:raise InvalidDealer(p['nodeId']) from error
        value=(value+share)%Q
    require(value!=0,'Zero secret share');identity.put('share:'+digest(setup),format(value,'064x'))
    return identity.signed({'domain':'sumuww-dkg-ready-v1','nodeId':identity.node_id,'manifest':digest(setup)})

@lru_cache(maxsize=128)
def _verify_setup(encoded):
    import json
    setup=json.loads(encoded);require(set(setup)=={'manifest','ready'},'Setup fields')
    m=setup['manifest'];key=group(m);ids=check_context(m['context']);seen=set()
    for ready in setup['ready']:
        p=verify_frame(ready)
        require(p['domain']=='sumuww-dkg-ready-v1' and p['nodeId'] in ids and p['nodeId'] not in seen and p['manifest']==digest(m),'Setup ready context')
        seen.add(p['nodeId'])
    require(len(seen)>=quorum(len(ids)),'Insufficient DKG readiness')
    return key
def verify_setup(setup):return _verify_setup(canonical(setup))
def beacon_message(setup,slot):return canonical(['SUMUWW-BEACON-9000',digest(setup['manifest']),slot])
def partial(identity,setup,slot):
    verify_setup(setup);value=identity.get('share:'+digest(setup['manifest']))
    if value is None:recover(identity,setup['manifest']);value=identity.get('share:'+digest(setup['manifest']))
    return {'nodeId':identity.node_id,'signature':BLS.Sign(int(value,16),beacon_message(setup,slot)).hex()}
def verify_partial(setup,slot,value):
    key=verification_share(setup['manifest'],value['nodeId'])
    require(BLS.Verify(raw(key,48),beacon_message(setup,slot),raw(value['signature'],96)),'Invalid beacon partial')
def combine(setup,slot,partials):
    ids=check_context(setup['manifest']['context']);needed=threshold(len(ids));require(len(partials)>=needed,'Insufficient beacon shares')
    samples=partials[:needed];points=[];seen=set()
    for value in samples:
        require(value['nodeId'] not in seen,'Duplicate beacon partial');seen.add(value['nodeId']);verify_partial(setup,slot,value)
        points.append(ids.index(value['nodeId'])+1)
    result=Z2
    for i,value in enumerate(samples):
        coefficient=1
        for j,x in enumerate(points):
            if i!=j:coefficient=coefficient*x*pow(x-points[i],-1,Q)%Q
        result=add(result,multiply(signature_to_G2(raw(value['signature'],96)),coefficient))
    signature=G2_to_signature(result).hex();verify_beacon(setup,slot,signature);return signature

@lru_cache(maxsize=1024)
def _verify_beacon(encoded,slot,signature):
    import json
    setup=json.loads(encoded);key=verify_setup(setup)
    require(BLS.Verify(raw(key,48),beacon_message(setup,slot),raw(signature,96)),'Invalid threshold beacon')
    return sha256(raw(signature,96)).hexdigest()
def verify_beacon(setup,slot,signature):return _verify_beacon(canonical(setup),slot,signature)
