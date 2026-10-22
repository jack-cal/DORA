"""Authenticated local solo Stratum V1 bridge to SHA-256d ASIC devices.

No pooled shares, payment ledger or reward redistribution. The coinbase pays
the selected wallet; ordinary Chain.accept_block validates the complete block.
"""
import json
import secrets
import selectors
import socket
import struct
import time
from dataclasses import replace
from .block import Block
from .primitives import sha256d, merkle_root, valid_target, check_pow

def word_swap(raw):
    return b''.join(raw[i:i+4][::-1] for i in range(0,len(raw),4))

def coinbase_parts(block):
    original=block.transactions[0]
    script=original.inputs[0].script_sig
    if len(script)<5 or script[-5]!=4:
        raise ValueError('Unsupported coinbase extra-nonce layout')
    marker=secrets.token_bytes(8)
    coinbase=replace(original,inputs=(replace(original.inputs[0],script_sig=script[:-5]+b'\x08'+marker),))
    raw=coinbase.serialize(include_witness=False)
    # Serialized one-input coinbase: version + input count + outpoint + script length.
    offset=4+1+36+1+len(script)-5+1
    if raw[offset:offset+8]!=marker:
        raise ValueError('Invalid coinbase serialization offset')
    return coinbase,raw[:offset],raw[offset+8:]

def coinbase_branch(transactions):
    level=[t.txid() for t in transactions];branch=[]
    while len(level)>1:
        if len(level)%2:level.append(level[-1])
        branch.append(level[1])
        level=[sha256d(level[i]+level[i+1]) for i in range(0,len(level),2)]
    return branch

class StratumMiner:
    mode='asic'
    def __init__(self,host,port,password):
        self.password=password
        self.selector=selectors.DefaultSelector();self.clients={};self.job=None
        self.listener=socket.socket(socket.AF_INET,socket.SOCK_STREAM)
        try:
            # Do not reuse another node's port or silently choose another port.
            self.listener.bind((host,port));self.listener.listen(4);self.listener.setblocking(False)
            self.selector.register(self.listener,selectors.EVENT_READ)
            self.endpoint=self.listener.getsockname()
        except BaseException:
            self.listener.close();self.selector.close();raise
    def _drop(self,sock):
        self.clients.pop(sock,None)
        try:self.selector.unregister(sock)
        except (KeyError,ValueError):pass
        sock.close()
    def _send(self,sock,value):
        data=(json.dumps(value,separators=(',',':'))+'\n').encode()
        c=self.clients[sock]
        if len(c['out'])+len(data)>65536:
            self._drop(sock);return
        c['out']+=data;self.selector.modify(sock,selectors.EVENT_READ|selectors.EVENT_WRITE)
    def _reply(self,sock,request,result=None,error=None):
        self._send(sock,{'id':request.get('id'),'result':result,'error':error})
    def _notify(self,sock):
        block,_,one,two=self.job
        difficulty=0xffff*2**208/valid_target(block.header.bits,(1<<256)-1)
        self._send(sock,{'id':None,'method':'mining.set_difficulty','params':[difficulty]})
        self._send(sock,{'id':None,'method':'mining.notify','params':[
            self.job_id,word_swap(block.header.previous_hash).hex(),one.hex(),two.hex(),
            [h.hex() for h in coinbase_branch(block.transactions)],
            f'{block.header.version&0xffffffff:08x}',f'{block.header.bits:08x}',f'{block.header.timestamp:08x}',True]})
    def _request(self,sock,request,pow_limit):
        c=self.clients[sock];method=request.get('method');params=request.get('params',[])
        if type(params) is not list or len(params)>8:raise ValueError('Invalid Stratum parameters')
        if method=='mining.subscribe':
            c['subscribed']=True
            self._reply(sock,request,[[['mining.set_difficulty',c['extra'].hex()],['mining.notify',c['extra'].hex()]],c['extra'].hex(),4])
            if c['authorized']:self._notify(sock)
        elif method=='mining.authorize':
            accepted=len(params)==2 and all(type(v) is str for v in params) and params[0] in ('sumuww','dora') and secrets.compare_digest(params[1],self.password)
            c['authorized']=accepted;self._reply(sock,request,accepted)
            if accepted and c['subscribed']:self._notify(sock)
        elif method=='mining.configure':
            # Explicitly decline extensions; no silent version/difficulty rolling.
            self._reply(sock,request,{'version-rolling':False,'minimum-difficulty':False})
        elif method=='mining.extranonce.subscribe':self._reply(sock,request,True)
        elif method=='mining.submit':
            if not c['authorized'] or not c['subscribed']:
                self._reply(sock,request,False,[24,'Not authorized',None]);return None
            if len(params)!=5 or any(type(v) is not str for v in params):raise ValueError('Invalid submit fields')
            if params[0] not in ('sumuww','dora') or params[1]!=self.job_id:
                self._reply(sock,request,False,[21,'Stale job',None]);return None
            if any(len(v)!=8 for v in params[2:]):raise ValueError('Invalid nonce length')
            extra=bytes.fromhex(params[2]);timestamp=int(params[3],16);nonce=int(params[4],16)
            key=tuple(params[1:])
            if key in c['seen'] or len(c['seen'])>=4096:
                self._reply(sock,request,False,[22,'Duplicate or excessive submissions',None]);return None
            c['seen'].add(key)
            block,cb,_,_=self.job
            if timestamp!=block.header.timestamp:
                self._reply(sock,request,False,[20,'Time rolling not supported',None]);return None
            old=cb.inputs[0].script_sig
            cb=replace(cb,inputs=(replace(cb.inputs[0],script_sig=old[:-8]+c['extra']+extra),))
            txs=(cb,)+block.transactions[1:];root,mutated=merkle_root([t.txid() for t in txs])
            header=replace(block.header,merkle_root=root,nonce=nonce)
            if mutated or not check_pow(header.digest(),header.bits,pow_limit):
                self._reply(sock,request,False,[23,'Proof of work does not meet block target',None]);return None
            self._reply(sock,request,True);return Block(header,txs)
        else:self._reply(sock,request,None,[20,'Unsupported Stratum method',None])
        return None
    def mine(self,block,pow_limit,cancel_check):
        self.job=(block,*coinbase_parts(block));self.job_id=secrets.token_hex(12)
        for sock,c in list(self.clients.items()):
            c['seen'].clear()
            if c['authorized'] and c['subscribed']:self._notify(sock)
        while True:
            if cancel_check and cancel_check():raise RuntimeError('Mining cancelled')
            for sock,c in list(self.clients.items()):
                if time.monotonic()-c['created']>10 and not c['authorized']:self._drop(sock)
            for key,events in self.selector.select(.1):
                sock=key.fileobj
                if sock is self.listener:
                    peer,_=sock.accept();peer.setblocking(False)
                    if len(self.clients)>=4:peer.close();continue
                    self.clients[peer]={'in':b'','out':b'','extra':secrets.token_bytes(4),'authorized':False,'subscribed':False,'created':time.monotonic(),'window':time.monotonic(),'count':0,'seen':set()}
                    self.selector.register(peer,selectors.EVENT_READ);continue
                c=self.clients.get(sock)
                if c is None:continue
                try:
                    if events&selectors.EVENT_WRITE:
                        sent=sock.send(c['out']);c['out']=c['out'][sent:]
                        if not c['out']:self.selector.modify(sock,selectors.EVENT_READ)
                    if not events&selectors.EVENT_READ:continue
                    data=sock.recv(4096)
                    if not data:self._drop(sock);continue
                    c['in']+=data
                    if len(c['in'])>8192:raise ValueError('Frame too large')
                    while b'\n' in c['in']:
                        raw,c['in']=c['in'].split(b'\n',1)
                        if len(raw)>4096:raise ValueError('Frame too large')
                        now=time.monotonic()
                        if now-c['window']>=1:c['window']=now;c['count']=0
                        c['count']+=1
                        if c['count']>100:raise ValueError('Request rate exceeded')
                        request=json.loads(raw)
                        if type(request) is not dict:raise ValueError('Invalid request')
                        result=self._request(sock,request,pow_limit)
                        if result is not None:
                            # Flush the bounded acceptance reply before returning.
                            try:sock.send(c['out']);c['out']=b''
                            except (BlockingIOError,OSError):pass
                            return result
                except (OSError,ValueError,TypeError,RecursionError,KeyError):self._drop(sock)
    def close(self):
        for sock in list(self.clients):self._drop(sock)
        self.listener.close();self.selector.close()
