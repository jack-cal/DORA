"""Independent SUMUWW network survey: DHT/LAN discovery and direct P2P queries.

No miner process, RPC, wallet or chain database is read. Reported activity is
direct protocol response and observed tip changes, never inferred hash power.
"""
import asyncio
import copy
import ipaddress
import json
from pathlib import Path
import secrets
import socket
import sys
import threading
import time

from .block import Block
from .dht_discovery import DhtDiscovery
from .lan_discovery import LanDiscovery
from .network_settings import _atomic_json
from .peer_discovery import discovery_endpoint
from .primitives import check_pow,hash_to_display,merkle_root
from .profiles import get_network
from .self_address import async_enumerate_ipv4_interfaces
from .wire import (Version,Inventory,INV_BLOCK,PeerDisconnected,ProtocolError,
                   encode_version,decode_version,encode_inventory,decode_addresses,
                   read_frame,write_frame)

MAX_CONTACTS=512
PROBE_INTERVAL=30
ACTIVE_SECONDS=75
MAX_CONNECTIONS=64


def format_address(target):
    host,port=target
    return (f'[{host}]:{port}' if ':' in host else f'{host}:{port}')


def tip_height(block,profile):
    if block.block_hash()==profile.genesis.block_hash():return 0
    if not block.transactions or not block.transactions[0].is_coinbase():raise ValueError('Missing coinbase')
    script=block.transactions[0].inputs[0].script_sig
    if not script:raise ValueError('Missing block height')
    if 0x51<=script[0]<=0x60:return script[0]-0x50
    length=script[0]
    if not 1<=length<=5 or len(script)<length+1 or script[length]&0x80:raise ValueError('Invalid block height')
    height=int.from_bytes(script[1:1+length],'little')
    if not 17<=height<(1<<31):raise ValueError('Invalid block height')
    return height


async def inspect_node(target,*,network='dora',scope='lan',timeout=8):
    target=discovery_endpoint(*target,scope=scope)
    profile=get_network(network);started=time.monotonic()
    result={'endpoint':target,'responding':False,'peer_id':None,'tip':None,'height':None,
            'tip_pow_merkle_checked':False,'latency_ms':None,'contacts':[],'error':None}
    async def attempt(protocol):
        writer=None
        try:
            reader,writer=await asyncio.open_connection(*target,
                family=socket.AF_INET6 if ':' in target[0] else socket.AF_INET,limit=64*1024)
            frame=await read_frame(reader,timeout,magic=profile.message_magic)
            if frame.command!='version':raise ProtocolError('Expected version')
            remote=decode_version(frame.payload)
            if remote.genesis!=profile.genesis.block_hash() or remote.profile!=profile.profile_id:
                raise ValueError('Wrong network')
            if remote.protocol not in (1,2,3):raise ValueError('Unsupported protocol')
            protocol=max(protocol,remote.protocol)
            own=Version(protocol,profile.genesis.block_hash(),secrets.randbits(64),profile.profile_id,profile.genesis.block_hash())
            await write_frame(writer,'version',encode_version(own),timeout,magic=profile.message_magic)
            ack=await read_frame(reader,timeout,magic=profile.message_magic)
            if ack.command!='verack' or ack.payload:raise ProtocolError('Invalid acknowledgement')
            result.update(responding=True,peer_id=f'{remote.nonce:016x}',tip=hash_to_display(remote.tip),
                          latency_ms=round((time.monotonic()-started)*1000,1))
            await write_frame(writer,'verack',b'',timeout,magic=profile.message_magic)
            if protocol>=2:await write_frame(writer,'getaddr',b'',timeout,magic=profile.message_magic)
            await write_frame(writer,'getdata',encode_inventory((Inventory(INV_BLOCK,remote.tip),)),timeout,magic=profile.message_magic)
            got_addresses=protocol<2;got_block=False
            for _ in range(32):
                frame=await read_frame(reader,timeout,magic=profile.message_magic)
                if frame.command=='addr':
                    listener,contacts=decode_addresses(frame.payload)
                    for address in ((listener,) if listener else ())+contacts:
                        try:
                            candidate=discovery_endpoint(address.host,address.port,scope=scope)
                            if candidate not in result['contacts']:result['contacts'].append(candidate)
                        except ValueError:pass
                    got_addresses=True
                elif frame.command=='block':
                    block=Block.deserialize(frame.payload)
                    if block.block_hash()!=remote.tip:raise ValueError('Tip block hash mismatch')
                    if not check_pow(remote.tip,block.header.bits,profile.pow_limit):raise ValueError('Invalid tip PoW')
                    root,mutated=merkle_root([tx.txid() for tx in block.transactions])
                    if root!=block.header.merkle_root or mutated:raise ValueError('Invalid tip transactions')
                    result.update(height=tip_height(block,profile),tip_pow_merkle_checked=True)
                    got_block=True
                elif frame.command=='ping':
                    if len(frame.payload)!=8:raise ProtocolError('Invalid ping')
                    await write_frame(writer,'pong',frame.payload,timeout,magic=profile.message_magic)
                elif frame.command=='notfound':break
                # Do not fabricate headers or serve block/transaction data.
                if got_addresses and got_block:break
            return False
        except PeerDisconnected:
            if not result['responding'] and protocol>1:return True
            result['error']='Peer closed connection';return False
        finally:
            if writer is not None:
                writer.close()
                try:await asyncio.wait_for(writer.wait_closed(),.5)
                except (OSError,TimeoutError,asyncio.CancelledError):pass
    async def complete():
        for protocol in (3,2,1):
            if not await attempt(protocol):break
    try:await asyncio.wait_for(complete(),timeout)
    except TimeoutError:result['error']='No response before deadline'
    except (OSError,ValueError,ProtocolError) as error:
        result['error']=str(error) if isinstance(error,(ValueError,ProtocolError)) else 'Connection failed'
        # A malformed advertised block does not count as a working SUMUWW node.
        if isinstance(error,ValueError):result['responding']=False
    return result


class _ListenOnlyLan(LanDiscovery):
    async def _announce(self):
        # The observer has no public node listener and must not announce one.
        await asyncio.Event().wait()


class NetworkSurvey:
    def __init__(self,directory,*,network='dora',scope='lan',initial=(),discover=True,
                 listen=True,listen_host='0.0.0.0',listen_port=18446):
        self.directory=Path(directory);self.profile=get_network(network);self.scope=scope
        self.discover=discover;self.contacts={};self.observations={};self.failures={}
        self._thread=None;self._loop=None;self._stop=None;self._lock=threading.Lock()
        self._state={'running':False,'nodes':[],'candidates':0,'checking':0,'errors':0,'discovery':[]}
        self._stop_requested=threading.Event();self._dht=[];self._lan=None
        self.connections={};self.nonce=secrets.randbits(64);self._servers=[]
        self.listen=listen;self.listen_host=listen_host;self.listen_port=listen_port
        self.own_contacts=set();self._listeners={};self._incoming=set()
        self._refresh_requested=threading.Event()
        for target in initial:self.add(target,'initial')
        self._load_cache()

    def add(self,target,source):
        try:target=discovery_endpoint(*target,scope=self.scope)
        except (ValueError,TypeError):return
        if target in self.own_contacts:return
        if target not in self.contacts and len(self.contacts)<MAX_CONTACTS:
            self.contacts[target]={'source':source,'next':0,'failures':0}

    def _load_cache(self):
        path=self.directory/'network-contacts.json'
        try:
            if path.is_symlink() or path.stat().st_size>65536:return
            value=json.loads(path.read_text(encoding='utf-8'))
            if value.get('profile')!=self.profile.profile_id or value.get('genesis')!=self.profile.genesis.block_hash().hex():return
            for item in value.get('contacts',[])[:MAX_CONTACTS]:
                if time.time()-item['seen']<=86400:self.add((item['host'],item['port']),'monitor cache')
        except (OSError,ValueError,TypeError,KeyError,AttributeError,UnicodeError,RecursionError):pass

    def _save_cache(self):
        contacts=[{'host':host,'port':port,'seen':row['seen']} for (host,port),row in self.observations.items()
                  if row.get('direction','outgoing')=='outgoing'][:MAX_CONTACTS]
        try:_atomic_json(self.directory/'network-contacts.json',{'profile':self.profile.profile_id,
                         'genesis':self.profile.genesis.block_hash().hex(),'contacts':contacts})
        except (OSError,ValueError):pass

    def start(self):
        if self._thread is not None:raise RuntimeError('Survey already started')
        self._thread=threading.Thread(target=self._run_thread,name='sumuww-network-monitor',daemon=True)
        self._thread.start()

    def stop(self):
        self._stop_requested.set()
        if self._loop is not None and self._stop is not None:
            try:self._loop.call_soon_threadsafe(self._stop.set)
            except RuntimeError:pass

    @property
    def stopped(self):return self._thread is None or not self._thread.is_alive()

    def snapshot(self):
        with self._lock:return copy.deepcopy(self._state)

    def request_refresh(self):
        self._refresh_requested.set()

    def observe(self,target,row):
        if target not in self.observations and len(self.observations)>=MAX_CONTACTS:
            active={connection.target for connection in self.connections.values() if connection.ready}
            oldest=min((key for key in self.observations if key not in active),
                       key=lambda key:self.observations[key]['seen'],default=None)
            if oldest is not None:self.observations.pop(oldest,None)
        self.observations[target]=row

    def _publish(self,checking=0,*,running=True,error=None):
        now=time.time();nodes={}
        for connection in self.connections.values():
            if not connection.ready or now-connection.row['seen']>ACTIVE_SECONDS:continue
            row=connection.row;target=connection.target
            key=row['peer_id']
            if key not in nodes:nodes[key]={**row,'addresses':[],'tip_updates':0}
            value=nodes[key];value.pop('aliases',None)
            value['addresses']=sorted({format_address(alias) for alias in row['aliases']})
            value['tip_updates']=max(value['tip_updates'],row.get('tip_updates',0))
            if row['seen']>=value['seen']:
                value.update({name:row[name] for name in ('seen','height','tip','tip_pow_merkle_checked','latency_ms')})
        value={'running':running,'nodes':sorted(nodes.values(),key=lambda row:row['peer_id']),
               'candidates':len(self.contacts),'checking':checking,'errors':len(self.failures),
               'discovery':[item.info() for item in self._dht], 'error':error,
               'lan':self._lan.info() if self._lan else None,
               'scope':'Directly responding discovered SUMUWW peers; no global census or mining-status claim',
               'miner_rpc_wallet_or_chain_read':False}
        value['listeners']=[format_address(target) for target in self.own_contacts]
        value['history']=[{key:val for key,val in row.items() if key!='aliases'}
                          for row in self.observations.values() if row['peer_id'] not in nodes]
        value['attempts']=[{'address':format_address(target),'source':entry['source'],
                            'error':self.failures.get(target)} for target,entry in self.contacts.items()]
        with self._lock:self._state=value

    def listener_for(self,remote_host,protocol=3):
        family=socket.AF_INET6 if ':' in remote_host and protocol>=3 else socket.AF_INET
        return self._listeners.get(family)

    def shareable_contacts(self,protocol):
        contacts=set(self.own_contacts)
        for connection in self.connections.values():
            if connection.ready:
                if connection.outgoing:contacts.add(connection.target)
                if connection.listener:contacts.add(connection.listener)
        return sorted(target for target in contacts if protocol>=3 or ':' not in target[0])[:32]

    async def _connection(self,target,reader=None,writer=None):
        from .network_observer import ObserverConnection
        entry=self.contacts.get(target)
        try:
            for protocol in ((3,2,1) if writer is None else (3,)):
                connection=ObserverConnection(self,target,reader=reader,writer=writer,protocol=protocol)
                self.connections[id(connection)]=connection
                try:
                    await connection.run()
                    if entry:entry['failures']=0
                    break
                except PeerDisconnected:
                    if not connection.handshake_completed and connection.peer_id is not None and protocol>1 and writer is None:
                        continue
                    raise
                finally:self.connections.pop(id(connection),None)
        except (OSError,ValueError,TimeoutError) as error:
            if target not in self.failures and len(self.failures)>=MAX_CONTACTS:
                self.failures.pop(next(iter(self.failures)),None)
            self.failures[target]=(str(error) if isinstance(error,ValueError) else type(error).__name__+': '+str(error))[:180]
            if entry:entry['failures']+=1
        finally:
            if entry:entry['next']=time.monotonic()+min(300,PROBE_INTERVAL*2**min(entry['failures'],4))

    def _accepted(self,reader,writer):
        if self._stop.is_set():writer.close();return
        try:
            host,port,*_=writer.get_extra_info('peername')
            target=discovery_endpoint(host,port,scope=self.scope)
        except (ValueError,TypeError):writer.close();return
        if sum(connection.outgoing for connection in self.connections.values())+len(self._incoming)>=MAX_CONNECTIONS:
            writer.close();return
        task=asyncio.create_task(self._connection(target,reader,writer))
        self._incoming.add(task);task.add_done_callback(self._incoming.discard)

    async def _listen(self,interfaces):
        if not self.listen:return
        hosts=[(self.listen_host,socket.AF_INET6 if ':' in self.listen_host else socket.AF_INET)]
        if self.listen_host=='0.0.0.0':hosts.append(('::',socket.AF_INET6))
        for host,family in hosts:
            try:
                server=await asyncio.start_server(self._accepted,host,self.listen_port,
                    family=family,limit=64*1024,start_serving=True)
            except OSError:continue
            self._servers.append(server)
            port=server.sockets[0].getsockname()[1]
            for item in interfaces:
                if host not in ('0.0.0.0','::') and item.host!=host:continue
                address=ipaddress.ip_address(item.host)
                if address.version!=(6 if family==socket.AF_INET6 else 4):continue
                if address.is_global:
                    target=(item.host,port);self.own_contacts.add(target)
                    self._listeners.setdefault(family,target)
            if host not in ('0.0.0.0','::'):
                self.own_contacts.add((host,port));self._listeners[family]=(host,port)
        for target in self.own_contacts:self.contacts.pop(target,None)

    async def _run(self):
        self._loop=asyncio.get_running_loop();self._stop=asyncio.Event();tasks={};next_batch=0
        if self._stop_requested.is_set():self._stop.set()
        try:
            interfaces=await async_enumerate_ipv4_interfaces()
            await self._listen(interfaces)
            if self.discover:
                source6=next((item.host for item in interfaces if ':' in item.host and ipaddress.ip_address(item.host).is_global),None)
                for family in (socket.AF_INET,socket.AF_INET6):
                    dht=DhtDiscovery(self.profile,lambda hints:[self.add(hint,'DHT') for hint in hints],
                                     family=family,source_provider=(lambda:source6) if family==socket.AF_INET6 else None,
                                     contact_provider=lambda family=family:self._listeners.get(family),interval=60)
                    self._dht.append(dht);await dht.start()
                port=self._servers[0].sockets[0].getsockname()[1] if self._servers else 1
                lan_class=LanDiscovery if self._servers else _ListenOnlyLan
                self._lan=lan_class(self.profile,port,self.nonce,lambda hint:self.add(hint,'LAN'),
                                        tuple(item.host for item in interfaces if ':' not in item.host))
                await self._lan.start()
            while not self._stop.is_set():
                if self._refresh_requested.is_set():
                    self._refresh_requested.clear()
                    for entry in self.contacts.values():entry['next']=min(entry['next'],time.monotonic())
                    for connection in tuple(self.connections.values()):
                        if connection.ready and time.monotonic()-connection.address_request>35:
                            try:await connection.request_addresses()
                            except (OSError,ProtocolError):connection.writer.close()
                for task,target in tuple(tasks.items()):
                    if task.done():
                        try:task.result()
                        except Exception:self.failures[target]='Query failed';self.contacts[target]['next']=time.monotonic()+PROBE_INTERVAL
                        del tasks[task]
                targets=set(tasks.values())
                for connection in self.connections.values():
                    if connection.ready:targets.update(connection.row['aliases'])
                if time.monotonic()>=next_batch:
                    opening=sum(not connection.ready for connection in self.connections.values())
                    for target,entry in sorted(self.contacts.items(),key=lambda item:item[1]['next']):
                        if opening>=2 or len(tasks)+len(self._incoming)>=MAX_CONNECTIONS:break
                        if target not in targets and entry['next']<=time.monotonic():
                            tasks[asyncio.create_task(self._connection(target))]=target
                            targets.add(target)
                            opening+=1
                    next_batch=time.monotonic()+1
                self._publish(sum(not connection.ready for connection in self.connections.values()))
                try:await asyncio.wait_for(self._stop.wait(),.25)
                except TimeoutError:pass
            self._save_cache()
        finally:
            for server in self._servers:server.close()
            for task in tasks:task.cancel()
            for task in self._incoming:task.cancel()
            await asyncio.gather(*tasks,*self._incoming,return_exceptions=True)
            for server in self._servers:await server.wait_closed()
            for dht in self._dht:await dht.stop()
            if self._lan:await self._lan.stop()
            self._publish(running=False)

    def _run_thread(self):
        try:
            # Keep Windows TCP reset cleanup local to this observer's loop;
            # do not change the application's process-wide asyncio policy.
            with asyncio.Runner(loop_factory=asyncio.SelectorEventLoop if sys.platform=='win32' else None) as runner:
                runner.run(self._run())
        except Exception:self._publish(running=False,error='Network discovery failed')
        finally:self._loop=None
