"""Reproduce the actual miner pause during normal peer block notification."""
import asyncio,tempfile,threading,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock,MagicMock
from sumuww.app_service import AppService
from sumuww.peer import PeerNode,_Session,VERIFIED_PEER_FRESHNESS
from sumuww.profiles import SUMUWW
from sumuww.wallet import RegtestKey
from sumuww.wire import Inventory,INV_BLOCK,encode_headers,encode_inventory

class ConnectedWorkTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.clock=[100.0]
        self.node=PeerNode(Path(self.temp.name)/'node.sqlite',network='regtest',port=0,discover_peers=False)
        self.node._peer_clock=lambda:self.clock[0];self.node._running=True;self.node._send=AsyncMock()
        self.writer=MagicMock();self.writer.is_closing.return_value=False;self.writer.wait_closed=AsyncMock()
        self.session=_Session(asyncio.StreamReader(),self.writer,ready=True,header_requested=True)
        self.node._sessions[id(self.writer)]=self.session
    def tearDown(self):self.node.chain.close();self.temp.cleanup()
    async def notify(self,block):
        await self.node._received_inventory(self.session,encode_inventory((Inventory(INV_BLOCK,block.block_hash()),)))
    async def monitor(self,expected_pause):
        # Real main-network guard; owned temporary regtest blocks, no main coins.
        actor=SimpleNamespace(network=SUMUWW,_mining_reserved=True,_node=self.node,
            _mining_pause=threading.Event(),_mining_cancel=threading.Event(),_mining_state='running')
        task=asyncio.create_task(AppService._monitor_mining(actor))
        try:
            await asyncio.sleep(.12)
            self.assertEqual(expected_pause,actor._mining_pause.is_set())
            self.assertEqual('waiting' if expected_pause else 'running',actor._mining_state)
        finally:
            task.cancel()
            try:await task
            except asyncio.CancelledError:pass
    async def test_ordinary_new_block_does_not_pause_actual_mining_guard(self):
        await self.node._received_headers(self.session,encode_headers(()))
        block=self.node.chain.make_block(RegtestKey.from_int(4040).script_pubkey)
        original_tip=self.node.chain.tip_hash
        await self.notify(block)
        self.assertFalse(self.session.synchronized)
        await self.monitor(False)
        await self.node._received_headers(self.session,encode_headers((block.header,)))
        self.assertEqual(original_tip,self.node.chain.tip_hash)
        await self.monitor(False)
        await self.node._received_block(self.session,block.serialize())
        self.assertEqual(block.block_hash(),self.node.chain.tip_hash)
        await self.monitor(False)
        await self.node._received_headers(self.session,encode_headers(()))
        self.assertTrue(self.session.synchronized)
        self.assertFalse(self.session.live_update_pending)
        self.assertEqual(1,len(self.node._sessions))
    async def test_initial_sync_still_blocks_mining_before_full_body_and_terminal_reply(self):
        block=self.node.chain.make_block(RegtestKey.from_int(4041).script_pubkey)
        self.session.header_requested=False
        await self.notify(block)
        await self.monitor(True)
        await self.node._received_headers(self.session,encode_headers((block.header,)))
        await self.monitor(True)
        await self.node._received_block(self.session,block.serialize())
        await self.monitor(True)
        await self.node._received_headers(self.session,encode_headers(()))
        await self.monitor(False)
    async def test_unknown_fork_revokes_anchor_after_headers_reveal_it(self):
        sibling=self.node.chain.make_block(RegtestKey.from_int(4042).script_pubkey,extra_nonce=1)
        self.node.chain.mine(RegtestKey.from_int(4043).script_pubkey,1)
        await self.node._received_headers(self.session,encode_headers(()))
        await self.notify(sibling)
        await self.node._received_headers(self.session,encode_headers((sibling.header,)))
        await self.monitor(True)
    async def test_disconnection_and_stale_reply_still_pause_during_live_update(self):
        await self.node._received_headers(self.session,encode_headers(()))
        block=self.node.chain.make_block(RegtestKey.from_int(4044).script_pubkey)
        await self.notify(block)
        self.clock[0]+=VERIFIED_PEER_FRESHNESS+1
        await self.monitor(True)
        self.clock[0]=100.0;self.writer.is_closing.return_value=True
        await self.monitor(True)
    async def test_continuous_fully_validated_extensions_do_not_expire_old_anchor(self):
        await self.node._received_headers(self.session,encode_headers(()))
        for value in (4045,4046):
            self.clock[0]+=VERIFIED_PEER_FRESHNESS-1
            block=self.node.chain.make_block(RegtestKey.from_int(value).script_pubkey)
            self.session.header_requested=False
            await self.notify(block)
            await self.node._received_headers(self.session,encode_headers((block.header,)))
            await self.node._received_block(self.session,block.serialize())
            self.assertEqual(self.clock[0],self.session.last_verified_at)
            await self.monitor(False)

if __name__=='__main__':unittest.main()
