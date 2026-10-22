import concurrent.futures,copy,json,tempfile,unittest
from pathlib import Path
from smw_trade.market.amounts import quote_total,units
from smw_trade.market.board import Board,identifier
from smw_trade.market.application import MarketApplication
from smw_trade.market.vault import TradeVault
from smw_trade.bitcoin import Bitcoin
from market_support import SmwNode

ROOT=Path(__file__).resolve().parents[1]
PASSWORD='disposable-market-test-password'

class BoardTests(unittest.TestCase):
    def setUp(self):self.temp=tempfile.TemporaryDirectory();self.path=Path(self.temp.name)
    def tearDown(self):self.temp.cleanup()
    def test_precision_supported_coins(self):
        for coin,price in [('BTC','0.00000001')]:
            self.assertEqual(quote_total('100',price,coin)[1],100)
            with self.assertRaises(ValueError):quote_total('0.1',price,coin)
        for v in ('-1','NaN','Infinity','1e3','0','1,000','0.000000001'):
            with self.assertRaises(ValueError):units(v,'SMW')
    def test_concurrent_reservation_and_forgery(self):
        a,b,c=(Board(self.path/x,'test') for x in ('a','b','c'))
        post=a.create('sell','BTC','2.5','0.02');oid=identifier(post['body'])
        for peer in (b,c):peer.import_packet(post)
        requests=[p.request(oid) for p in (b,c)]
        def reserve(r):
            try:return a.reserve(r)
            except ValueError:return None
        with concurrent.futures.ThreadPoolExecutor() as pool:results=list(pool.map(reserve,requests))
        self.assertEqual(sum(r is not None for r in results),1)
        with self.assertRaises(ValueError):a.cancel(oid)
        changed=copy.deepcopy(post);changed['body']['price']='0.03'
        with self.assertRaises(Exception):b.import_packet(changed)
        with self.assertRaises(ValueError):Board(self.path/'wrong','mainnet').import_packet(post)
        late=Board(self.path/'late','test')
        for p in a.export():late.import_packet(p)
        self.assertEqual(late.listing()[0]['status'],'reserved')
    def test_cancel_and_cursor_growth(self):
        a=Board(self.path/'a','test');p=a.create('buy','BTC','10','2');oid=identifier(p['body']);a.cancel(oid)
        first=a.export();a.create('sell','BTC','1','0.001')
        self.assertEqual(a.export()[:2],first);self.assertEqual(len(a.export(2)),1)
        with self.assertRaises(ValueError):a.reserve(Board(self.path/'b','test').sign('request',post=oid,nonce='00'*16,expires=int(a.clock())+100))
    def test_encrypted_wallet_restore(self):
        v=TradeVault(self.path/'a.vault','test');v.create(PASSWORD);addresses=v.state()['addresses'];secret=v.secret('ab'*32)
        sealed=v.seal('test',{'secret':secret.hex()});self.assertNotIn(secret.hex(),sealed)
        v.backup(self.path/'backup.vault');v.lock()
        with self.assertRaises(ValueError):v.unseal('test',sealed)
        w=TradeVault(self.path/'b.vault','test');w.restore(self.path/'backup.vault',PASSWORD)
        self.assertEqual(w.state()['addresses'],addresses);self.assertEqual(w.secret('ab'*32),secret)
        self.assertEqual(w.unseal('test',sealed)['secret'],secret.hex())
        with self.assertRaises(Exception):w.unseal('changed',sealed)

class BitcoinTradeTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.path=Path(self.temp.name)
        self.node=SmwNode(self.path/'smw');self.btc=Bitcoin(ROOT/'tools/bitcoin-31.1/bin/bitcoind.exe',self.path/'btc').start()
        self.a=MarketApplication(ROOT,self.path/'a','test');self.b=MarketApplication(ROOT,self.path/'b','test')
        for a in (self.a,self.b):a.vault.create(PASSWORD)
        self.node.mine(self.a.vault.key('SMW'),103)
        self.btc.rpc('generatetoaddress',103,self.b.vault.public('BTC')['address'])
        config={'SMW':{'url':f'http://127.0.0.1:{self.node.port}/rpc','credential_file':str(self.node.token_file),'block_seconds':1},
                'BTC':{'url':f'http://127.0.0.1:{self.btc.port}/','credential_file':str(self.btc.cookie),'block_seconds':1}}
        for a in (self.a,self.b):
            for c,v in config.items():a.configure(c,v)
        self.a.connect('127.0.0.1',self.b.relay.address[1]);self.b.connect('127.0.0.1',self.a.relay.address[1])
    def tearDown(self):
        self.a.close();self.b.close();self.btc.close();self.node.close();self.temp.cleanup()
    def prepare(self,side='sell'):
        author=self.a if side=='sell' else self.b;taker=self.b if side=='sell' else self.a
        post=author.create(side=side,coin='BTC',quantity='2.12345678',price='0.5')
        taker.sync();session=taker.reserve(post['id'])
        for a in (self.a,self.b):a.engine.prepare(session)
        self.a.sync_trade(session);self.b.sync_trade(session);return session
    def send(self,app,sid,action,coin):
        p=app.engine.preview(sid,action);app.engine.submit(sid,action,p['txid'])
        if coin=='SMW':self.node.mine(self.a.vault.key('SMW'))
        else:self.btc.mine()
    def locks(self,sid):
        with self.assertRaises(ValueError):self.b.engine.preview(sid,'lock')
        self.send(self.a,sid,'lock','SMW');self.a.sync_trade(sid)
        self.send(self.b,sid,'lock','BTC');self.b.sync_trade(sid)
    def test_trade_both_directions_and_secret_recovery(self):
        for side in ('sell','buy'):
            sid=self.prepare(side);self.locks(sid)
            self.send(self.a,sid,'claim','BTC')
            # Counterparty notice is deliberately withheld; read Bitcoin itself.
            self.send(self.b,sid,'claim','SMW')
            for a in (self.a,self.b):self.assertEqual(a.engine.status(sid)['state'],'completed')
            t,s=self.a.engine._load(sid);self.assertNotIn(self.a.vault.secret(sid).hex(),json.dumps(s))
            forged=self.b.engine.snapshot(sid);forged['body']['complete']=True
            with self.assertRaises(Exception):self.a.engine.receive(forged)
    def test_cancellation_restart_and_real_refunds(self):
        sid=self.prepare();self.locks(sid)
        self.a.engine.cancel(sid);self.a.sync_trade(sid)
        self.assertEqual(self.b.engine.status(sid)['state'],'refund_wait')
        for a in (self.a,self.b):
            with self.assertRaises(ValueError):a.engine.preview(sid,'refund')
        self.a.backup(self.path/'funded-recovery.smwbackup')
        self.a.close();self.b.close();self.a=MarketApplication(ROOT,self.path/'restored-a','test');self.b=MarketApplication(ROOT,self.path/'b','test')
        self.a.restore_backup(self.path/'funded-recovery.smwbackup',PASSWORD)
        for a in (self.a,self.b):a.vault.unlock(PASSWORD)
        self.node.mine(self.a.vault.key('SMW'),121);self.btc.mine(51)
        for a,c in ((self.a,'SMW'),(self.b,'BTC')):
            self.send(a,sid,'refund',c);self.assertEqual(a.engine.status(sid)['state'],'refunded')
    def test_cancel_before_funding_and_reject_changed_terms(self):
        sid=self.prepare();self.assertEqual(self.a.cancel_trade(sid)['state'],'canceled')
        self.assertEqual(self.b.engine.status(sid)['state'],'canceled')
        for a in (self.a,self.b):
            with self.assertRaises(ValueError):a.engine.preview(sid,'lock')
        packet=self.b.engine.snapshot(sid);packet['body']['offer']['keys']['BTC']['address']=self.a.vault.public('BTC')['address']
        packet=self.b.store.identity.sign(packet['body'])
        with self.assertRaises(ValueError):self.a.engine.receive(packet)

if __name__=='__main__':unittest.main()
