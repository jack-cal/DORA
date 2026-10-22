"""Disposable actual-chain HTLC checks; no user wallet or public money."""
from dataclasses import replace
import hashlib,json,tempfile
from pathlib import Path
from types import SimpleNamespace
from .chain import Chain
from .wallet import RegtestKey,sign_p2wpkh
from .transaction import Transaction,TxInput,TxOutput
from .htlc import Contract,sign_spend
from .htlc_policy import PUBLIC_HTLC_ACTIVATION_HEIGHT
from .errors import InvalidTransaction,UnsupportedFeature,StorageError
from .rpc import RpcServer


def fund(chain,key,script,value):
    height=chain._row(chain.tip_hash)[2]
    point,coin=next((p,c) for p,c in chain.list_utxos(key.script_pubkey)
                   if not c.coinbase or height+1-c.height>=100)
    tx=Transaction(2,(TxInput(*point),),(TxOutput(value,script),TxOutput(coin.output.value-value-1000,key.script_pubkey)),0)
    tx=sign_p2wpkh(tx,0,coin.output,key)
    chain.submit_transaction(tx);chain.mine(key.script_pubkey)
    return tx


def run(*,activation_height=106,progress=None):
    checks={};seller,buyer=RegtestKey.from_int(8784),RegtestKey.from_int(3848)
    # Advancing an isolated test clock lets thousands of genuine PoW blocks be
    # produced quickly without disabling the unchanged future-time validator.
    now=[2_000_000_000]
    secret=hashlib.sha256(b'isolated HTLC activation check').digest()
    contract=Contract(hashlib.sha256(secret).digest(),buyer.pubkey,seller.pubkey,activation_height+20)
    with tempfile.TemporaryDirectory(prefix='sumuww-htlc-check-') as temp:
        database=Path(temp)/'test.sqlite'
        with Chain(database,htlc_activation=activation_height,clock=lambda:now[0]) as chain:
            remaining=activation_height-3
            while remaining:
                count=min(500,remaining);chain.mine(seller.script_pubkey,count);remaining-=count
                now[0]+=count
                if progress:progress(chain._row(chain.tip_hash)[2])
            funding=fund(chain,seller,contract.script_pubkey,100001000) # N-2
            claim=Transaction(2,(TxInput(funding.txid(),0,sequence=0xFFFFFFFE),),(TxOutput(100000000,buyer.script_pubkey),),0)
            claim=sign_spend(claim,0,funding.outputs[0],contract,buyer,secret=secret)
            try:chain.submit_transaction(claim)
            except UnsupportedFeature:checks['conditional_spend_rejected_before_activation']=True
            else:raise AssertionError('Conditional spend accepted before activation')
            # Existing coins and ordinary transfers work BEFORE the new rule.
            normal=fund(chain,seller,buyer.script_pubkey,200000000) # N-1
            checks['ordinary_transfer_before_activation']=chain.balance(buyer.script_pubkey)==200000000
            assert chain._row(chain.tip_hash)[2]==activation_height-1
            # Candidate height (tip+1), not age of the funding coin, controls validation.
            wrong=replace(claim,inputs=(replace(claim.inputs[0],witness=(claim.inputs[0].witness[0],bytes(32),b'\x01',contract.script)),))
            try:chain.submit_transaction(wrong)
            except InvalidTransaction:checks['wrong_secret_rejected']=True
            else:raise AssertionError('Wrong secret accepted')
            chain.submit_transaction(claim);block=chain.mine(seller.script_pubkey)[0]
            assert chain._row(chain.tip_hash)[2]==activation_height
            checks['conditional_claim_at_activation']=chain.balance(buyer.script_pubkey)==300000000
            checks['pre_activation_coins_spendable']=True
            normal_after=fund(chain,seller,buyer.script_pubkey,400000000)
            checks['ordinary_transfer_after_activation']=chain.balance(buyer.script_pubkey)==700000000
            refund_funding=fund(chain,seller,contract.script_pubkey,100001000)
            refund=Transaction(2,(TxInput(refund_funding.txid(),0,sequence=0xFFFFFFFE),),
                               (TxOutput(100000000,seller.script_pubkey),),contract.refund_height)
            refund=sign_spend(refund,0,refund_funding.outputs[0],contract,seller)
            try:chain.submit_transaction(refund)
            except InvalidTransaction:checks['early_refund_rejected']=True
            else:raise AssertionError('Early refund accepted')
            chain.mine(seller.script_pubkey,contract.refund_height-chain._row(chain.tip_hash)[2])
            chain.submit_transaction(refund);chain.mine(seller.script_pubkey)
            checks['mature_refund_accepted']=any(p[0]==refund.txid() for p,c in chain.list_utxos(seller.script_pubkey))
            node=SimpleNamespace(chain=chain,running=True,synchronization_info=lambda:{})
            rpc=RpcServer(lambda:node,token='1'*64)
            info=rpc.call('gethtlcinfo')
            assert info['active'] and info['activation_height']==activation_height
            output=rpc.call('gettxout',[claim.txid()[::-1].hex(),0])
            observed=rpc.call('findspendingtransaction',[funding.txid()[::-1].hex(),0])
            checks['rpc_chain_observation']=output['value_units']==100000000 and observed['txid']==claim.txid()[::-1].hex()
            state=chain.state_commitment();tip=chain.tip_hash
        with Chain(database,htlc_activation=activation_height,clock=lambda:now[0]) as chain:
            checks['restart_state_preserved']=chain.tip_hash==tip and chain.state_commitment()==state
        try:Chain(database,htlc_activation=activation_height+1)
        except StorageError:checks['activation_change_rejected']=True
        else:raise AssertionError('Activation changed on restart')
        with Chain(Path(temp)/'public.sqlite',network='sumuww') as public:
            checks['public_htlc_height_9100']=public.htlc_activation==9100
            checks['bls_height_9000_unchanged']=public.boundary.activation==9000
    assert all(checks.values())
    return {'passed':True,'public_htlc_activation_height':PUBLIC_HTLC_ACTIVATION_HEIGHT,
            'tested_boundary_height':activation_height,'checks':checks,'public_funds':False,'isolated_virtual_clock':True}


def run_json():return json.dumps(run(),sort_keys=True)
