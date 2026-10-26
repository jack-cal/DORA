"""Two-party hash-time-lock settlement with an encrypted write-ahead journal.

Peer messages cannot sign or broadcast transactions. Every spend is prepared,
reviewed, then explicitly submitted locally. Chain observations decide status.
"""
import hashlib, json, threading
from coincurve import PublicKey
from ..orders import canonical, valid_hex
from .board import authenticate, identifier
from .utxo import UtxoAdapter
from .amounts import show

POLICY=('identity','kind','seconds','fee','confirmations')

def adapters(config,network,directory=None,progress=None):
    result={}
    for coin,c in config.items():
        if coin=='BTC' and c.get('mode')=='light':
            if directory is None:raise ValueError('A private light-client profile directory is required.')
            from .light import BitcoinLightAdapter
            result[coin]=BitcoinLightAdapter(c,directory,network,progress)
        elif coin in ('SMW','BTC'):result[coin]=UtxoAdapter(coin,c,network)
        else:raise ValueError('Unknown coin connection.')
    return result

class Engine:
    def __init__(self,board,vault,nodes):
        self.board=board;self.vault=vault;self.nodes=nodes;self.lock=threading.RLock()
        self.long=172800 if board.network=='mainnet' else 120
        self.short=43200 if board.network=='mainnet' else 50
        self.margin=21600 if board.network=='mainnet' else 20
        self.minimum=21600 if board.network=='mainnet' else 20
        self.claim_minimum=3600 if board.network=='mainnet' else 5
        from .funding import Funding
        self.funding=Funding(self)

    def _load(self,session):
        terms=self.board.terms(session)
        with self.board.connect() as c:row=c.execute('SELECT state FROM swaps WHERE id=?',(session,)).fetchone()
        if not row:raise ValueError('Prepare this trade on both devices first.')
        return terms,json.loads(row[0])

    def _save(self,session,state):
        with self.board.connect() as c:c.execute('INSERT INTO swaps VALUES(?,?) ON CONFLICT(id) DO UPDATE SET state=excluded.state',(session,canonical(state).decode()))

    def selling(self,t):return t['seller']==self.board.identity.public
    def own_coin(self,t):return 'SMW' if self.selling(t) else t['coin']
    def other_coin(self,t):return t['coin'] if self.selling(t) else 'SMW'

    @staticmethod
    def proof_digest(t,owner,offer):return hashlib.sha256(b'SUMUWW market keys v2\0'+canonical(t)+bytes.fromhex(owner)+canonical({k:v for k,v in offer.items() if k!='proofs'})).digest()

    def prepare(self,session):
        with self.lock:
            t=self.board.terms(session)
            with self.board.connect() as c:
                if c.execute('SELECT 1 FROM swaps WHERE id=?',(session,)).fetchone():return self.snapshot(session)
            coins=('SMW',t['coin'])
            if any(c not in self.nodes for c in coins):raise ValueError('Configure both chain connections first.')
            if t['smw_units']<294 or (t['coin']=='BTC' and t['quote_units']<294):raise ValueError('Amount is below the native witness dust limit.')
            infos={c:self.nodes[c].info() for c in coins}
            if not all(v['active'] for v in infos.values()):raise ValueError('SUMUWW conditional transfers require height 9100.')
            offer={'chains':{c:{k:infos[c][k] for k in POLICY} for c in coins},
                   'keys':{c:self.vault.public(c) for c in coins},'start':{c:infos[c]['height'] for c in coins},'hash':None,'expiry':None}
            if self.selling(t):
                offer['hash']=hashlib.sha256(self.vault.secret(session)).hexdigest()
                offer['expiry']={c:self.nodes[c].deadline(self.long if c=='SMW' else self.short) for c in coins}
            proofs={}
            digest=self.proof_digest(t,self.board.identity.public,offer)
            for c in coins:
                key=self.vault.key(c)
                proofs[c]=key.sign_digest(digest).hex()
            offer['proofs']=proofs
            self._save(session,{'offer':offer,'remote':None,'ops':{},'refs':{},'canceled':False,'revision':0})
            return self.snapshot(session)

    def snapshot(self,session):
        t,s=self._load(session)
        return self.board.sign('swap',session=session,terms=identifier(t),offer=s['offer'],references=s['refs'],canceled=s['canceled'],revision=s['revision'])

    def _validate_offer(self,t,owner,offer,local):
        if not isinstance(offer,dict) or set(offer)!={'chains','keys','start','hash','expiry','proofs'}:raise ValueError('Invalid key offer.')
        coins={'SMW',t['coin']}
        if any(set(offer[k])!=coins for k in ('chains','keys','start','proofs')) or offer['chains']!=local['chains']:raise ValueError('Different chain identity, fees or confirmation policy.')
        digest=self.proof_digest(t,owner,offer)
        for c in coins:
            key=offer['keys'][c];proof=offer['proofs'][c]
            if key.get('address')==local['keys'][c]['address']:raise ValueError('Shared counterparty address refused.')
            if type(offer['start'][c]) is not int or offer['start'][c]<0:raise ValueError('Invalid scan height.')
            if abs(offer['start'][c]-local['start'][c])>100:raise ValueError('Prepare both parties on synchronized chains.')
            if c in ('SMW','BTC'):
                from sumuww.address import encode_address,_bech32_encode,_convert_bits
                from sumuww.wallet import p2wpkh_script
                pub=PublicKey(bytes.fromhex(key['pubkey']))
                if len(bytes.fromhex(key['pubkey']))!=33 or not pub.verify(bytes.fromhex(proof),digest,hasher=None):raise ValueError('Invalid ownership proof.')
                script=p2wpkh_script(pub.format())
                address=encode_address(script,network='dora' if self.board.network=='mainnet' else 'regtest') if c=='SMW' else _bech32_encode('bc' if self.board.network=='mainnet' else 'bcrt',[0]+_convert_bits(script[2:],8,5,pad=True))
                if address!=key['address']:raise ValueError('Address and signing key disagree.')
            else:raise ValueError('Unsupported trade asset.')
        if owner==t['seller']:
            if not valid_hex(offer['hash'],32) or not isinstance(offer['expiry'],dict) or set(offer['expiry'])!=coins or any(type(v) is not int or v<=0 for v in offer['expiry'].values()):raise ValueError('Invalid seller commitment.')
        elif offer['hash'] is not None or offer['expiry'] is not None:raise ValueError('Buyer cannot replace seller commitment.')

    def receive(self,packet):
        with self.lock:
            b=authenticate(packet,self.board.network)
            if set(b)!={'domain','network','maker','kind','session','terms','offer','references','canceled','revision'} or b['kind']!='swap':raise ValueError('Invalid swap message.')
            t,s=self._load(b['session']);other=t['buyer'] if self.selling(t) else t['seller']
            if b['maker']!=other or b['terms']!=identifier(t) or type(b['canceled']) is not bool or type(b['revision']) is not int or b['revision']<0:raise ValueError('Wrong participant or signed terms.')
            if not isinstance(b['references'],dict) or not set(b['references']).issubset({'SMW',t['coin']}) or len(canonical(b['references']))>2048:raise ValueError('Invalid transaction references.')
            self._validate_offer(t,other,b['offer'],s['offer'])
            if s['remote']:
                old=s['remote']['body']
                if old['offer']!=b['offer']:raise ValueError('Cannot replace agreed keys or deadlines.')
                if b['revision']<old['revision']:return self.snapshot(b['session'])
                if b['revision']==old['revision'] and packet!=s['remote']:raise ValueError('Conflicting signed trade revision.')
                if old['canceled'] and not b['canceled']:raise ValueError('Cancellation cannot be withdrawn.')
                if any(b['references'].get(c)!=v for c,v in old['references'].items()):raise ValueError('Cannot replace a funding reference.')
            s['remote']=packet;self._save(b['session'],s)
            return self.snapshot(b['session'])

    def specs(self,t,s):
        if not s['remote']:raise ValueError('Exchange trade details with the counterparty first.')
        seller,buyer=(s['offer'],s['remote']['body']['offer']) if self.selling(t) else (s['remote']['body']['offer'],s['offer'])
        specs={}
        for c in ('SMW',t['coin']):
            source,dest=(seller,buyer) if c=='SMW' else (buyer,seller)
            specs[c]={'id':hashlib.sha256((t['session']+c).encode()).hexdigest(),'hash':seller['hash'],
                      'sender':source['keys'][c],'receiver':dest['keys'][c],'amount':t['smw_units' if c=='SMW' else 'quote_units'],
                      'expiry':seller['expiry'][c],'scan_start':min(seller['start'][c],buyer['start'][c]),'fee':seller['chains'][c]['fee']}
        return specs

    @staticmethod
    def canceled(s):
        return s['canceled'] or bool(s.get('remote') and s['remote']['body']['canceled'])

    def _observe(self,t,s,specs,*,action=None,tolerant=False):
        result={}
        for c,sp in specs.items():
            if action=='refund' and c!=self.own_coin(t):continue
            ref=s['refs'].get(c) or s['remote']['body']['references'].get(c)
            # References are hints only. An invalid hint cannot hide a valid lock.
            try:
                try:result[c]=self.nodes[c].observe(sp,ref)
                except (ValueError,KeyError,TypeError):
                    if not ref:raise
                    result[c]=self.nodes[c].observe(sp,None)
            except (OSError,ValueError,KeyError,TypeError):
                if not tolerant:raise
                result[c]={'status':'unavailable','confirmed':False}
        return result

    def _window(self,t,specs):
        remaining={c:self.nodes[c].remaining(sp) for c,sp in specs.items()}
        if remaining[t['coin']]<self.minimum or remaining['SMW']<remaining[t['coin']]+self.margin:raise ValueError('Insufficient refund safety window. No new funding allowed.')
        if remaining['SMW']>self.long+600 or remaining[t['coin']]>self.short+600:raise ValueError('Refund window exceeds the signed protocol policy.')

    def reserved_inputs(self,coin,session=None,include_holds=True):
        reserved=[]
        with self.board.connect() as c:rows=[json.loads(r[0]) for r in c.execute('SELECT state FROM swaps')]
        for row in rows:
            for saved in row['ops'].values():
                if self.canceled(row) and not saved['submitted']:continue
                if saved['coin']==coin:reserved.extend(tuple(x) for x in saved.get('inputs',[]))
        if include_holds:reserved.extend(self.funding.reserved(coin,session=session))
        return reserved

    def _check(self,action,t,s,specs,observed):
        own=self.own_coin(t);other=self.other_coin(t)
        for c in ((own,) if action=='refund' else specs):
            info=self.nodes[c].info()
            if not info['active'] or {k:info[k] for k in POLICY}!=s['offer']['chains'][c]:raise ValueError('Chain identity or policy changed.')
        if action=='lock':
            if s['canceled'] or s['remote']['body']['canceled']:raise ValueError('Trade canceled; new funding is disabled.')
            self._window(t,specs)
            if observed[own]['status'] not in ('missing','pending'):raise ValueError('Local trade lock already exists.')
            if not self.selling(t) and observed['SMW']['status']!='locked':raise ValueError('Wait for the confirmed SMW lock before paying.')
        elif action=='claim':
            if observed[other]['status']!='locked':raise ValueError('Confirmed counterparty lock required.')
            if self.selling(t):
                if observed['SMW']['status']!='locked':raise ValueError('The SMW lock must remain available to the buyer.')
                remain={c:self.nodes[c].remaining(sp) for c,sp in specs.items()}
                if remain[t['coin']]<self.claim_minimum or remain['SMW']<remain[t['coin']]+self.margin:raise ValueError('Too close to refund; do not reveal the secret.')
            elif observed[t['coin']]['status']!='claimed':raise ValueError('Wait for the confirmed quote-chain claim revealing the secret.')
        elif action=='refund':
            if observed[own]['status']!='locked' or self.nodes[own].remaining(specs[own])>0:raise ValueError('Refund requires an unspent lock past its deadline.')
        else:raise ValueError('Unknown transaction action.')

    def preview(self,session,action):
        with self.lock:
            t,s=self._load(session);specs=self.specs(t,s);coin=self.other_coin(t) if action=='claim' else self.own_coin(t)
            if action not in ('lock','claim','refund'):raise ValueError('Unknown action.')
            if action not in s['ops']:
                with self.board.connect() as c:others=[(r[0],json.loads(r[1])) for r in c.execute('SELECT id,state FROM swaps WHERE id<>?',(session,))]
                for sid,other in (others if action=='lock' else ()):
                    if any(op['coin']==coin for op in other['ops'].values()):
                        state=self.status(sid)['state']
                        if state not in ('completed','refunded') and not (state=='canceled' and all(not op['submitted'] for op in other['ops'].values())):
                            raise ValueError('Resolve the other trade using this coin before signing another transaction.')
                observed=self._observe(t,s,specs,action=action);self._check(action,t,s,specs,observed)
                key=self.vault.key(coin);node=self.nodes[coin];ref=observed[coin].get('reference')
                reserved=self.reserved_inputs(coin,session=session)
                if action=='lock':
                    op=node.prepare_lock(specs[coin],key,reserved)
                elif action=='claim':
                    secret=self.vault.secret(session) if self.selling(t) else bytes.fromhex(observed[t['coin']]['secret'])
                    if hashlib.sha256(secret).hexdigest()!=specs[coin]['hash']:raise ValueError('Observed preimage mismatch.')
                    op=node.prepare_claim(specs[coin],ref,key,secret,reserved)
                else:op=node.prepare_refund(specs[coin],ref,key,reserved)
                s['ops'][action]={'coin':coin,'txid':op['txid'],'fee':op['fee'],'value':op['value'],'inputs':op.get('inputs',[]),'sealed':self.vault.seal(session+':'+action,op),'submitted':False}
                self._save(session,s)
            op=s['ops'][action]
            return {'session':session,'action':action,'coin':coin,'txid':op['txid'],'fee':show(op['fee']+(specs[coin]['fee'] if action=='lock' else 0),coin),
                    'amount':show(specs[coin]['amount'],coin),'from':self.vault.public(coin)['address'],
                    'to':specs[coin]['sender' if action=='refund' else 'receiver']['address'],
                    'expiry':specs[coin]['expiry'],'network':self.board.network,'submitted':op['submitted']}

    def submit(self,session,action,txid):
        with self.lock:
            if action.startswith('fee:'):return self.submit_fee_increase(session,action,txid)
            t,s=self._load(session);saved=s['ops'].get(action)
            if not saved or saved['txid']!=txid:raise ValueError('Review the exact saved transaction first.')
            specs=self.specs(t,s);observed=self._observe(t,s,specs,action=action);coin=saved['coin']
            expected={'lock':'locked','claim':'claimed','refund':'refunded'}[action]
            if saved['submitted'] and observed[coin]['status']==expected:return self.status(session)
            self._check(action,t,s,specs,observed)
            operation=self.vault.unseal(session+':'+action,saved['sealed'])
            self.nodes[coin].preflight(operation)
            # Persist the exact transaction and reference BEFORE any network call.
            saved['submitted']=True
            if action=='lock':s['refs'][coin]=self.nodes[coin].reference(specs[coin],operation);s['revision']+=1
            self._save(session,s)
            self.nodes[coin].broadcast(operation)
            return self.status(session)

    def preview_fee_increase(self,session):
        with self.lock:
            t,s=self._load(session);last_error=None
            for action,parent in reversed(tuple(s['ops'].items())):
                if not parent['submitted']:continue
                coin=parent['coin'];node=self.nodes[coin];name='fee:'+parent['txid']
                if name in s['ops']:
                    if s['ops'][name]['submitted']:continue
                    saved=s['ops'][name]
                else:
                    operation=self.vault.unseal(session+':'+action,parent['sealed'])
                    try:child=node.prepare_fee_child(operation,self.vault.key(coin),self.reserved_inputs(coin))
                    except ValueError as error:last_error=error;continue
                    saved={'coin':coin,'txid':child['txid'],'fee':child['fee'],'value':0,'inputs':child['inputs'],
                           'sealed':self.vault.seal(session+':'+name,child),'submitted':False}
                    s['ops'][name]=saved;self._save(session,s)
                address=self.vault.public(coin)['address']
                return {'session':session,'action':name,'coin':coin,'txid':saved['txid'],'fee':show(saved['fee'],coin),
                        'amount':'0','from':address,'to':address,'network':self.board.network,'submitted':saved['submitted']}
            if last_error:raise last_error
            raise ValueError('No pending transaction is available for a fee increase.')

    def submit_fee_increase(self,session,action,txid):
        t,s=self._load(session);saved=s['ops'].get(action)
        if not saved or saved['txid']!=txid:raise ValueError('Review the exact saved fee increase first.')
        node=self.nodes[saved['coin']];operation=self.vault.unseal(session+':'+action,saved['sealed'])
        node.preflight(operation)
        saved['submitted']=True;self._save(session,s)
        node.broadcast(operation)
        return self.status(session)

    def cancel(self,session):
        with self.lock:
            t,s=self._load(session);s['canceled']=True;s['revision']+=1;self._save(session,s)
            return self.snapshot(session)

    def status(self,session):
        with self.lock:
            t,s=self._load(session)
            result={'session':session,'prepared':True,'peer_ready':bool(s['remote']),'canceled':s['canceled'],'state':'canceled' if s['canceled'] else 'prepared'}
            if not s['remote']:return result
            specs=self.specs(t,s);observed=self._observe(t,s,specs,tolerant=True)
            result['chains']={c:{k:v for k,v in o.items() if k!='secret'} for c,o in observed.items()}
            result['remaining']={}
            for c,sp in specs.items():
                if observed[c]['status']=='unavailable':continue
                try:result['remaining'][c]=max(0,self.nodes[c].remaining(sp))
                except (OSError,ValueError,KeyError,TypeError):
                    observed[c]['status']='unavailable'
                    observed[c]['confirmed']=False
                    result['chains'][c]['status']='unavailable'
                    result['chains'][c]['confirmed']=False
            states=[o['status'] for o in observed.values()]
            if all(v=='claimed' for v in states):result['state']='completed'
            elif observed[self.own_coin(t)]['status']=='refunded':result['state']='refunded'
            elif 'claimed' in states:result['state']='claim_ready'
            elif 'locked' in states:result['state']='refund_wait' if s['canceled'] or s['remote']['body']['canceled'] else 'locked'
            elif 'pending' in states:result['state']='pending'
            elif any(op['submitted'] for op in s['ops'].values()):result['state']='pending'
            elif s['canceled'] or s['remote']['body']['canceled']:result['state']='canceled'
            elif 'unavailable' in states:result['state']='unavailable'
            return result
