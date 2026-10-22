"""Actual independent key owners and two chain engines, no public assets."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from smw_trade.app import Application
from smw_trade.bitcoin import Bitcoin
from smw_trade.research_node import ResearchNode
from smw_trade.research_chain import SwapChain
from smw_trade.orders import order_id
from smw_trade.settlement import address, height
from smw_trade.wallet_link import WalletLinks, endpoint
from sumuww.wallet import RegtestKey

ROOT=Path(__file__).resolve().parents[1]
PASSWORD='isolated-test-password-not-user'


class IndependentSwapTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.path=Path(self.tmp.name)
        self.btc=Bitcoin(ROOT/'tools/bitcoin-31.1/bin/bitcoind.exe',self.path/'bitcoin').start()
        self.node=ResearchNode(self.path/'smw').start()
        self.a=Application(ROOT,self.path/'a');self.b=Application(ROOT,self.path/'b')
        for app in (self.a,self.b):app.command('wallet_create',{'password':PASSWORD})
        self.config={'smw_url':f'http://127.0.0.1:{self.node.port}/rpc','smw_token':str(self.node.token_file),
                     'btc_url':f'http://127.0.0.1:{self.btc.port}/','btc_cookie':str(self.btc.cookie)}
        for app in (self.a,self.b):app.command('swap_configure',self.config)
        self.a.command('connect',{'port':self.b.relay.address[1]})
        self.b.command('connect',{'port':self.a.relay.address[1]})
        self.keys_a=self.a.vault.keys();self.keys_b=self.b.vault.keys()
        with self.node.lock,SwapChain(self.node.database) as chain:chain.mine(self.keys_a['smw'].script_pubkey,103)
        self.btc.rpc('generatetoaddress',103,address(self.keys_b['btc'].script_pubkey))

    def tearDown(self):
        self.a.close();self.b.close();self.node.close();self.btc.close();self.tmp.cleanup()

    def prepare(self):
        order=self.a.command('order',{'side':'sell','smw':'2.12345678','btc':'0.00007654'})['order']
        self.b.command('sync',{})
        session=self.b.command('reserve',{'id':order_id(order['body'])})['confirmation']['body']['session']
        self.a.command('peer_prepare',{'session':session});self.b.command('peer_prepare',{'session':session})
        self.a.command('peer_sync',{'session':session})
        return session

    def mine(self,coin,count=1):
        if coin=='btc':self.btc.mine(count)
        else:
            with self.node.lock,SwapChain(self.node.database) as chain:chain.mine(self.keys_a['smw'].script_pubkey,count)

    def locks(self,session):
        with self.assertRaises(ValueError):self.b.command('peer_fund',{'session':session})
        self.a.command('peer_fund',{'session':session});self.mine('smw')
        self.a.command('peer_sync',{'session':session})
        self.b.command('peer_fund',{'session':session});self.mine('btc')
        self.b.command('peer_sync',{'session':session})

    def test_independent_keys_real_claim_and_withheld_notice(self):
        session=self.prepare();self.locks(session)
        self.a.command('peer_claim',{'session':session});self.mine('btc')
        # Deliberately no peer sync: buyer learns preimage from Bitcoin blocks.
        self.b.command('peer_claim',{'session':session});self.mine('smw')
        for app in (self.a,self.b):self.assertTrue(app.command('peer_status',{'session':session})['received_confirmed'])
        with self.node.lock,SwapChain(self.node.database) as chain:
            self.assertEqual(chain.balance(self.keys_b['smw'].script_pubkey),212345678)
        _,state_a=self.a.peer_swap._get(session)
        raw=json.dumps(self.a.peer_swap.snapshot(session))
        self.assertNotIn('refund_raw',raw);self.assertNotIn('ciphertext',raw);self.assertNotIn(PASSWORD,raw)
        self.assertTrue(state_a['refund_raw'])
        for key in self.keys_a.values():self.assertNotIn(key._private_key.secret.hex(),raw)
        with self.assertRaises(ValueError):self.a.command('execute',{'session':session,'mode':'success'})

    def test_restart_locked_and_refund_without_peer_or_password(self):
        session=self.prepare();self.locks(session)
        for app in (self.a,self.b):
            with self.assertRaises(ValueError):app.command('peer_refund',{'session':session})
        self.a.close();self.b.close()
        self.a=Application(ROOT,self.path/'a');self.b=Application(ROOT,self.path/'b')
        self.assertTrue(self.a.state()['wallet']['locked']);self.assertTrue(self.b.state()['wallet']['locked'])
        self.mine('btc',16);self.mine('smw',41)
        for app,coin in ((self.a,'smw'),(self.b,'btc')):
            app.command('peer_refund',{'session':session});self.mine(coin)
            self.assertTrue(app.command('peer_status',{'session':session})['refund_confirmed'])

    def test_wrong_keys_terms_spoofed_complete_and_replay(self):
        session=self.prepare()
        packet=self.b.peer_swap.snapshot(session)
        forged=copy.deepcopy(packet);forged['body']['offer']['pubkeys']['btc']=self.keys_a['btc'].pubkey.hex()
        with self.assertRaises(Exception):self.a.peer_swap.receive(forged)
        forged=copy.deepcopy(packet);forged['body']['complete']=True
        forged=self.b.store.identity.sign(forged['body'])
        with self.assertRaises(ValueError):self.a.peer_swap.receive(forged)
        wrong=copy.deepcopy(packet['body']);wrong['offer']['pubkeys']['smw']=RegtestKey.from_int(123).pubkey.hex()
        with self.assertRaises(Exception):self.a.peer_swap.receive(self.b.store.identity.sign(wrong))
        old=self.a.peer_swap.snapshot(session)
        self.a.command('peer_fund',{'session':session});self.mine('smw');self.a.command('peer_sync',{'session':session})
        self.b.peer_swap.receive(old)
        _,state=self.b.peer_swap._get(session)
        self.assertIsNotNone(state['remote']['body']['funding'])

    def test_real_wallet_read_only_links_and_wrong_network(self):
        links=WalletLinks(self.path/'a')
        smw=self.a.vault.state()['addresses']['smw'];btc=self.b.vault.state()['addresses']['btc']
        result=links.configure('smw',self.config['smw_url'],self.config['smw_token'],smw)
        self.assertTrue(result['read_only']);self.assertGreater(result['available_units'],0)
        self.assertFalse(result['htlc_spending_supported'])
        result=links.configure('btc',self.config['btc_url'],self.config['btc_cookie'],btc)
        self.assertTrue(result['read_only']);self.assertEqual(result['available_units'],200*100000000)
        self.assertFalse(links.state()['public_trading'])
        raw=links.path.read_text();self.assertNotIn(self.node.token,raw)
        self.assertNotIn(self.btc.cookie.read_text().strip(),raw)
        with self.assertRaises(ValueError):links.configure('btc',self.config['btc_url'],self.config['btc_cookie'],smw.replace('bcrt','bc'))
        with self.assertRaises(ValueError):endpoint('http://example.com:8332/')
        with self.assertRaises(ValueError):endpoint('http://user:secret@127.0.0.1:8332/')
