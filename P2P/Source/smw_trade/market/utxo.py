"""Bitcoin Core and SUMUWW HTLC adapters with locally signed recovery plans."""
import hashlib, math
from decimal import Decimal
from ..wallet_link import LocalRPC
from ..htlc import Contract, sign_spend, verify_spend
from sumuww.block import Block
from sumuww.transaction import Transaction, TxInput, TxOutput
from sumuww.wallet import sign_p2wpkh,p2wpkh_script
from sumuww.address import encode_address, _bech32_encode, _convert_bits
from sumuww.profiles import get_network
from .fee_quote import quote,MAX_FEE,validate_settings

BTC_GENESIS='000000000019d6689c085ae165831e934ff763ae46a2a6c172b3f1b60a8ce26f'

def txid(tx):return tx.txid()[::-1].hex()

class UtxoAdapter:
    def __init__(self,coin,config,network='mainnet'):
        if coin not in ('SMW','BTC'):raise ValueError('Invalid UTXO coin.')
        self.coin=coin;self.config=config;self.network=network
        validate_settings(config)
        self.rpc=LocalRPC(config['url'],config['credential_file'],coin.lower())
        self.confirmations=int(config.get('confirmations',6 if network=='mainnet' else 1))
        if self.confirmations<1 or (network=='mainnet' and self.confirmations<6):raise ValueError('Insufficient confirmation policy.')
        self.fee=int(config.get('fee_units',10000 if coin=='SMW' else 2000))
        if not 294<=self.fee<=1_000_000:raise ValueError('Invalid fee budget.')
        self.seconds=int(config.get('block_seconds',600))
        if self.seconds<1 or (network=='mainnet' and self.seconds!=600):raise ValueError('Public timing profile is fixed at 600 seconds.')
        self._known={}

    def info(self):
        c=self.rpc
        value=c.call('getblockchaininfo')
        height=int(value['blocks'] if self.coin=='BTC' else value['height'])
        genesis=c.call('getblockhash',0)
        if self.coin=='BTC':
            if value['chain']!=('main' if self.network=='mainnet' else 'regtest'):raise ValueError('Wrong Bitcoin network.')
            if self.network=='mainnet' and genesis!=BTC_GENESIS:raise ValueError('Wrong Bitcoin genesis.')
            if value.get('pruned') or value.get('initialblockdownload'):raise ValueError('Use a synchronized unpruned Bitcoin node.')
            indexes=c.call('getindexinfo')
            if not indexes.get('txindex',{}).get('synced'):raise ValueError('Bitcoin Core needs a synchronized txindex.')
            active=True
        else:
            htlc=c.call('gethtlcinfo')
            expected=get_network('dora' if self.network=='mainnet' else 'regtest').genesis.block_hash()[::-1].hex()
            if genesis!=expected or htlc.get('template')!='exact-p2wsh-htlc-v1':raise ValueError('Wrong SUMUWW chain or conditional-spend rules.')
            if self.network=='mainnet' and (htlc.get('activation_height')!=9100 or value.get('sync_state')!='ready'):
                raise ValueError('SUMUWW must be synchronized with the height-9100 activation rule.')
            active=bool(htlc['active'])
        return {'identity':f'{self.coin}:{genesis}','height':height,'clock':height,'kind':'height','seconds':self.seconds,'active':active,'fee':self.fee,'confirmations':self.confirmations}

    def deadline(self,seconds):return max(17,self.info()['height']+math.ceil(seconds/self.seconds))
    def remaining(self,spec):return (spec['expiry']-self.info()['height'])*self.seconds

    def contract(self,spec):
        return Contract(bytes.fromhex(spec['hash']),bytes.fromhex(spec['receiver']['pubkey']),bytes.fromhex(spec['sender']['pubkey']),spec['expiry'])

    def fee_quote(self,size,mode=None):
        mode=mode or self.config.get('fee_mode','normal')
        manual=self.config.get('fee_rate')
        if self.coin=='SMW':
            estimate=self.rpc.call('estimatefee',size,mode)
            if manual is None:
                if estimate.get('capped'):raise ValueError('Fee quote exceeds the automatic spending limit.')
                return int(estimate['fee_units'])
            policy=self.rpc.call('getmempoolpolicy')
            floor=Decimal(str(policy['minimum_fee_units_per_kvb']))/1000
            return quote(size,[],max(floor,Decimal('0.001')),mode,manual)
        info=self.rpc.call('getmempoolinfo')
        floor=max(Decimal(str(info.get('mempoolminfee','0'))),Decimal(str(info.get('minrelaytxfee','0.00001'))))*100000
        pool=self.rpc.call('getrawmempool',True) if manual is None else {}
        bins=[(str(Decimal(str(e['fees']['base']))*100000000/e['vsize']),int(e['vsize'])) for e in pool.values()]
        return quote(size,bins,max(floor,Decimal('0.001')),mode,manual)

    @staticmethod
    def vsize(transaction):return (transaction.weight()+3)//4

    def output(self,digest,index):
        value=self.rpc.call('gettxout',digest,index,True)
        if value is None:return None
        if self.coin=='SMW':return {'value':value['value_units'],'script':value['script_pubkey'],'confirmations':value['confirmations'],'coinbase':value['coinbase']}
        amount=Decimal(str(value['value']))*10**8
        if amount!=amount.to_integral_value():raise ValueError('Nonintegral Bitcoin output.')
        return {'value':int(amount),'script':value['scriptPubKey']['hex'],'confirmations':value['confirmations'],'coinbase':value['coinbase']}

    def coins(self,key):
        if self.coin=='BTC':
            addr=_bech32_encode('bc' if self.network=='mainnet' else 'bcrt',[0]+_convert_bits(key.script_pubkey[2:],8,5,pad=True))
            scan=self.rpc.call('scantxoutset','start',['addr('+addr+')'])
            if not scan['success']:raise ValueError('Bitcoin UTXO scan incomplete.')
            points=[(x['txid'],x['vout']) for x in scan['unspents']]
        else:
            addr=encode_address(key.script_pubkey,network='dora' if self.network=='mainnet' else 'regtest');offset=0;points=[]
            while True:
                page=self.rpc.call('listunspent',addr,1000,offset)
                points.extend((x['txid'],x['index']) for x in page['utxos'] if x['spendable'])
                offset+=len(page['utxos'])
                if offset>=page['total']:break
                if not page['utxos']:raise ValueError('Invalid UTXO cursor.')
        result=[]
        for digest,index in points:
            o=self.output(digest,index)
            if o and o['confirmations']>=self.confirmations and (not o['coinbase'] or o['confirmations']>=101):
                if o['script']!=key.script_pubkey.hex():raise ValueError('Input ownership mismatch.')
                result.append({'txid':digest,'index':index,**o})
        return result

    def transaction(self,digest):
        value=self.rpc.call('getrawtransaction',digest,True)
        tx=Transaction.deserialize(bytes.fromhex(value['hex']))
        if txid(tx)!=digest:raise ValueError('RPC transaction ID mismatch.')
        return tx,value.get('confirmations',0)

    def select_funding(self,amount,key,reserved=()):
        selected=[];total=0;fee=0
        for coin in self.coins(key):
            if (coin['txid'],coin['index']) in reserved:continue
            selected.append(coin);total+=coin['value']
            dummy=Transaction(2,tuple(TxInput(bytes.fromhex(c['txid'])[::-1],c['index'],witness=(bytes(73),key.pubkey)) for c in selected),
                              (TxOutput(amount,b'\x00\x20'+bytes(32)),TxOutput(294,key.script_pubkey)),0)
            fee=self.fee_quote(self.vsize(dummy))
            # Keep an owned change output for a reviewed child-fee increase.
            if total>=amount+fee+294:break
        if total<amount+fee+294:raise ValueError('Deposit confirmed funds and network fees into your trading wallet first.')
        return selected,fee

    def prepare_lock(self,spec,key,reserved=()):
        if not self.info()['active']:raise ValueError('SUMUWW HTLC spending activates at height 9100. No funding before activation.')
        if key.pubkey.hex()!=spec['sender']['pubkey']:raise ValueError('Wrong funding key.')
        contract=self.contract(spec);amount=spec['amount']+spec['fee']
        selected,fee=self.select_funding(amount,key,reserved);total=sum(c['value'] for c in selected)
        change=total-amount-fee
        outputs=[TxOutput(amount,contract.script_pubkey)]
        if change:outputs.append(TxOutput(change,key.script_pubkey))
        tx=Transaction(2,tuple(TxInput(bytes.fromhex(c['txid'])[::-1],c['index']) for c in selected),tuple(outputs),0)
        for i,c in enumerate(selected):tx=sign_p2wpkh(tx,i,TxOutput(c['value'],key.script_pubkey),key)
        refund=Transaction(2,(TxInput(tx.txid(),0,sequence=0xfffffffe),),(TxOutput(spec['amount'],key.script_pubkey),),contract.refund_height)
        refund=sign_spend(refund,0,tx.outputs[0],contract,key)
        return {'raw':tx.serialize().hex(),'txid':txid(tx),'refund_raw':refund.serialize().hex(),'fee':fee,'value':amount,'coin':self.coin,'inputs':[(c['txid'],c['index']) for c in selected]}

    def reference(self,spec,operation):return {'txid':operation['txid'],'index':0}

    def find_reference(self,spec):
        script=self.contract(spec).script_pubkey;tip=self.info()['height']
        for height in range(spec['scan_start'],tip+1):
            digest=self.rpc.call('getblockhash',height)
            raw=self.rpc.call('getblock',digest,0 if self.coin=='BTC' else False)
            block=Block.deserialize(bytes.fromhex(raw))
            if block.block_hash()[::-1].hex()!=digest:raise ValueError('RPC block hash mismatch.')
            for tx in block.transactions:
                for index,out in enumerate(tx.outputs):
                    if out.script_pubkey==script and out.value==spec['amount']+spec['fee']:
                        return {'txid':txid(tx),'index':index}
        return None

    def _funding(self,spec,reference):
        tx,count=self.transaction(reference['txid']);index=reference['index']
        if type(index) is not int or not 0<=index<len(tx.outputs):raise ValueError('Invalid funding index.')
        out=tx.outputs[index]
        if out.script_pubkey!=self.contract(spec).script_pubkey or out.value!=spec['amount']+spec['fee']:
            raise ValueError('Funding output differs from agreed amount or conditions.')
        return tx,index,out,count

    def _spend(self,spec,reference):
        if self.coin=='SMW':
            result=self.rpc.call('findspendingtransaction',reference['txid'],reference['index'],spec['scan_start'])
            return result['txid'] if result else None
        tip=self.info()['height']
        for height in range(spec['scan_start'],tip+1):
            block=self.rpc.call('getblock',self.rpc.call('getblockhash',height),2)
            for tx in block['tx']:
                if any(i.get('txid')==reference['txid'] and i.get('vout')==reference['index'] for i in tx['vin']):return tx['txid']
        return None

    def observe(self,spec,reference=None):
        self.info();reference=reference or self.find_reference(spec)
        if not reference:return {'status':'missing','confirmed':False}
        try:fund,index,out,count=self._funding(spec,reference)
        except ValueError as exc:
            # Missing transactions must not be treated as settled or refunded.
            raise ValueError('Funding could not be verified: '+str(exc)) from exc
        if count<self.confirmations:return {'status':'pending','confirmed':False,'reference':reference}
        current=self.output(reference['txid'],index)
        if current:return {'status':'locked','confirmed':True,'reference':reference,'confirmations':count}
        spend_id=self._spend(spec,reference)
        if not spend_id:return {'status':'pending','confirmed':False,'reference':reference}
        spend,confirmations=self.transaction(spend_id)
        matches=[i for i,x in enumerate(spend.inputs) if x.prev_txid==fund.txid() and x.prev_index==index]
        if len(matches)!=1 or not verify_spend(spend,matches[0],out):raise ValueError('Invalid on-chain HTLC spend.')
        witness=spend.inputs[matches[0]].witness
        result={'status':('claimed' if len(witness)==4 else 'refunded') if confirmations>=self.confirmations else 'pending','confirmed':confirmations>=self.confirmations,'reference':reference,'txid':spend_id}
        if len(witness)==4:result['secret']=witness[1].hex()
        return result

    def prepare_claim(self,spec,reference,key,secret,reserved=()):
        observed=self.observe(spec,reference);reference=observed.get('reference')
        if observed['status']!='locked':raise ValueError('A confirmed unspent lock is required.')
        return self._prepare_spend(spec,reference,key,secret=secret,reserved=reserved)

    def prepare_refund(self,spec,reference,key,reserved=()):
        if self.remaining(spec)>0:raise ValueError('Refund height has not arrived.')
        return self._prepare_spend(spec,reference,key,reserved=reserved)

    def _prepare_spend(self,spec,reference,key,secret=None,reserved=()):
        fund,index,out,count=self._funding(spec,reference)
        contract=self.contract(spec);extra=[];total=0;available=None
        refund=secret is None;locktime=spec['expiry'] if refund else 0
        sponsor=p2wpkh_script(bytes.fromhex(spec['sender']['pubkey']))
        while True:
            witness=(bytes(73),b'',contract.script) if refund else (bytes(73),bytes(32),b'\x01',contract.script)
            inputs=(TxInput(fund.txid(),index,sequence=0xfffffffe,witness=witness),)+tuple(
                TxInput(bytes.fromhex(c['txid'])[::-1],c['index'],witness=(bytes(73),key.pubkey)) for c in extra)
            dummy=Transaction(2,inputs,(TxOutput(spec['amount'],key.script_pubkey),TxOutput(294,sponsor),TxOutput(294,key.script_pubkey)),locktime)
            fee=self.fee_quote(self.vsize(dummy))
            if spec['fee']+total>=fee:break
            if available is None:available=iter(c for c in self.coins(key) if (c['txid'],c['index']) not in reserved)
            coin=next(available,None)
            if coin is None:raise ValueError('Additional confirmed funds are needed for the current network fee.')
            extra.append(coin);total+=coin['value']
        outputs=[TxOutput(spec['amount'],key.script_pubkey)]
        unused=max(0,spec['fee']-fee);change=total-max(0,fee-spec['fee'])
        for value,script in ((unused,sponsor),(change,key.script_pubkey)):
            if value>=294:outputs.append(TxOutput(value,script))
            else:fee+=value
        if fee>MAX_FEE:raise ValueError('Fee exceeds the spending limit.')
        inputs=tuple(TxInput(i.prev_txid,i.prev_index,sequence=i.sequence) for i in inputs)
        tx=Transaction(2,inputs,tuple(outputs),locktime)
        tx=sign_spend(tx,0,out,contract,key,secret=secret)
        for position,coin in enumerate(extra,1):tx=sign_p2wpkh(tx,position,TxOutput(coin['value'],key.script_pubkey),key)
        return {'raw':tx.serialize().hex(),'txid':txid(tx),'fee':fee,'value':0,'coin':self.coin,'inputs':[(c['txid'],c['index']) for c in extra]}

    def prepare_fee_child(self,parent,key,reserved=()):
        tx=Transaction.deserialize(bytes.fromhex(parent['raw']))
        if txid(tx)!=parent['txid']:raise ValueError('Changed parent transaction.')
        available=[]
        for index,out in enumerate(tx.outputs):
            if out.script_pubkey!=key.script_pubkey:continue
            current=self.output(parent['txid'],index)
            if current and current['confirmations']==0:
                available.append((out.value,index))
        if not available:raise ValueError('No unconfirmed owned output is available for a fee increase.')
        value,index=max(available);point=(parent['txid'],index)
        if point in reserved:raise ValueError('Fee-increase output is already reserved.')
        selected=[{'txid':parent['txid'],'index':index,'value':value}];total=value
        package=parent.get('package',[])+[{'txid':parent['txid'],'vsize':self.vsize(tx),'fee':parent['fee']}]
        if len(package)>20:raise ValueError('Wait for confirmations before adding another fee increase.')
        old_size=sum(p['vsize'] for p in package);old_fee=sum(p['fee'] for p in package)
        coins=None
        while True:
            dummy=Transaction(2,tuple(TxInput(bytes.fromhex(c['txid'])[::-1],c['index'],witness=(bytes(73),key.pubkey)) for c in selected),
                              (TxOutput(294,key.script_pubkey),),0)
            size=self.vsize(dummy)
            fee=max(self.fee_quote(size,'fast'),self.fee_quote(size+old_size,'fast')-old_fee,
                    (old_fee*size+old_size-1)//old_size+size)
            if fee>MAX_FEE:raise ValueError('Fee increase exceeds the spending limit.')
            if total>=fee+294:break
            if coins is None:coins=iter(c for c in self.coins(key) if (c['txid'],c['index']) not in reserved)
            coin=next(coins,None)
            if coin is None:raise ValueError('Additional confirmed funds are needed for the fee increase.')
            selected.append(coin);total+=coin['value']
        child=Transaction(2,tuple(TxInput(bytes.fromhex(c['txid'])[::-1],c['index']) for c in selected),
                          (TxOutput(total-fee,key.script_pubkey),),0)
        for i,c in enumerate(selected):child=sign_p2wpkh(child,i,TxOutput(c['value'],key.script_pubkey),key)
        return {'raw':child.serialize().hex(),'txid':txid(child),'fee':fee,'value':0,'coin':self.coin,
                'inputs':[(c['txid'],c['index']) for c in selected],'package':package,'parent':parent['txid']}

    def preflight(self,operation):
        if not self.info()['active']:raise ValueError('Conditional spending is not active.')
        tx=Transaction.deserialize(bytes.fromhex(operation['raw']))
        if txid(tx)!=operation['txid']:raise ValueError('Changed signed transaction.')
        try:
            known,confirmations=self.transaction(txid(tx))
        except ValueError:known=None
        if known is not None:
            if known.serialize()!=tx.serialize():raise ValueError('Different known witness.')
            if confirmations>0:return txid(tx)
            try:
                if self.rpc.call('getmempoolentry',txid(tx)) is not None:return txid(tx)
            except ValueError:pass
        if self.coin=='SMW':
            preflight=self.rpc.call('testmempoolaccept',operation['raw'])
            if not preflight.get('allowed'):
                raise ValueError('SUMUWW transaction rejected by current node policy: '+str(preflight.get('reject_reason','validation failed')))
        else:
            checks=self.rpc.call('testmempoolaccept',[operation['raw']])
            if not checks or not checks[0].get('allowed'):
                raise ValueError('Bitcoin transaction rejected by current node policy.')
        return None

    def broadcast(self,operation):
        known=self.preflight(operation)
        if known is not None:return known
        tx=Transaction.deserialize(bytes.fromhex(operation['raw']))
        result=self.rpc.call('sendrawtransaction',operation['raw'])
        digest=result if self.coin=='BTC' else result['txid']
        if digest!=txid(tx):raise ValueError('Unexpected broadcast ID.')
        return digest
