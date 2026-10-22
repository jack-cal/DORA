"""Actual loopback profile isolation and contextual retarget block relay."""

import asyncio
from contextlib import redirect_stderr
from dataclasses import replace
from io import StringIO
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import AsyncMock, Mock, patch

from sumuww.block import Block, GENESIS_TIME, mine_header
from sumuww.chain import Chain
from sumuww import peerd
from sumuww.network_demo import Daemon, node_command
from sumuww.peer import PeerNode
from sumuww.profiles import REGTEST, RETARGET_LAB
from sumuww.wallet import RegtestKey
from sumuww.wire import (
    Frame, INV_BLOCK, Inventory, PROTOCOL_VERSION, ProtocolError, Version,
    decode_getheaders, decode_inventory, decode_version, encode_frame,
    encode_headers, encode_version, read_frame, write_frame,
)


WORK = Path(os.environ.get('SUMUWW_TEST_WORKDIR', tempfile.gettempdir()))
NOW = GENESIS_TIME + 1000
MINER = RegtestKey.from_int(1)


async def eventually(predicate, timeout=10):
    async with asyncio.timeout(timeout):
        while not predicate():
            await asyncio.sleep(.02)


class ProfileFrameTests(unittest.IsolatedAsyncioTestCase):
    async def test_explicit_lab_magic_round_trip(self):
        writer = Mock()
        writer.drain = AsyncMock()
        await write_frame(writer, 'ping', b'12345678', magic=RETARGET_LAB.message_magic)
        encoded = writer.write.call_args.args[0]
        self.assertEqual(RETARGET_LAB.message_magic, encoded[:4])
        reader = asyncio.StreamReader()
        reader.feed_data(encoded)
        self.assertEqual(Frame('ping', b'12345678'),
                         await read_frame(reader, magic=RETARGET_LAB.message_magic))

    async def test_default_magic_stays_regtest_and_rejects_lab_frame(self):
        writer = Mock()
        writer.drain = AsyncMock()
        await write_frame(writer, 'verack', b'')
        self.assertEqual(REGTEST.message_magic, writer.write.call_args.args[0][:4])
        reader = asyncio.StreamReader()
        reader.feed_data(encode_frame('verack', b'', RETARGET_LAB.message_magic))
        with self.assertRaisesRegex(ProtocolError, 'magic mismatch'):
            await read_frame(reader)

    async def test_invalid_magic_rejected_before_any_stream_operation(self):
        for magic in (None, b'', b'123', b'12345', 'abcd'):
            reader = Mock()
            reader.readexactly = AsyncMock()
            writer = Mock()
            writer.drain = AsyncMock()
            with self.subTest(magic=magic):
                with self.assertRaises(ProtocolError):
                    await read_frame(reader, magic=magic)
                reader.readexactly.assert_not_called()
                with self.assertRaises(ProtocolError):
                    await write_frame(writer, 'verack', b'', magic=magic)
                writer.write.assert_not_called()


class ProfilePeerTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        WORK.mkdir(parents=True, exist_ok=True)
        self.directory = tempfile.TemporaryDirectory(prefix='sumuww-profile-peer-', dir=WORK)
        self.root = Path(self.directory.name)
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

    def node(self, network=RETARGET_LAB, **options):
        node = PeerNode(self.root / f'node-{len(self.nodes)}.sqlite', network=network,
                        poll_interval=.1, timeout=1, clock=lambda: NOW, **options)
        self.nodes.append(node)
        return node

    def seed(self, node, height):
        blocks = []
        for number in range(1, height + 1):
            block = node.chain.make_block(MINER.script_pubkey, timestamp=GENESIS_TIME + number)
            node.chain.accept_block(block)
            blocks.append(block)
        return blocks

    async def raw_peer(self, node, *, genesis=None, profile=None, magic=None, tip=b'\xff' * 32):
        reader, writer = await asyncio.open_connection(*node.address)
        self.writers.append(writer)
        own = await read_frame(reader, timeout=2, magic=node.network.message_magic)
        self.assertEqual('version', own.command)
        ours = decode_version(own.payload)
        identity = Version(PROTOCOL_VERSION, node.genesis if genesis is None else genesis,
                           ours.nonce ^ 1, node.network.profile_id if profile is None else profile, tip)
        await write_frame(writer, 'version', encode_version(identity), timeout=2,
                          magic=node.network.message_magic if magic is None else magic)
        if genesis is None and profile is None and magic is None:
            ack = await read_frame(reader, timeout=2, magic=node.network.message_magic)
            self.assertEqual(Frame('verack', b''), ack)
            await write_frame(writer, 'verack', b'', timeout=2, magic=node.network.message_magic)
        return reader, writer

    async def next_command(self, node, reader, command):
        for _ in range(10):
            frame = await read_frame(reader, timeout=2, magic=node.network.message_magic)
            if frame.command == command:
                return frame
        self.fail(f'Expected {command} within the response budget')

    async def test_lab_nodes_sync_across_actual_difficulty_boundary(self):
        source, target = self.node(), self.node('retarget-lab')
        blocks = self.seed(source, 33)
        self.assertEqual(RETARGET_LAB.initial_bits, blocks[14].header.bits)
        self.assertNotEqual(blocks[14].header.bits, blocks[15].header.bits)
        self.assertNotEqual(blocks[30].header.bits, blocks[31].header.bits)
        await source.start()
        await target.start()
        await target.connect(*source.address)
        await eventually(lambda: target.chain.tip_hash == source.chain.tip_hash)
        self.assertEqual(33, target.info()['stats']['blocks_stored'])
        self.assertEqual(source.info()['chainwork'], target.info()['chainwork'])
        self.assertEqual(source.info()['utxo_commitment'], target.info()['utxo_commitment'])
        self.assertEqual(RETARGET_LAB.profile_id, target.info()['profile'])
        self.assertEqual(RETARGET_LAB.message_magic.hex(), target.info()['network_magic'])
        self.assertEqual(0, target.info()['stats']['protocol_errors'])

    async def test_wrong_context_bits_with_valid_pow_is_rejected_at_full_block(self):
        target = self.node()
        self.seed(target, 15)
        correct = target.chain.make_block(MINER.script_pubkey, timestamp=GENESIS_TIME + 16)
        self.assertNotEqual(correct.header.bits, RETARGET_LAB.initial_bits)
        wrong_header = mine_header(replace(correct.header, bits=RETARGET_LAB.initial_bits),
                                   pow_limit=RETARGET_LAB.pow_limit)
        wrong = Block(wrong_header, correct.transactions)
        before = target.chain.info()
        await target.start()
        reader, writer = await self.raw_peer(target)
        request = await self.next_command(target, reader, 'getheaders')
        locator, _ = decode_getheaders(request.payload)
        self.assertEqual(target.chain.tip_hash, locator[0])
        self.assertEqual(before, target.chain.info())
        await write_frame(writer, 'headers', encode_headers((wrong.header,)),
                          timeout=2, magic=RETARGET_LAB.message_magic)
        getdata = await self.next_command(target, reader, 'getdata')
        self.assertEqual((Inventory(INV_BLOCK, wrong.block_hash()),), decode_inventory(getdata.payload))
        # PoW-qualified headers and a foreign claimed tip do not change state.
        self.assertEqual(before, target.chain.info())
        await write_frame(writer, 'block', wrong.serialize(), timeout=2,
                          magic=RETARGET_LAB.message_magic)
        await asyncio.wait_for(reader.read(), 2)
        await eventually(lambda: target.info()['sessions'] == 0)
        self.assertEqual(before, target.chain.info())
        self.assertFalse(target.chain.has_block(wrong.block_hash()))
        self.assertEqual(1, target.info()['stats']['validation_rejections'])
        self.assertEqual(0, target.info()['stats']['protocol_errors'])
        self.assertTrue(target.running)

    async def test_actual_regtest_and_lab_nodes_cannot_handshake(self):
        laboratory, legacy = self.node(), self.node(REGTEST)
        await laboratory.start()
        await legacy.start()
        before = laboratory.chain.info(), legacy.chain.info()
        await legacy.add_peer(*laboratory.address)
        await eventually(lambda: laboratory.info()['stats']['protocol_errors'] >= 1)
        self.assertEqual(0, laboratory.info()['stats']['handshakes'])
        self.assertEqual(0, legacy.info()['stats']['handshakes'])
        self.assertEqual(before, (laboratory.chain.info(), legacy.chain.info()))
        self.assertNotEqual(laboratory.genesis, legacy.genesis)
        self.assertTrue(laboratory.running and legacy.running)

    async def test_correct_magic_foreign_genesis_or_profile_is_rejected(self):
        target = self.node()
        await target.start()
        before = target.chain.info()
        choices = ({'genesis': REGTEST.genesis.block_hash()}, {'profile': REGTEST.profile_id})
        for rejected_count, options in enumerate(choices, 1):
            reader, _ = await self.raw_peer(target, **options)
            self.assertEqual(b'', await asyncio.wait_for(reader.read(), 2))
            await eventually(lambda: target.info()['stats']['protocol_errors'] == rejected_count)
            self.assertEqual(before, target.chain.info())
        self.assertEqual(0, target.info()['stats']['handshakes'])

    async def test_unknown_network_rejected_before_database_creation(self):
        path = self.root / 'forbidden.sqlite'
        with self.assertRaises(ValueError):
            PeerNode(path, network='public-mainnet')
        self.assertFalse(path.exists())


class ProfileDaemonTests(unittest.TestCase):
    def setUp(self):
        WORK.mkdir(parents=True, exist_ok=True)
        self.directory = tempfile.TemporaryDirectory(prefix='sumuww-profile-daemon-', dir=WORK)
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)

    def test_cli_selected_wrong_database_profile_returns_safe_json_error(self):
        database = self.root / 'node.sqlite'
        with Chain(database, network=REGTEST) as chain:
            original = chain.info()
        error = StringIO()
        with redirect_stderr(error):
            code = peerd.main(['--database', str(database), '--network', 'retarget-lab'])
        self.assertEqual(2, code)
        self.assertEqual('StorageError', json.loads(error.getvalue())['error'])
        with Chain(database, network=REGTEST) as reopened:
            self.assertEqual(original, reopened.info())

    def test_helper_profiles_are_forwarded_before_node_subcommand(self):
        with patch('sumuww.network_demo.subprocess.run', return_value=Mock(returncode=0, stdout='{}', stderr='')) as run:
            node_command(self.root / 'node.sqlite', 'info', network=RETARGET_LAB)
        arguments = run.call_args.args[0]
        self.assertEqual('retarget-lab', arguments[arguments.index('--network') + 1])
        self.assertLess(arguments.index('--network'), arguments.index('info'))

    def test_daemon_helper_selected_profile_and_default_remain_compatible(self):
        for name, network in (('legacy', 'regtest'), ('lab', RETARGET_LAB)):
            with patch('sumuww.network_demo.subprocess.Popen') as popen:
                daemon = Daemon(self.root, name, self.root / (name + '.sqlite'), network=network)
            self.addCleanup(daemon.log.close)
            arguments = popen.call_args.args[0]
            self.assertEqual('regtest' if name == 'legacy' else 'retarget-lab',
                             arguments[arguments.index('--network') + 1])


if __name__ == '__main__':
    unittest.main()
