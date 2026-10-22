import asyncio
import dataclasses
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from sumuww.dgw import next_bits
from sumuww.difficulty import expected_bits
from sumuww.profiles import SUMUWW, RETARGET_LAB
from sumuww.primitives import Header, encode_compact, valid_target
from sumuww.block import Block, mine_header
from sumuww.chain import Chain
from sumuww.errors import ValidationError
from sumuww.peer import PeerNode

class DgwTests(unittest.TestCase):
    def test_public_activation_and_exclusive_algorithm(self):
        self.assertEqual(8064, SUMUWW.dgw_activation_height)
        self.assertIsNone(SUMUWW.asert_activation_height)
        with self.assertRaises(ValueError):
            dataclasses.replace(SUMUWW, asert_activation_height=8064)

    def test_official_dash_reference(self):
        root = Path(__file__).resolve().parents[1]
        row = json.loads((root/'vectors/dgw/official.json').read_text(encoding='utf-8'))
        self.assertEqual(row['expected_bits'], next_bits(list(reversed(row['history_oldest_first'])),
                                                       (1<<256)-1, spacing=row['spacing']))

    def test_uniform_window_clamps_and_validation(self):
        limit = SUMUWW.pow_limit
        bits = encode_compact(limit//100)
        target = valid_target(bits, limit)
        for spacing, multiplier, divisor in ((600,23,24),(1,1,3),(6000,3,1)):
            rows = [(100000-index*spacing,bits) for index in range(24)] if spacing != 6000 else [(200000-index*spacing,bits) for index in range(24)]
            self.assertEqual(encode_compact(target*multiplier//divisor), next_bits(rows,limit))
        with self.assertRaises(ValueError):
            next_bits([(1000,bits)]*23, limit)
        with self.assertRaises(ValueError):
            next_bits([(1000,0)]*24, limit)

    def test_context_uses_only_24_actual_parent_headers(self):
        p = RETARGET_LAB
        headers = {p.genesis.block_hash():p.genesis.header}
        parent = p.genesis.header
        for height in range(1, 40):
            child = Header(4,parent.digest(),bytes([height])*32,parent.timestamp+600,p.initial_bits,0)
            headers[child.digest()] = child
            parent = child
        with patch('sumuww.dgw.next_bits', wraps=next_bits) as calculate:
            reads = []
            def load(h):
                reads.append(h);return headers.get(h)
            result = expected_bits(39,parent.digest(),load,p.pow_limit,p.initial_bits,
                                   interval=16,target_timespan=16,dgw_activation_height=32)
            self.assertEqual(24,len(reads))
            self.assertEqual(next_bits(calculate.call_args.args[0],p.pow_limit),result)
        headers.pop(parent.previous_hash)
        with self.assertRaises(ValueError):
            expected_bits(39,parent.digest(),headers.get,p.pow_limit,p.initial_bits,
                          interval=16,target_timespan=16,dgw_activation_height=32)

    def test_chain_activation_wrong_bits_replay_and_bounded_summary(self):
        profile = dataclasses.replace(RETARGET_LAB,dgw_activation_height=32)
        with patch.dict('sumuww.profiles._NETWORKS',{'retarget-lab':profile}):
            with tempfile.TemporaryDirectory() as directory:
                path=Path(directory)/'fixture.sqlite'
                clock=lambda:profile.genesis.header.timestamp+60000
                with Chain(path,network=profile,clock=clock) as chain:
                    script=b'\x00\x14'+bytes(20)
                    for height in range(1,41):
                        block=chain.make_block(script,timestamp=profile.genesis.header.timestamp+height*600)
                        chain.accept_block(block)
                        with patch.object(chain,'_summary_row',wraps=chain._summary_row) as reads:
                            summary=chain.summary()
                            expected_reads=24 if height+1>=32 else 16 if (height+1)%16==0 else 1
                            self.assertEqual(expected_reads,reads.call_count)
                        self.assertEqual(chain.expected_bits(),int(summary['next_bits'],16))
                    original=chain.tip_hash
                    candidate=chain.make_block(script)
                    self.assertNotEqual(profile.initial_bits,candidate.header.bits)
                    wrong=mine_header(dataclasses.replace(candidate.header,bits=profile.initial_bits),pow_limit=profile.pow_limit)
                    with self.assertRaises(ValidationError):
                        chain.accept_block(Block(wrong,candidate.transactions))
                    self.assertEqual(original,chain.tip_hash)
                    parent=chain.tip_hash
                    first=chain.make_block(script,parent_hash=parent,timestamp=profile.genesis.header.timestamp+41*600)
                    chain.accept_block(first)
                    second=chain.make_block(script,parent_hash=parent,timestamp=profile.genesis.header.timestamp+43*600)
                    chain.accept_block(second)
                    self.assertNotEqual(chain.expected_bits(first.block_hash()),chain.expected_bits(second.block_hash()))
                    tip=chain.tip_hash
                with Chain(path,network=profile,clock=clock) as chain:
                    self.assertEqual(tip,chain.tip_hash)

class DgwRelayTests(unittest.IsolatedAsyncioTestCase):
    async def test_peer_sync_crosses_activation_using_full_block_validation(self):
        profile=dataclasses.replace(RETARGET_LAB,dgw_activation_height=32)
        with patch.dict('sumuww.profiles._NETWORKS',{'retarget-lab':profile}):
            with tempfile.TemporaryDirectory() as directory:
                source=PeerNode(Path(directory)/'a.sqlite',network=profile,discover_peers=False,poll_interval=.05,timeout=2)
                target=None
                try:
                    for height in range(1,41):
                        source.chain.accept_block(source.chain.make_block(b'\x00\x14'+bytes(20),timestamp=profile.genesis.header.timestamp+height*600))
                    await source.start()
                    target=PeerNode(Path(directory)/'b.sqlite',network=profile,peers=[source.address],discover_peers=False,poll_interval=.05,timeout=2)
                    await target.start()
                    end=asyncio.get_running_loop().time()+15
                    while target.chain.tip_hash!=source.chain.tip_hash:
                        self.assertLess(asyncio.get_running_loop().time(),end)
                        await asyncio.sleep(.02)
                    self.assertEqual(40,target.chain.info()['height'])
                finally:
                    if target is not None:await target.stop()
                    await source.stop()
