"""A late TCP peer must recover both sides of conflicting connection evidence."""
import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock
from sumuww.peer import PeerNode
from sumuww.link_crypto import digest
from sumuww.link_runtime import LinkRuntime
from tests.test_links9000 import LinkUpgradeTests


class LinkTransportTests(unittest.IsolatedAsyncioTestCase):
    async def test_proof_completed_after_initial_sync_is_announced_again(self):
        LinkUpgradeTests.setUpClass();fixture=LinkUpgradeTests();runtime=None
        try:
            fixture.setUp();parent,sig=fixture.selected_parent();pair=fixture.pair(parent,91)
            proof=fixture.proof(pair,sig,locked=False)
            runtime=LinkRuntime(SimpleNamespace(chain=fixture.chain,database=fixture.path,timeout=10,_sessions={}))
            runtime.publish=AsyncMock()
            for row in fixture.chain.connection.execute('SELECT hash FROM blocks'):
                runtime.keys.put('job:'+row[0].hex(),{'done':True})
            runtime.deferred[digest(proof)]=proof
            await runtime.background();await asyncio.sleep(0)
            runtime.publish.assert_awaited_once_with('proof',proof)
            runtime.deferred[digest(proof)]=proof
            await runtime.background();await asyncio.sleep(0)
            self.assertEqual(1,runtime.publish.await_count)
        finally:
            if runtime:await runtime.close()
            fixture.doCleanups();LinkUpgradeTests.tearDownClass()

    async def test_late_transitive_peer_recovers_conflicting_side_branch(self):
        LinkUpgradeTests.setUpClass()
        fixture=LinkUpgradeTests()
        nodes=[]
        try:
            fixture.setUp()
            parent,sig=fixture.selected_parent()
            left=fixture.pair(parent,31);right=fixture.pair(parent,32)
            for pair in (left,right):
                fixture.chain.boundary.add_proof(fixture.proof(pair,sig,locked=False))
            expected=fixture.chain.tip_hash
            fixture.chain.close()
            for i in range(3):
                db=fixture.path if i==0 else fixture.path.parent/f'late-{i}.sqlite'
                node=PeerNode(db,boundary_activation=3,
                              peers=[nodes[-1].address] if nodes else [],
                              discover_peers=False,dht_enabled=False,auto_address=False,
                              poll_interval=.05,timeout=10)
                nodes.append(node);await node.start()
            deadline=asyncio.get_running_loop().time()+60
            while asyncio.get_running_loop().time()<deadline:
                if all(n.chain.tip_hash==expected and len(n.chain.boundary.all_proofs())==2
                       for n in nodes):break
                await asyncio.sleep(.1)
            for node in nodes:
                self.assertEqual(expected,node.chain.tip_hash)
                self.assertEqual(2,len(node.chain.boundary.all_proofs()),
                                 (node.boundary_runtime.last_error,node._last_error,len(node.boundary_runtime.deferred)))
                self.assertEqual(1,node.chain.boundary.scores()[1])
                self.assertEqual(0,node.chain.boundary.score(node.chain._path(expected)))
                for block in (*left,*right):self.assertTrue(node.chain.has_block(block.block_hash()))
        finally:
            for node in reversed(nodes):await node.stop()
            fixture.doCleanups()
            LinkUpgradeTests.tearDownClass()


if __name__=='__main__':unittest.main()
