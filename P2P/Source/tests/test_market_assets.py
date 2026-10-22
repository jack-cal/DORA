"""Removed markets cannot be used; older private backups remain recoverable."""
import base64,json,tempfile,unittest
from pathlib import Path
from coincurve import PrivateKey
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from smw_trade.orders import canonical
from smw_trade.vault import _key,_unb64
from smw_trade.market.amounts import QUOTES,units,quote_total
from smw_trade.market.application import MarketApplication
from smw_trade.market.board import Board,identifier
from smw_trade.market.engine import adapters
from smw_trade.market.vault import TradeVault,COINS
from test_market import ROOT,PASSWORD


class AssetRemovalTests(unittest.TestCase):
    def test_removed_assets_rejected_at_all_entry_points(self):
        self.assertEqual(QUOTES,('BTC',))
        with tempfile.TemporaryDirectory() as tmp:
            app=MarketApplication(ROOT,Path(tmp)/'a','test')
            try:
                app.vault.create(PASSWORD)
                self.assertEqual(set(app.vault.payload),set(COINS))
                self.assertEqual(set(app.vault.state()['addresses']),set(COINS))
                for coin in ('ETH','BNB','XRP'):
                    for action in (lambda:units('1',coin),lambda:quote_total('1','1',coin),
                                   lambda:app.create(side='sell',coin=coin,quantity='1',price='1'),
                                   lambda:app.configure(coin,{}),lambda:adapters({coin:{}},'test'),
                                   lambda:app.vault.key(coin)):
                        with self.assertRaises(ValueError):action()
                    packet=app.store.create('sell','BTC','1','1')
                    packet['body']['coin']=coin;packet=app.store.identity.sign(packet['body'])
                    with self.assertRaises(ValueError):app.store.import_packet(packet)
            finally:app.close()

    def test_legacy_wallet_preserves_keys_and_recovery_secret(self):
        with tempfile.TemporaryDirectory() as tmp:
            for version,extra in [('0.2.0',('ETH','BNB')),('0.2.1',())]:
                with self.subTest(version=version):
                    path=Path(tmp)/version;path.mkdir();vault=TradeVault(path/'old.vault','test');vault.create(PASSWORD)
                    addresses=vault.state()['addresses'];secret=vault.secret('ab'*32)
                    journal=vault.seal('existing-operation',{'value':42})
                    payload=dict(vault.payload)
                    payload.update({c:PrivateKey().secret.hex() for c in extra})
                    payload['XRP']='opaque-test-only-retired-seed'
                    envelope=json.loads(vault.path.read_text());envelope.pop('ciphertext')
                    envelope['ciphertext']=base64.b64encode(AESGCM(_key(PASSWORD,_unb64(envelope['salt'],16))).encrypt(
                        _unb64(envelope['nonce'],12),canonical(payload),canonical(envelope))).decode()
                    raw=canonical(envelope);vault.path.write_bytes(raw);vault.lock();vault.unlock(PASSWORD)
                    self.assertEqual(vault.path.read_bytes(),raw)
                    self.assertEqual(vault.payload,payload)
                    self.assertEqual(vault.state()['addresses'],addresses)
                    self.assertEqual(vault.secret('ab'*32),secret)
                    self.assertEqual(vault.unseal('existing-operation',journal),{'value':42})
                    vault.backup(path/'backup.vault')
                    recovered=TradeVault(path/'restored.vault','test');recovered.restore(path/'backup.vault',PASSWORD)
                    self.assertEqual(recovered.payload,payload)
                    self.assertEqual(recovered.path.read_bytes(),raw)

    def test_old_profiles_skip_retired_records_without_erasing_them(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp);board=Board(path/'old','test')
            # Construct validly signed v0.2.0 history without enabling new orders.
            for coin in ('ETH','BNB','XRP'):
                p=board.create('sell','BTC','1','1')
                p['body']['coin']=coin;p['body']['quote_units']=10**6 if coin=='XRP' else 10**18;p=board.identity.sign(p['body'])
                oid=identifier(p['body']);closure=board.sign('canceled',post=oid)
                with board.connect() as db:
                    db.execute('INSERT INTO posts VALUES(?,?)',(oid,canonical(p).decode()))
                    db.execute('INSERT INTO closures VALUES(?,?)',(oid,canonical(closure).decode()))
                    for event in (p,closure):db.execute('INSERT INTO events(packet) VALUES(?)',(canonical(event).decode(),))
            board.create('buy','BTC','10','2')
            settings={'nodes':{'ETH':{'url':'https://unused.invalid'},'BNB':{},'XRP':{'url':'https://unused.invalid'}},'listen':{'host':'127.0.0.1','port':0},'peers':[]}
            (board.directory/'market-connections.json').write_text(json.dumps(settings))
            with board.connect() as db:before={t:db.execute('SELECT * FROM '+t).fetchall() for t in ('posts','closures','events')}
            app=MarketApplication(ROOT,board.directory,'test');peer=MarketApplication(ROOT,path/'peer','test');recovered=None
            try:
                app.vault.create(PASSWORD)
                self.assertEqual(app.engine.nodes,{})
                self.assertEqual(app.config['nodes'],settings['nodes'])
                self.assertEqual({p['coin'] for p in app.state()['orders']},{'BTC'})
                peer.connect('127.0.0.1',app.relay.address[1])
                self.assertEqual(peer.store.listing(),[{**p,'mine':False} for p in app.store.listing()])
                app.backup(path/'recovery.smwbackup')
                recovered=MarketApplication(ROOT,path/'restore','test');recovered.restore_backup(path/'recovery.smwbackup',PASSWORD)
                self.assertEqual(recovered.engine.nodes,{})
                self.assertEqual(recovered.config['nodes'],settings['nodes'])
                with recovered.store.connect() as db:
                    for table,rows in before.items():self.assertEqual(db.execute('SELECT * FROM '+table).fetchall(),rows)
            finally:
                if recovered:recovered.close()
                peer.close();app.close()

    def test_old_xrp_reservation_cannot_start_a_trade(self):
        with tempfile.TemporaryDirectory() as tmp:
            app=MarketApplication(ROOT,Path(tmp)/'a','test');peer=Board(Path(tmp)/'b','test')
            try:
                p=app.store.create('sell','BTC','1','1')
                p['body'].update(coin='XRP',quote_units=10**6);p=app.store.identity.sign(p['body']);oid=identifier(p['body'])
                request=peer.sign('request',post=oid,nonce='00'*16,expires=int(peer.clock())+100)
                sid=identifier(request['body']);closure=app.store.sign('reserved',post=oid,request=request,session=sid)
                with app.store.connect() as db:
                    db.execute('INSERT INTO posts VALUES(?,?)',(oid,canonical(p).decode()))
                    db.execute('INSERT INTO reservations VALUES(?,?,?)',(sid,oid,canonical(closure).decode()))
                with self.assertRaises(ValueError):app.store.reserve(request)
                with self.assertRaises(ValueError):app.engine.prepare(sid)
                self.assertEqual(app.store.sessions(),[])
                with app.store.connect() as db:self.assertEqual(db.execute('SELECT COUNT(*) FROM swaps').fetchone()[0],0)
            finally:app.close()


if __name__=='__main__':unittest.main()
