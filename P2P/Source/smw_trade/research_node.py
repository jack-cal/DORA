"""Explicit, isolated regtest RPC service for independent-party integration.

Never open an existing public-chain database. No remote mining or key APIs.
This is a research node adapter, not a public SUMUWW protocol activation.
"""
import hmac
import secrets
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from .research_chain import SwapChain
from .orders import canonical, valid_hex
from .network import decode
from .settlement import display, height
from .vault import _write_new
from sumuww.transaction import Transaction
from sumuww.rpc import RpcServer
from types import SimpleNamespace


class ResearchNode:
    def __init__(self, directory, port=0):
        self.directory=Path(directory);self.directory.mkdir(parents=True,exist_ok=True)
        self.database=self.directory/'smw-regtest.sqlite';self.token_file=self.directory/'rpc.token'
        if self.database.exists():
            # SwapChain itself verifies the database network before opening.
            with SwapChain(self.database):pass
        else:
            with SwapChain(self.database):pass
        if not self.token_file.exists():_write_new(self.token_file,secrets.token_hex(32).encode())
        self.token=self.token_file.read_text().strip()
        if not valid_hex(self.token,32):raise ValueError('Invalid research node token')
        self.lock=threading.RLock();owner=self
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*args):pass
            def do_POST(self):
                self.connection.settimeout(10)
                identifier=None
                try:
                    if (self.path!='/rpc' or self.headers.get('Origin') or self.headers.get('Transfer-Encoding')
                        or self.headers.get('Host')!=f'127.0.0.1:{owner.port}'
                        or not hmac.compare_digest(self.headers.get('Authorization',''),'Bearer '+owner.token)):
                        raise ValueError('Unauthorized request')
                    count=int(self.headers.get('Content-Length','0'))
                    if not 0<count<=8*1024*1024:raise ValueError('Invalid frame')
                    value=decode(self.rfile.read(count));identifier=value['id']
                    result=owner.call(value['method'],value.get('params',[]))
                    response={'jsonrpc':'2.0','id':identifier,'result':result}
                except Exception:
                    response={'jsonrpc':'2.0','id':identifier,'error':{'code':-32000,'message':'Rejected regtest node request'}}
                raw=canonical(response)
                self.send_response(200);self.send_header('Content-Type','application/json')
                self.send_header('Content-Length',str(len(raw)));self.send_header('Connection','close')
                self.end_headers();self.wfile.write(raw)
        self.server=ThreadingHTTPServer(('127.0.0.1',port),Handler)
        self.server.daemon_threads=True;self.port=self.server.server_port
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True)

    def start(self):self.thread.start();return self
    def close(self):self.server.shutdown();self.server.server_close();self.thread.join(5)

    def call(self,method,args):
        with self.lock,SwapChain(self.database) as chain:
            # Actual existing SUMUWW RPC dispatcher, used by read-only wallet links.
            if not method.startswith('swap'):
                node=SimpleNamespace(chain=chain,running=True,synchronization_info=lambda:{})
                rpc=RpcServer(lambda:node,token=self.token)
                return rpc.call(method,args)
            def transactions():
                for h,(_,block) in enumerate(chain._path(chain.tip_hash)):
                    for tx in block.transactions:yield tx,height(chain)-h+1
                for tx in chain.mempool_transactions():yield tx,0
            if method=='swapinfo' and not args:
                return {'network':'regtest','genesis':chain.network.genesis.block_hash()[::-1].hex(),
                        'height':height(chain),'htlc':'exact-p2wsh-htlc-v1'}
            if method=='swapcoins' and len(args)==1:
                script=bytes.fromhex(args[0])
                pending={(i.prev_txid,i.prev_index) for tx in chain.mempool_transactions() for i in tx.inputs}
                return [{'txid':p[0][::-1].hex(),'vout':p[1],'value':c.output.value,'script':c.output.script_pubkey.hex()}
                        for p,c in chain.list_utxos(script) if p not in pending and (not c.coinbase or height(chain)+1-c.height>=100)]
            if method=='swapoutput' and len(args)==2:
                txid,index=args
                pending={(i.prev_txid,i.prev_index) for tx in chain.mempool_transactions() for i in tx.inputs}
                point=(bytes.fromhex(txid)[::-1],index)
                for p,c in chain.list_utxos():
                    if p==point and p not in pending:
                        return {'value':c.output.value,'script':c.output.script_pubkey.hex(),
                                'confirmations':height(chain)-c.height+1,'coinbase':c.coinbase}
                return None
            if method=='swaptransaction' and len(args)==1:
                for tx,count in transactions():
                    if display(tx)==args[0]:return {'hex':tx.serialize().hex(),'confirmations':count}
                raise ValueError('Transaction not found')
            if method=='swapbroadcast' and len(args)==1:
                tx=Transaction.deserialize(bytes.fromhex(args[0]))
                for known,count in transactions():
                    if known.txid()==tx.txid():
                        if known.serialize()!=tx.serialize():raise ValueError('Witness mismatch')
                        return display(tx)
                chain.submit_transaction(tx);return display(tx)
            if method=='swapfindspend' and len(args)==3:
                txid,index,start=args
                for tx,count in transactions():
                    if count<1:continue
                    if any(i.prev_txid==bytes.fromhex(txid)[::-1] and i.prev_index==index for i in tx.inputs):return display(tx)
                return None
            raise ValueError('Unknown research node request')

    def __enter__(self):return self.start()
    def __exit__(self,*args):self.close()
