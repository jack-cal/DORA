"""Native PoW, persisted paired proofs and preserved monetary rules."""
import copy
from contextlib import closing
from dataclasses import replace
import json
from pathlib import Path
import tempfile
import unittest
from sumuww.chain import Chain
from sumuww.block import Block,mine_header
from sumuww.wallet import RegtestKey
from sumuww.link_crypto import Identity,canonical,compress,decompress,digest,message,producer,slot,sample,proof_selected
from sumuww import link_beacon as beacon
from sumuww.primitives import subsidy,MAX_MONEY,merkle_root
from sumuww.profiles import SUMUWW

class LinkUpgradeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory();cls.root=Path(cls.tmp.name)
        cls.keys=[Identity(cls.root/f'key-{i}.sqlite') for i in range(4)]
        cls.miner=RegtestKey.from_int(700)
        cls.seed=cls.root/'seed.sqlite'
        with Chain(cls.seed,boundary_activation=3) as c:
            c.mine(cls.miner.script_pubkey,2);cls.root_hash=c.tip_hash.hex();cls.network=c.network.genesis.block_hash().hex()
        contacts=[k.signed({'domain':'sumuww-link-contact-v1','network':cls.network,'nodeId':k.node_id,'encryption':k.encryption_key}) for k in cls.keys]
        ctx=beacon.context(cls.network,cls.root_hash,contacts)
        deals=[beacon.make_deal(k,ctx) for k in cls.keys]
        m=beacon.manifest(ctx,deals);ready=[beacon.recover(k,m) for k in cls.keys]
        cls.setup={'manifest':m,'ready':sorted(ready,key=lambda r:r['payload']['nodeId'])};beacon.verify_setup(cls.setup)
    @classmethod
    def tearDownClass(cls):
        for k in cls.keys:k.close()
        cls.tmp.cleanup()
    def setUp(self):
        import sqlite3
        self.scratch=tempfile.TemporaryDirectory();self.addCleanup(self.scratch.cleanup)
        self.path=Path(self.scratch.name)/'chain.sqlite'
        with closing(sqlite3.connect(self.seed)) as old,closing(sqlite3.connect(self.path)) as new:old.backup(new)
        self.chain=Chain(self.path,boundary_activation=3);self.addCleanup(self.chain.close)
        self.chain.boundary.set_local('ready_setup',self.setup)
        self.chain.mine(self.miner.script_pubkey,1)
        self.owner=self.chain.boundary.identity();self.addCleanup(self.owner.close)
    def selected_parent(self):
        for _ in range(256):
            h=self.chain._row(self.chain.tip_hash)[2]+1;s=slot(self.network,h,self.chain.tip_hash.hex())
            partials=[beacon.partial(k,self.setup,s) for k in self.keys[:2]]
            sig=beacon.combine(self.setup,s,partials)
            if proof_selected(beacon.verify_beacon(self.setup,s,sig)):return self.chain.tip_hash,sig
            self.chain.mine(self.miner.script_pubkey)
        self.fail('No selected random event in test sample')
    def pair(self,parent,nonce):
        a=self.chain.make_block(self.miner.script_pubkey,parent_hash=parent,extra_nonce=nonce);self.chain.accept_block(a)
        b=self.chain.make_block(self.miner.script_pubkey,parent_hash=a.block_hash(),extra_nonce=nonce);self.chain.accept_block(b)
        return a,b
    def proof(self,pair,sig,locked=True):
        a,b=pair;h=self.chain._row(a.block_hash())[2];signers=[k.node_id for k in self.keys[:3]]
        m=message(self.network,a.block_hash().hex(),b.block_hash().hex(),h,a.header.previous_hash.hex(),signers,sig)
        signatures=[bytes.fromhex(k.sign_once(m['slot'],m) if locked else k.sign(m)) for k in self.keys[:3]]
        p={'message':m,'left':compress(b''.join(s[:32] for s in signatures)),'right':compress(b''.join(s[32:] for s in signatures))}
        body={'domain':'sumuww-source-attachment-v1',**p};p['source_receipt']=self.owner.sign(body)
        p['target_receipt']=self.owner.sign({'domain':'sumuww-target-attachment-v1','source_attachment':digest(body),'source_receipt':p['source_receipt']})
        return p
    def test_old_economics_and_dgw_are_unchanged(self):
        self.assertEqual([50,50,25,25,12.5],[subsidy(h)/100000000 for h in (8999,149999,150000,359999,360000)])
        self.assertEqual(MAX_MONEY,1799999997690000);self.assertEqual(SUMUWW.dgw_activation_height,8064)
        self.assertEqual(SUMUWW.target_timespan//SUMUWW.retarget_interval,600)
    def test_unique_beacon_recovers_with_missing_share_and_rejects_bad_share(self):
        s='a'*64
        left=beacon.combine(self.setup,s,[beacon.partial(k,self.setup,s) for k in self.keys[:2]])
        right=beacon.combine(self.setup,s,[beacon.partial(k,self.setup,s) for k in self.keys[2:]])
        self.assertEqual(left,right)
        bad=beacon.partial(self.keys[0],self.setup,s);bad['signature']='00'*96
        with self.assertRaises(ValueError):beacon.verify_partial(self.setup,s,bad)
    def test_no_signature_is_needed_to_mine_or_accept(self):
        self.chain.mine(self.miner.script_pubkey,10)
        self.assertEqual(13,self.chain._row(self.chain.tip_hash)[2]);self.assertFalse(self.chain.boundary.required(13))
    def test_paired_proof_and_tamper_and_late_verification(self):
        parent,sig=self.selected_parent();pair=self.pair(parent,1);p=self.proof(pair,sig)
        before=[b.serialize() for b in pair];self.chain.boundary.add_proof(p)
        self.assertEqual(before,[self.chain.get_block(b.block_hash()).serialize() for b in pair])
        self.assertEqual(1,self.chain.boundary.score(self.chain._path(pair[1].block_hash())))
        for changed in ('left','right'):
            bad=copy.deepcopy(p);bad[changed]['data']='00'*96;bad[changed]['codec']='raw'
            with self.assertRaises(Exception):self.chain.boundary.add_proof(bad)
        self.chain.close();self.chain=Chain(self.path,boundary_activation=3);self.addCleanup(self.chain.close)
        self.chain.boundary.verify_storage();self.assertEqual(1,len(self.chain.boundary.all_proofs()))
    def test_real_beacon_in_old_fifty_percent_range_is_rejected(self):
        from sumuww.link_crypto import PROOF_SELECTION_THRESHOLD
        for _ in range(256):
            h=self.chain._row(self.chain.tip_hash)[2]+1;s=slot(self.network,h,self.chain.tip_hash.hex())
            sig=beacon.combine(self.setup,s,[beacon.partial(k,self.setup,s) for k in self.keys[:2]])
            value=int(beacon.verify_beacon(self.setup,s,sig),16)
            if PROOF_SELECTION_THRESHOLD<=value<(1<<255):
                p=self.proof(self.pair(self.chain.tip_hash,71),sig,locked=False)
                with self.assertRaisesRegex(ValueError,'random event does not request'):
                    self.chain.boundary.add_proof(p)
                return
            self.chain.mine(self.miner.script_pubkey)
        self.fail('Test could not find a 20-to-50 percent beacon event')
    def test_equal_work_choice_and_all_three_double_signing_neutralized(self):
        parent,sig=self.selected_parent();one=self.pair(parent,11);two=self.pair(parent,22)
        loser=one if self.chain.tip_hash!=one[1].block_hash() else two
        other=two if loser is one else one
        self.chain.boundary.add_proof(self.proof(loser,sig))
        self.assertEqual(self.chain.tip_hash,loser[1].block_hash())
        with self.assertRaises(ValueError):self.proof(other,sig)
        self.chain.boundary.add_proof(self.proof(other,sig,locked=False))
        self.assertEqual(1,self.chain.boundary.scores()[1]);self.assertEqual(0,self.chain.boundary.score(self.chain._path(loser[1].block_hash())))
        self.chain.accept_block(self.chain.make_block(self.miner.script_pubkey,parent_hash=other[1].block_hash()))
        self.assertEqual(self.chain.get_block(self.chain.tip_hash).header.previous_hash,other[1].block_hash())
    def test_activation_rejects_uncommitted_old_block_without_rewriting_history(self):
        block=self.chain.make_block(self.miner.script_pubkey)
        cb=replace(block.transactions[0],outputs=(block.transactions[0].outputs[0],));txs=(cb,)+block.transactions[1:]
        root,_=merkle_root([t.txid() for t in txs]);bad=Block(mine_header(replace(block.header,merkle_root=root)),txs)
        with self.assertRaises(Exception):self.chain.accept_block(bad)
    def test_compression_bounds_and_entire_candidate_pool(self):
        keys=[format(i,'064x') for i in range(1,102)];chosen=set()
        for i in range(300):chosen.update(sample(format(i,'064x'),keys))
        self.assertEqual(set(keys),chosen)
        payload=bytes(range(96));self.assertEqual(payload,decompress(compress(payload),96))
        with self.assertRaises(ValueError):decompress({'codec':'raw','data':'00'*97},96)

if __name__=='__main__':unittest.main()
