"""Probability boundary, preactivation compatibility, and branch-aware DGW cadence."""
import asyncio
from contextlib import closing
from dataclasses import replace
from hashlib import sha256
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
from sumuww.block import Block,mine_header
from sumuww.chain import Chain
from sumuww.difficulty import expected_bits
from sumuww.dgw import next_bits
from sumuww.errors import StorageError,ValidationError
from sumuww.link_crypto import POLICY,PROOF_SELECTION_THRESHOLD,proof_selected
from sumuww.peer import PeerNode
from sumuww.primitives import Header
from sumuww.profiles import SUMUWW,RETARGET_LAB


class ProbabilityAndMigrationTests(unittest.TestCase):
    def test_twenty_percent_integer_boundary_and_nonperiodic_events(self):
        t=PROOF_SELECTION_THRESHOLD
        self.assertTrue(proof_selected(format(t-1,'064x')))
        self.assertFalse(proof_selected(format(t,'064x')))
        self.assertFalse(proof_selected(format((1<<255)-1,'064x')))
        events=[proof_selected(sha256(str(i).encode()).hexdigest()) for i in range(10000)]
        self.assertTrue(1800<sum(events)<2200,sum(events))
        self.assertTrue(any(events[i] and events[i+1] for i in range(len(events)-1)))
        self.assertTrue(any(not any(events[i:i+10]) for i in range(0,len(events)-10)))
    def test_preactivation_v1_database_updates_without_changing_history(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'old.sqlite'
            with Chain(path,boundary_activation=3) as c:
                c.mine(b'\x00\x14'+bytes(20),2)
                blocks=c.connection.execute('SELECT * FROM blocks ORDER BY hash').fetchall()
                coins=c.state_commitment()
                c.connection.execute('UPDATE link_upgrade SET policy=?',('sumuww-postpow-links-9000-v1',))
            with Chain(path,boundary_activation=3) as c:
                self.assertEqual(blocks,c.connection.execute('SELECT * FROM blocks ORDER BY hash').fetchall())
                self.assertEqual(coins,c.state_commitment())
                self.assertEqual(POLICY,c.connection.execute('SELECT policy FROM link_upgrade').fetchone()[0])
                c.mine(b'\x00\x14'+bytes(20))
                c.connection.execute('UPDATE link_upgrade SET policy=?',('sumuww-postpow-links-9000-v1',))
            with self.assertRaises(StorageError):Chain(path,boundary_activation=3)
            with closing(sqlite3.connect(path)) as c:
                self.assertEqual('sumuww-postpow-links-9000-v1',c.execute('SELECT policy FROM link_upgrade').fetchone()[0])


class DgwTenTests(unittest.TestCase):
    def history(self,spacing=600):
        p=SUMUWW;parent=Header(1,bytes(32),bytes(32),1000000,p.initial_bits,0);headers={parent.digest():parent}
        for i in range(30):
            parent=Header(1,parent.digest(),bytes([i])*32,parent.timestamp+spacing,p.initial_bits,0)
            headers[parent.digest()]=parent
        return parent,headers
    def bits(self,height,parent,headers,**extra):
        return expected_bits(height-1,parent.digest(),headers.get,SUMUWW.pow_limit,SUMUWW.initial_bits,
                             dgw_activation_height=8064,**extra)
    def test_public_boundary_8999_9000_9001_9009_9010(self):
        self.assertEqual((9000,10),(SUMUWW.dgw_interval_activation_height,SUMUWW.dgw_retarget_interval))
        for spacing in (120,1200):
            parent,headers=self.history(spacing)
            for height in (8998,8999,9000,9001,9009,9010,9011,9020):
                with self.subTest(height=height,spacing=spacing):
                    reads=[]
                    def lookup(key):reads.append(key);return headers.get(key)
                    value=expected_bits(height-1,parent.digest(),lookup,SUMUWW.pow_limit,SUMUWW.initial_bits,
                                        dgw_activation_height=8064,dgw_interval_activation_height=9000,dgw_retarget_interval=10)
                    if height>=9000 and height%10:
                        self.assertEqual(parent.bits,value);self.assertEqual(1,len(reads))
                    else:
                        self.assertEqual(self.bits(height,parent,headers),value);self.assertEqual(24,len(reads))
        with self.assertRaises(ValueError):replace(SUMUWW,dgw_interval_activation_height=8000)
    def test_retarget_uses_own_branch_and_hold_blocks_reject_wrong_bits(self):
        profile=replace(RETARGET_LAB,dgw_activation_height=25,dgw_interval_activation_height=30,dgw_retarget_interval=10)
        with patch.dict('sumuww.profiles._NETWORKS',{'retarget-lab':profile}),tempfile.TemporaryDirectory() as d:
            path=Path(d)/'chain.sqlite';script=b'\x00\x14'+bytes(20)
            clock=lambda:profile.genesis.header.timestamp+100000
            with Chain(path,network=profile,clock=clock) as c:
                seen={0:profile.initial_bits};fork=None
                for height in range(1,42):
                    b=c.make_block(script,timestamp=profile.genesis.header.timestamp+height*600);c.accept_block(b);seen[height]=b.header.bits
                    if height>=30 and height%10:self.assertEqual(seen[height-1],seen[height])
                    self.assertEqual(c.expected_bits(),int(c.summary()['next_bits'],16))
                    if height==38:fork=c.tip_hash
                    if height==30:
                        candidate=c.make_block(script,timestamp=profile.genesis.header.timestamp+height*600+1)
                        wrong=mine_header(replace(candidate.header,bits=profile.initial_bits),pow_limit=profile.pow_limit)
                        self.assertNotEqual(candidate.header.bits,profile.initial_bits)
                        with self.assertRaises(ValidationError):c.accept_block(Block(wrong,candidate.transactions))
                slow=c.make_block(script,parent_hash=fork,timestamp=profile.genesis.header.timestamp+60000,extra_nonce=99);c.accept_block(slow)
                fast=c.get_block(c._path(c.tip_hash)[39][0][0])
                self.assertNotEqual(c.expected_bits(fast.block_hash()),c.expected_bits(slow.block_hash()))
                tip=c.tip_hash;coins=c.state_commitment()
            with Chain(path,network=profile,clock=clock) as c:
                self.assertEqual(tip,c.tip_hash);self.assertEqual(coins,c.state_commitment())


class DgwTenRelayTests(unittest.IsolatedAsyncioTestCase):
    async def test_three_nodes_validate_both_sides_of_two_retargets(self):
        profile=replace(RETARGET_LAB,dgw_activation_height=25,dgw_interval_activation_height=30,dgw_retarget_interval=10)
        nodes=[]
        with patch.dict('sumuww.profiles._NETWORKS',{'retarget-lab':profile}),tempfile.TemporaryDirectory() as d:
            try:
                for i in range(3):
                    n=PeerNode(Path(d)/f'{i}.sqlite',network=profile,peers=[nodes[-1].address] if nodes else [],
                               discover_peers=False,dht_enabled=False,poll_interval=.05,timeout=5)
                    nodes.append(n);await n.start()
                for height in range(1,43):
                    c=nodes[0].chain;c.accept_block(c.make_block(b'\x00\x14'+bytes(20),timestamp=profile.genesis.header.timestamp+height*600))
                deadline=asyncio.get_running_loop().time()+30
                while len({n.chain.tip_hash for n in nodes})!=1:
                    self.assertLess(asyncio.get_running_loop().time(),deadline)
                    await asyncio.sleep(.05)
                self.assertEqual(42,nodes[2].chain.summary()['height'])
                self.assertEqual(1,len({n.chain.state_commitment() for n in nodes}))
                self.assertEqual(1,len({n.chain.expected_bits() for n in nodes}))
            finally:
                for n in reversed(nodes):await n.stop()

if __name__=='__main__':unittest.main()
