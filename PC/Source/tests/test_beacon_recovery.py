"""Generation changes must preserve historical proofs and branch determinism."""
import copy
import asyncio
from dataclasses import replace
import unittest

from sumuww import link_beacon as beacon
from sumuww.block import Block,mine_header
from sumuww.errors import InvalidBlock
from sumuww.link_crypto import (Identity,beacon_outputs,block_beacon,digest,
                               message,compress,slot,proof_selected)
from sumuww.primitives import merkle_root
from tests.test_links9000 import LinkUpgradeTests


class BeaconRecoveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        LinkUpgradeTests.setUpClass()
        cls.new_keys=[Identity(LinkUpgradeTests.root/f'replacement-{i}.sqlite') for i in range(3)]

    @classmethod
    def tearDownClass(cls):
        for key in cls.new_keys:key.close()
        LinkUpgradeTests.tearDownClass()

    def setUp(self):
        self.fixture=LinkUpgradeTests();self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.c=self.fixture.chain;self.state=self.c.boundary
        self.original=self.state.anchor(self.c._path(self.c.tip_hash))

    def path(self):return self.c._path(self.c.tip_hash)

    def mature(self):
        needed=self.c._row(self.original[0])[2]+beacon.MIN_GENERATION_BLOCKS-self.c._row(self.c.tip_hash)[2]
        if needed>0:self.c.mine(self.fixture.miner.script_pubkey,needed)

    def context(self,previous=None,round_hash=None):
        contacts=[k.signed({'domain':'sumuww-link-contact-v1','network':self.state.network,
                           'nodeId':k.node_id,'encryption':k.encryption_key}) for k in self.new_keys]
        return beacon.recovery_context(self.state.network,self.state.root(self.path()),contacts,
                                       previous or self.original[0].hex(),round_hash or self.c.tip_hash.hex())

    def setup(self,ctx):
        m=beacon.manifest(ctx,[beacon.make_deal(k,ctx) for k in self.new_keys])
        return {'manifest':m,'ready':[beacon.recover(k,m) for k in self.new_keys]}

    def committed_block(self,setup):
        block=self.c.make_block(self.fixture.miner.script_pubkey)
        cb=replace(block.transactions[0],outputs=block.transactions[0].outputs+beacon_outputs(setup))
        txs=(cb,)+block.transactions[1:];root,_=merkle_root([t.txid() for t in txs])
        return Block(mine_header(replace(block.header,merkle_root=root)),txs)

    def test_old_proof_survives_rekey_restart_and_new_key_cannot_rewrite_it(self):
        parent,sig=self.fixture.selected_parent();pair=self.fixture.pair(parent,110)
        proof=self.fixture.proof(pair,sig);self.state.add_proof(proof)
        old_bytes=[b.serialize() for _,b in self.path()]
        self.mature();setup=self.setup(self.context());self.state.set_local('ready_setup',setup)
        block=self.c.mine(self.fixture.miner.script_pubkey)[0]
        self.assertEqual(block.block_hash(),self.state.anchor(self.path())[0])
        self.assertEqual(old_bytes,[b.serialize() for _,b in self.path()][:len(old_bytes)])
        self.state.verify_proof(proof)
        m=proof['message'];sig2=beacon.combine(setup,m['slot'],[beacon.partial(k,setup,m['slot']) for k in self.new_keys[:2]])
        bad=copy.deepcopy(proof);bad['message']['beacon']=sig2
        with self.assertRaisesRegex(ValueError,'threshold beacon'):self.state.verify_proof(bad)
        self.c.close()
        from sumuww.chain import Chain
        with Chain(self.fixture.path,boundary_activation=3) as reopened:
            reopened.boundary.verify_storage()
            self.assertEqual(block.block_hash(),reopened.boundary.anchor(reopened._path(reopened.tip_hash))[0])
            self.assertEqual(1,len(reopened.boundary.all_proofs()))

    def test_offline_old_group_not_needed_for_new_threshold_beacon(self):
        self.mature();setup=self.setup(self.context())
        s=slot(self.state.network,99,self.c.tip_hash.hex())
        signatures=[beacon.partial(k,setup,s) for k in self.new_keys]
        self.assertEqual(beacon.combine(setup,s,signatures[:2]),beacon.combine(setup,s,signatures[1:]))
        with self.assertRaises(ValueError):beacon.combine(setup,s,signatures[:1])

    def test_wrong_predecessor_unknown_round_and_early_generation_rejected(self):
        with self.assertRaisesRegex(ValueError,'too early'):self.state.check_setup_context(self.context(),self.path())
        self.mature()
        for field,value,reason in [('previous','ab'*32,'predecessor'),('round','ab'*32,'ancestor'),('root','ab'*32,'ancestry')]:
            ctx=self.context();ctx[field]=value
            with self.assertRaisesRegex(ValueError,reason):self.state.check_setup_context(ctx,self.path())

    def test_incomplete_or_forged_ready_cannot_be_committed(self):
        self.mature();setup=self.setup(self.context())
        for broken in (dict(setup,ready=setup['ready'][:1]),copy.deepcopy(setup)):
            if len(broken['ready'])==3:broken['ready'][0]['signature']='00'*64
            with self.assertRaises(InvalidBlock):self.c.accept_block(self.committed_block(broken))
        self.c.mine(self.fixture.miner.script_pubkey,3)

    def test_stale_prepared_setup_never_blocks_mining_or_replaces_current_key(self):
        self.mature();setup=self.setup(self.context());self.state.set_local('ready_setup',setup)
        anchor=self.c.mine(self.fixture.miner.script_pubkey)[0]
        blocks=self.c.mine(self.fixture.miner.script_pubkey,3)
        self.assertTrue(all(block_beacon(b) is None for b in blocks))
        self.assertEqual(anchor.block_hash(),self.state.anchor(self.path())[0])
        with self.assertRaises(InvalidBlock):self.c.accept_block(self.committed_block(setup))

    def test_reorg_uses_generation_on_its_own_ancestry(self):
        self.mature();parent=self.c.tip_hash;setup=self.setup(self.context())
        self.state.set_local('ready_setup',setup);left=self.c.mine(self.fixture.miner.script_pubkey)[0]
        self.state.set_local('ready_setup',None)
        right=self.c.make_block(self.fixture.miner.script_pubkey,parent_hash=parent,extra_nonce=501)
        self.c.accept_block(right)
        child=self.c.make_block(self.fixture.miner.script_pubkey,parent_hash=right.block_hash(),extra_nonce=502)
        self.c.accept_block(child)
        self.assertEqual(child.block_hash(),self.c.tip_hash)
        self.assertEqual(self.original[0],self.state.anchor(self.path())[0])
        self.assertEqual(left.block_hash(),self.state.anchor(self.c._path(left.block_hash()))[0])

    def test_legacy_setup_cannot_overwrite_an_existing_generation(self):
        with self.assertRaises(InvalidBlock):self.c.accept_block(self.committed_block(self.fixture.setup))

    def test_invalid_encrypted_deal_identifies_actual_dealer(self):
        self.mature();ctx=self.context();deals=[beacon.make_deal(k,ctx) for k in self.new_keys]
        bad=copy.deepcopy(deals[0]['payload'])
        for encrypted in bad['encrypted']:encrypted['ciphertext']='00'*48
        deals[0]=self.new_keys[0].signed(bad);m=beacon.manifest(ctx,deals)
        beacon.group(m) # Its public commitments/signature pass; ciphertext does not.
        with self.assertRaises(beacon.InvalidDealer) as caught:beacon.recover(self.new_keys[1],m)
        self.assertEqual(self.new_keys[0].node_id,caught.exception.dealer)

    def test_failed_old_jobs_do_not_replace_a_healthy_new_generation(self):
        from types import SimpleNamespace
        from sumuww.link_recovery import BeaconRecovery
        self.mature();setup=self.setup(self.context());self.state.set_local('ready_setup',setup)
        self.c.mine(self.fixture.miner.script_pubkey)
        recovery=BeaconRecovery(SimpleNamespace(state=self.state,node=SimpleNamespace(chain=self.c)))
        recovery.failure(self.original[0],{k.node_id for k in self.fixture.keys})
        self.assertIsNone(recovery.failed_anchor);self.assertFalse(recovery.excluded)

    def test_prepared_but_unavailable_group_cannot_starve_new_proposal(self):
        from types import SimpleNamespace
        from unittest.mock import AsyncMock
        from sumuww.link_recovery import BeaconRecovery
        self.mature()
        obsolete=copy.deepcopy(self.fixture.setup)
        old_members=obsolete['manifest']['context']['members']
        obsolete['manifest']['context']=beacon.recovery_context(self.state.network,self.state.root(self.path()),old_members,self.original[0].hex(),self.c.tip_hash.hex())
        self.state.set_local('ready_setup',obsolete)
        contacts={c['payload']['nodeId']:c for c in old_members+self.context()['members']}
        fresh={k.node_id for k in self.new_keys}
        async def request(node_id,method,body,**kwargs):
            if method=='dkg_probe' and node_id in fresh:return body['nonce']
            raise TimeoutError()
        runtime=SimpleNamespace(state=self.state,node=SimpleNamespace(chain=self.c),network=self.state.network,
                                contacts=contacts,request=request,publish=AsyncMock(),contexts={},keys=self.new_keys[0])
        recovery=BeaconRecovery(runtime);asyncio.run(recovery.step())
        self.assertIsNone(self.state.local('ready_setup'))
        runtime.publish.assert_awaited_once()
        proposed=runtime.publish.call_args.args[1]['context']
        self.assertEqual(fresh,set(beacon.check_context(proposed)))
        self.assertEqual(7,len(contacts)) # Unresponsive DKG participants stay witnesses.


if __name__=='__main__':unittest.main()
