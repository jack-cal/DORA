"""Isolated synthetic-chain tests. Never reads an installed application's data."""
import json
from pathlib import Path
import sys
import tempfile
import time
import unittest

root = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(root.parent / 'sumuww_wallet_test_deps'), str(root / 'app/src/main/python')]
import wallet_runtime as runtime
from dora import keystore
from dora.chain import Chain
from dora.address import decode_address
from dora.app_service import AppService


class WalletFlow(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name)
        runtime.start(self.path / 'node', mobile=False, network='regtest', bootstrap=False)
        self.call('foreground', 'true')
        self.password = 'test-only-wallet-password'

    def tearDown(self):
        runtime.stop()
        self.temp.cleanup()

    def call(self, command, *args):
        result = json.loads(runtime.call(command, *args))
        self.assertTrue(result['ok'], result.get('error'))
        return result['data']

    def rejected(self, command, *args):
        value = json.loads(runtime.call(command, *args))
        self.assertFalse(value['ok'])
        return value

    def test_recovery_backup_and_background_lock(self):
        address = self.call('create', self.password)['address']
        words = self.call('phrase', self.password)['words']
        self.assertEqual(24, len(words.split()))
        recovered = keystore.recover_hd_wallet(self.path / 'recovered.json', 'a-different-password', words, network='regtest')
        self.assertEqual(address, recovered.address)
        self.rejected('backup', 'wrong-password')
        raw = self.call('backup', self.password)['encrypted']
        original = (self.path / 'node/wallet.json').read_bytes()
        self.rejected('recover', self.password, words)
        self.assertEqual(original, (self.path / 'node/wallet.json').read_bytes())
        self.call('foreground', 'false')
        self.assertFalse(self.call('status')['wallet']['unlocked'])
        self.rejected('phrase', self.password)
        self.call('foreground', 'true')
        self.rejected('unlock', 'wrong-password')
        self.call('unlock', self.password)
        self.assertTrue(self.call('status')['wallet']['unlocked'])
        runtime.stop()
        runtime.start(self.path / 'restore-node', mobile=False, network='regtest', bootstrap=False)
        self.call('foreground', 'true')
        self.assertEqual(address, self.call('restore', self.password, raw)['address'])
        self.assertNotIn(words, runtime.call('status'))
        runtime.stop()
        runtime.start(self.path / 'restore-node', mobile=False, network='regtest', bootstrap=False)
        self.call('foreground', 'true')
        self.assertIsNone(self.call('status')['wallet'])
        self.assertTrue(self.call('backup', self.password)['encrypted'])
        self.assertEqual(words, self.call('phrase', self.password)['words'])

    def test_real_signed_transfer_and_single_use_quote(self):
        sender = self.call('create', self.password)['address']
        receiver = keystore.create_hd_wallet(self.path / 'recipient.json', self.password, network='regtest')
        script = decode_address(sender, network='regtest')
        with Chain(self.path / 'node/node.sqlite', network='regtest') as chain:
            for _ in range(101):
                chain.accept_block(chain.make_block(script))
        self.assertGreater(float(self.call('status')['wallet']['available_dora']), 0)
        self.rejected('prepare', receiver.address, '0', '')
        self.rejected('prepare', receiver.address, '1.000000001', '')
        mainnet = keystore.create_hd_wallet(self.path / 'mainnet.json', self.password, network='dora')
        self.assertTrue(mainnet.address.startswith('sumuww1'))
        self.rejected('parse_address', mainnet.address)
        self.rejected('prepare', mainnet.address, '1', '')
        quote = self.call('prepare', receiver.address, '1.25000000', '0.00001000')
        self.assertEqual('1.25000000', quote['amount_dora'])
        self.assertEqual('1.25001000', quote['total_dora'])
        result = self.call('submit', quote['quote_id'])
        self.assertEqual('accepted', result['outcome'])
        self.assertEqual('rejected', self.call('submit', quote['quote_id'])['outcome'])
        with Chain(self.path / 'node/node.sqlite', network='regtest') as chain:
            chain.accept_block(chain.make_block(script))
            self.assertEqual(125000000, sum(coin.output.value for _, coin in chain.list_utxos(receiver.script_pubkey)))
        self.assertEqual(1, self.call('history', '0')['transactions'][0]['confirmations'])

    def test_lock_invalidates_prepared_payment(self):
        sender = self.call('create', self.password)['address']
        recipient = keystore.create_hd_wallet(self.path / 'recipient.json', self.password, network='regtest')
        with Chain(self.path / 'node/node.sqlite', network='regtest') as chain:
            for _ in range(101):
                chain.accept_block(chain.make_block(decode_address(sender, network='regtest')))
        quote = self.call('prepare', recipient.address, '1', '0.00001')
        self.call('lock')
        self.call('unlock', self.password)
        self.assertEqual('rejected', self.call('submit', quote['quote_id'])['outcome'])

    def test_transfer_reaches_an_independent_peer(self):
        sender = self.call('create', self.password)['address']
        script = decode_address(sender, network='regtest')
        with Chain(self.path / 'node/node.sqlite', network='regtest') as chain:
            for _ in range(101):
                chain.accept_block(chain.make_block(script))
        receiver = AppService(self.path / 'receiver', network='regtest', listen='127.0.0.1:0',
                              allow_lan=False, allow_internet=False, peers=[], auto_address=False)
        try:
            receiver.start().result(30)
            receiving = receiver.create_seed_wallet('wallet.json', self.password).result(30)
            listener = receiver.status().result(30)['node']['listen']
            self.call('peer', f"127.0.0.1:{listener['port']}")
            def await_state(condition):
                deadline = time.monotonic() + 30
                while time.monotonic() < deadline:
                    snapshot = receiver.status().result(10)
                    if condition(snapshot):
                        return snapshot
                    time.sleep(.1)
                self.fail('Independent peer did not reach the expected verified state')
            await_state(lambda state: state['node']['height'] == 101)
            quote = self.call('prepare', receiving['address'], '2.5', '0.00001')
            self.assertEqual('accepted', self.call('submit', quote['quote_id'])['outcome'])
            await_state(lambda state: state['wallet']['pending_dora'] == '2.50000000')
            with Chain(self.path / 'node/node.sqlite', network='regtest') as chain:
                chain.accept_block(chain.make_block(script))
            confirmed = await_state(lambda state: state['wallet']['available_dora'] == '2.50000000')
            self.assertEqual('0.00000000', confirmed['wallet']['pending_dora'])
        finally:
            receiver.stop().result(30)


if __name__ == '__main__':
    unittest.main(verbosity=2)
