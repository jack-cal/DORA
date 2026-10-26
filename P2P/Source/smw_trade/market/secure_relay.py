"""Signed board and trade messages over bounded, bidirectional TLS sessions."""
import json,queue,threading
from ..network import FRAME_BYTES
from ..orders import canonical,valid_hex
from .board import authenticate,identifier
from .secure_transport import SecureTransport


class BoardRelay(SecureTransport):
    def __init__(self,board,host='127.0.0.1',port=0):
        super().__init__(board,host,port)
        self.swap_handler=None;self.reserve_handler=None
        self.forward=queue.Queue(maxsize=128);self.revision=0;self.shared=set()
        self.maintenance=threading.Thread(target=self.maintain,daemon=True)

    def start(self):super().start();self.maintenance.start();return self

    def learn(self,packet,source):
        body=authenticate(packet,self.store.network)
        if source and body['maker']!=self.store.identity.public:
            with self.lock:
                if body['maker'] not in self.sessions:
                    if len(self.routes)>=4096:self.routes={k:k for k in self.sessions}
                    self.routes[body['maker']]=source

    def enqueue(self,packet,source=None):
        try:self.forward.put_nowait((packet,source))
        except queue.Full:pass

    def handle(self,message,source=None):
        if message.get('protocol')!=self.protocol:raise ValueError('Different market network.')
        kind=message.get('type')
        if kind=='push':
            packet=message['packet'];added=self.store.import_packet(packet);self.learn(packet,source)
            if added:self.revision+=1;self.enqueue(packet,source)
            return {'ok':True}
        if kind=='pull':
            offset=message.get('offset',0);packets=self.store.export(offset);page=[];size=256
            for packet in packets:
                length=len(canonical(packet))+1
                if size+length>FRAME_BYTES-1024:break
                size+=length;page.append(packet)
            return {'node':self.store.identity.public,'packets':page,'next':offset+len(page) if page else None}
        if kind=='route':
            target=message.get('target');hops=message.get('hops');inner=message.get('message')
            if not valid_hex(target,32) or type(hops) is not int or not 0<=hops<=4 or not isinstance(inner,dict) or set(inner)!={'type','packet'} or inner['type'] not in ('reserve','swap'):
                raise ValueError('Invalid trade route.')
            body=authenticate(inner['packet'],self.store.network)
            if body['kind']!=('request' if inner['type']=='reserve' else 'swap'):raise ValueError('Invalid routed message.')
            self.learn(inner['packet'],source)
            if target!=self.store.identity.public:
                if not hops:raise ValueError('Trade route exhausted.')
                return self.route_request(target,inner,hops-1,exclude=source)
            if inner['type']=='reserve':
                if not self.reserve_handler:raise ValueError('Trading wallet is not ready.')
                packet=self.reserve_handler(inner['packet']);self.revision+=1;self.enqueue(packet)
                return {'packet':packet}
            if not self.swap_handler:raise ValueError('Prepare this trade first.')
            return {'packet':self.swap_handler(inner['packet'])}
        raise ValueError('Unknown market request.')

    def pull(self,session):
        offset=session.cursor
        for _ in range(128):
            result=session.request({'protocol':self.protocol,'type':'pull','offset':offset})
            if result.get('node')!=session.identity or not isinstance(result.get('packets'),list) or len(result['packets'])>64:raise ValueError('Invalid peer history.')
            for packet in result['packets']:
                if self.store.import_packet(packet):self.revision+=1;self.enqueue(packet,session.identity)
                self.learn(packet,session.identity)
            cursor=result.get('next')
            if cursor is None:return
            if type(cursor) is not int or cursor!=offset+len(result['packets']) or cursor<=offset:raise ValueError('Invalid history cursor.')
            offset=cursor;session.cursor=cursor

    def connect(self,host,port,expected=None,public=False):
        session=self.dial(host,port,expected,public);self.pull(session)
        return len(self.store.listing())

    def publish(self,packet,exclude=None):
        with self.lock:sessions=list(self.sessions.values())
        result=[]
        for session in sessions:
            if session.identity==exclude:continue
            try:
                response=session.request({'protocol':self.protocol,'type':'push','packet':packet});ok=response.get('ok') is True
            except (OSError,ValueError):ok=False
            result.append({'peer':session.identity,'delivered':ok})
        if packet['body'].get('kind')=='post' and any(r['delivered'] for r in result):
            with self.lock:self.shared.add(identifier(packet['body']))
        return result

    def route_request(self,identity,inner,hops=4,exclude=None):
        with self.lock:
            via=identity if identity in self.sessions else self.routes.get(identity)
            session=self.sessions.get(via)
        if session is None or via==exclude:raise ValueError('The trading peer is not connected yet.')
        return session.request({'protocol':self.protocol,'type':'route','target':identity,'hops':hops,'message':inner})

    def reserve(self,identity,oid):
        with self.store.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS pending_requests (post TEXT PRIMARY KEY,packet TEXT NOT NULL)')
            row=db.execute('SELECT packet FROM pending_requests WHERE post=?',(oid,)).fetchone()
            request=json.loads(row[0]) if row else self.store.request(oid)
            if request['body']['expires']<=self.store.clock():request=self.store.request(oid)
            db.execute('INSERT OR REPLACE INTO pending_requests VALUES(?,?)',(oid,canonical(request).decode()))
        packet=self.route_request(identity,{'type':'reserve','packet':request})['packet']
        body=authenticate(packet,self.store.network)
        if body.get('request')!=request or body.get('post')!=oid:raise ValueError('Changed reservation terms.')
        self.store.import_packet(packet);return body['session']

    def sync_swap(self,identity,packet):
        response=self.route_request(identity,{'type':'swap','packet':packet})
        if self.swap_handler is None:raise ValueError('Trade engine unavailable.')
        return self.swap_handler(response['packet'])

    def maintain(self):
        while not self.closed.wait(1):
            try:
                for _ in range(32):
                    packet,source=self.forward.get_nowait();self.publish(packet,source)
            except queue.Empty:pass
            with self.lock:sessions=list(self.sessions.values())
            for session in sessions:
                if self.closed.is_set():break
                try:self.pull(session)
                except Exception:session.close()
            if sessions:
                with self.store.connect() as db:
                    for post in self.store.listing():
                        if post['mine'] and post['status']=='active' and post['id'] not in self.shared:
                            packet=json.loads(db.execute('SELECT packet FROM posts WHERE id=?',(post['id'],)).fetchone()[0])
                            self.publish(packet)
            self.closed.wait(4)

    def close(self):
        super().close();self.maintenance.join(3)
