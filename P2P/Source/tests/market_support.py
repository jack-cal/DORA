"""Real current SUMUWW consensus and RPC, disposable regtest database only."""
import json,secrets,threading
from pathlib import Path
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from types import SimpleNamespace
from sumuww.chain import Chain
from sumuww.rpc import RpcServer

class SmwNode:
    def __init__(self,directory):
        self.directory=Path(directory);self.directory.mkdir(parents=True,exist_ok=True)
        self.database=self.directory/'chain.sqlite';self.token_file=self.directory/'rpc.token'
        self.token=secrets.token_hex(32);self.token_file.write_text(self.token)
        self.lock=threading.RLock();self.errors=[]
        with self.chain():pass
        owner=self
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*args):pass
            def do_POST(self):
                packet=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                try:
                    if self.headers.get('Authorization')!='Bearer '+owner.token:raise ValueError('Authentication')
                    with owner.lock,owner.chain() as chain:
                        node=SimpleNamespace(chain=chain,running=True,synchronization_info=lambda:{'sync_state':'ready'})
                        result=RpcServer(lambda:node,token=owner.token).call(packet['method'],packet.get('params',[]))
                    response={'jsonrpc':'2.0','id':packet['id'],'result':result}
                except Exception as exc:
                    owner.errors.append(repr(exc));response={'jsonrpc':'2.0','id':packet['id'],'error':{'message':str(exc)}}
                raw=json.dumps(response).encode();self.send_response(200);self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
        self.server=ThreadingHTTPServer(('127.0.0.1',0),Handler);self.server.daemon_threads=True
        self.port=self.server.server_port;self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
    def chain(self):return Chain(self.database,network='regtest',htlc_activation=1)
    def mine(self,key,count=1):
        with self.lock,self.chain() as chain:return chain.mine(key.script_pubkey,count)
    def close(self):self.server.shutdown();self.server.server_close();self.thread.join(5)
