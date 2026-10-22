import json
import struct
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch,MagicMock
from smw_trade.market.application import MarketApplication
from smw_trade.market.light import BitcoinLightAdapter
from smw_trade.market.light_headers import HeaderChain, GENESIS, compact, target, sha256d
from smw_trade.market.light_network import endpoint, LightNetwork, ElectrumPeer
from smw_trade.bitcoin import Bitcoin
from market_support import SmwNode
from light_support import Index, ElectrumFixture
from test_market import BitcoinTradeTests, ROOT, PASSWORD


def mine_header(previous, timestamp, root=bytes(32), bits=0x207fffff):
    prefix = struct.pack('<I', 4) + sha256d(previous) + root + struct.pack('<II', timestamp, bits)
    for nonce in range(10000):
        raw = prefix + struct.pack('<I', nonce)
        if int.from_bytes(sha256d(raw), 'little') <= target(bits):
            return raw
    raise AssertionError('Regtest mining failed')


class HeaderTests(unittest.TestCase):
    def test_malformed_network_features_and_proof_are_rejected(self):
        peer=ElectrumPeer('tcp://127.0.0.1:12345','test')
        raw=MagicMock();raw.getpeername.return_value=('127.0.0.1',12345)
        with patch('socket.create_connection',return_value=raw),patch.object(peer,'_request',side_effect=[['fixture','1.4'],[]]):
            with self.assertRaises(ValueError):peer.call('server.ping')
        self.assertIsNone(peer.socket)
        with tempfile.TemporaryDirectory() as tmp:
            chain=HeaderChain(Path(tmp)/'headers','test')
            with self.assertRaises(ValueError):chain.verify_merkle('00'*32,0,[])

    def test_genesis_targets_and_cache_revalidation(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'headers.bin'
            c = HeaderChain(path, 'test')
            now = int(time.time()) - 100
            for i in range(15):
                c.append(mine_header(c.header(c.height), now + i))
            c.save()
            restored = HeaderChain(path, 'test')
            self.assertEqual(restored.work, c.work)
            self.assertEqual(path.stat().st_size, 16 * 80)
            damaged = bytearray(path.read_bytes()); damaged[-10] ^= 0x40; path.write_bytes(damaged)
            with self.assertRaises(ValueError): HeaderChain(path, 'test')
            with self.assertRaises(ValueError): HeaderChain(path, 'mainnet')
        self.assertEqual(compact(target(0x1d00ffff)), 0x1d00ffff)
        for bits in (0, 0x1d80ffff, 0x2300ffff):
            with self.assertRaises(ValueError): target(bits)

    def test_difficulty_parent_time_and_merkle_forgery(self):
        with tempfile.TemporaryDirectory() as tmp:
            c = HeaderChain(Path(tmp) / 'headers.bin', 'test')
            now = int(time.time()) - 100
            leaf = sha256d(b'known test transaction')
            other = sha256d(b'other test transaction')
            c.append(mine_header(c.header(0), now, sha256d(leaf + other)))
            proof = {'block_height': 1, 'pos': 0, 'merkle': [other[::-1].hex()]}
            c.verify_merkle(leaf[::-1].hex(), 1, proof)
            for wrong in ({**proof, 'pos': 2}, {**proof, 'block_height': 0}, {**proof, 'merkle': ['00' * 32]}):
                with self.assertRaises(ValueError): c.verify_merkle(leaf[::-1].hex(), 1, wrong)
            for raw in (mine_header(c.header(0), now + 1), mine_header(c.header(1), now),
                        mine_header(c.header(1), int(time.time()) + 10000)):
                with self.assertRaises(ValueError): c.append(raw)
            changed = bytearray(mine_header(c.header(1), now + 1));struct.pack_into('<I', changed, 72, 0x2070ffff)
            with self.assertRaises(ValueError): c.append(bytes(changed))

    def test_mainnet_retarget_clamp_and_version_rule(self):
        with tempfile.TemporaryDirectory() as tmp:
            c = HeaderChain(Path(tmp) / 'headers.bin')
            # Synthetic metadata exercises the retarget arithmetic independently
            # of generating mainnet proof of work. Live sync validates real data.
            raw = bytearray(GENESIS['mainnet'])
            struct.pack_into('<I', raw, 72, 0x1c0ffff0)
            headers = []
            for h in range(2016):
                row = raw.copy();struct.pack_into('<I', row, 68, 1231006505 + h)
                headers.append(row)
            c.data = bytearray().join(headers);c.work = list(range(2016))
            self.assertEqual(c.expected_bits(), compact(target(0x1c0ffff0) // 4))
            struct.pack_into('<I', c.data, 2015 * 80 + 68, 1231006505 + 1209600 * 10)
            self.assertEqual(c.expected_bits(), compact(target(0x1c0ffff0) * 4))

    def test_transport_and_duplicate_endpoint_policy(self):
        for value in ('tcp://example.com:50001', 'https://example.com:443', 'ssl://user:pass@example.com:50002', 'ssl://example.com:50002/path'):
            with self.assertRaises(ValueError): endpoint(value, 'mainnet')
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                LightNetwork(Path(tmp) / 'h', ['ssl://same.example:50002'] * 3)
        self.assertEqual(endpoint('tcp://127.0.0.1:1234', 'test'), ('tcp', '127.0.0.1', 1234))

    def test_public_chainwork_floor_and_cached_quorum_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            urls = ['ssl://server'+str(i)+'.invalid:50002' for i in range(3)]
            client = LightNetwork(Path(tmp)/'headers', urls)
            for i, p in enumerate(client.peers):p.address='192.0.2.'+str(i+1)
            def call(peer, method, *params):
                if method=='blockchain.headers.subscribe':return {'height':0,'hex':GENESIS['mainnet'].hex()}
                return GENESIS['mainnet'].hex()
            with patch.object(ElectrumPeer,'call',call):
                with self.assertRaisesRegex(ValueError,'insufficient cumulative work'):client.sync(force=True)
                self.assertEqual(client.active,[])
                client.last_sync=time.monotonic()
                with self.assertRaisesRegex(ValueError,'insufficient cumulative work'):client.sync()


class LightTradeTests(BitcoinTradeTests):
    LIGHT_PARTIES = ('a', 'b')

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory();self.path = Path(self.temp.name)
        self.node = SmwNode(self.path / 'smw')
        self.btc = Bitcoin(ROOT / 'tools/bitcoin-31.1/bin/bitcoind.exe', self.path / 'btc').start()
        self.fixtures = [ElectrumFixture(Index(self.btc)) for _ in range(3)]
        for name in ('a', 'b'):
            app = MarketApplication(ROOT, self.path / name, 'test', flavor='light' if name in self.LIGHT_PARTIES else 'full')
            setattr(self, name, app);app.vault.create(PASSWORD)
        self.node.mine(self.a.vault.key('SMW'), 103)
        self.btc.rpc('generatetoaddress', 103, self.b.vault.public('BTC')['address'])
        for name in ('a', 'b'):
            app = getattr(self, name)
            app.configure('SMW', {'url': f'http://127.0.0.1:{self.node.port}/rpc', 'credential_file': str(self.node.token_file), 'block_seconds': 1})
            config = {'mode': 'light', 'servers': [s.url for s in self.fixtures], 'block_seconds': 1} if name in self.LIGHT_PARTIES else {'url': f'http://127.0.0.1:{self.btc.port}/', 'credential_file': str(self.btc.cookie), 'block_seconds': 1}
            app.configure('BTC', config)
        self.a.connect('127.0.0.1', self.b.relay.address[1]);self.b.connect('127.0.0.1', self.a.relay.address[1])

    def tearDown(self):
        self.a.close();self.b.close()
        for fixture in self.fixtures: fixture.close()
        self.btc.close();self.node.close();self.temp.cleanup()

    def test_cancellation_restart_and_real_refunds(self):
        sid = self.prepare();self.locks(sid)
        self.a.engine.cancel(sid);self.a.sync_trade(sid)
        for app in (self.a, self.b):
            with self.assertRaises(ValueError): app.engine.preview(sid, 'refund')
        for name in ('a', 'b'):
            app = getattr(self, name);app.backup(self.path / (name + '.smwbackup'));app.close()
            restored = MarketApplication(ROOT, self.path / ('restored-' + name), 'test', flavor='light' if name in self.LIGHT_PARTIES else 'full')
            setattr(self, name, restored);restored.restore_backup(self.path / (name + '.smwbackup'), PASSWORD)
        self.node.mine(self.a.vault.key('SMW'), 121);self.btc.mine(51)
        for app, coin in ((self.a, 'SMW'), (self.b, 'BTC')):
            self.send(app, sid, 'refund', coin)
            self.assertEqual(app.engine.status(sid)['state'], 'refunded')

    def test_server_outage_and_conflicting_history(self):
        sid = self.prepare()
        node = self.b.engine.nodes['BTC']
        self.assertIsInstance(node, BitcoinLightAdapter)
        self.fixtures[0].offline = True
        self.assertEqual(node.info()['verified_servers'], 2)
        self.locks(sid)
        self.send(self.a, sid, 'claim', 'BTC');self.send(self.b, sid, 'claim', 'SMW')
        self.assertEqual(self.b.engine.status(sid)['state'], 'completed')
        self.fixtures[0].offline = False
        self.fixtures[0].mutate = lambda method, value: [] if method == 'blockchain.scripthash.get_history' else value
        with self.assertRaisesRegex(ValueError, 'disagree'):
            self.b.engine.status(sid)
        self.fixtures[0].mutate = lambda method, value: value
        self.assertEqual(self.b.engine.status(sid)['state'], 'completed')

    def test_forged_amount_and_merkle_proof_rejected(self):
        node = self.b.engine.nodes['BTC']
        def amount(method, value):
            if method == 'blockchain.scripthash.listunspent':
                return [{**v, 'value': v['value'] + 100000} for v in value]
            return value
        for fixture in self.fixtures: fixture.mutate = amount
        with self.assertRaisesRegex(ValueError, 'amount or script'): node.coins(self.b.vault.key('BTC'))
        def proof(method, value):
            return {**value, 'merkle': ['00' * 32]} if method == 'blockchain.transaction.get_merkle' else value
        for fixture in self.fixtures: fixture.mutate = proof
        node.proofs.clear()
        with self.assertRaisesRegex(ValueError, 'invalid inclusion proof'): node.coins(self.b.vault.key('BTC'))

    def test_reorganization_revalidates_inclusion(self):
        node = self.b.engine.nodes['BTC']
        old_height = node.info()['height'];old_hash = node.client.chain.digest(old_height)
        self.btc.rpc('invalidateblock', self.btc.rpc('getblockhash', old_height))
        self.btc.mine(3)
        new_height = node.info()['height']
        self.assertEqual(new_height, old_height + 2)
        self.assertNotEqual(node.client.chain.digest(old_height), old_hash)
        # Restart independently revalidates the replacement chain from genesis.
        fresh = HeaderChain(node.client.chain.path, 'test')
        self.assertEqual(fresh.digest(new_height), self.btc.rpc('getbestblockhash'))

    def test_one_response_is_never_enough(self):
        self.fixtures[0].offline = self.fixtures[1].offline = True
        with self.assertRaisesRegex(ValueError, 'Two distinct'):
            self.b.engine.nodes['BTC'].info()


class MixedEditionTradeTests(LightTradeTests):
    LIGHT_PARTIES = ('b',)


class ReverseMixedEditionTradeTests(BitcoinTradeTests):
    LIGHT_PARTIES = ('a',)
    setUp = LightTradeTests.setUp
    tearDown = LightTradeTests.tearDown
    test_cancellation_restart_and_real_refunds = LightTradeTests.test_cancellation_restart_and_real_refunds


if __name__ == '__main__':
    unittest.main()
