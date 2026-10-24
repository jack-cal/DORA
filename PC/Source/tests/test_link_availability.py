"""Real signatures and persisted jobs over an isolated signed-message relay."""
import asyncio
import json
from pathlib import Path
import sqlite3
from types import SimpleNamespace
import unittest

from sumuww.link_crypto import Identity, sample, slot
from sumuww.link_runtime import LinkRuntime
from sumuww import link_beacon as beacon
from tests import test_links9000 as fixtures


class LinkAvailabilityTests(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):fixtures.LinkUpgradeTests.setUpClass()

    @classmethod
    def tearDownClass(cls):fixtures.LinkUpgradeTests.tearDownClass()

    async def asyncSetUp(self):
        self.fixture=fixtures.LinkUpgradeTests();self.fixture.setUp()
        self.chain=self.fixture.chain
        self.runtimes={};self.extra_keys=[];self.requests=[]
        self.source=self.runtime(self.fixture.path)
        for i,key in enumerate(self.fixture.keys[:3]):
            database=self.fixture.path.parent/f'participant-{i}.sqlite'
            path=database.with_name(database.name+'.link-keys.sqlite')
            with sqlite3.connect(path) as dest:key.db.backup(dest)
            self.runtime(database)
        contacts=[runtime.contact for runtime in self.runtimes.values()]
        for i in range(12):
            key=Identity(self.fixture.path.parent/f'offline-{i}.sqlite');self.extra_keys.append(key)
            contacts.append(key.signed({'domain':'sumuww-link-contact-v1','network':self.source.network,
                'nodeId':key.node_id,'encryption':key.encryption_key}))
        for runtime in self.runtimes.values():
            for contact in contacts:runtime.add_contact(contact)
        self.all_contacts=contacts

    def runtime(self,database):
        runtime=LinkRuntime(SimpleNamespace(chain=self.chain,database=database,timeout=5,_sessions={}))
        self.runtimes[runtime.keys.node_id]=runtime
        # Relay verified signed requests/replies to all reachable nodes, including
        # nodes with no direct session. Unreachable identities retain contacts.
        async def broadcast(frame,exclude=None):
            await asyncio.gather(*(other.receive(frame,runtime) for other in tuple(self.runtimes.values()) if other is not runtime))
        runtime.broadcast=broadcast
        original=runtime.request
        async def request(target,method,body,timeout=20):
            self.requests.append((target,method))
            if target not in self.runtimes:raise TimeoutError('Isolated participant is offline')
            return await original(target,method,body,timeout=timeout)
        runtime.request=request
        return runtime

    async def asyncTearDown(self):
        for runtime in self.runtimes.values():await runtime.close()
        for key in self.extra_keys:key.close()
        self.fixture.doCleanups()

    def selected_pair(self, require_offline=True):
        for nonce in range(64):
            parent,signature=self.fixture.selected_parent()
            height=self.chain._row(parent)[2]+1
            s=slot(self.source.network,height,parent.hex())
            random=beacon.verify_beacon(self.fixture.setup,s,signature)
            old_team=sample(random,self.source.contacts)
            if not require_offline or any(i not in self.runtimes for i in old_team):
                return self.fixture.pair(parent,1000+nonce),signature,old_team
            self.chain.mine(self.fixture.miner.script_pubkey)
        self.fail('No selected event with an offline historical contact')

    async def test_new_job_probes_entire_discovery_pool_and_completes_with_live_witnesses(self):
        (a,b),_,old_team=self.selected_pair()
        self.assertTrue(set(old_team)-self.runtimes.keys())
        await self.source.link(a.block_hash(),b.block_hash())
        proofs=self.chain.boundary.all_proofs()
        self.assertEqual(1,len(proofs))
        self.chain.boundary.verify_proof(proofs[0])
        self.assertEqual(16,len(self.source.contacts))
        probed={i for i,method in self.requests if method=='dkg_probe'}
        self.assertEqual(set(self.source.contacts),probed)
        saved=self.source.keys.get('job:'+a.block_hash().hex())
        self.assertEqual(set(self.runtimes),set(saved['candidates']))
        self.assertEqual('complete',saved['phase'])
        self.assertTrue(saved['done'])
        self.assertEqual({'total':1,'not_selected':0,'awaiting_lottery':0,'selected_pending':0,'selected_complete':1},self.source.job_counts())
        self.assertEqual(1,self.source.info()['stored_complete_proofs'])

    async def test_legacy_selected_team_is_preserved_and_failure_is_explained(self):
        from sumuww.link_crypto import message
        (a,b),signature,team=self.selected_pair()
        m=message(self.source.network,a.block_hash().hex(),b.block_hash().hex(),self.chain._row(a.block_hash())[2],a.header.previous_hash.hex(),team,signature)
        self.source.keys.put('job:'+a.block_hash().hex(),{'target':b.block_hash().hex(),'message':m,'candidates':sorted(self.source.contacts)})
        with self.assertRaises(Exception):await self.source.link(a.block_hash(),b.block_hash())
        saved=self.source.keys.get('job:'+a.block_hash().hex())
        self.assertEqual(m,saved['message'])
        self.assertEqual('witnesses',saved['phase'])
        self.assertTrue(saved['last_error'])
        self.assertEqual(set(team)-self.runtimes.keys(),set(saved['waiting_for']))
        self.assertFalse(self.chain.boundary.all_proofs())
        # A returning original participant completes the exact old message.
        for key in self.extra_keys:
            if key.node_id not in team:continue
            db=self.fixture.path.parent/f'rejoined-{key.node_id}.sqlite'
            with sqlite3.connect(db.with_name(db.name+'.link-keys.sqlite')) as dest:key.db.backup(dest)
            joined=self.runtime(db)
            for contact in self.all_contacts:joined.add_contact(contact)
        await self.source.link(a.block_hash(),b.block_hash())
        proof=self.chain.boundary.all_proofs()[0]
        self.assertEqual(m,proof['message']);self.chain.boundary.verify_proof(proof)

    async def test_receipt_retry_reuses_valid_persisted_witness_pieces(self):
        (a,b),_,_=self.selected_pair()
        original=self.source.request
        async def fail_receipt(target,method,body,**kwargs):
            if method=='attach':raise TimeoutError('Target receipt temporarily unavailable')
            return await original(target,method,body,**kwargs)
        self.source.request=fail_receipt
        with self.assertRaises(Exception):await self.source.link(a.block_hash(),b.block_hash())
        saved=self.source.keys.get('job:'+a.block_hash().hex())
        self.assertEqual('target_receipt',saved['phase']);self.assertEqual(3,len(saved['pieces']))
        # Reopen the producer's identity store, exactly as on application restart.
        await self.source.close();self.source=self.runtime(self.fixture.path)
        self.requests.clear()
        await self.source.link(a.block_hash(),b.block_hash())
        self.assertNotIn('sign',[method for _,method in self.requests])
        self.assertEqual(1,len(self.chain.boundary.all_proofs()))

    async def test_fewer_than_three_responders_does_not_choose_a_team_or_block_mining(self):
        (a,b),_,_=self.selected_pair()
        original=self.source.request
        live=set(list(self.runtimes)[:2])
        async def two_only(target,method,body,**kwargs):
            if method=='dkg_probe' and target not in live:raise TimeoutError('Offline')
            return await original(target,method,body,**kwargs)
        self.source.request=two_only
        with self.assertRaises(Exception):await self.source.link(a.block_hash(),b.block_hash())
        saved=self.source.keys.get('job:'+a.block_hash().hex())
        self.assertNotIn('message',saved)
        self.assertEqual('participants',saved['phase'])
        before=self.chain.summary()['height']
        self.chain.mine(self.fixture.miner.script_pubkey)
        self.assertEqual(before+1,self.chain.summary()['height'])
        self.assertFalse(self.chain.boundary.required(before+1))

    async def test_invalid_persisted_piece_is_replaced_without_losing_valid_replies(self):
        (a,b),_,_=self.selected_pair()
        original=self.source.request
        async def fail_receipt(target,method,body,**kwargs):
            if method=='attach':raise TimeoutError('Target unavailable')
            return await original(target,method,body,**kwargs)
        self.source.request=fail_receipt
        with self.assertRaises(Exception):await self.source.link(a.block_hash(),b.block_hash())
        key='job:'+a.block_hash().hex();saved=self.source.keys.get(key)
        bad=saved['message']['signers'][0]
        saved['pieces'][bad]={'left':'00'*32,'right':'00'*32}
        self.source.keys.put(key,saved)
        await self.source.close();self.source=self.runtime(self.fixture.path)
        self.requests.clear()
        await self.source.link(a.block_hash(),b.block_hash())
        self.assertEqual([bad],[target for target,method in self.requests if method=='sign'])
        proofs=self.chain.boundary.all_proofs()
        self.assertEqual(1,len(proofs));self.chain.boundary.verify_proof(proofs[0])


if __name__=='__main__':unittest.main()
