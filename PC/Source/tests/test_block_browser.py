"""Public block pages and actual peer relay on isolated, fully validated chains."""
import asyncio
from dataclasses import replace
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from sumuww.app_service import AppService
from sumuww.block_history import block_history, block_transactions
from sumuww.chain import Chain
from sumuww.link_crypto import producer_output
from sumuww.peer import PeerNode
from sumuww.profiles import REGTEST
from sumuww.wallet import RegtestKey

SCRIPT=RegtestKey.from_int(701).script_pubkey
LOCAL='11'*32
REMOTE='22'*32

def mine(chain, identity=None, **options):
    original=chain.boundary.template_coinbase
    def template(coinbase,path):
        coinbase=original(coinbase,path)
        return replace(coinbase,outputs=coinbase.outputs+(producer_output(identity),)) if identity else coinbase
    with patch.object(chain.boundary,'template_coinbase',side_effect=template):
        block=chain.make_block(SCRIPT,**options)
    chain.accept_block(block)
    return block

class BlockHistoryTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.database=Path(self.temp.name)/'node.sqlite'
        self.chain=Chain(self.database)
    def tearDown(self):
        self.chain.close();self.temp.cleanup()
    def test_all_pages_reach_genesis_and_height_search_without_wallet(self):
        for index in range(103):mine(self.chain,LOCAL if index%2 else REMOTE)
        results=[block_history(self.database,offset,50,own_node_id=LOCAL) for offset in (0,50,100)]
        rows=[row for result in results for row in result['blocks']]
        self.assertEqual(list(range(103,-1,-1)),[r['height'] for r in rows])
        self.assertEqual(104,len({r['hash'] for r in rows}))
        self.assertEqual('unknown',rows[-1]['origin'])
        self.assertEqual({'local','other'},set(r['origin'] for r in rows[:-1]))
        self.assertEqual(0,block_history(self.database,height=0)['blocks'][0]['height'])
        self.assertEqual(99,block_history(self.database,height=99)['blocks'][0]['height'])
        self.assertEqual(1,len(block_history(self.database,999)['blocks']))
        for args in ({'height':104},{'height':-1},{'limit':51},{'offset':-1}):
            with self.assertRaises(ValueError):block_history(self.database,**args)
    def test_reorg_replaces_active_branch_in_same_height_page(self):
        genesis=self.chain.tip_hash
        old=mine(self.chain,LOCAL)
        branch=mine(self.chain,REMOTE,parent_hash=genesis,extra_nonce=12)
        winner=mine(self.chain,REMOTE,parent_hash=branch.block_hash())
        rows=block_history(self.database,own_node_id=LOCAL)['blocks']
        self.assertEqual(winner.block_hash()[::-1].hex(),rows[0]['hash'])
        self.assertNotIn(old.block_hash()[::-1].hex(),[r['hash'] for r in rows])
        self.assertEqual(0,rows[-1]['height'])
        for newer,older in zip(rows,rows[1:]):self.assertEqual(newer['parent_hash'],older['hash'])
    def test_body_reads_bounded_and_query_does_not_modify_database(self):
        for _ in range(52):mine(self.chain,REMOTE)
        from sumuww.block import Block
        changes=self.chain.connection.total_changes
        with patch('sumuww.block_history.Block.deserialize',wraps=Block.deserialize) as parse:
            result=block_history(self.database,50)
            self.assertEqual(3,parse.call_count)
            self.assertEqual(3,len(result['blocks']))
        self.assertEqual(changes,self.chain.connection.total_changes)
        self.assertEqual(52,self.chain.summary()['height'])
    def test_service_runs_read_off_event_loop_without_wallet(self):
        with tempfile.TemporaryDirectory() as root:
            service=AppService(Path(root),network=REGTEST,peers=[],bootstrap=False)
            try:
                service.start().result(timeout=10)
                self.assertIsNone(service.status().result(timeout=5)['wallet'])
                import threading
                def reader(*args):
                    self.assertNotEqual(service._thread.ident,threading.get_ident())
                    return block_history(*args)
                with patch('sumuww.block_history.block_history',side_effect=reader):
                    result=service.block_history(height=0).result(timeout=5)
                self.assertEqual([0],[r['height'] for r in result['blocks']])
                detail=service.block_transactions(result['blocks'][0]['hash']).result(timeout=5)
                self.assertTrue(detail['transactions'][0]['coinbase'])
            finally:service.stop().result(timeout=10)

    def test_other_wallet_rewards_and_transfers_are_visible_but_recent_stays_private(self):
        from sumuww.wallet_history import WalletHistory
        from sumuww.wallet import sign_p2wpkh
        from sumuww.transaction import Transaction, TxInput, TxOutput
        from sumuww.address import encode_address
        other=RegtestKey.from_int(702);recipient=RegtestKey.from_int(703)
        blocks=self.chain.mine(other.script_pubkey,100)
        reward=blocks[0].transactions[0]
        tx=Transaction(2,(TxInput(reward.txid(),0),),(TxOutput(reward.outputs[0].value-1000,recipient.script_pubkey),))
        tx=sign_p2wpkh(tx,0,reward.outputs[0],other)
        self.chain.submit_transaction(tx)
        block=self.chain.mine(other.script_pubkey)[0]
        digest=block.block_hash()[::-1].hex()
        details=block_transactions(self.database,digest,network=REGTEST)
        self.assertEqual([True,False],[t['coinbase'] for t in details['transactions']])
        self.assertEqual(tx.txid()[::-1].hex(),details['transactions'][1]['txid'])
        self.assertEqual(encode_address(recipient.script_pubkey,network=REGTEST),details['transactions'][1]['outputs'][0]['address'])
        self.assertEqual(reward.txid()[::-1].hex(),details['transactions'][1]['inputs'][0]['txid'])
        self.assertEqual([],WalletHistory(SCRIPT).recent(self.chain))
        self.assertEqual(1,len(block_transactions(self.database,digest,offset=1,limit=1,network=REGTEST)['transactions']))
        self.assertEqual(1,details['confirmations'])
        self.chain.mine(SCRIPT)
        self.assertEqual(2,block_transactions(self.database,digest,network=REGTEST)['confirmations'])

    def test_details_reject_orphan_block_after_reorganization(self):
        genesis=self.chain.tip_hash
        old=mine(self.chain,LOCAL)
        fork=mine(self.chain,REMOTE,parent_hash=genesis,extra_nonce=31)
        mine(self.chain,REMOTE,parent_hash=fork.block_hash())
        with self.assertRaisesRegex(ValueError,'active chain'):
            block_transactions(self.database,old.block_hash()[::-1].hex(),network=REGTEST)
        for value in ('bad','00'*32):
            with self.assertRaises(ValueError):block_transactions(self.database,value)

class BlockHistoryPeerTests(unittest.IsolatedAsyncioTestCase):
    async def test_three_real_nodes_and_browsing_while_mining(self):
        with tempfile.TemporaryDirectory() as folder:
            nodes=[PeerNode(Path(folder)/f'{i}.sqlite',discover_peers=False,
                            dht_enabled=False,poll_interval=.04,timeout=3) for i in range(3)]
            async def wait(check):
                for _ in range(250):
                    if check():return
                    await asyncio.sleep(.02)
                self.fail('Three-node synchronization deadline')
            try:
                for node in nodes:await node.start()
                await nodes[0].connect(*nodes[1].address)
                await nodes[1].connect(*nodes[2].address)
                await wait(lambda:all(n.synchronization_info()['mining_ready'] for n in nodes))
                for i,identity in enumerate((LOCAL,REMOTE,LOCAL)):
                    block=mine(nodes[i].chain,identity)
                    await wait(lambda:all(n.chain.tip_hash==block.block_hash() for n in nodes))
                    results=await asyncio.gather(*(asyncio.to_thread(block_history,n.chain.database,0,50,None,LOCAL) for n in nodes))
                    self.assertTrue(all(r['tip_hash']==block.block_hash()[::-1].hex() for r in results))
                    self.assertEqual(['local','other','local'][i],results[0]['blocks'][0]['origin'])
                    self.assertTrue(all(n.synchronization_info()['mining_ready'] for n in nodes))
                self.assertEqual([3,2,1,0],[r['height'] for r in results[0]['blocks']])
            finally:
                for node in reversed(nodes):await node.stop()
