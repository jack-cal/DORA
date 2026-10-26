import json,socket,tempfile,time,unittest
from pathlib import Path
from unittest.mock import patch
from smw_trade.market.application import MarketApplication
from smw_trade.market.auto_network import AutoNetwork,LanHints
from smw_trade.market.secure_transport import endpoint
from smw_trade.orders import canonical
from test_market import ROOT


class SecureMarket(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.apps=[]
    def tearDown(self):
        for app in self.apps:app.close()
        self.temp.cleanup()
    def app(self,name,**kw):
        app=MarketApplication(ROOT,Path(self.temp.name)/name,'test',**kw);self.apps.append(app);return app
    def wait(self,predicate):
        until=time.monotonic()+12
        while not predicate() and time.monotonic()<until:time.sleep(.05)
        self.assertTrue(predicate())

    def test_one_connection_supports_both_directions_and_rejects_plaintext(self):
        a,b=self.app('a'),self.app('b')
        a.connect('127.0.0.1',b.relay.address[1])
        self.assertIn(a.store.identity.public,b.relay.sessions)
        self.assertEqual(next(iter(a.relay.sessions.values())).sock.version(),'TLSv1.3')
        packet=b.store.create('sell','BTC','1','0.01')
        self.assertTrue(b.relay.publish(packet)[0]['delivered'])
        self.assertEqual(len(a.store.listing()),1)
        with socket.create_connection(b.relay.address,timeout=2) as raw:
            raw.sendall(b'{"type":"pull"}\n')
            try:self.assertFalse(raw.recv(100))
            except (ConnectionResetError,OSError):pass
        self.assertEqual(len(b.relay.sessions),1)

    def test_certificate_identity_pin_and_wrong_network(self):
        a,b,c=self.app('a'),self.app('b'),self.app('c')
        target=b.relay.address;a.connect(*target)
        with a.store.connect() as db:db.execute('UPDATE peer_pins SET identity=? WHERE host=? AND port=?',(c.store.identity.public,*target))
        for session in list(a.relay.sessions.values()):session.close()
        with self.assertRaisesRegex(ValueError,'identity changed'):a.connect(*target)
        wrong=MarketApplication(ROOT,Path(self.temp.name)/'wrong','mainnet',auto_network=False);self.apps.append(wrong)
        with self.assertRaises(ValueError):wrong.connect(*target)
        self.assertFalse(list(Path(self.temp.name).rglob('transport-*.tmp')))

    def test_public_hints_cannot_target_local_services(self):
        for host in ('127.0.0.1','10.0.0.1','169.254.169.254','0.0.0.0','224.0.0.1','::1','fe80::1'):
            with self.subTest(host=host),self.assertRaises(ValueError):endpoint(host,80,public=True)
        a,b=self.app('a'),self.app('b');network=AutoNetwork(a);hints=LanHints(network)
        body={'protocol':a.relay.protocol,'maker':b.store.identity.public,'port':b.relay.address[1],'time':int(time.time())}
        packet=b.store.identity.sign(body)
        hints.datagram_received(canonical(packet),('192.168.1.20',18487))
        self.assertEqual(network.pending.qsize(),1)
        packet['body']['port']=80
        hints.datagram_received(canonical(packet),('192.168.1.21',18487))
        self.assertEqual(network.pending.qsize(),1)
        hints.datagram_received(canonical(b.store.identity.sign(body)),('169.254.169.254',18487))
        self.assertEqual(network.pending.qsize(),1)

    def test_discovered_contact_connects_without_user_ip_entry(self):
        a,b=self.app('a'),self.app('b');network=AutoNetwork(a)
        network.connector.start()
        try:
            network.offer(*b.relay.address,identity=b.store.identity.public,public=False)
            self.wait(lambda:b.store.identity.public in a.relay.sessions)
            self.assertIn(a.store.identity.public,b.relay.sessions)
        finally:network.stopped.set();network.connector.join(3)

    def test_malformed_frames_and_route_budget_do_not_reach_wallet(self):
        a,b=self.app('a'),self.app('b');a.connect(*b.relay.address)
        session=a.relay.sessions[b.store.identity.public]
        with patch.object(b,'accept_reservation',side_effect=AssertionError('must not reach wallet')):
            with self.assertRaises(ValueError):session.request({'protocol':a.relay.protocol,'type':'route','target':b.store.identity.public,'hops':999,'message':{}})
        self.assertFalse(b.store.sessions())

    def test_actual_lan_discovery_without_entering_addresses(self):
        from sumuww.self_address import enumerate_ipv4_interfaces
        from smw_trade.market.auto_network import lan_address
        interfaces=enumerate_ipv4_interfaces();available=[]
        for item in interfaces:
            try:available.append(lan_address(item.host))
            except ValueError:pass
        if not available:self.skipTest('No local LAN interface; real LAN discovery cannot be checked here.')
        a,b=self.app('lan-a',auto_network=True),self.app('lan-b',auto_network=True)
        self.wait(lambda:b.store.identity.public in a.relay.sessions)
        self.assertIn(a.store.identity.public,b.relay.sessions)


if __name__=='__main__':unittest.main()
