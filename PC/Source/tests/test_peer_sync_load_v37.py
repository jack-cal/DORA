"""Known-header refresh coalescing without delaying full-block validation."""
import asyncio
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import AsyncMock, MagicMock

from sumuww.block import GENESIS_TIME
from sumuww.chain import Chain
from sumuww.peer import PeerNode, _Session
from sumuww.wallet import RegtestKey
from sumuww.wire import (INV_BLOCK, Inventory, decode_getheaders, decode_inventory,
                       encode_headers, encode_inventory)

NOW = GENESIS_TIME + 4000
ALICE = RegtestKey.from_int(3701)
BOB = RegtestKey.from_int(3702)


class PeerSyncLoadTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.directory=tempfile.TemporaryDirectory(prefix='sumuww-owned-sync-load-',
                                                  dir=os.environ.get('SUMUWW_TEST_WORKDIR'))
        self.folder=Path(self.directory.name)
        self.node=PeerNode(self.folder/'target.sqlite',poll_interval=.1,clock=lambda:NOW,
                           discover_peers=False,dht_enabled=False)
        self.node._running=True
        self.node._send=AsyncMock()
        writer=MagicMock()
        writer.is_closing.return_value=False
        self.session=_Session(asyncio.StreamReader(),writer,ready=True)
        self.session.last_announced_tip=self.node.chain.tip_hash

    async def asyncTearDown(self):
        await self.node.stop()
        self.directory.cleanup()

    async def known_reply(self,headers):
        self.session.header_requested=True
        # Model a delayed reply: coalescing starts at completion, not send time.
        self.session.last_headers_at=asyncio.get_running_loop().time()-10
        await self.node._received_headers(self.session,encode_headers(tuple(headers)))

    async def test_known_only_reply_waits_for_poll_from_reply_completion(self):
        block=self.node.chain.mine(ALICE.script_pubkey,1)[0]
        self.session.last_announced_tip=self.node.chain.tip_hash
        started=asyncio.get_running_loop().time()
        await self.known_reply((block.header,))
        self.assertGreaterEqual(self.session.last_headers_at,started)
        self.node._send.assert_not_awaited()
        self.assertFalse(self.session.header_requested)
        self.assertFalse(self.session.synchronized)
        self.assertEqual(self.session.branch_tip,block.block_hash())
        completed=self.session.last_headers_at
        await self.node._poll_session(self.session,self.node.chain.tip_hash,(),completed+.09)
        self.node._send.assert_not_awaited()
        await self.node._poll_session(self.session,self.node.chain.tip_hash,(),completed+.11)
        self.assertTrue(self.session.header_requested)
        self.assertEqual(self.node._send.await_count,1)
        self.assertEqual(self.node._send.await_args.args[1],'getheaders')

    async def test_new_inventory_still_refreshes_immediately_during_coalescing(self):
        known=self.node.chain.mine(ALICE.script_pubkey,1)[0]
        await self.known_reply((known.header,))
        unknown=self.node.chain.make_block(ALICE.script_pubkey)
        await self.node._received_inventory(self.session,
              encode_inventory((Inventory(INV_BLOCK,unknown.block_hash()),)))
        self.assertTrue(self.session.header_requested)
        self.assertEqual(self.node._send.await_count,1)
        self.assertEqual(self.node._send.await_args.args[1],'getheaders')
        self.assertFalse(self.session.synchronized)

    async def test_full_body_validation_and_next_page_request_remain_immediate(self):
        with Chain(self.folder/'source.sqlite',clock=lambda:NOW) as source:
            blocks=source.mine(ALICE.script_pubkey,129)
        self.session.header_requested=True
        await self.node._received_headers(self.session,encode_headers(tuple(b.header for b in blocks[:128])))
        self.assertEqual(self.node._send.await_args.args[1],'getdata')
        self.assertEqual(decode_inventory(self.node._send.await_args.args[2]),
                         tuple(Inventory(INV_BLOCK,b.block_hash()) for b in blocks[:16]))
        self.assertEqual(len(self.session.block_requests),16)
        for block in blocks[:128]:
            await self.node._received_block(self.session,block.serialize())
            self.assertLessEqual(len(self.session.block_requests),16)
        requested=[item.digest for call in self.node._send.await_args_list
                   if call.args[1]=='getdata' for item in decode_inventory(call.args[2])]
        self.assertEqual(requested,[b.block_hash() for b in blocks[:128]])
        self.assertFalse(self.session.block_requests)
        self.assertEqual(self.node.chain.summary()['height'],128)
        self.assertEqual(self.node._send.await_args.args[1],'getheaders')
        self.assertTrue(self.session.header_requested)
        self.assertFalse(self.session.synchronized)
        await self.node._received_headers(self.session,encode_headers((blocks[128].header,)))
        await self.node._received_block(self.session,blocks[128].serialize())
        self.assertEqual(self.node.chain.tip_hash,blocks[-1].block_hash())
        self.assertEqual(self.node._send.await_args.args[1],'getheaders')
        await self.node._received_headers(self.session,encode_headers(()))
        self.assertTrue(self.session.synchronized)

    async def test_pipelined_body_already_received_from_another_peer_is_consumed(self):
        with Chain(self.folder/'source.sqlite',clock=lambda:NOW) as source:
            blocks=source.mine(ALICE.script_pubkey,20)
        self.session.header_requested=True
        await self.node._received_headers(self.session,encode_headers(tuple(b.header for b in blocks)))
        for block in blocks[:3]:self.node.chain.accept_block(block)
        # Queued wire replies must still be consumed in their original order.
        for block in blocks:await self.node._received_block(self.session,block.serialize())
        self.assertEqual(self.node.chain.tip_hash,blocks[-1].block_hash())
        self.assertFalse(self.session.block_requests)
        self.assertFalse(self.session.headers)

    async def test_known_shorter_branch_preserves_branch_locator_after_wait(self):
        self.node.chain.mine(ALICE.script_pubkey,3)
        with Chain(self.folder/'side.sqlite',clock=lambda:NOW) as side:
            blocks=side.mine(BOB.script_pubkey,2)
        for block in blocks:
            self.node.chain.accept_block(block)
        active=self.node.chain.tip_hash
        self.session.last_announced_tip=active
        await self.known_reply(tuple(b.header for b in blocks))
        self.assertEqual(self.node.chain.tip_hash,active)
        self.assertEqual(self.session.branch_tip,blocks[-1].block_hash())
        self.node._send.assert_not_awaited()
        await self.node._poll_session(self.session,active,(),self.session.last_headers_at+.11)
        locator,_=decode_getheaders(self.node._send.await_args.args[2])
        self.assertEqual(locator[0],blocks[-1].block_hash())

    async def test_unknown_header_still_blocks_readiness_before_full_body(self):
        block=self.node.chain.make_block(ALICE.script_pubkey)
        self.session.synchronized=True
        self.session.header_requested=True
        before=self.node.chain.state_commitment()
        await self.node._received_headers(self.session,encode_headers((block.header,)))
        self.assertFalse(self.session.synchronized)
        self.assertFalse(self.node.chain.has_block(block.block_hash()))
        self.assertEqual(self.node.chain.state_commitment(),before)
        self.assertEqual(self.node._send.await_args.args[1],'getdata')


if __name__=='__main__':
    unittest.main()
