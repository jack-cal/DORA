"""Punish definitive invalid data, never valid competing proof-of-work chains."""

import asyncio
from dataclasses import replace
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch

from sumuww.block import Block, GENESIS_TIME, mine_header
from sumuww.errors import UnsupportedFeature
from sumuww.peer import PeerNode, MAX_INVALID_PEER_IPS
from sumuww.primitives import COIN, merkle_root
from sumuww.transaction import Transaction, TxInput, TxOutput
from sumuww.wallet import RegtestKey
from sumuww.wire import (
    INV_BLOCK, INV_TRANSACTION, PROTOCOL_VERSION, Inventory, Version,
    decode_version, encode_headers, encode_inventory, encode_version,
    encode_frame, encode_ping, read_frame, write_frame,
)


NOW = GENESIS_TIME + 10000
ALICE = RegtestKey.from_int(1)
BOB = RegtestKey.from_int(2)


async def eventually(predicate, timeout=8):
    deadline = asyncio.get_running_loop().time() + timeout
    while not predicate():
        if asyncio.get_running_loop().time() >= deadline:
            raise AssertionError('Peer did not reach the expected state')
        await asyncio.sleep(.01)


class PeerEnforcementTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix='sumuww-peer-enforcement-')
        self.nodes = []
        self.writers = []
        self.policy_time = [1000.0]
        self.chain_time = [NOW]

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

    def node(self):
        path = Path(self.directory.name) / f'node-{len(self.nodes)}.sqlite'
        node = PeerNode(path, poll_interval=.08, timeout=2,
                        clock=lambda: self.chain_time[0])
        node._enforcement_clock = lambda: self.policy_time[0]
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
        remote = Version(PROTOCOL_VERSION, node.genesis, own.nonce ^ len(self.writers),
                         node.network.profile_id, node.genesis if tip is None else tip)
        await self.send(writer, node, 'version', encode_version(remote))
        await self.command(reader, node, 'verack')
        await self.send(writer, node, 'verack')
        await self.command(reader, node, 'getheaders')
        return reader, writer

    async def offer_block(self, node, block):
        reader, writer = await self.raw_peer(node)
        await self.send(writer, node, 'headers', encode_headers((block.header,)))
        await self.command(reader, node, 'getdata')
        await self.send(writer, node, 'block', block.serialize())
        return reader, writer

    def overclaimed_block(self, node):
        valid = node.chain.make_block(ALICE.script_pubkey)
        coinbase = replace(valid.transactions[0], outputs=(TxOutput(51 * COIN, ALICE.script_pubkey),))
        root, _ = merkle_root([coinbase.txid()])
        return Block(mine_header(replace(valid.header, merkle_root=root)), (coinbase,))

    async def test_repeated_invalid_blocks_are_rejected_and_cooldown_expires(self):
        node = self.node()
        await node.start()
        invalid = self.overclaimed_block(node)
        before = node.chain.info()
        for index in range(3):
            await self.offer_block(node, invalid)
            await eventually(lambda: node.info()['sessions'] == 0)
            self.assertEqual(index + 1, node.info()['stats']['invalid_peer_incidents'])
            self.assertEqual(before, node.chain.info())
            self.assertFalse(node.chain.has_block(invalid.block_hash()))
        self.assertEqual(1, node.info()['peer_enforcement']['cooling_down_ips'])
        reader, writer = await asyncio.open_connection(*node.address)
        self.writers.append(writer)
        self.assertEqual(b'', await asyncio.wait_for(reader.read(), 2))
        self.assertGreaterEqual(node.info()['stats']['cooldown_rejections'], 1)
        self.policy_time[0] += 301
        _, writer = await self.raw_peer(node)
        await self.send(writer, node, 'headers', encode_headers(()))
        await eventually(lambda: node.info()['mining_ready'])
        self.assertEqual(0, node.info()['peer_enforcement']['tracked_ips'])

    async def test_malformed_payloads_are_counted_but_unknown_tip_is_not(self):
        node = self.node()
        await node.start()
        for _ in range(3):
            _, writer = await self.raw_peer(node, b'\x88' * 32)
            await self.send(writer, node, 'headers', encode_headers(()))
            await eventually(lambda: node.info()['sessions'] == 0)
        self.assertEqual(0, node.info()['stats']['invalid_peer_incidents'])
        for index in range(3):
            _, writer = await self.raw_peer(node)
            await self.send(writer, node, 'ping', b'wrong')
            await eventually(lambda: node.info()['sessions'] == 0)
            self.assertEqual(index + 1, node.info()['stats']['invalid_peer_incidents'])
        self.assertEqual(1, node.info()['stats']['peer_cooldowns'])

    async def test_equal_work_and_seven_block_valid_branch_are_unrestricted(self):
        target, source = self.node(), self.node()
        target.chain.mine(ALICE.script_pubkey, 6)
        old = target.chain.tip_hash
        source.chain.mine(BOB.script_pubkey, 6)
        await target.start()
        await source.start()
        await target.connect(*source.address)
        await eventually(lambda: target.chain.has_block(source.chain.tip_hash)
                         and target.info()['mining_ready'])
        self.assertEqual(old, target.chain.tip_hash)
        self.assertNotEqual(source.chain.tip_hash, old)
        source.chain.mine(BOB.script_pubkey)
        await eventually(lambda: target.chain.tip_hash == source.chain.tip_hash
                         and target.info()['mining_ready'])
        self.assertTrue(target.chain.has_block(old))
        self.assertEqual(7, target.info()['height'])
        for node in (source, target):
            self.assertEqual(0, node.info()['stats']['invalid_peer_incidents'])
            self.assertEqual(0, node.info()['peer_enforcement']['cooling_down_ips'])

    async def test_partial_connection_loss_is_unscored_but_corrupt_frame_is_scored(self):
        node = self.node()
        await node.start()
        for _ in range(3):
            _, writer = await self.raw_peer(node)
            writer.write(node.network.message_magic[:1])
            await writer.drain()
            writer.close()
            await eventually(lambda: node.info()['sessions'] == 0)
        self.assertEqual(0, node.info()['stats']['invalid_peer_incidents'])
        for index in range(3):
            _, writer = await self.raw_peer(node)
            frame = encode_frame('ping', encode_ping(7), magic=node.network.message_magic)
            writer.write(frame[:-1] + bytes((frame[-1] ^ 1,)))
            await writer.drain()
            await eventually(lambda: node.info()['sessions'] == 0)
            self.assertEqual(index + 1, node.info()['stats']['invalid_peer_incidents'])
        self.assertEqual(1, node.info()['peer_enforcement']['cooling_down_ips'])

    async def test_future_timestamp_can_be_retried_without_penalty(self):
        node = self.node()
        await node.start()
        block = node.chain.make_block(ALICE.script_pubkey, timestamp=NOW + 7201)
        for _ in range(3):
            await self.offer_block(node, block)
            await eventually(lambda: node.info()['sessions'] == 0)
        self.assertEqual(3, node.info()['stats']['validation_rejections'])
        self.assertEqual(0, node.info()['stats']['invalid_peer_incidents'])
        self.assertEqual(0, node.info()['height'])
        self.chain_time[0] += 2
        reader, writer = await self.offer_block(node, block)
        await self.command(reader, node, 'getheaders')
        await self.send(writer, node, 'headers', encode_headers(()))
        await eventually(lambda: node.info()['height'] == 1 and node.info()['mining_ready'])

    async def test_unsupported_feature_does_not_penalize_a_peer(self):
        node = self.node()
        await node.start()
        block = node.chain.make_block(ALICE.script_pubkey)
        with patch.object(node.chain, 'accept_block', side_effect=UnsupportedFeature('fixture')):
            for _ in range(3):
                await self.offer_block(node, block)
                await eventually(lambda: node.info()['sessions'] == 0)
        self.assertEqual(3, node.info()['stats']['unsupported_features'])
        self.assertEqual(0, node.info()['stats']['invalid_peer_incidents'])
        _, writer = await self.raw_peer(node)
        await self.send(writer, node, 'headers', encode_headers(()))
        await eventually(lambda: node.info()['mining_ready'])

    async def test_missing_mempool_inputs_do_not_count_or_disconnect(self):
        node = self.node()
        await node.start()
        reader, writer = await self.raw_peer(node)
        await self.send(writer, node, 'headers', encode_headers(()))
        await eventually(lambda: node.info()['mining_ready'])
        for index in range(3):
            transaction = Transaction(2, (TxInput(bytes([index + 1]) * 32, 0),),
                                      (TxOutput(COIN, BOB.script_pubkey),))
            await self.send(writer, node, 'inv', encode_inventory((Inventory(INV_TRANSACTION, transaction.txid()),)))
            await self.command(reader, node, 'getdata')
            await self.send(writer, node, 'tx', transaction.serialize())
            await eventually(lambda: node.info()['stats']['validation_rejections'] == index + 1)
        self.assertEqual(1, node.info()['peers'])
        self.assertEqual(0, node.info()['stats']['invalid_peer_incidents'])
        self.assertEqual((), node.chain.mempool_transactions())

    async def test_outgoing_dns_addresses_observe_numeric_ip_cooldown(self):
        node = self.node()
        await node.start()
        invalid = self.overclaimed_block(node)
        for _ in range(3):
            await self.offer_block(node, invalid)
            await eventually(lambda: node.info()['sessions'] == 0)
        with patch.object(node, '_resolve_target', new=AsyncMock(return_value=(('127.0.0.1', 8123), ('127.0.0.2', 8123)))), \
                patch('sumuww.peer.asyncio.open_connection', new=AsyncMock(return_value=('reader', 'writer'))) as dial:
            self.assertEqual(('reader', 'writer'), await node._open_target(('example.invalid', 8123)))
            self.assertEqual('127.0.0.2', dial.await_args.args[0])
            self.assertEqual(1, dial.await_count)

    async def test_incident_buckets_are_bounded_and_expire(self):
        node = self.node()
        for index in range(MAX_INVALID_PEER_IPS + 3):
            address = f'10.0.{index // 255}.{index % 255 + 1}'
            node._record_invalid_peer(SimpleNamespace(remote_ip=address))
        self.assertEqual(MAX_INVALID_PEER_IPS, node.info()['peer_enforcement']['tracked_ips'])
        self.assertEqual(0, node.info()['peer_enforcement']['cooling_down_ips'])
        self.policy_time[0] += 601
        self.assertEqual(0, node.info()['peer_enforcement']['tracked_ips'])


if __name__ == '__main__':
    unittest.main()
