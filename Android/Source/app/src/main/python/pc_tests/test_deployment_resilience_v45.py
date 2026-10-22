"""Owned local stress and process-loss fixtures; no Internet-scale claim."""
import asyncio
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest

from sumuww.block import GENESIS_TIME
from sumuww.chain import Chain
from sumuww.peer import PeerNode
from sumuww.wallet import RegtestKey

NOW = GENESIS_TIME + 50000
KEY = RegtestKey.from_int(451701)
RECORDS = []

async def eventually(predicate, timeout=30):
    deadline = asyncio.get_running_loop().time() + timeout
    while not predicate():
        if asyncio.get_running_loop().time() >= deadline:
            raise AssertionError('Owned topology failed to converge')
        await asyncio.sleep(.02)

class ChurnTests(unittest.IsolatedAsyncioTestCase):
    async def test_32_node_ring_repeated_restart_preserves_consensus_and_readiness(self):
        with tempfile.TemporaryDirectory(prefix='sumuww-owned-churn-') as tmp:
            folder = Path(tmp)
            def create(i):
                return PeerNode(folder/f'node-{i}.sqlite', clock=lambda:NOW,
                    poll_interval=.1, timeout=5, discover_peers=False, dht_enabled=False)
            nodes = [create(i) for i in range(32)]
            delays=[]; began=time.monotonic()
            try:
                await asyncio.gather(*(n.start() for n in nodes))
                for i in range(32):
                    await nodes[i].connect(*nodes[(i+1)%32].address)
                await eventually(lambda:all(n.synchronization_info()['mining_ready'] for n in nodes))
                for round_number in range(8):
                    # The ring retains an alternate path while one node is down.
                    index=1+round_number*3
                    old=nodes[index]
                    await old.stop()
                    self.assertFalse(old._sessions); self.assertFalse(old._tasks)
                    source=nodes[0]
                    source.chain.mine(KEY.script_pubkey,4)
                    tip=source.chain.tip_hash
                    await eventually(lambda:all(n.chain.tip_hash==tip for j,n in enumerate(nodes) if j!=index))
                    nodes[index]=create(index)
                    await nodes[index].start()
                    await nodes[index].connect(*nodes[(index-1)%32].address)
                    await nodes[index].connect(*nodes[(index+1)%32].address)
                    relay=time.monotonic()
                    await eventually(lambda:all(n.chain.tip_hash==tip and n.synchronization_info()['mining_ready'] for n in nodes))
                    delays.append(round(time.monotonic()-relay,4))
                    self.assertEqual(1,len({n.chain.state_commitment() for n in nodes}))
                    self.assertTrue(all(len(n._sessions)<=8 for n in nodes))
                for node in nodes:
                    node.chain.verify_persisted_state()
                    self.assertEqual('ok',node.chain.connection.execute('PRAGMA integrity_check').fetchone()[0])
                RECORDS.append({'case':'32_node_ring_churn','nodes':32,'restarts':8,
                    'blocks':32,'same_tip_and_utxo':True,'all_persisted_states_verified':True,
                    'rejoin_seconds':delays,'elapsed_seconds':round(time.monotonic()-began,3)})
            finally:
                await asyncio.gather(*(n.stop() for n in nodes))
                self.assertTrue(all(not n._sessions and not n._tasks for n in nodes))

class AbruptProcessLossTests(unittest.TestCase):
    def test_uncommitted_block_utxo_and_tip_are_atomic_at_three_crash_points(self):
        with tempfile.TemporaryDirectory(prefix='sumuww-owned-crash-') as tmp:
            database=Path(tmp)/'node.sqlite'
            with Chain(database,clock=lambda:NOW) as chain:
                chain.mine(KEY.script_pubkey,100)
                expected_tip=chain.tip_hash;expected_state=chain.state_commitment()
            environment=dict(os.environ, PYTHONDONTWRITEBYTECODE='1')
            environment['PYTHONPATH']=str(Path(__file__).resolve().parents[1])
            for stage in ('after_block_saved','after_utxos_saved','after_tip_saved'):
                script=(
                    'import os,sys\nfrom sumuww.chain import Chain\nfrom sumuww.wallet import RegtestKey\n'
                    'def fault(stage):\n    if stage==sys.argv[2]:os._exit(73)\n'
                    f'chain=Chain(sys.argv[1],clock=lambda:{NOW},fault_hook=fault)\n'
                    'chain.mine(RegtestKey.from_int(451701).script_pubkey)\n')
                result=subprocess.run([sys.executable,'-B','-c',script,str(database),stage],
                    env=environment,capture_output=True,text=True,timeout=30)
                self.assertEqual(73,result.returncode,result.stderr)
                with Chain(database,clock=lambda:NOW) as chain:
                    self.assertEqual(expected_tip,chain.tip_hash)
                    self.assertEqual(expected_state,chain.state_commitment())
                    chain.verify_persisted_state()
                    self.assertEqual('ok',chain.connection.execute('PRAGMA integrity_check').fetchone()[0])
            with Chain(database,clock=lambda:NOW) as chain:
                chain.mine(KEY.script_pubkey)
                self.assertEqual(101,chain.info()['height'])
            RECORDS.append({'case':'abrupt_process_loss','crash_points':3,
                'confirmed_block_utxo_preserved':True,'partial_block_not_committed':True,
                'mining_resumed_after_recovery':True,'physical_power_loss':False})

if __name__=='__main__':
    unittest.main()
