"""Bounded, bidirectional TLS 1.3 sessions authenticated by board identities.

Discovery is only a contact hint. Certificates prove the order-signing key;
endpoint pins prevent silent key changes. Wallet keys never enter this module.
"""
import collections,datetime,ipaddress,secrets,socket,socketserver,ssl,threading,time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from cryptography import x509
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from cryptography.x509.oid import NameOID
from ..network import decode,FRAME_BYTES
from ..orders import canonical,valid_hex
from ..vault import _write_new

MAX_PEERS=24
MAX_PENDING=16
MAX_REQUESTS=32
TIMEOUT=60


def endpoint(host,port,*,public=False):
    if not isinstance(host,str) or '%' in host:raise ValueError('Invalid peer address.')
    ip=ipaddress.ip_address(host)
    if ip.is_unspecified or ip.is_multicast or ip.is_link_local or ip.is_reserved or type(port) is not int or not 1<=port<=65535:
        raise ValueError('Invalid peer address.')
    if public and not ip.is_global:raise ValueError('Public discovery cannot connect to private addresses.')
    return str(ip),port


def frame(stream):
    raw=stream.readline(FRAME_BYTES+1)
    if len(raw)>FRAME_BYTES or not raw.endswith(b'\n'):raise ValueError('Invalid frame.')
    message=decode(raw)
    if not isinstance(message,dict):raise ValueError('Invalid message.')
    return message


def wire(sock,message):
    raw=canonical(message)+b'\n'
    if len(raw)>FRAME_BYTES:raise ValueError('Message byte budget exceeded.')
    sock.sendall(raw)


def verify(packet):
    if not isinstance(packet,dict) or set(packet)!={'body','signature'}:raise ValueError('Invalid identity proof.')
    body=packet['body']
    if not isinstance(body,dict) or not valid_hex(body.get('maker'),32) or not valid_hex(packet['signature'],64):raise ValueError('Invalid identity proof.')
    Ed25519PublicKey.from_public_bytes(bytes.fromhex(body['maker'])).verify(bytes.fromhex(packet['signature']),canonical(body))
    return body


def server_context(board):
    now=datetime.datetime.now(datetime.timezone.utc)
    name=x509.Name([x509.NameAttribute(NameOID.COMMON_NAME,'SUMUWW P2P')])
    cert=(x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(board.identity.key.public_key())
          .serial_number(x509.random_serial_number()).not_valid_before(now-datetime.timedelta(minutes=5))
          .not_valid_after(now+datetime.timedelta(days=7)).sign(board.identity.key,None))
    password=secrets.token_bytes(32)
    # Only an encrypted temporary copy is needed for OpenSSL's file API.
    path=board.directory/('transport-'+secrets.token_hex(16)+'.tmp')
    payload=cert.public_bytes(serialization.Encoding.PEM)+board.identity.key.private_bytes(
        serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.BestAvailableEncryption(password))
    context=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER);context.minimum_version=ssl.TLSVersion.TLSv1_3
    try:
        _write_new(path,payload);context.load_cert_chain(str(path),password=password)
    finally:path.unlink(missing_ok=True)
    return context


class Session:
    def __init__(self,owner,sock,stream,identity,outgoing):
        self.owner,self.sock,self.stream,self.identity=owner,sock,stream,identity
        self.outgoing=outgoing;self.closed=threading.Event();self.send_lock=threading.Lock();self.lock=threading.Lock()
        self.pending={};self.seen=collections.deque(maxlen=128);self.started=False;self.cursor=0
        self.tokens=32.;self.tick=time.monotonic();self.thread=threading.Thread(target=self.read,daemon=True)

    def start(self):self.started=True;self.thread.start();return self

    def send(self,message):
        with self.send_lock:
            if self.closed.is_set():raise OSError('Peer disconnected.')
            wire(self.sock,message)

    def request(self,body):
        ident=secrets.token_hex(16);event=threading.Event();result=[]
        with self.lock:
            if len(self.pending)>=MAX_PENDING:raise ValueError('Peer request limit reached.')
            self.pending[ident]=(event,result)
        try:
            self.send({'id':ident,'request':body})
            if not event.wait(TIMEOUT):raise OSError('Peer request timed out.')
            if not result:raise OSError('Peer disconnected.')
            response=result[0]
            if response.get('error'):raise ValueError(response['error'])
            return response
        finally:
            with self.lock:self.pending.pop(ident,None)

    def read(self):
        try:
            while not self.closed.is_set():
                msg=frame(self.stream)
                if not valid_hex(msg.get('id'),16):raise ValueError('Invalid request identifier.')
                if set(msg)=={'id','response'}:
                    if not isinstance(msg['response'],dict):raise ValueError('Invalid reply.')
                    with self.lock:
                        pending=self.pending.get(msg['id'])
                        if pending and not pending[0].is_set():pending[1].append(msg['response']);pending[0].set()
                    continue
                if set(msg)!={'id','request'} or not isinstance(msg['request'],dict) or msg['id'] in self.seen:raise ValueError('Invalid or repeated request.')
                now=time.monotonic();self.tokens=min(32.,self.tokens+(now-self.tick)*8);self.tick=now
                if self.tokens<1:raise ValueError('Peer rate limit exceeded.')
                self.tokens-=1;self.seen.append(msg['id'])
                if not self.owner.allow_request():raise ValueError('Global request limit exceeded.')
                if not self.owner.slots.acquire(blocking=False):raise ValueError('Request capacity reached.')
                try:self.owner.workers.submit(self.respond,msg)
                except BaseException:self.owner.slots.release();raise
        except (OSError,ValueError,TypeError,RecursionError):pass
        finally:
            self.close();self.stream.close()

    def respond(self,msg):
        try:
            try:reply=self.owner.handle(msg['request'],self.identity)
            except Exception:reply={'error':'Invalid or unavailable signed request.'}
            try:self.send({'id':msg['id'],'response':reply})
            except (OSError,ValueError):self.close()
        finally:self.owner.slots.release()

    def close(self):
        if self.closed.is_set():return
        self.closed.set()
        try:self.sock.shutdown(socket.SHUT_RDWR)
        except OSError:pass
        self.sock.close()
        if not self.started:self.stream.close()
        with self.lock:
            for event,_ in self.pending.values():event.set()
        self.owner.drop(self)


class SecureTransport:
    def __init__(self,board,host='127.0.0.1',port=0):
        bind=ipaddress.ip_address(host)
        if bind.is_multicast or type(port) is not int or not 0<=port<=65535:raise ValueError('Invalid listening address.')
        self.store=board;self.protocol='sumuww-market-tls-3/'+board.network
        self.peers=set();self.routes={};self.sessions={};self.endpoints={};self.lock=threading.RLock();self.closed=threading.Event()
        self.slots=threading.BoundedSemaphore(MAX_REQUESTS);self.handshakes=threading.BoundedSemaphore(8)
        self.workers=ThreadPoolExecutor(max_workers=12,thread_name_prefix='p2p-request')
        self.context=server_context(board);self.rates=collections.OrderedDict();self.tokens=64.;self.tick=time.monotonic()
        with board.connect() as db:db.execute('CREATE TABLE IF NOT EXISTS peer_pins (host TEXT,port INTEGER,identity TEXT,PRIMARY KEY(host,port))')
        transport=self
        class Handler(socketserver.BaseRequestHandler):
            def handle(self):transport.accept(self.request)
        class Server(socketserver.ThreadingTCPServer):
            allow_reuse_address=True;daemon_threads=True
            address_family=socket.AF_INET6 if bind.version==6 else socket.AF_INET
            def server_bind(self):
                if bind.version==6 and bind.is_unspecified:self.socket.setsockopt(socket.IPPROTO_IPV6,socket.IPV6_V6ONLY,0)
                super().server_bind()
            def verify_request(self,request,address):
                with transport.lock:
                    if len(transport.sessions)>=MAX_PEERS:return False
                    now=time.monotonic();stamp,count=transport.rates.get(address[0],(now,0))
                    if now-stamp>10:stamp,count=now,0
                    if count>=8:return False
                    transport.rates[address[0]]=(stamp,count+1);transport.rates.move_to_end(address[0])
                    while len(transport.rates)>256:transport.rates.popitem(last=False)
                    return transport.handshakes.acquire(blocking=False)
        self.server=Server((host,port),Handler);self.address=self.server.server_address[:2]
        self.thread=threading.Thread(target=self.server.serve_forever,kwargs={'poll_interval':.1},daemon=True)

    def start(self):self.thread.start();return self

    def allow_request(self):
        with self.lock:
            now=time.monotonic();self.tokens=min(64.,self.tokens+(now-self.tick)*16);self.tick=now
            if self.tokens<1:return False
            self.tokens-=1;return True

    def attach(self,session):
        with self.lock:
            old=self.sessions.get(session.identity)
            if old and not old.closed.is_set():
                preferred=self.store.identity.public<session.identity
                if old.outgoing==preferred or session.outgoing!=preferred:
                    session.close();return old
                old.close()
            if len(self.sessions)>=MAX_PEERS or self.closed.is_set():session.close();raise ValueError('Peer capacity reached.')
            self.sessions[session.identity]=session;self.routes[session.identity]=session.identity
        return session.start()

    def drop(self,session):
        with self.lock:
            if self.sessions.get(session.identity) is session:
                self.sessions.pop(session.identity,None)
                self.routes={key:via for key,via in self.routes.items() if via!=session.identity}

    def accept(self,raw):
        sock=None;stream=None
        try:
            raw.settimeout(5);sock=self.context.wrap_socket(raw,server_side=True);stream=sock.makefile('rb')
            challenge=secrets.token_hex(32)
            wire(sock,{'protocol':self.protocol,'challenge':challenge,'node':self.store.identity.public})
            packet=frame(stream);body=verify(packet)
            if set(body)!={'protocol','challenge','server','maker','nonce'} or body['protocol']!=self.protocol or body['challenge']!=challenge or body['server']!=self.store.identity.public or not valid_hex(body['nonce'],32) or body['maker']==self.store.identity.public:
                raise ValueError('Invalid handshake.')
            wire(sock,self.store.identity.sign({'protocol':self.protocol,'challenge':challenge,'client':body['maker'],'nonce':body['nonce'],'maker':self.store.identity.public}))
            sock.settimeout(90);self.attach(Session(self,sock,stream,body['maker'],False));sock=None
        except Exception:pass
        finally:
            if sock:
                sock.close()
                if stream:stream.close()
            if sock is not None or raw.fileno()!=-1:raw.close()
            self.handshakes.release()

    def dial(self,host,port,expected=None,public=False):
        target=endpoint(host,port,public=public)
        with self.lock:
            peer=self.endpoints.get(target);current=self.sessions.get(peer)
            if current and not current.closed.is_set():return current
            if len(self.sessions)>=MAX_PEERS:raise ValueError('Peer capacity reached.')
        with self.store.connect() as db:pin=db.execute('SELECT identity FROM peer_pins WHERE host=? AND port=?',target).fetchone()
        if pin:
            if expected and expected!=pin[0]:raise ValueError('Peer identity changed.')
            expected=pin[0]
        raw=socket.create_connection(target,timeout=5);sock=None;stream=None
        try:
            context=ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT);context.minimum_version=ssl.TLSVersion.TLSv1_3
            context.check_hostname=False;context.verify_mode=ssl.CERT_NONE
            sock=context.wrap_socket(raw,server_hostname=None)
            cert=x509.load_der_x509_certificate(sock.getpeercert(binary_form=True));key=cert.public_key()
            if not isinstance(key,Ed25519PublicKey):raise ValueError('Wrong peer certificate key.')
            key.verify(cert.signature,cert.tbs_certificate_bytes)
            identity=key.public_bytes(serialization.Encoding.Raw,serialization.PublicFormat.Raw).hex()
            if expected and identity!=expected:raise ValueError('Peer identity changed.')
            if identity==self.store.identity.public:raise ValueError('Cannot connect to self.')
            stream=sock.makefile('rb');hello=frame(stream)
            if set(hello)!={'protocol','challenge','node'} or hello['protocol']!=self.protocol or hello['node']!=identity or not valid_hex(hello['challenge'],32):raise ValueError('Wrong peer handshake.')
            nonce=secrets.token_hex(32)
            wire(sock,self.store.identity.sign({'protocol':self.protocol,'challenge':hello['challenge'],'server':identity,'maker':self.store.identity.public,'nonce':nonce}))
            body=verify(frame(stream))
            if body!={'protocol':self.protocol,'challenge':hello['challenge'],'client':self.store.identity.public,'nonce':nonce,'maker':identity}:raise ValueError('Peer handshake proof mismatch.')
            sock.settimeout(90);session=self.attach(Session(self,sock,stream,identity,True));sock=None
            with self.store.connect() as db:
                db.execute('INSERT OR IGNORE INTO peer_pins VALUES(?,?,?)',(*target,identity))
                if db.execute('SELECT identity FROM peer_pins WHERE host=? AND port=?',target).fetchone()[0]!=identity:
                    session.close();raise ValueError('Peer identity changed.')
            with self.lock:self.endpoints[target]=identity;self.peers.add(target)
            return session
        finally:
            if sock:
                sock.close()
                if stream:stream.close()
            if raw.fileno()!=-1:raw.close()

    def close(self):
        if self.closed.is_set():return
        self.closed.set();self.server.shutdown();self.server.server_close()
        with self.lock:sessions=list(self.sessions.values())
        for session in sessions:session.close()
        self.thread.join(2);self.workers.shutdown(wait=True,cancel_futures=True)
