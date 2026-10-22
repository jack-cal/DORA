"""Authenticated board traffic over the application's framed TCP transport."""
import ipaddress, threading
from ..network import Relay, exchange, FRAME_BYTES
from ..orders import canonical, valid_hex
from .board import authenticate

class BoardRelay(Relay):
    def __init__(self,board,host='127.0.0.1',port=0):
        super().__init__(board,host,port)
        self.protocol='sumuww-market-2/'+board.network

    def handle(self,message):
        if message.get('protocol')!=self.protocol:raise ValueError('Different market network.')
        kind=message.get('type')
        if kind=='push':
            if self.store.import_packet(message['packet']):
                threading.Thread(target=self.publish,args=(message['packet'],),daemon=True).start()
            return {'ok':True}
        if kind=='pull':
            offset=message.get('offset',0);packets=self.store.export(offset)
            page=[];size=256
            for p in packets:
                length=len(canonical(p))+1
                if size+length>FRAME_BYTES-1024:break
                size+=length;page.append(p)
            return {'node':self.store.identity.public,'packets':page,'next':offset+len(page) if page else None}
        if kind=='reserve':
            packet=self.store.reserve(message['packet'])
            threading.Thread(target=self.publish,args=(packet,),daemon=True).start()
            return {'packet':packet}
        if kind=='swap':
            if self.swap_handler is None:raise ValueError('Prepare this trade on both devices first.')
            return {'packet':self.swap_handler(message['packet'])}
        raise ValueError('Unknown market request.')

    def connect(self,host,port):
        addr=ipaddress.ip_address(host)
        if addr.is_unspecified or addr.is_multicast or type(port) is not int or not 1<=port<=65535:raise ValueError('Invalid peer address.')
        endpoint=(str(addr),port);offset=0
        while True:
            r=exchange(endpoint,{'protocol':self.protocol,'type':'pull','offset':offset})
            if not valid_hex(r.get('node'),32):raise ValueError('Invalid peer identity.')
            for p in r['packets']:self.store.import_packet(p)
            if r['next'] is None:break
            if type(r['next']) is not int or r['next']<=offset:raise ValueError('Invalid history cursor.')
            offset=r['next']
        with self.lock:self.peers.add(endpoint);self.routes[r['node']]=endpoint
        return len(self.store.listing())

    def publish(self,packet):
        with self.lock:peers=list(self.peers)
        result=[]
        for endpoint in peers:
            try:exchange(endpoint,{'protocol':self.protocol,'type':'push','packet':packet});ok=True
            except (OSError,ValueError):ok=False
            result.append({'peer':endpoint,'delivered':ok})
        return result

    def reserve(self,endpoint,oid):
        request=self.store.request(oid)
        packet=exchange(endpoint,{'protocol':self.protocol,'type':'reserve','packet':request})['packet']
        b=authenticate(packet,self.store.network)
        if b.get('request')!=request or b.get('post')!=oid:raise ValueError('Changed reservation terms.')
        self.store.import_packet(packet);return b['session']

    def sync_swap(self,endpoint,packet):
        response=exchange(endpoint,{'protocol':self.protocol,'type':'swap','packet':packet})
        if self.swap_handler is None:raise ValueError('Trade engine unavailable.')
        return self.swap_handler(response['packet'])
