"""Automatic contact discovery and reconnect, separate from coin consensus.

LAN hints are signed and source-address bounded. Public DHT hints can only
target public IPs. Neither mechanism grants spending authority or proves funds.
No firewall or router configuration is modified.
"""
import asyncio,hashlib,ipaddress,json,queue,secrets,socket,struct,threading,time
from ..orders import canonical
from .secure_transport import endpoint,verify
from sumuww.dht_discovery import DhtDiscovery
from sumuww.self_address import enumerate_ipv4_interfaces

GROUP='239.255.83.77'
PORT=18487
LAN_RANGES=tuple(ipaddress.ip_network(n) for n in ('10.0.0.0/8','172.16.0.0/12','192.168.0.0/16'))


def lan_address(host):
    ip=ipaddress.ip_address(host)
    if not any(ip in net for net in LAN_RANGES):raise ValueError('Not a LAN source.')
    return str(ip)


class LanHints(asyncio.DatagramProtocol):
    def __init__(self,network):
        self.network=network;self.transport=None;self.count=0;self.window=0

    def connection_made(self,transport):self.transport=transport

    def datagram_received(self,raw,address):
        now=int(time.monotonic())
        if now!=self.window:self.window,self.count=now,0
        self.count+=1
        if self.count>40 or len(raw)>2048:return
        try:
            host=lan_address(address[0]);body=verify(json.loads(raw))
            if set(body)!={'protocol','maker','port','time'} or body['protocol']!=self.network.app.relay.protocol or body['maker']==self.network.app.store.identity.public:
                return
            if type(body['time']) is not int or abs(time.time()-body['time'])>90:return
            self.network.offer(host,body['port'],body['maker'],False)
        except Exception:return


class AutoNetwork:
    def __init__(self,app):
        self.app=app;self.stopped=threading.Event();self.pending=queue.Queue(maxsize=128)
        self.retry={};self.lock=threading.Lock();self.interfaces=();self.dht=None;self.dht6=None;self.lan=None
        self.status={'state':'starting','lan':False,'public_discovery':False,'attempts':0,'connected':0}
        self.thread=threading.Thread(target=self.run,daemon=True)
        self.connector=threading.Thread(target=self.connect_loop,daemon=True)

    def start(self):self.connector.start();self.thread.start();return self

    def offer(self,host,port,identity=None,public=True):
        target=endpoint(host,port,public=public)
        with self.lock:
            if time.monotonic()<self.retry.get(target,0):return
            self.retry[target]=time.monotonic()+30
            if len(self.retry)>256:self.retry.pop(next(iter(self.retry)))
        try:self.pending.put_nowait((target,identity,public))
        except queue.Full:pass

    def public_hints(self,values):
        for host,port in values:
            try:self.offer(host,port,public=True)
            except ValueError:pass

    def connect_loop(self):
        while not self.stopped.is_set():
            try:target,identity,public=self.pending.get(timeout=.5)
            except queue.Empty:continue
            if self.stopped.is_set():break
            self.status['attempts']+=1
            try:
                self.app.relay.connect(*target,expected=identity,public=public)
                self.status['connected']+=1
            except Exception:pass

    def contact(self,version=4):
        for item in self.interfaces:
            ip=ipaddress.ip_address(item.host)
            if ip.version==version and ip.is_global:return item.host,self.app.relay.address[1]
        return None

    def run(self):
        try:asyncio.run(self.loop())
        except Exception:self.status['state']='unavailable'

    async def loop(self):
        for _ in range(5):
            try:
                self.interfaces=enumerate_ipv4_interfaces();break
            except OSError:await asyncio.sleep(.2)
        addresses=[]
        for item in self.interfaces:
            try:addresses.append(lan_address(item.host))
            except ValueError:pass
        transport=None;sock=None
        try:
            if addresses:
                sock=socket.socket(socket.AF_INET,socket.SOCK_DGRAM,socket.IPPROTO_UDP)
                sock.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
                sock.setsockopt(socket.IPPROTO_IP,socket.IP_MULTICAST_TTL,1)
                sock.setsockopt(socket.IPPROTO_IP,socket.IP_MULTICAST_LOOP,1)
                sock.bind(('0.0.0.0',PORT))
                for host in addresses[:8]:sock.setsockopt(socket.IPPROTO_IP,socket.IP_ADD_MEMBERSHIP,socket.inet_aton(GROUP)+socket.inet_aton(host))
                sock.setblocking(False)
                transport,self.lan=await asyncio.get_running_loop().create_datagram_endpoint(lambda:LanHints(self),sock=sock)
                self.status['lan']=True
        except OSError:
            if sock:sock.close()
            transport=None
        try:
            if self.app.store.network=='mainnet':
                self.dht=DhtDiscovery('dora',self.public_hints,contact_provider=self.contact,
                    connected_provider=lambda:bool(self.app.relay.sessions))
                self.dht.key=hashlib.sha256(b'SUMUWW/market/TLS3/'+self.app.store.network.encode()).digest()[:20]
                await self.dht.start();self.status['public_discovery']=True
                if self.app.relay.address[0]=='::' and self.contact(6):
                    self.dht6=DhtDiscovery('dora',self.public_hints,family=socket.AF_INET6,
                        contact_provider=lambda:self.contact(6),source_provider=lambda:self.contact(6)[0],
                        connected_provider=lambda:bool(self.app.relay.sessions))
                    self.dht6.key=self.dht.key;await self.dht6.start()
            self.status['state']='searching';last=0
            while not self.stopped.is_set():
                if time.monotonic()-last>10:
                    last=time.monotonic()
                    if transport:
                        body={'protocol':self.app.relay.protocol,'maker':self.app.store.identity.public,'port':self.app.relay.address[1],'time':int(time.time())}
                        payload=canonical(self.app.store.identity.sign(body))
                        for host in addresses[:8]:
                            try:
                                sock.setsockopt(socket.IPPROTO_IP,socket.IP_MULTICAST_IF,socket.inet_aton(host));transport.sendto(payload,(GROUP,PORT))
                            except OSError:pass
                    with self.app.store.connect() as db:remembered=db.execute('SELECT host,port,identity FROM peer_pins ORDER BY rowid DESC LIMIT 64').fetchall()
                    for host,port,identity in remembered:
                        try:self.offer(host,port,identity,False)
                        except ValueError:pass
                    for host,port in self.app.config.get('peers',[])[:24]:
                        try:self.offer(host,port,public=False)
                        except ValueError:pass
                self.status['state']='connected' if self.app.relay.sessions else 'searching'
                await asyncio.sleep(.5)
        finally:
            if transport:transport.close()
            if self.dht:await self.dht.stop()
            if self.dht6:await self.dht6.stop()
            self.status['state']='stopped'

    def close(self):
        self.stopped.set();self.thread.join(3);self.connector.join(6)
