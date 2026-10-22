"""Synchronization gates exercised through real loopback protocol messages."""

import asyncio
from dataclasses import replace
from pathlib import Path
import tempfile
import unittest

from sumuww.block import Block, GENESIS_TIME, mine_header
from sumuww.peer import PeerNode
from sumuww.primitives import COIN, merkle_root
from sumuww.transaction import TxOutput
from sumuww.wallet import RegtestKey
from sumuww.wire import (
    INV_BLOCK, PROTOCOL_VERSION, Inventory, Version, decode_inventory,
    decode_version, encode_headers, encode_inventory, encode_version,
    read_frame, write_frame,
)


KEY = RegtestKey.from_int(73)


async def eventually(predicate, timeout=8):
    deadline = asyncio.get_running_loop().time() + timeout
    while not predicate():
        if asyncio.get_running_loop().time() >= deadline:
            raise AssertionError('Peer did not reach the required state')
        await asyncio.sleep(.01)


class PeerSafetyTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix='sumuww-peer-safety-')
        self.nodes = []
        self.writers = []

    async def asyncTearDown(self):
        for writer in self.writers:
            writer.close()
        await asyncio.gather(*(node.stop() for node in self.nodes), return_exceptions=True)
        for writer in self.writers:
            try:
                await asyncio.wait_for(writer.wait_closed(), 1)
            except (OSError, TimeoutError):
                pass
        self.directory.cleanup()

    def node(self, **options):
        path = Path(self.directory.name) / f'node-{len(self.nodes)}.sqlite'
        node = PeerNode(path, poll_interval=.08, timeout=2,
                        clock=lambda: GENESIS_TIME + 10000, **options)
        self.nodes.append(node)
        return node

    async def send(self, writer, node, command, payload=b''):
        await write_frame(writer, command, payload, timeout=2, magic=node.network.message_magic)

    async def command(self, reader, node, command):
        for _ in range(30):
            frame = await read_frame(reader, timeout=2, magic=node.network.message_magic)
            if frame.command == command:
                return frame
        self.fail(f'Missing {command} frame')

    async def raw_peer(self, node, tip=None):
        reader, writer = await asyncio.open_connection(*node.address)
        self.writers.append(writer)
        frame = await self.command(reader, node, 'version')
        own = decode_version(frame.payload)
        remote = Version(PROTOCOL_VERSION, node.genesis, own.nonce ^ (len(self.writers) + 1),
                         node.network.profile_id, node.genesis if tip is None else tip)
        await self.send(writer, node, 'version', encode_version(remote))
        await self.command(reader, node, 'verack')
        await self.send(writer, node, 'verack')
        await self.command(reader, node, 'getheaders')
        await eventually(lambda: node.info()['peers'] > 0)
        return reader, writer

    async def finish_empty(self, node, writer):
        await self.send(writer, node, 'headers', encode_headers(()))
        await eventually(lambda: node.info()['mining_ready'])

    async def test_sumuww_handshake_is_not_ready_and_refresh_does_not_flap(self):
        node = self.node(network='dora')
        await node.start()
        self.assertEqual(node.info()['sync_state'], 'disconnected')
        reader, writer = await self.raw_peer(node)
        self.assertEqual(node.info()['sync_state'], 'syncing')
        self.assertFalse(node.info()['mining_ready'])
        await self.finish_empty(node, writer)
        self.assertEqual(node.info()['synchronized_peers'], 1)
        await node._request_headers(next(iter(node._sessions.values())))
        await self.command(reader, node, 'getheaders')
        # Merely asking a synchronized peer for a refresh does not interrupt
        # mining; a newly announced unknown block does.
        self.assertTrue(node.info()['mining_ready'])
        await self.send(writer, node, 'headers', encode_headers(()))
        writer.close()
        await eventually(lambda: node.info()['sync_state'] == 'disconnected')
        self.assertFalse(node.info()['mining_ready'])

    async def test_live_inventory_keeps_validated_tip_usable_without_accepting_unvalidated_body(self):
        node = self.node()
        await node.start()
        reader, writer = await self.raw_peer(node)
        await self.finish_empty(node, writer)
        # The already requested empty reply predates this newly announced
        # block. A fresh cycle must fetch it instead of declaring readiness.
        await node._request_headers(next(iter(node._sessions.values())))
        await self.command(reader, node, 'getheaders')
        block = node.chain.make_block(KEY.script_pubkey)
        await self.send(writer, node, 'inv', encode_inventory((Inventory(INV_BLOCK, block.block_hash()),)))
        await eventually(lambda: node.info()['live_block_updates'] == 1)
        self.assertTrue(node.info()['mining_ready'])
        await self.send(writer, node, 'headers', encode_headers(()))
        await self.command(reader, node, 'getheaders')
        self.assertEqual(node.info()['sync_state'], 'updating')
        await self.send(writer, node, 'headers', encode_headers((block.header,)))
        await self.command(reader, node, 'getdata')
        self.assertEqual(node.info()['height'], 0)
        await self.send(writer, node, 'block', block.serialize())
        await self.command(reader, node, 'getheaders')
        self.assertEqual(node.info()['height'], 1)
        self.assertTrue(node.info()['mining_ready'])
        await self.finish_empty(node, writer)

    async def test_header_pagination_cannot_finish_after_first_batch(self):
        node, source = self.node(), self.node()
        blocks = source.chain.mine(KEY.script_pubkey, 129)
        await node.start()
        reader, writer = await self.raw_peer(node, blocks[-1].block_hash())
        for batch in (blocks[:128], blocks[128:]):
            await self.send(writer, node, 'headers', encode_headers(tuple(block.header for block in batch)))
            for block in batch:
                request = await self.command(reader, node, 'getdata')
                self.assertEqual(decode_inventory(request.payload), (Inventory(INV_BLOCK, block.block_hash()),))
                await self.send(writer, node, 'block', block.serialize())
            await self.command(reader, node, 'getheaders')
            self.assertFalse(node.info()['mining_ready'])
        self.assertEqual(node.chain.tip_hash, blocks[-1].block_hash())
        self.assertEqual(node.chain.info()['utxo_commitment'], source.chain.info()['utxo_commitment'])
        await self.finish_empty(node, writer)

    async def test_invalid_body_revokes_ready_and_never_changes_ledger(self):
        node = self.node()
        await node.start()
        reader, writer = await self.raw_peer(node)
        await self.finish_empty(node, writer)
        await node._request_headers(next(iter(node._sessions.values())))
        await self.command(reader, node, 'getheaders')
        valid = node.chain.make_block(KEY.script_pubkey)
        coinbase = replace(valid.transactions[0], outputs=(TxOutput(51 * COIN, KEY.script_pubkey),))
        root, _ = merkle_root([coinbase.txid()])
        invalid = Block(mine_header(replace(valid.header, merkle_root=root)), (coinbase,))
        before = node.chain.info()
        await self.send(writer, node, 'headers', encode_headers((invalid.header,)))
        await self.command(reader, node, 'getdata')
        self.assertFalse(node.info()['mining_ready'])
        await self.send(writer, node, 'block', invalid.serialize())
        await eventually(lambda: node.info()['sessions'] == 0)
        self.assertEqual(node.chain.info(), before)
        self.assertFalse(node.chain.has_block(invalid.block_hash()))
        self.assertEqual(node.info()['stats']['validation_rejections'], 1)

    async def test_claimed_unknown_tip_cannot_complete_with_empty_headers(self):
        node = self.node()
        await node.start()
        _, writer = await self.raw_peer(node, b'\x73' * 32)
        await self.send(writer, node, 'headers', encode_headers(()))
        await eventually(lambda: node.info()['sessions'] == 0)
        self.assertFalse(node.info()['mining_ready'])
        self.assertEqual(node.info()['height'], 0)
        self.assertEqual(node.info()['stats']['protocol_errors'], 1)

    async def test_missing_body_cannot_turn_empty_headers_into_readiness(self):
        node = self.node()
        await node.start()
        reader, writer = await self.raw_peer(node)
        block = node.chain.make_block(KEY.script_pubkey)
        await self.send(writer, node, 'headers', encode_headers((block.header,)))
        await self.command(reader, node, 'getdata')
        await self.send(writer, node, 'notfound', encode_inventory((Inventory(INV_BLOCK, block.block_hash()),)))
        await eventually(lambda: node.info()['sessions'] == 0)
        self.assertFalse(node.info()['mining_ready'])
        self.assertEqual(node.info()['height'], 0)

    async def test_new_unsynchronized_backup_preserves_healthy_anchor_readiness(self):
        node = self.node()
        await node.start()
        _, first = await self.raw_peer(node)
        await self.finish_empty(node, first)
        _, second = await self.raw_peer(node)
        self.assertEqual(node.info()['peers'], 2)
        self.assertEqual(node.info()['synchronized_peers'], 1)
        self.assertTrue(node.info()['mining_ready'])
        self.assertEqual(1, sum(not session.synchronized for session in node._sessions.values()))
        second.close()
        await eventually(lambda: node.info()['mining_ready'])


if __name__ == '__main__':
    unittest.main()
