"""A missing third witness must not stop native block production or sync."""
import asyncio
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from sumuww.peer import PeerNode
from sumuww.wallet import RegtestKey

class DiscoveryRecoveryTests(unittest.IsolatedAsyncioTestCase):
    async def test_two_nodes_keep_mining_then_late_third_recovers_same_history(self):
        nodes=[];pay=RegtestKey.from_int(1).script_pubkey
        async def until(predicate):
            async with asyncio.timeout(20):
                while not predicate():await asyncio.sleep(.03)
        with TemporaryDirectory(prefix='sumuww-late-witness-') as folder:
            async def add():
                n=PeerNode(Path(folder)/f'{len(nodes)}.sqlite',boundary_activation=3,
                           peers=[nodes[-1].address] if nodes else [],
                           discover_peers=False,dht_enabled=False,auto_address=False,
                           poll_interval=.05,timeout=5)
                await n.start();nodes.append(n);return n
            try:
                a=await add();b=await add()
                await until(lambda:all(len(n.boundary_runtime.contacts)==2 for n in nodes))
                blocks=a.chain.mine(pay,12)
                await until(lambda:b.chain.tip_hash==a.chain.tip_hash)
                before=[v.serialize() for v in blocks]
                self.assertEqual(12,b.chain.summary()['height'])
                self.assertFalse(a.chain.boundary.required(12))
                c=await add()
                await until(lambda:c.chain.tip_hash==a.chain.tip_hash and all(len(n.boundary_runtime.contacts)==3 for n in nodes))
                self.assertEqual(before,[c.chain.get_block(v.block_hash()).serialize() for v in blocks])
                self.assertEqual(1,len({n.chain.state_commitment() for n in nodes}))
            finally:
                for n in reversed(nodes):await n.stop()

if __name__=='__main__':unittest.main()
