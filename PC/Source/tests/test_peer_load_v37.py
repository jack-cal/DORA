"""Bounded request amplification without changing block validation or wire limits."""
import asyncio
from pathlib import Path
import tempfile
import unittest

from sumuww.block import GENESIS_TIME
from sumuww.peer import PeerNode
from sumuww.wallet import RegtestKey
from sumuww.wire import INV_BLOCK, INV_TRANSACTION, MAX_INV, Inventory, ProtocolError, encode_inventory, decode_inventory


class DataRequestLoadTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.folder = tempfile.TemporaryDirectory(prefix='sumuww-owned-v37-request-')
        self.node = PeerNode(Path(self.folder.name) / 'node.sqlite', discover_peers=False,
                             clock=lambda: GENESIS_TIME + 10000)
        self.blocks = self.node.chain.mine(RegtestKey.from_int(7337).script_pubkey, 2)
        self.sent = []

        async def send(session, command, payload=b''):
            self.sent.append((command, payload))

        self.node._send = send

    async def asyncTearDown(self):
        await self.node.stop()
        self.folder.cleanup()

    async def test_repeated_known_body_is_served_once_per_request(self):
        item = Inventory(INV_BLOCK, self.blocks[0].block_hash())
        await self.node._serve_data(None, encode_inventory((item,) * MAX_INV))
        self.assertEqual([('block', self.blocks[0].serialize())], self.sent)

    async def test_repeated_missing_items_have_one_notfound_entry(self):
        item = Inventory(INV_BLOCK, bytes.fromhex('a1' * 32))
        await self.node._serve_data(None, encode_inventory((item,) * MAX_INV))
        self.assertEqual(['notfound'], [command for command, _ in self.sent])
        self.assertEqual((item,), decode_inventory(self.sent[0][1]))

    async def test_inventory_kind_remains_part_of_request_identity(self):
        digest = self.blocks[0].block_hash()
        body, transaction = Inventory(INV_BLOCK, digest), Inventory(INV_TRANSACTION, digest)
        await self.node._serve_data(None, encode_inventory((body, transaction, body, transaction)))
        self.assertEqual(['block', 'notfound'], [command for command, _ in self.sent])
        self.assertEqual((transaction,), decode_inventory(self.sent[1][1]))

    async def test_distinct_body_requests_preserve_order_and_raw_bytes(self):
        first, second = (Inventory(INV_BLOCK, block.block_hash()) for block in self.blocks)
        await self.node._serve_data(None, encode_inventory((second, first, second)))
        self.assertEqual([('block', self.blocks[1].serialize()), ('block', self.blocks[0].serialize())], self.sent)

    async def test_invalid_oversized_inventory_still_rejected_without_response(self):
        # Canonical compact-size 257 plus existing item bytes exceeds MAX_INV.
        item = Inventory(INV_BLOCK, self.blocks[0].block_hash())
        valid = encode_inventory((item,) * MAX_INV)
        oversized = b'\xfd\x01\x01' + valid[3:] + valid[3:39]
        with self.assertRaises(ProtocolError):
            await self.node._serve_data(None, oversized)
        self.assertEqual([], self.sent)


if __name__ == '__main__':
    unittest.main()
