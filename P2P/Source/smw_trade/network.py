"""Real TCP regtest order relay. No public discovery/mainnet transport implied."""
import json, socket, socketserver, threading, ipaddress
from .orders import canonical

FRAME_BYTES = 128 * 1024  # Message byte budget, not a peer/responder count cap.

def decode(raw):
    def pairs(items):
        d={}
        for k,v in items:
            if k in d: raise ValueError('Duplicate JSON key')
            d[k]=v
        return d
    return json.loads(raw, object_pairs_hook=pairs, parse_constant=lambda _: (_ for _ in ()).throw(ValueError('Invalid JSON number')))

def exchange(endpoint, packet):
    with socket.create_connection(endpoint,timeout=5) as c:
        c.settimeout(5)
        wire=canonical(packet)+b'\n'
        if len(wire)>FRAME_BYTES: raise ValueError('Message byte budget')
        c.sendall(wire)
        f=c.makefile('rb'); raw=f.readline(FRAME_BYTES+1)
        if not raw.endswith(b'\n') or len(raw)>FRAME_BYTES: raise ValueError('Invalid frame')
        response=decode(raw)
        if response.get('error'): raise ValueError(response['error'])
        return response

class Relay:
    def __init__(self, store, host='127.0.0.1',port=0):
        bind=ipaddress.ip_address(host)
        if bind.is_multicast:raise ValueError('Invalid listening address')
        self.store=store; self.peers=set(); self.routes={}; self.lock=threading.Lock()
        self.swap_handler=None
        relay=self
        class Handler(socketserver.StreamRequestHandler):
            def handle(self):
                self.request.settimeout(5)
                try:
                    raw=self.rfile.readline(FRAME_BYTES+1)
                    if len(raw)>FRAME_BYTES or not raw.endswith(b'\n'): raise ValueError('Invalid frame')
                    reply=relay.handle(decode(raw))
                except Exception:
                    reply={'error':'Invalid or unavailable signed request'}
                self.wfile.write(canonical(reply)+b'\n')
        class Server(socketserver.ThreadingTCPServer):
            allow_reuse_address=True
            daemon_threads=True
            address_family=socket.AF_INET6 if bind.version==6 else socket.AF_INET
        self.server=Server((host,port),Handler)
        self.address=self.server.server_address
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True)

    def start(self): self.thread.start(); return self
    def close(self): self.server.shutdown();self.server.server_close();self.thread.join(5)

    def handle(self, message):
        if message.get('protocol')!='smw-trade-regtest-1': raise ValueError('Wrong network')
        kind=message.get('type')
        if kind=='swap':
            if self.swap_handler is None:raise ValueError('Independent swap is not configured/prepared')
            return {'packet':self.swap_handler(message['packet'])}
        if kind=='push':
            packet=message['packet']
            seen=self.store.has_packet(packet)
            if packet['body']['kind']=='order': self.store.import_order(packet)
            else: self.store.import_event(packet)
            if not seen:
                # Forward only authenticated newly persisted messages; no re-signing.
                # Use a background sender so a mesh cycle cannot deadlock handlers.
                threading.Thread(target=self.publish,args=(packet,),daemon=True).start()
            return {'ok':True}
        if kind=='accept':
            confirmation=self.store.reserve(message['packet'])
            threading.Thread(target=self.publish,args=(confirmation,),daemon=True).start()
            return {'confirmation':confirmation}
        if kind=='pull':
            # Cursor pagination avoids building one unbounded response bundle.
            offset=message.get('offset',0)
            if type(offset) is not int or offset<0: raise ValueError('Invalid cursor')
            snapshot=self.store.export(); packets=snapshot['orders']+snapshot['events']
            page=[]; size=64
            for p in packets[offset:]:
                n=len(canonical(p))+1
                if size+n>FRAME_BYTES-1024: break
                size+=n;page.append(p)
            return {'node':self.store.identity.public,'packets':page,'next':offset+len(page) if offset+len(page)<len(packets) else None}
        raise ValueError('Unknown message')

    def connect(self, host,port):
        address=ipaddress.ip_address(host)
        if address.is_unspecified or address.is_multicast or type(port) is not int or not 1<=port<=65535:
            raise ValueError('A peer IP and valid port are required')
        host=str(address)
        endpoint=(host,port); offset=0
        while True:
            response=exchange(endpoint,{'protocol':'smw-trade-regtest-1','type':'pull','offset':offset})
            for p in response['packets']:
                if p['body']['kind']=='order':
                    # Expired history may be omitted without blocking live orders.
                    if p['body']['expires_at']>self.store.clock(): self.store.import_order(p)
                else:
                    try:self.store.import_event(p)
                    except ValueError:pass  # Expired/missing source order.
            if response['next'] is None:break
            if response['next']<=offset:raise ValueError('Non-advancing cursor')
            offset=response['next']
        with self.lock:
            from .orders import valid_hex
            if not valid_hex(response['node'],32):raise ValueError('Invalid peer identity')
            self.peers.add(endpoint)
            self.routes[response['node']]=endpoint
        return len(self.store.listing())

    def publish(self, packet):
        result=[]
        with self.lock:peers=list(self.peers)
        for p in peers:
            try:
                exchange(p,{'protocol':'smw-trade-regtest-1','type':'push','packet':packet});result.append({'peer':p,'delivered':True})
            except (OSError,ValueError):result.append({'peer':p,'delivered':False})
        return result

    def accept(self, endpoint, oid):
        request=self.store.acceptance_request(oid)
        confirmation=exchange(endpoint,{'protocol':'smw-trade-regtest-1','type':'accept','packet':request})['confirmation']
        from .orders import authenticate, order_id
        b=authenticate(confirmation)
        if b['kind']!='reserve' or b['order_id']!=oid or b['session']!=order_id(request['body']):
            raise ValueError('Wrong reservation confirmation')
        self.store.import_event(confirmation)
        from .trades import TradeBook
        TradeBook(self.store).remember(request,confirmation)
        return confirmation

    def sync_swap(self, endpoint, packet):
        response=exchange(endpoint,{'protocol':'smw-trade-regtest-1','type':'swap','packet':packet})
        if self.swap_handler is None:raise ValueError('Independent swap is not configured')
        return self.swap_handler(response['packet'])
