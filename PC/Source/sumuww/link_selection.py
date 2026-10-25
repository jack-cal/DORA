"""Auditable live-candidate selection, using the existing beacon and sampler.

An activity certificate does not prove independent human operators. It binds
signed responses to one source/target/round and requires the PoW-anchored
beacon generation's quorum to attest the complete observed responder set.
The verifier never substitutes its own local peer list for consensus data.
"""
from .link_crypto import digest, require, raw, verify_frame, sample
from . import link_beacon as beacon

ACTIVITY_DOMAIN='sumuww-link-activity-v1'
VOTE_DOMAIN='sumuww-link-candidate-vote-v1'
MAX_ROUND_LAG=6
PUBLIC_ACTIVATION_HEIGHT=9_600
SELECTION_POLICY='sumuww-certified-active-selection-v1'


def context(state,source,target,round_hash,nonce):
    found=state.anchor(state.chain._path(round_hash))
    require(found is not None,'Selection needs a PoW-anchored beacon generation')
    return {'network':state.network,'source':source.hex(),'target':target.hex(),
            'round':round_hash.hex(),'anchor':found[0].hex(),'nonce':nonce}


def check_context(state,ctx,*,fresh=False):
    require(type(ctx) is dict and set(ctx)=={'network','source','target','round','anchor','nonce'},'Selection context fields')
    require(ctx['network']==state.network,'Selection network')
    for name in ('source','target','round','anchor','nonce'):raw(ctx[name],32)
    chain=state.chain;source=bytes.fromhex(ctx['source']);target=bytes.fromhex(ctx['target'])
    a=chain._row(source);b=chain._row(target);head=chain._row(bytes.fromhex(ctx['round']))
    require(b[1]==source and b[2]==a[2]+1,'Selection must name a direct connection')
    path=chain._path(head[0]);ids={row[0] for row,_ in path}
    require(target in ids,'Selection round must descend from the target block')
    found=state.anchor(path)
    require(found is not None and found[0].hex()==ctx['anchor'],'Selection beacon anchor mismatch')
    if fresh:
        current=chain._row(chain.tip_hash)
        require(current[2]-MAX_ROUND_LAG<=head[2]<=current[2],'Selection activity round is stale')
        require(head[0] in {row[0] for row,_ in chain._path(chain.tip_hash)},'Selection round is not active')
    return beacon.check_context(found[1]['manifest']['context'])


def activity(identity,ctx,contact):
    return {'contact':contact,'response':identity.signed({
        'domain':ACTIVITY_DOMAIN,'network':ctx['network'],'nodeId':identity.node_id,'context':digest(ctx)})}


def check_activity(record,ctx):
    require(type(record) is dict and set(record)=={'contact','response'},'Activity record fields')
    contact=verify_frame(record['contact']);response=verify_frame(record['response'])
    require(set(contact)=={'domain','network','nodeId','encryption'} and
            contact['domain']=='sumuww-link-contact-v1' and contact['network']==ctx['network'],'Activity contact')
    raw(contact['encryption'],32)
    require(response=={'domain':ACTIVITY_DOMAIN,'network':ctx['network'],
            'nodeId':contact['nodeId'],'context':digest(ctx)},'Activity challenge binding')
    return contact['nodeId']


def proposal(ctx,records):
    return {'context':ctx,'responders':sorted(records,key=lambda r:r['response']['payload']['nodeId'])}


def check_proposal(state,value,*,fresh=False):
    require(type(value) is dict and set(value)=={'context','responders'},'Candidate proposal fields')
    electorate=check_context(state,value['context'],fresh=fresh)
    require(type(value['responders']) is list,'Candidate response list')
    ids=[check_activity(record,value['context']) for record in value['responders']]
    require(len(ids)>=3 and ids==sorted(set(ids)),'Three or more unique sorted active candidates required')
    return ids,electorate


def vote(identity,value):
    body={'domain':VOTE_DOMAIN,'network':value['context']['network'],'nodeId':identity.node_id,
          'context':digest(value['context']),'proposal':digest(value)}
    signature=identity.sign_once(digest(['candidate-vote',value['context']]),body)
    return {'payload':body,'signature':signature}


def verify_certificate(state,certificate,random,*,fresh=False):
    require(type(certificate) is dict and set(certificate)=={'proposal','approvals'},'Candidate certificate fields')
    value=certificate['proposal'];ids,electorate=check_proposal(state,value,fresh=fresh)
    require(type(certificate['approvals']) is list,'Candidate approval list')
    voters=[]
    for approval in certificate['approvals']:
        p=verify_frame(approval)
        require(p=={'domain':VOTE_DOMAIN,'network':state.network,'nodeId':p['nodeId'],
                'context':digest(value['context']),'proposal':digest(value)},'Candidate vote context')
        require(p['nodeId'] in electorate,'Candidate vote outside anchored generation')
        voters.append(p['nodeId'])
    require(voters==sorted(set(voters)) and len(voters)>=beacon.quorum(len(electorate)),
            'Anchored quorum must attest the active candidate set')
    return sample(random,ids)


def witness_lock(message):
    # A new certified availability round may replace an unavailable team for
    # the same edge. Existing signatures and locks are never overwritten.
    return digest(['certified-link',message['slot'],message['source'],message['target'],message['selection']])
