"""Public SUMUWW genesis/profile with the actual RPC dispatcher; no user wallet."""
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from smw_trade.research_node import ResearchNode
from smw_trade.wallet_link import WalletLinks, LocalRPC
from smw_trade.vault import Vault
from sumuww.chain import Chain
from sumuww.rpc import RpcServer
from sumuww.address import encode_address
from sumuww.wallet import RegtestKey


class PublicProfileNode(ResearchNode):
    """Only a test fixture; it does not touch an existing public node/database."""
    def __init__(self,directory):
        self.methods=[]
        super().__init__(directory)
    def call(self,method,args):
        with self.lock,Chain(self.directory/'public-genesis.sqlite',network='sumuww') as chain:
            self.methods.append(method)
            node=SimpleNamespace(chain=chain,running=True,synchronization_info=lambda:{})
            return RpcServer(lambda:node,token=self.token).call(method,args)


class WalletLinkTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.path=Path(self.tmp.name)
        self.node=PublicProfileNode(self.path/'node').start()
        self.links=WalletLinks(self.path/'links')
        self.address=encode_address(RegtestKey.from_int(773).script_pubkey,network='sumuww')
        self.url=f'http://127.0.0.1:{self.node.port}/rpc'
    def tearDown(self):self.node.close();self.tmp.cleanup()
    def connect(self):return self.links.configure('smw',self.url,self.node.token_file,self.address)
    def test_public_profile_address_and_balance_are_read_from_actual_rpc(self):
        value=self.connect()
        self.assertEqual(value['address'],self.address)
        self.assertEqual(value['confirmed_units'],0);self.assertEqual(value['height'],0)
        self.assertFalse(value['htlc_spending_supported']);self.assertTrue(value['read_only'])
        self.assertEqual(self.node.methods,['getblockchaininfo','getblockhash','getaddressbalance','gethtlcinfo'])
        self.assertNotIn(self.node.token,self.links.path.read_text())
    def test_failed_refresh_removes_stale_balance_and_does_not_create_vault(self):
        self.connect()
        self.node.token_file.write_text('0'*64)
        with self.assertRaises(ValueError):self.links.refresh('smw')
        self.assertEqual(self.links.state()['results'],{})
        self.assertFalse((self.path/'links/wallet-regtest.vault').exists())
    def test_regtest_address_rejected_on_public_profile(self):
        address=encode_address(RegtestKey.from_int(773).script_pubkey,network='regtest')
        with self.assertRaises(ValueError):self.links.configure('smw',self.url,self.node.token_file,address)
        self.assertFalse(self.links.path.exists())
    def test_existing_public_node_cannot_be_configured_as_swap_node(self):
        from smw_trade.swap_backend import SMWBackend
        with self.assertRaises(ValueError):SMWBackend(self.url,self.node.token_file).info()
