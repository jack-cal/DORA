"""Owned loopback proofs for optional discovery, reorg bodies and frame budgets."""
import asyncio
from dataclasses import replace
from pathlib import Path
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from sumuww import peer
from sumuww.block import Block, GENESIS_TIME, mine_header
from sumuww.chain import Chain
from sumuww.errors import InvalidBlock
from sumuww.primitives import COIN, merkle_root
from sumuww.transaction import TxOutput
from sumuww.wallet import RegtestKey
from sumuww.wire import (DISCOVERY_PROTOCOL_VERSION, INV_BLOCK, Inventory, ProtocolError,
                       decode_inventory, encode_addresses, encode_frame, read_frame)

OWNED_EVIDENCE = {}

async def eventually(predicate, timeout=10):
    async with asyncio.timeout(timeout):
        while not predicate():
            await asyncio.sleep(.005)


class FrameBudgetTests(unittest.IsolatedAsyncioTestCase):
    async def test_idle_wait_is_longer_than_partial_frame_budget(self):
        reader = asyncio.StreamReader()
        task = asyncio.create_task(read_frame(reader, .02, idle_timeout=.2))
        await asyncio.sleep(.08)
        reader.feed_data(encode_frame('ping', bytes(8)))
        self.assertEqual('ping', (await task).command)
        OWNED_EVIDENCE['idle_first_byte'] = {'frame_seconds': .02, 'idle_seconds': .2, 'valid_frame_delay_seconds': .08}

    async def test_first_byte_starts_short_whole_frame_deadline(self):
        reader = asyncio.StreamReader()
        started = time.monotonic()
        task = asyncio.create_task(read_frame(reader, .04, idle_timeout=.5))
        await asyncio.sleep(.02)
        reader.feed_data(b'\xfa')
        with self.assertRaisesRegex(ProtocolError, 'Whole-frame read timed out'):
            await task
        self.assertLess(time.monotonic() - started, .25)
        OWNED_EVIDENCE['partial_frame'] = {'frame_seconds': .04, 'idle_seconds': .5,
                                           'observed_timeout_seconds': time.monotonic() - started}


class PeerStabilityTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='sumuww-owned-v35-stability-')
        self.folder = Path(self.temporary.name)
        self.nodes = []

    async def asyncTearDown(self):
        await asyncio.gather(*(node.stop() for node in self.nodes), return_exceptions=True)
        self.temporary.cleanup()

    def node(self, name, **extra):
        options = {'network': 'regtest', 'host': '127.0.0.1', 'port': 0,
                   'poll_interval': .03, 'timeout': 5, 'discover_peers': False,
                   'dht_enabled': False, 'clock': lambda: GENESIS_TIME + 1000}
        options.update(extra)
        node = peer.PeerNode(self.folder / (name + '.sqlite'), **options)
        self.nodes.append(node)
        return node

    async def connected(self, reciprocal=False, **extra):
        target, remote = self.node('target', **extra), self.node('remote', **extra)
        await asyncio.gather(target.start(), remote.start())
        await target.connect(*remote.address)
        if reciprocal:
            await remote.connect(*target.address)
        await eventually(lambda: target.synchronization_info()['mining_ready'] and
                         remote.synchronization_info()['mining_ready'])
        return target, remote

    async def test_reply_relative_query_spacing_supports_legacy_strict_receiver(self):
        target, remote = await self.connected(discover_peers=True, discovery_interval=1)
        original = peer.PeerNode._serve_addresses
        received = []
        delayed = False
        starting = [set(node._sessions) for node in (target, remote)]

        async def legacy_with_jitter(node, session, payload):
            nonlocal delayed
            if node is remote:
                if not delayed:
                    delayed = True
                    await asyncio.sleep(.25)
                now = asyncio.get_running_loop().time()
                # Match the strict older listener; new sender must avoid its
                # boundary even when the first query's latency is higher.
                if now - session.last_discovery_response < node.discovery_interval:
                    raise ProtocolError('Peer address request rate exceeded')
                received.append(now)
            return await original(node, session, payload)

        with patch.object(peer.PeerNode, '_serve_addresses', legacy_with_jitter):
            await eventually(lambda: len(received) >= 3, timeout=5)
        self.assertGreaterEqual(received[1] - received[0], 1)
        self.assertGreaterEqual(received[2] - received[1], 1)
        for index, node in enumerate((target, remote)):
            self.assertEqual(starting[index], set(node._sessions))
            self.assertEqual(0, node._stats['protocol_errors'])
            self.assertTrue(node.synchronization_info()['mining_ready'])
        OWNED_EVIDENCE['legacy_strict_address_jitter'] = {
            'interval_seconds': 1, 'first_query_processing_delay_seconds': .25,
            'receiver_gaps_seconds': [received[1] - received[0], received[2] - received[1]],
            'original_sessions_preserved': True, 'protocol_errors': 0}

    async def test_early_empty_query_is_ignored_without_extra_response(self):
        target, remote = await self.connected(discover_peers=True, discovery_interval=30)
        session = next(iter(remote._sessions.values()))
        previous = session.last_discovery_response
        responses = remote._stats['address_responses_sent']
        for _ in range(10):
            await remote._serve_addresses(session, b'')
        self.assertEqual(previous, session.last_discovery_response)
        self.assertEqual(responses, remote._stats['address_responses_sent'])
        self.assertEqual(10, remote._stats['address_rate_rejections'])
        self.assertFalse(session.writer.is_closing())
        candidates=remote._addresses.info()['candidates']
        remote._received_addresses(session, encode_addresses(None))
        self.assertEqual(candidates,remote._addresses.info()['candidates'])
        self.assertFalse(session.writer.is_closing())
        OWNED_EVIDENCE['early_optional_requests'] = {'ignored': 10, 'additional_responses': 0,
                                                    'session_preserved': True, 'late_duplicate_addr_ignored': True}

    async def test_one_peer_and_normal_5_point_5_second_reply_keep_connection(self):
        target = remote = None
        original = peer.PeerNode._handle
        entered = asyncio.Event()
        armed = False
        delayed = False

        async def slow_reply(node, session, frame):
            nonlocal delayed
            if node is remote and armed and frame.command == 'getheaders' and not delayed:
                delayed = True
                entered.set()
                await asyncio.sleep(5.5)
            return await original(node, session, frame)

        with patch.object(peer.PeerNode, '_handle', slow_reply):
            # Install before the socket reader binds its next handler.
            target, remote = await self.connected()
            await eventually(lambda: all(not session.header_requested and not session.headers
                                         for session in target._sessions.values()))
            self.assertEqual(1, len(target._sessions))
            self.assertTrue(target.synchronization_info()['mining_ready'])
            starting = [set(node._sessions) for node in (target, remote)]
            armed = True
            # Stable peers now refresh every ten seconds. Trigger the owned
            # delayed response explicitly; keep its original reply deadlines.
            await target._request_headers(next(iter(target._sessions.values())))
            await asyncio.wait_for(entered.wait(), 1)
            await asyncio.sleep(5.7)
        for index, node in enumerate((target, remote)):
            self.assertEqual(starting[index], set(node._sessions))
            self.assertEqual(0, node._stats['protocol_errors'])
            self.assertEqual(0, node._stats['requests_expired'])
            self.assertTrue(node.synchronization_info()['mining_ready'])
        OWNED_EVIDENCE['one_peer_delayed_reply'] = {'ready_peers': 1, 'configured_timeout_seconds': 5,
                                                   'normal_reply_delay_seconds': 5.5,
                                                   'original_sessions_preserved': True,
                                                   'protocol_errors': 0, 'requests_expired': 0}

    async def reorg_case(self, missing=False):
        target = remote = None
        original_handle, original_data = peer.PeerNode._handle, peer.PeerNode._serve_data
        headers_gate, body_gate = asyncio.Event(), asyncio.Event()
        held_headers = set()
        held_body = asyncio.Event()
        armed = False
        old_tip = None

        async def delayed_headers(node, session, frame):
            if node is remote and armed and frame.command == 'getheaders':
                held_headers.add(id(session))
                await headers_gate.wait()
            return await original_handle(node, session, frame)

        async def delayed_or_missing_body(node, session, payload):
            items = decode_inventory(payload)
            if node is remote and old_tip is not None and Inventory(INV_BLOCK, old_tip) in items:
                held_body.set()
                if missing:
                    from sumuww.wire import encode_inventory
                    await node._send(session, 'notfound', encode_inventory((Inventory(INV_BLOCK, old_tip),)))
                    return
                await body_gate.wait()
            return await original_data(node, session, payload)

        with Chain(self.folder / 'fork.sqlite', clock=lambda: GENESIS_TIME + 1000) as fork:
            replacement = fork.mine(RegtestKey.from_int(3502).script_pubkey, 4)
        with patch.object(peer.PeerNode, '_handle', delayed_headers), \
                patch.object(peer.PeerNode, '_serve_data', delayed_or_missing_body):
            # Readers resolve _handle before awaiting the next frame, so arm
            # these hooks on readers created while the patch is active.
            target, remote = await self.connected(reciprocal=True)
            await eventually(lambda: all(session.synchronized and not session.header_requested and not session.headers
                                         for session in target._sessions.values()))
            old_target = tuple(target._sessions.values())
            old_remote = tuple(remote._sessions.values())
            starting = [set(node._sessions) for node in (target, remote)]
            armed = True
            try:
                # Exercise both original sockets without waiting for the
                # stable-peer fallback interval to arm this reorg fixture.
                await asyncio.gather(*(target._request_headers(session) for session in old_target))
                await eventually(lambda: len(held_headers) == len(old_target))
                old_blocks = remote.chain.mine(RegtestKey.from_int(3501).script_pubkey, 3)
                old_tip = old_blocks[-1].block_hash()
                await eventually(lambda: all(old_tip in session.unknown_blocks for session in old_target))
                for block in replacement:
                    remote.chain.accept_block(block)
                armed = False
                headers_gate.set()
                await asyncio.wait_for(held_body.wait(), 5)
                if missing:
                    await eventually(lambda: all(session.writer.is_closing() for session in old_target))
                    self.assertTrue(all(not session.synchronized for session in old_target))
                    self.assertFalse(target.chain.has_block(old_tip))
                    self.assertGreaterEqual(target._stats['protocol_errors'], 1)
                    OWNED_EVIDENCE['missing_stale_body'] = {'notfound_rejects_old_sessions': True,
                                                            'old_tip_not_stored': True,
                                                            'old_sessions_synchronized': False}
                    return
                self.assertEqual(replacement[-1].block_hash(), target.chain.tip_hash)
                self.assertFalse(target.synchronization_info()['mining_ready'])
                self.assertFalse(target.chain.has_block(old_tip))
                body_gate.set()
                await eventually(lambda: target.synchronization_info()['mining_ready'] and
                                 remote.synchronization_info()['mining_ready'])
                for block in old_blocks:
                    self.assertTrue(target.chain.has_block(block.block_hash()))
                self.assertEqual(replacement[-1].block_hash(), target.chain.tip_hash)
                for index, node in enumerate((target, remote)):
                    self.assertEqual(starting[index], set(node._sessions))
                    self.assertEqual(0, node._stats['protocol_errors'])
                    self.assertEqual(0, node._stats['validation_rejections'])
                self.assertTrue(all(not session.writer.is_closing() for session in old_remote))
                OWNED_EVIDENCE['valid_stale_tip_reorg'] = {
                    'original_sessions_per_node': len(old_target), 'orphan_blocks_fully_validated': len(old_blocks),
                    'active_height': target.chain.summary()['height'], 'readiness_before_body': False,
                    'readiness_after_body': True, 'original_sessions_preserved': True,
                    'protocol_errors': 0, 'validation_rejections': 0}
            finally:
                armed = False
                headers_gate.set()
                body_gate.set()

    async def test_valid_reorg_fetches_old_tip_ancestors_before_readiness(self):
        await self.reorg_case()

    async def test_unavailable_stale_tip_body_never_promotes_old_session(self):
        await self.reorg_case(missing=True)

    async def test_hint_body_uses_full_coinbase_validation(self):
        node = self.node('invalid-hint')
        valid = node.chain.make_block(RegtestKey.from_int(3503).script_pubkey)
        coinbase = replace(valid.transactions[0], outputs=(TxOutput(51 * COIN, RegtestKey.from_int(3503).script_pubkey),))
        root, _ = merkle_root([coinbase.txid()])
        invalid = Block(mine_header(replace(valid.header, merkle_root=root)), (coinbase,))
        session = peer._Session(None, None)
        session.hint_requested = invalid.block_hash()
        before = node.chain.info()
        with self.assertRaises(InvalidBlock):
            await node._received_block(session, invalid.serialize())
        self.assertFalse(node.chain.has_block(invalid.block_hash()))
        self.assertEqual(before, node.chain.info())
        self.assertFalse(session.synchronized)
        OWNED_EVIDENCE['invalid_hint_body'] = {'excess_coinbase_rejected': True, 'ledger_unchanged': True,
                                              'unvalidated_block_stored': False, 'synchronized': False}

    async def test_pending_reply_expiration_remains_bounded(self):
        target, remote = await self.connected()
        session = next(iter(target._sessions.values()))
        session.header_requested = True
        now = asyncio.get_running_loop().time()
        session.header_requested_at = now - 31
        await target._poll_session(session, target.chain.tip_hash, (), now)
        self.assertTrue(session.writer.is_closing())
        self.assertFalse(session.synchronized)
        self.assertEqual(1, target._stats['requests_expired'])
        OWNED_EVIDENCE['reply_budget_expiration'] = {'request_age_seconds': 31,
                                                   'budget_seconds': peer.CONNECTED_REPLY_TIMEOUT,
                                                   'session_closed': True, 'synchronized': False}

    async def test_hint_count_limit_rejects_next_valid_ancestor_without_store(self):
        node = self.node('hint-count-target')
        with Chain(self.folder / 'hint-count-fork.sqlite', clock=lambda: GENESIS_TIME + 1000) as fork:
            blocks = fork.mine(RegtestKey.from_int(3504).script_pubkey, peer.MAX_HINT_BLOCKS + 1)
        session = peer._Session(None, None)
        session.hint_blocks = {block.block_hash(): (block, len(block.serialize())) for block in blocks[1:]}
        session.hint_block_bytes = sum(size for _, size in session.hint_blocks.values())
        session.hint_requested = blocks[0].block_hash()
        before = node.chain.info()
        with self.assertRaisesRegex(ProtocolError, 'bounded body budget'):
            await node._received_block(session, blocks[0].serialize())
        self.assertEqual(before, node.chain.info())
        self.assertFalse(session.synchronized)
        self.assertFalse(any(node.chain.has_block(block.block_hash()) for block in blocks))
        OWNED_EVIDENCE['hint_count_overflow'] = {'limit': peer.MAX_HINT_BLOCKS, 'pending_blocks': len(session.hint_blocks),
                                               'new_blocks_stored': 0, 'synchronized': False}

    async def test_hint_byte_limit_rejects_next_valid_ancestor_without_store(self):
        node = self.node('hint-bytes-target')
        key = RegtestKey.from_int(3505)
        blocks = []
        with Chain(self.folder / 'hint-bytes-fork.sqlite', clock=lambda: GENESIS_TIME + 1000) as fork:
            # These are canonical, consensus-valid coinbases. Their outputs
            # make real serialized bodies cross the memory budget before the
            # block-count limit, without fabricated byte accounting.
            outputs = (TxOutput(50 * COIN, key.script_pubkey),) + (TxOutput(0, b'\x6a' + bytes(999)),) * 900
            for _ in range(10):
                ordinary = fork.make_block(key.script_pubkey)
                coinbase = replace(ordinary.transactions[0], outputs=outputs)
                root, _ = merkle_root([coinbase.txid()])
                block = Block(mine_header(replace(ordinary.header, merkle_root=root)), (coinbase,))
                self.assertTrue(fork.accept_block(block))
                blocks.append(block)
        session = peer._Session(None, None)
        session.hint_blocks = {block.block_hash(): (block, len(block.serialize())) for block in blocks[1:]}
        session.hint_block_bytes = sum(size for _, size in session.hint_blocks.values())
        session.hint_requested = blocks[0].block_hash()
        self.assertLessEqual(session.hint_block_bytes, peer.MAX_HINT_BLOCK_BYTES)
        self.assertGreater(session.hint_block_bytes + len(blocks[0].serialize()), peer.MAX_HINT_BLOCK_BYTES)
        before = node.chain.info()
        with self.assertRaisesRegex(ProtocolError, 'bounded body budget'):
            await node._received_block(session, blocks[0].serialize())
        self.assertEqual(before, node.chain.info())
        self.assertFalse(session.synchronized)
        self.assertFalse(any(node.chain.has_block(block.block_hash()) for block in blocks))
        OWNED_EVIDENCE['hint_bytes_overflow'] = {'limit': peer.MAX_HINT_BLOCK_BYTES,
                                               'pending_bytes': session.hint_block_bytes,
                                               'incoming_bytes': len(blocks[0].serialize()),
                                               'new_blocks_stored': 0, 'synchronized': False}

    async def test_hint_digest_mismatch_is_rejected_without_store(self):
        node = self.node('hint-digest-target')
        block = node.chain.make_block(RegtestKey.from_int(3506).script_pubkey)
        session = peer._Session(None, None)
        session.hint_requested = bytes.fromhex('ab' * 32)
        before = node.chain.info()
        with self.assertRaisesRegex(ProtocolError, 'differs from its requested header'):
            await node._received_block(session, block.serialize())
        self.assertEqual(before, node.chain.info())
        self.assertFalse(node.chain.has_block(block.block_hash()))
        self.assertFalse(session.synchronized)
        OWNED_EVIDENCE['hint_digest_mismatch'] = {'rejected': True, 'unrequested_block_stored': False,
                                                'synchronized': False}


if __name__ == '__main__':
    unittest.main()
