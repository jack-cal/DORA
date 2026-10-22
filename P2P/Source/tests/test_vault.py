import base64,copy,json,secrets,tempfile,time,unittest
from pathlib import Path
from unittest.mock import patch
from coincurve import PublicKey
from smw_trade.vault import Vault
from smw_trade.app import Application
from smw_trade.orders import Store,order_id
from smw_trade.network import Relay,exchange

ROOT=Path(__file__).resolve().parents[1]
PASSWORD='local-test-password-012345'

class VaultTest(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.path=Path(self.tmp.name)
        self.vault=Vault(self.path/'wallet.vault');self.addCleanup(self.vault.lock)
    def create(self):return self.vault.create(PASSWORD)
    def test_real_encryption_and_independent_coin_keys(self):
        state=self.create();raw=self.vault.path.read_bytes()
        self.assertNotIn(PASSWORD.encode(),raw)
        for value in self.vault._secrets.values():
            self.assertNotIn(bytes(value).hex().encode(),raw);self.assertNotIn(bytes(value),raw)
        self.assertNotEqual(state['addresses']['smw'],state['addresses']['btc'])
        for key in self.vault.keys().values():
            digest=secrets.token_bytes(32);self.assertTrue(PublicKey(key.pubkey).verify(key.sign_digest(digest),digest,hasher=None))
    def test_restart_starts_locked_and_unlock_restores_same_addresses(self):
        expected=self.create();self.vault.lock();second=Vault(self.vault.path);self.addCleanup(second.lock)
        self.assertTrue(second.state()['locked']);self.assertEqual(second.state()['addresses'],{})
        self.assertEqual(second.unlock(PASSWORD)['addresses'],expected['addresses'])
        self.assertEqual(second.state()['wallet_id'],expected['wallet_id'])
    def test_wrong_password_and_short_password_never_create_or_unlock(self):
        with self.assertRaises(ValueError):self.vault.create('short')
        self.assertFalse(self.vault.path.exists());self.create()
        with self.assertRaises(ValueError):self.vault.unlock('wrong-password-012345')
        self.assertTrue(self.vault.state()['locked'])
        with self.assertRaises(ValueError):self.vault.keys()
    def test_ciphertext_tampering_rejected(self):
        self.create();body=json.loads(self.vault.path.read_bytes());raw=bytearray(base64.b64decode(body['ciphertext']))
        raw[9]^=1;body['ciphertext']=base64.b64encode(raw).decode();self.vault.path.write_text(json.dumps(body))
        with self.assertRaises(ValueError):self.vault.unlock(PASSWORD)
        self.assertTrue(self.vault.state()['locked'])
    def test_metadata_bound_by_aead_and_kdf_profile_not_attacker_controlled(self):
        self.create();original=self.vault.path.read_bytes();b=json.loads(original)
        b['wallet_id']='ab'*16;self.vault.path.write_text(json.dumps(b))
        with self.assertRaises(ValueError):self.vault.unlock(PASSWORD)
        b=json.loads(original);b['kdf']='scrypt-n999999999-r99999-p1';self.vault.path.write_text(json.dumps(b))
        with patch('smw_trade.vault._key',side_effect=AssertionError('Must reject before KDF')):
            with self.assertRaises(ValueError):self.vault.unlock(PASSWORD)
    def test_network_profile_and_duplicate_json_rejected(self):
        self.create();b=json.loads(self.vault.path.read_bytes());b['network']='mainnet'
        self.vault.path.write_text(json.dumps(b))
        with self.assertRaises(ValueError):self.vault.unlock(PASSWORD)
        self.vault.path.write_text('{"version":1,"version":1}')
        with self.assertRaises(ValueError):self.vault.unlock(PASSWORD)
    def test_backup_restore_and_actual_signatures_are_identical(self):
        expected=self.create();backup=self.path/'backup.smwvault';self.vault.backup(backup)
        restored=Vault(self.path/'restored.vault');self.addCleanup(restored.lock)
        self.assertEqual(restored.restore(backup,PASSWORD)['addresses'],expected['addresses'])
        digest=secrets.token_bytes(32)
        for coin,key in self.vault.keys().items():
            restored_key=restored.keys()[coin]
            self.assertEqual(key.pubkey,restored_key.pubkey)
            self.assertTrue(PublicKey(key.pubkey).verify(restored_key.sign_digest(digest),digest,hasher=None))
        self.assertEqual(backup.read_bytes(),self.vault.path.read_bytes())
    def test_backup_requires_unlock_and_will_not_overwrite(self):
        self.create();backup=self.path/'backup.smwvault';self.vault.backup(backup);before=backup.read_bytes()
        with self.assertRaises(FileExistsError):self.vault.backup(backup)
        self.assertEqual(backup.read_bytes(),before)
        self.vault.lock()
        with self.assertRaises(ValueError):self.vault.backup(self.path/'locked.smwvault')
        self.assertFalse((self.path/'locked.smwvault').exists())
    def test_restore_authenticates_before_creating_file_and_preserves_existing_wallet(self):
        self.create();backup=self.path/'backup.smwvault';self.vault.backup(backup)
        other=Vault(self.path/'other.vault');self.addCleanup(other.lock)
        with self.assertRaises(ValueError):other.restore(backup,'wrong-password-012345')
        self.assertFalse(other.path.exists());self.assertEqual(other.state()['addresses'],{})
        before=self.vault.path.read_bytes()
        with self.assertRaises(ValueError):self.vault.restore(backup,PASSWORD)
        with self.assertRaises(ValueError):self.vault.create(PASSWORD)
        self.assertEqual(self.vault.path.read_bytes(),before)
    def test_distinct_wallets_salts_nonces_and_addresses(self):
        a=self.create();second=Vault(self.path/'second.vault');self.addCleanup(second.lock);b=second.create(PASSWORD)
        ea=json.loads(self.vault.path.read_bytes());eb=json.loads(second.path.read_bytes())
        for field in ('salt','nonce','ciphertext'):self.assertNotEqual(ea[field],eb[field])
        self.assertNotEqual(a['addresses'],b['addresses'])
    def test_state_contains_only_public_metadata_and_locked_state_hides_addresses(self):
        self.create();state=json.dumps(self.vault.state())
        self.assertNotIn(PASSWORD,state)
        for value in self.vault._secrets.values():self.assertNotIn(bytes(value).hex(),state)
        self.vault.lock();self.assertEqual(self.vault.state()['addresses'],{})
        self.assertIsNone(self.vault.state()['wallet_id'])
    def test_corrupt_oversized_or_legacy_backup_is_not_imported(self):
        other=self.path/'bad.smwvault'
        for content in (b'not a wallet',b'x'*65537,b'{"legacy_wallet":true}'):
            other.write_bytes(content)
            with self.assertRaises(ValueError):self.vault.restore(other,PASSWORD)
            self.assertFalse(self.vault.path.exists())

class VaultTradeTest(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.path=Path(self.tmp.name)
        self.maker=Store(self.path/'maker');self.relay=Relay(self.maker).start();self.addCleanup(self.relay.close)
        self.app=Application(ROOT,self.path/'taker');self.addCleanup(self.app.close)
    def prepare(self,side):
        packet=self.maker.create(side,'3.12345678','0.00005432')
        self.app.command('connect',{'port':self.relay.address[1]})
        confirmation=self.app.command('reserve',{'id':order_id(packet['body'])})['confirmation']
        state=self.app.command('wallet_create',{'password':PASSWORD})
        return confirmation['body']['session'],state
    def execute(self,side,mode):
        sid,wallet=self.prepare(side);self.app.command('wallet_lock',{})
        with self.assertRaises(ValueError):self.app.command('execute',{'session':sid,'mode':mode})
        self.assertEqual(self.app.state()['trades'][0]['state'],'RESERVED')
        self.app.command('wallet_unlock',{'password':PASSWORD})
        self.app.command('execute',{'session':sid,'mode':mode})
        self.app.command('wallet_lock',{}) # In-flight approved operation retains its own keys only.
        deadline=time.monotonic()+60
        while self.app.state()['job']['running'] and time.monotonic()<deadline:time.sleep(.1)
        result=self.app.state()['job'];self.assertTrue(result.get('passed'),result)
        result=result['result'];self.assertEqual(result['wallet_source'],'encrypted-local-test-vault')
        self.assertEqual(result['local_wallet_id'],wallet['wallet_id'])
        if side=='buy':
            self.assertEqual(result['smw_seller'],wallet['addresses']['smw'])
            self.assertEqual(result['btc_recipient'],wallet['addresses']['btc'])
        else:
            self.assertEqual(result['smw_recipient'],wallet['addresses']['smw'])
            self.assertEqual(result['btc_buyer'],wallet['addresses']['btc'])
        self.assertNotIn(PASSWORD,json.dumps(self.app.state()))
        self.assertTrue(self.app.state()['wallet']['locked'])
        self.assertFalse(result['public_funds'])
        return result
    def test_vault_smw_seller_actual_cross_chain_claim(self):
        result=self.execute('buy','success')
        self.assertEqual(result['smw_received_atoms'],312345678);self.assertEqual(result['btc_received_sats'],5432)
    def test_vault_btc_buyer_funds_and_claims_with_local_key(self):
        result=self.execute('sell','success')
        self.assertEqual(result['smw_received_atoms'],312345678);self.assertEqual(result['btc_received_sats'],5432)
    def test_encrypted_keys_refund_after_bitcoin_restart(self):
        result=self.execute('sell','refund')
        self.assertTrue(result['bitcoin_node_restarted']);self.assertEqual(result['btc_refunded_sats'],5432)
        self.assertEqual(result['smw_refunded_atoms'],312345678)
    def test_wallet_file_never_sent_by_order_transport(self):
        self.prepare('sell')
        response=exchange(self.app.relay.address,{'protocol':'smw-trade-regtest-1','type':'pull','offset':0})
        raw=json.dumps(response)
        self.assertNotIn('ciphertext',raw);self.assertNotIn('wallet',raw);self.assertNotIn(PASSWORD,raw)
