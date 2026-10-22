import copy, hashlib, json, secrets, tempfile, threading, time, unittest
from dataclasses import replace
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from urllib.request import Request,urlopen,build_opener,ProxyHandler
from urllib.error import HTTPError
from smw_trade.orders import Store, atoms, order_id, authenticate
from smw_trade.network import Relay,exchange
from smw_trade.htlc import Contract,sign_spend,verify_spend
from smw_trade.research_chain import SwapChain
from smw_trade.settlement import key,run_round
from smw_trade.app import serve
from sumuww.transaction import Transaction,TxInput,TxOutput
from sumuww.wallet import sign_p2wpkh

ROOT=Path(__file__).resolve().parents[1]

class OrdersTest(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name);self.now=[1_800_000_000]
        self.a=Store(self.path/'a',clock=lambda:self.now[0]);self.b=Store(self.path/'b',clock=lambda:self.now[0])
    def order(self):return self.a.create('sell','100','0.002')
    def test_exact_amounts(self):
        self.assertEqual(atoms('0.00000001'),1)
        for value in ('0','-1','0.000000001','NaN','Infinity','abc','99999999999999999999999'):
            with self.assertRaises(ValueError):atoms(value)
    def test_real_signature_tamper(self):
        p=self.order();self.b.import_order(p)
        p['body']['btc_sats']+=1
        with self.assertRaises(Exception):self.b.import_order(p)
        self.assertEqual(self.b.listing()[0]['btc_sats'],200000)
    def test_network_replay_rejected(self):
        p=self.order();p['body']['domain']='sumuww-mainnet'
        with self.assertRaises(ValueError):self.b.import_order(p)
    def test_cancel_persist_and_replay(self):
        p=self.order();oid=self.b.import_order(p);self.b.import_event(self.a.cancel(oid))
        self.b=Store(self.path/'b',clock=lambda:self.now[0]);self.b.import_order(p)
        self.assertEqual(self.b.listing()[0]['status'],'canceled')
        with self.assertRaises(ValueError):self.a.reserve(self.b.acceptance_request(oid))
    def test_nonowner_cannot_cancel(self):
        p=self.order();oid=self.b.import_order(p)
        with self.assertRaises(ValueError):self.b.cancel(oid)
        forged=self.b.identity.sign({'domain':p['body']['domain'],'kind':'cancel','maker':self.b.identity.public,'order_id':oid,'session':''})
        with self.assertRaises(ValueError):self.a.import_event(forged)
    def test_expiration(self):
        p=self.order();self.now[0]+=3601
        self.assertEqual(self.a.listing()[0]['status'],'expired')
        with self.assertRaises(ValueError):self.b.import_order(p)
        with self.assertRaises(ValueError):self.a.reserve(self.b.acceptance_request(order_id(p['body'])))
    def test_concurrent_reservation_single_winner(self):
        p=self.order();oid=order_id(p['body'])
        takers=[Store(self.path/f't{i}',clock=lambda:self.now[0]) for i in range(12)]
        requests=[s.acceptance_request(oid) for s in takers]
        def reserve(r):
            try:return self.a.reserve(r)
            except ValueError:return None
        with ThreadPoolExecutor(max_workers=12) as pool:results=list(pool.map(reserve,requests))
        self.assertEqual(sum(r is not None for r in results),1)
        winner=next(i for i,r in enumerate(results) if r is not None)
        self.assertEqual(self.a.reserve(requests[winner]),results[winner])
        self.assertEqual(Store(self.path/'a',clock=lambda:self.now[0]).listing()[0]['status'],'reserved')
    def test_accept_signature_and_expiry(self):
        oid=order_id(self.order()['body']);p=self.b.acceptance_request(oid)
        p['body']['nonce']='ab'*16
        with self.assertRaises(Exception):self.a.reserve(p)
        p=self.b.acceptance_request(oid);self.now[0]+=121
        with self.assertRaises(ValueError):self.a.reserve(p)
    def test_real_tcp_delivery_reservation_and_cancel(self):
        a=Relay(self.a).start();b=Relay(self.b).start();self.addCleanup(a.close);self.addCleanup(b.close)
        p=self.order();oid=order_id(p['body']);b.connect(*a.address)
        result=b.accept(a.address,oid)
        self.assertEqual(authenticate(result)['kind'],'reserve')
        self.assertEqual(self.a.listing()[0]['status'],'reserved')
        self.assertEqual(self.b.listing()[0]['status'],'reserved')
        a.connect(*b.address)
        p2=self.a.create('buy','2','0.0002');oid2=order_id(p2['body'])
        self.assertTrue(a.publish(p2)[0]['delivered'])
        a.publish(self.a.cancel(oid2))
        self.assertEqual(next(o for o in self.b.listing() if o['id']==oid2)['status'],'canceled')
    def test_pagination_has_no_1024_order_cap(self):
        # Every order is independently signed, delivered and verified over TCP.
        for _ in range(1100):self.order()
        relay=Relay(self.a).start();self.addCleanup(relay.close)
        receiver=Relay(self.b).start();self.addCleanup(receiver.close)
        self.assertEqual(receiver.connect(*relay.address),1100)
    def test_failed_peer_does_not_report_delivery(self):
        relay=Relay(self.a).start();self.addCleanup(relay.close)
        relay.peers.add(('127.0.0.1',1))
        self.assertFalse(relay.publish(self.order())[0]['delivered'])
    def test_wrong_transport_network(self):
        relay=Relay(self.a).start();self.addCleanup(relay.close)
        with self.assertRaises(ValueError):exchange(relay.address,{'protocol':'mainnet','type':'pull'})
    def test_mesh_forwarding_without_duplicate_orders(self):
        c=Store(self.path/'c',clock=lambda:self.now[0])
        a=Relay(self.a).start();b=Relay(self.b).start();third=Relay(c).start()
        self.addCleanup(a.close);self.addCleanup(b.close);self.addCleanup(third.close)
        a.connect(*b.address);b.connect(*third.address);third.connect(*a.address)
        p=self.order();a.publish(p)
        deadline=time.monotonic()+5
        while time.monotonic()<deadline and len(c.listing())!=1:time.sleep(.02)
        self.assertEqual(len(c.listing()),1)
        a.publish(p);self.assertEqual(len(self.a.listing()),1)

class ContractTest(unittest.TestCase):
    def setUp(self):
        self.receiver=key();self.refunder=key();self.secret=secrets.token_bytes(32)
        self.contract=Contract(hashlib.sha256(self.secret).digest(),self.receiver.pubkey,self.refunder.pubkey,150)
        self.previous=TxOutput(100000,self.contract.script_pubkey)
        self.tx=Transaction(2,(TxInput(secrets.token_bytes(32),0,sequence=0xFFFFFFFE),),
            (TxOutput(99000,self.receiver.script_pubkey),),0)
    def test_claim_real_signature(self):
        tx=sign_spend(self.tx,0,self.previous,self.contract,self.receiver,secret=self.secret)
        self.assertTrue(verify_spend(tx,0,self.previous))
    def test_wrong_secret(self):
        with self.assertRaises(ValueError):sign_spend(self.tx,0,self.previous,self.contract,self.receiver,secret=secrets.token_bytes(32))
    def test_wrong_key(self):
        with self.assertRaises(ValueError):sign_spend(self.tx,0,self.previous,self.contract,self.refunder,secret=self.secret)
    def test_signature_binds_amount_and_destination(self):
        tx=sign_spend(self.tx,0,self.previous,self.contract,self.receiver,secret=self.secret)
        self.assertFalse(verify_spend(tx,0,replace(self.previous,value=100001)))
        self.assertFalse(verify_spend(replace(tx,outputs=(TxOutput(99000,self.refunder.script_pubkey),)),0,self.previous))
    def test_refund_conditions(self):
        with self.assertRaises(ValueError):sign_spend(self.tx,0,self.previous,self.contract,self.refunder)
        tx=replace(self.tx,lock_time=150)
        signed=sign_spend(tx,0,self.previous,self.contract,self.refunder)
        self.assertTrue(verify_spend(signed,0,self.previous))
        self.assertFalse(verify_spend(replace(signed,inputs=(replace(signed.inputs[0],sequence=0xFFFFFFFF),)),0,self.previous))
    def test_script_tamper_or_noncanonical(self):
        self.assertEqual(Contract.parse(self.contract.script),self.contract)
        with self.assertRaises(Exception):Contract.parse(self.contract.script+b'\x00')
        tx=sign_spend(self.tx,0,self.previous,self.contract,self.receiver,secret=self.secret)
        witness=list(tx.inputs[0].witness);witness[-1]+=b'\x00'
        self.assertFalse(verify_spend(replace(tx,inputs=(replace(tx.inputs[0],witness=tuple(witness)),)),0,self.previous))
    def test_public_network_extension_disabled(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(ValueError):SwapChain(Path(d)/'node.sqlite',network='dora')
            self.assertFalse((Path(d)/'node.sqlite').exists())
    def test_source_snapshot_unmodified(self):
        manifest=json.loads((ROOT/'vendor/source-manifest.json').read_text())
        for name,h in manifest.items():self.assertEqual(hashlib.sha256((ROOT/'vendor/sumuww'/name).read_bytes()).hexdigest(),h)

class HttpTest(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.app,self.server=serve(ROOT,Path(self.tmp.name),0)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        self.addCleanup(self.cleanup)
        self.url=f'http://127.0.0.1:{self.server.server_port}';self.opener=build_opener(ProxyHandler({}))
    def cleanup(self):self.server.shutdown();self.server.server_close();self.app.close();self.thread.join(5)
    def request(self,path,body=None,**headers):
        req=Request(self.url+path,data=json.dumps(body).encode() if body is not None else None,
            headers={'X-App-Token':self.app.token,'Origin':self.url,**headers})
        with self.opener.open(req,timeout=5) as r:return r.read()
    def test_order_ui_api_and_cancel(self):
        html=self.request('/').decode();self.assertIn('시험망 전용',html)
        self.request('/api/order',{'side':'sell','smw':'100','btc':'0.002'})
        state=json.loads(self.request('/api/state'));self.assertEqual(len(state['orders']),1)
        self.assertNotIn('order-identity.key',self.request('/api/state').decode())
        self.request('/api/cancel',{'id':state['orders'][0]['id']})
        self.assertEqual(json.loads(self.request('/api/state'))['orders'][0]['status'],'canceled')
    def test_csrf_rejected(self):
        with self.assertRaises(HTTPError) as e:self.request('/api/order',{},Origin='https://evil.example')
        self.assertEqual(e.exception.code,403)
        with self.assertRaises(HTTPError) as e:self.request('/api/order',{},**{'X-App-Token':'wrong'})
        self.assertEqual(e.exception.code,403)
    def test_no_public_or_arbitrary_file_endpoint(self):
        for path in ('/order-identity.key','/../local-data/orders.sqlite','/api/live-trade'):
            with self.assertRaises(HTTPError) as e:self.request(path)
            self.assertEqual(e.exception.code,404)
    def test_invalid_amount_rejected(self):
        with self.assertRaises(HTTPError) as e:self.request('/api/order',{'side':'sell','smw':'-2','btc':'0.002'})
        self.assertEqual(e.exception.code,400)
    def test_legacy_http_cannot_submit_wallet_passwords(self):
        with self.assertRaises(HTTPError) as e:self.request('/api/wallet_create',{'password':'native-only-test-password'})
        self.assertEqual(e.exception.code,403)
        self.assertFalse(self.app.vault.path.exists())

class BitcoinIntegrationTest(unittest.TestCase):
    def test_real_bitcoin_and_smw_exchange(self):
        with tempfile.TemporaryDirectory() as d:
            result=run_round(Path(d)/'success',ROOT/'tools/bitcoin-31.1/bin/bitcoind.exe',mode='success')
            self.assertTrue(result['passed']);self.assertTrue(result['unmodified_core_rejects_htlc'])
            self.assertTrue(result['early_refunds_rejected']);self.assertTrue(result['bitcoin_wrong_secret_rejected'])
            self.assertEqual(result['smw_received_atoms'],result['smw_atoms'])
            self.assertEqual(result['btc_received_sats'],result['btc_sats'])
    def test_real_bitcoin_and_smw_refund_after_restart(self):
        with tempfile.TemporaryDirectory() as d:
            result=run_round(Path(d)/'refund',ROOT/'tools/bitcoin-31.1/bin/bitcoind.exe',mode='refund')
            self.assertTrue(result['passed']);self.assertTrue(result['smw_chain_and_journal_reopened'])
            self.assertTrue(result['bitcoin_node_restarted'])
            self.assertEqual(result['events'][-1]['state'],'REFUNDED')

if __name__=='__main__':unittest.main()
