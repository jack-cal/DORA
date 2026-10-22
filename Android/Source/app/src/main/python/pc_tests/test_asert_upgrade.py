import dataclasses
import re
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sumuww.asert import next_bits
from sumuww.difficulty import expected_bits
from sumuww.primitives import Header, valid_target
from sumuww.profiles import RETARGET_LAB
from sumuww.chain import Chain
from sumuww.block import mine_header, Block
from sumuww.errors import ValidationError, StorageError


class AsertTests(unittest.TestCase):
    def test_official_vectors(self):
        # Unmodified BCHN vectors, downloaded from the specification's mirror.
        root = Path(__file__).resolve().parents[1] / 'vectors' / 'asert'
        limit = valid_target(0x1d00ffff, (1 << 256) - 1)
        rows = 0
        for path in sorted(root.glob('run*')):
            text = path.read_text()
            height = int(re.search(r'anchor height: (\d+)', text)[1])
            timestamp = int(re.search(r'anchor (?:ancestor|parent) time: (-?\d+)', text)[1])
            bits = int(re.search(r'anchor nBits: (0x[0-9a-f]+)', text)[1], 16)
            for line in text.splitlines():
                if not line or line.startswith('#'):
                    continue
                _, h, t, expected = line.split()
                self.assertEqual(int(expected, 16), next_bits(bits, int(t)-timestamp,
                                 int(h)-height, limit), (path.name, line))
                rows += 1
        self.assertGreater(rows, 10000)

    def test_extreme_delta_is_bounded(self):
        limit = valid_target(0x1d00ffff, (1 << 256)-1)
        self.assertEqual(0x1d00ffff, next_bits(0x1d00ffff, (1 << 63)-1, 0, limit))
        self.assertEqual(0x01010000, next_bits(0x1d00ffff, -(1 << 63), 0, limit))

    def test_actual_branch_ancestry_and_activation(self):
        p = RETARGET_LAB
        headers = {p.genesis.block_hash(): p.genesis.header}
        parent = p.genesis.header
        for height in range(1, 9):
            bits = expected_bits(height-1, parent.digest(), headers.get, p.pow_limit,
                                 p.initial_bits, interval=16, target_timespan=16,
                                 asert_activation_height=4)
            if height < 4:
                self.assertEqual(p.initial_bits, bits)
            child = Header(4, parent.digest(), bytes([height])*32,
                           parent.timestamp+100, bits, 0)
            headers[child.digest()] = child
            parent = child
        anchor = list(headers.values())[3]
        ancestor = headers[anchor.previous_hash]
        expected = next_bits(anchor.bits, parent.timestamp-ancestor.timestamp, 8-3, p.pow_limit)
        self.assertEqual(expected, expected_bits(8, parent.digest(), headers.get,
                         p.pow_limit, p.initial_bits, interval=16, target_timespan=16,
                         asert_activation_height=4))
        broken = dict(headers)
        del broken[ancestor.digest()]
        with self.assertRaises(ValueError):
            expected_bits(8, parent.digest(), broken.get, p.pow_limit, p.initial_bits,
                          interval=16, target_timespan=16, asert_activation_height=4)

    def test_chain_replay_template_summary_and_wrong_bits(self):
        profile = dataclasses.replace(RETARGET_LAB, asert_activation_height=4)
        with patch.dict('sumuww.profiles._NETWORKS', {'retarget-lab': profile}):
            with tempfile.TemporaryDirectory() as directory:
                path = Path(directory)/'fixture.sqlite'
                clock = lambda: profile.genesis.header.timestamp + 60000
                chain = Chain(path, network=profile, clock=clock)
                script = b'\x00\x14' + bytes(20)
                for _ in range(8):
                    self.assertEqual(chain.expected_bits(), int(chain.info()['next_bits'], 16))
                    chain.mine(script)
                tip = chain.tip_hash
                block = chain.make_block(script)
                wrong = dataclasses.replace(block.header, bits=profile.initial_bits)
                if wrong.bits == block.header.bits:
                    wrong = dataclasses.replace(wrong, bits=0x1f7fffff)
                wrong = mine_header(wrong, pow_limit=profile.pow_limit)
                with self.assertRaises(ValidationError):
                    chain.accept_block(Block(wrong, block.transactions))
                chain.close()
                chain = Chain(path, network=profile, clock=clock)
                self.assertEqual(tip, chain.tip_hash)
                self.assertEqual(chain.expected_bits(), int(chain.info()['next_bits'], 16))
                chain.close()

    def test_fork_children_use_their_own_parent_times(self):
        profile = dataclasses.replace(RETARGET_LAB, asert_activation_height=4)
        clock_value = [profile.genesis.header.timestamp + 600]
        with patch.dict('sumuww.profiles._NETWORKS', {'retarget-lab': profile}):
            with tempfile.TemporaryDirectory() as directory:
                chain = Chain(Path(directory)/'fork.sqlite', network=profile,
                              clock=lambda: clock_value[0])
                try:
                    script = b'\x00\x14'+bytes(20)
                    chain.mine(script,3)
                    parent = chain.tip_hash
                    clock_value[0] = profile.genesis.header.timestamp+1000
                    first = chain.make_block(script,parent_hash=parent)
                    chain.accept_block(first)
                    clock_value[0] = profile.genesis.header.timestamp+3600
                    second = chain.make_block(script,parent_hash=parent)
                    chain.accept_block(second)
                    self.assertNotEqual(chain.expected_bits(first.block_hash()),
                                        chain.expected_bits(second.block_hash()))
                finally:
                    chain.close()

    def test_repeated_summary_is_cached_but_database_changes_invalidate_it(self):
        profile = dataclasses.replace(RETARGET_LAB, asert_activation_height=4)
        with patch.dict('sumuww.profiles._NETWORKS', {'retarget-lab': profile}):
            with tempfile.TemporaryDirectory() as directory:
                path = Path(directory)/'summary.sqlite'
                clock = lambda: profile.genesis.header.timestamp + 60000
                with Chain(path, network=profile, clock=clock) as reader:
                    reader.mine(b'\x00\x14'+bytes(20), 10)
                    first = reader.summary()
                    with patch.object(reader, '_summary_row', wraps=reader._summary_row) as rows:
                        self.assertEqual(first, reader.summary())
                        self.assertEqual(1, rows.call_count)
                    with Chain(path, network=profile, clock=clock) as writer:
                        writer.mine(b'\x00\x14'+bytes(20))
                    next_summary = reader.summary()
                    self.assertEqual(11, next_summary['height'])
                    self.assertEqual(reader.expected_bits(), int(next_summary['next_bits'], 16))
                    with patch.object(reader, '_summary_row', wraps=reader._summary_row) as rows:
                        self.assertEqual(next_summary, reader.summary())
                        self.assertEqual(1, rows.call_count)
                    anchor = reader.connection.execute('SELECT hash,raw FROM blocks WHERE height=3').fetchone()
                    reader.connection.execute('UPDATE blocks SET raw=? WHERE hash=?',
                                              (bytes([anchor[1][0] ^ 1])+anchor[1][1:], anchor[0]))
                    with self.assertRaises(StorageError):
                        reader.summary()
