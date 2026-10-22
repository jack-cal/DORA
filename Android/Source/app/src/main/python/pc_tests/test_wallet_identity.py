"""Current wallet branding, old encrypted envelopes and same-chain spending."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from sumuww import keystore
from sumuww.address import AddressError, _bech32_encode, _convert_bits, decode_address, encode_address
from sumuww.chain import Chain, Coin
from sumuww.__main__ import create_payment
from sumuww.primitives import COIN, hash_to_display
from sumuww.profiles import SUMUWW, REGTEST
from sumuww.transaction import Transaction, TxInput, TxOutput
from sumuww.wallet import sign_p2wpkh
from sumuww.wallet_paths import reject_wallet_overwrite

PASSWORD='Public identity test password only'

def legacy_address(script):
    return _bech32_encode('dora',[0]+_convert_bits(script[2:],8,5,pad=True))

class WalletIdentityTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='sumuww-identity-')
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)

    def legacy(self,name='old.json',hd=True):
        identity=keystore._wallet_identity
        with patch.object(keystore,'_wallet_identity',side_effect=lambda profile,is_hd,**kw:identity(profile,is_hd,legacy=True)):
            return (keystore.create_hd_wallet if hd else keystore.create_wallet)(self.root/name,PASSWORD,network=SUMUWW)

    def test_new_wallet_has_sumuww_identity_and_unchanged_genesis(self):
        for hd in (False,True):
            path=self.root/f'new-{hd}.json'
            key=(keystore.create_hd_wallet if hd else keystore.create_wallet)(path,PASSWORD,network=SUMUWW)
            raw=path.read_text()
            self.assertNotIn('dora',raw)
            self.assertTrue(key.address.startswith('sumuww1'))
            self.assertEqual(decode_address(key.address,network=SUMUWW),key.script_pubkey)
            self.assertEqual(decode_address(legacy_address(key.script_pubkey),network='sumuww'),key.script_pubkey)
            self.assertEqual(keystore.load_wallet(path,PASSWORD,network='dora').pubkey,key.pubkey)
            with self.assertRaises(ValueError):reject_wallet_overwrite(path)
        self.assertEqual(hash_to_display(SUMUWW.genesis.block_hash()),'00000032e243a8c71b449b13c2da733dd329f308a75aa4358f3f22707a28af97')
        self.assertEqual(SUMUWW.message_magic,bytes.fromhex('d052470c'))

    def test_legacy_wallets_open_without_rewriting_and_recovery_keeps_keys(self):
        for hd in (False,True):
            path=self.root/f'old-{hd}.json'
            key=self.legacy(path.name,hd)
            original=path.read_bytes()
            opened=keystore.load_wallet(path,PASSWORD,network='sumuww')
            self.assertEqual(opened.pubkey,key.pubkey)
            self.assertEqual(path.read_bytes(),original)
            if hd:
                phrase=keystore.export_mnemonic(path,PASSWORD,network=SUMUWW)
                recovered=keystore.recover_hd_wallet(self.root/'recovered.json',PASSWORD,phrase,network=SUMUWW)
                self.assertEqual(recovered.pubkey,opened.pubkey)
                self.assertEqual(recovered.derivation_path,opened.derivation_path)

    def test_alias_checksum_metadata_tampering_and_cross_network_are_rejected(self):
        path=self.root/'new.json'
        key=keystore.create_hd_wallet(path,PASSWORD,network=SUMUWW)
        with self.assertRaises(AddressError):decode_address(key.address.replace('sumuww1','dora1'),network=SUMUWW)
        with self.assertRaises(AddressError):decode_address(key.address,network=REGTEST)
        envelope=json.loads(path.read_bytes())
        envelope['address_hrp']='dora'
        path.write_text(json.dumps(envelope))
        with self.assertRaises(keystore.WalletFormatError):keystore.load_wallet(path,PASSWORD,network=SUMUWW)

    def test_public_rules_accept_legacy_to_new_payment_and_return_payment(self):
        old=self.legacy()
        new=keystore.create_hd_wallet(self.root/'new.json',PASSWORD,network=SUMUWW)
        spent=TxOutput(3*COIN,decode_address(legacy_address(old.script_pubkey),network=SUMUWW))
        tx=Transaction(2,(TxInput(b'\x71'*32,0),),
            (TxOutput(COIN,decode_address(new.address,network=SUMUWW)),TxOutput(2*COIN-100_000,old.script_pubkey)))
        signed=sign_p2wpkh(tx,0,spent,old)
        state={(b'\x71'*32,0):Coin(spent,0,False)}
        with Chain(self.root/'public-validation.sqlite',network=SUMUWW) as chain:
            path=chain._path(chain.tip_hash)
            self.assertEqual(chain._apply_transaction(signed,state,1,path),100_000)
            received=state[(signed.txid(),0)].output
            self.assertEqual(received,TxOutput(COIN,new.script_pubkey))
            return_tx=Transaction(2,(TxInput(signed.txid(),0),),
                (TxOutput(COIN-100_000,decode_address(legacy_address(old.script_pubkey),network=SUMUWW)),))
            returned=sign_p2wpkh(return_tx,0,received,new)
            self.assertEqual(chain._apply_transaction(returned,state,1,path),100_000)
            self.assertEqual(state[(returned.txid(),0)].output.script_pubkey,old.script_pubkey)

    def test_isolated_ledger_confirms_payment_and_reopened_recipient_balance(self):
        old=self.legacy()
        new_path=self.root/'new.json'
        new=keystore.create_hd_wallet(new_path,PASSWORD,network=SUMUWW)
        database=self.root/'isolated-ledger.sqlite'
        with Chain(database,network=REGTEST) as chain:
            chain.mine(old.script_pubkey,100)
            tx=create_payment(chain,old,decode_address(new.address,network=SUMUWW),COIN,100_000)
            chain.submit_transaction(tx)
            chain.accept_block(chain.make_block(old.script_pubkey))
            self.assertEqual(chain.balance(new.script_pubkey),COIN)
            self.assertEqual(chain.balance(new.script_pubkey,mature_only=True),COIN)
        with Chain(database,network=REGTEST) as chain:
            recipient=keystore.load_wallet(new_path,PASSWORD,network=SUMUWW)
            self.assertEqual(chain.balance(recipient.script_pubkey),COIN)
            self.assertEqual(chain.info()['height'],101)
