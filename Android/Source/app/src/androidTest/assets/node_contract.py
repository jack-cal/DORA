"""Disposable node-contract example: public test keys, no customer service.

Run from PC source: python examples/node_contract.py
This is source/test material, never a production node command or mobile bridge.
"""
import asyncio
from dataclasses import replace
import json
from pathlib import Path
import tempfile, sys
if __name__ == "__main__": sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sumuww.address import encode_address
from sumuww.block import GENESIS_TIME
from sumuww.peer import PeerNode
from sumuww.primitives import COIN, hash_to_display
from sumuww.rpc import RpcServer, load_or_create_token
from sumuww.rpc_client import call, RpcCallError
from sumuww.transaction import Transaction, TxInput, TxOutput
from sumuww.wallet import RegtestKey, sign_p2wpkh

async def demonstrate():
    checks=[]
    with tempfile.TemporaryDirectory(prefix='sumuww-node-contract-') as directory:
        root=Path(directory)
        payer,recipient=RegtestKey.from_int(1),RegtestKey.from_int(2)
        address=encode_address(recipient.script_pubkey)
        token_file=root/'rpc-token'
        node=PeerNode(root/'chain.sqlite',port=0,network='regtest',clock=lambda: GENESIS_TIME+1000)
        blocks=node.chain.mine(payer.script_pubkey,100)
        server=RpcServer(lambda:node,load_or_create_token(token_file),port=0)
        await node.start();await server.start()
        async def rpc(method,params=None):
            return await asyncio.to_thread(call,'http://%s:%s/rpc'%server.address,token_file,method,params)
        async def rejected(method,params,code):
            try:await rpc(method,params)
            except RpcCallError as e:assert e.code==code,(method,e.code)
            else:raise AssertionError('Expected node rejection: '+method)
        try:
            assert (await rpc('validateaddress',{'address':address}))['isvalid']
            assert not (await rpc('validateaddress',{'address':encode_address(recipient.script_pubkey,network='sumuww')}))['isvalid']
            assert not (await rpc('validateaddress',{'address':address[:-1]+('q' if address[-1]!='q' else 'p')}))['isvalid']
            await rejected('validateaddress',{'address':123},-32602)
            checks.append('address checksum, selected network and parameter type')
            previous=blocks[0].transactions[0]
            payload=b'{"p":"fixture","op":"data","n":1}'
            script=b'\x6a'+bytes([len(payload)])+payload
            unsigned=Transaction(2,(TxInput(previous.txid(),0),),(
                TxOutput(3*COIN,recipient.script_pubkey),
                TxOutput(47*COIN-100000,payer.script_pubkey),TxOutput(0,script)))
            decoded=await rpc('decoderawtransaction',{'hex':unsigned.serialize().hex()})
            assert decoded['validation']=='decoded_only' and 'in_mempool' not in decoded and 'confirmations' not in decoded
            assert decoded['outputs'][2]['script_pubkey']==script.hex()
            assert await rpc('getrawmempool')==[]
            await rejected('sendrawtransaction',{'hex':unsigned.serialize().hex()},-32002)
            await rejected('decoderawtransaction',{'hex':'00'},-32002)
            checks.append('decoding does not imply signature validity, acceptance or confirmation')
            # Public fixture signing models an external caller; the RPC accepts bytes only.
            signed=sign_p2wpkh(unsigned,0,previous.outputs[0],payer)
            invalid=replace(signed,inputs=(replace(signed.inputs[0],witness=(recipient.sign_digest(bytes(32))+b'\x01',payer.pubkey)),))
            await rejected('sendrawtransaction',{'hex':invalid.serialize().hex()},-32002)
            accepted=await rpc('sendrawtransaction',{'hex':signed.serialize().hex()})
            txid=hash_to_display(signed.txid())
            assert accepted=={'accepted':True,'txid':txid}
            await rejected('sendrawtransaction',{'hex':signed.serialize().hex()},-32002)
            conflict=replace(unsigned,outputs=(TxOutput(50*COIN-99000,payer.script_pubkey),))
            conflict=sign_p2wpkh(conflict,0,previous.outputs[0],payer)
            await rejected('sendrawtransaction',{'hex':conflict.serialize().hex()},-32006)
            pending=await rpc('getrawtransaction',{'txid':txid})
            assert pending['in_mempool'] and pending['confirmations']==0
            checks.append('external signed bytes accepted; bad signature, duplicate and underpriced replacement rejected')
            node.chain.mine(payer.script_pubkey,2)
            confirmed=await rpc('getrawtransaction',{'txid':txid})
            assert confirmed['confirmations']==2 and not confirmed['in_mempool']
            old_hash=confirmed['blockhash']
            records=await rpc('getdatarecords',{'blockhash':old_hash})
            record=next(r for r in records['records'] if r['txid']==txid)
            assert records['active'] and record['script_pubkey']==script.hex()
            assert record['transaction_index']==1
            assert (await rpc('gettxout',{'txid':txid,'index':0}))['value_units']==3*COIN
            assert await rpc('gettxout',{'txid':txid,'index':2}) is None
            assert signed.serialize().hex() in json.dumps(await rpc('getblock',{'hash':old_hash}))
            checks.append('active-chain confirmations, spendable output and raw data lookup')
            parent=blocks[-1].block_hash()
            for nonce in (11,12,13):
                alt=node.chain.make_block(payer.script_pubkey,transactions=(),parent_hash=parent,extra_nonce=nonce)
                node.chain.accept_block(alt);parent=alt.block_hash()
            inactive=await rpc('getblock',{'hash':old_hash})
            assert inactive['active'] is False and inactive['confirmations']==-1
            stored=await rpc('getdatarecords',{'blockhash':old_hash})
            assert stored['active'] is False and record in stored['records']
            assert signed.serialize().hex() in json.dumps(inactive)
            reverted=await rpc('getrawtransaction',{'txid':txid})
            assert reverted['in_mempool'] and reverted['confirmations']==0
            assert await rpc('gettxout',{'txid':txid,'index':0}) is None
            checks.append('reorganization changes active block and confirmation state without erasing stored block')
            node.chain.mine(payer.script_pubkey,1)
            again=await rpc('getrawtransaction',{'txid':txid})
            assert again['confirmations']==1 and again['blockhash']!=old_hash
            checks.append('same transaction reconfirms on replacement chain')
            for method in ('signrawtransaction','walletpassphrase','observe','sweep','withdraw','createtoken','gettokenbalance'):
                await rejected(method,{},-32601)
            checks.append('no custody, exchange accounting or token-operation RPC methods')
        finally:await server.stop();await node.stop()
        reopened=PeerNode(root/'chain.sqlite',port=0,network='regtest',clock=lambda: GENESIS_TIME+1000)
        await reopened.start()
        try:
            saved=RpcServer(lambda:reopened,'a'*64,port=0).call('getrawtransaction',{'txid':txid})
            assert saved['outputs'][2]['script_pubkey']==script.hex() and saved['confirmations']==1
            checks.append('arbitrary data persists across chain database reopen')
        finally:await reopened.stop()
    return {'network':'disposable regtest','public_test_keys_only':True,
            'persistent_user_data_accessed':False,'real_token_issued':False,'passed':len(checks),'checks':checks}

if __name__=='__main__':print(json.dumps(asyncio.run(demonstrate()),indent=2))
