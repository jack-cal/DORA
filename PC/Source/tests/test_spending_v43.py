"""Activation, signatures and timelocks on isolated chains only."""
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from sumuww.block import GENESIS_TIME
from sumuww.chain import Chain
from sumuww.errors import ValidationError, StorageError, UnsupportedFeature
from sumuww.htlc import digest
from sumuww.spending import SpendingTemplate, verify_spend
from sumuww.transaction import Transaction, TxInput, TxOutput
from sumuww.wallet import RegtestKey, sign_p2wpkh

KEYS = tuple(RegtestKey.from_int(43100+i) for i in range(16))
NOW = GENESIS_TIME + 100_000


def signed(template, *, sequence=0xfffffffe, lock_time=0, signers=None, version=2):
    spent = TxOutput(100_000, template.script_pubkey)
    tx = Transaction(version, (TxInput(b'\x31'*32, 0, sequence=sequence),), (TxOutput(99_000, KEYS[0].script_pubkey),), lock_time)
    signers = KEYS[:template.required] if signers is None else signers
    signatures = tuple(key.sign_digest(digest(tx, 0, spent, template.script))+b'\x01' for key in signers)
    witness = ((b'',) if len(template.pubkeys)>1 else ()) + signatures + (template.script,)
    return replace(tx, inputs=(replace(tx.inputs[0], witness=witness),)), spent


class SpendingTests(unittest.TestCase):
    def test_templates_roundtrip_and_multisig_threshold(self):
        for count, required in ((1,1),(3,2),(16,16)):
            for kind, value in (('none',0),('height',350),('time',1_800_000_000),('relative_height',7),('relative_time',1024)):
                template = SpendingTemplate(required, tuple(k.pubkey for k in KEYS[:count]), kind, value)
                self.assertEqual(template, SpendingTemplate.parse(template.script))
        template = SpendingTemplate(2, tuple(k.pubkey for k in KEYS[:3]))
        tx, spent = signed(template)
        self.assertTrue(verify_spend(tx,0,spent))
        # The ordered subset 1,3 is valid; reversed signatures are not.
        tx, spent = signed(template, signers=(KEYS[0],KEYS[2]))
        self.assertTrue(verify_spend(tx,0,spent))
        tx, spent = signed(template, signers=(KEYS[2],KEYS[0]))
        self.assertFalse(verify_spend(tx,0,spent))
        tx, spent = signed(template, signers=(KEYS[0],))
        self.assertFalse(verify_spend(tx,0,spent))

    def test_empty_dummy_and_all_signatures_required(self):
        template = SpendingTemplate(2,tuple(k.pubkey for k in KEYS[:3]))
        tx, spent = signed(template)
        witness = (b'\x01',)+tx.inputs[0].witness[1:]
        self.assertFalse(verify_spend(replace(tx, inputs=(replace(tx.inputs[0],witness=witness),)),0,spent))
        self.assertFalse(verify_spend(replace(tx,outputs=(replace(tx.outputs[0],value=98_000),)),0,spent))

    def test_absolute_lock_height_and_time_domains(self):
        for kind, value in (('height',300),('time',1_800_000_000)):
            template = SpendingTemplate(1,(KEYS[0].pubkey,),kind,value)
            for lock, sequence, expected in ((value,0xfffffffe,True),(value-1,0xfffffffe,False),(value,0xffffffff,False)):
                tx, spent = signed(template, lock_time=lock,sequence=sequence)
                self.assertEqual(expected,verify_spend(tx,0,spent))
        template = SpendingTemplate(1,(KEYS[0].pubkey,),'height',300)
        tx, spent = signed(template,lock_time=1_800_000_000)
        self.assertFalse(verify_spend(tx,0,spent))

    def test_relative_locks_require_version_type_and_sequence(self):
        for kind,value,sequence in (('relative_height',2,2),('relative_time',1024,(1<<22)|2)):
            template = SpendingTemplate(1,(KEYS[0].pubkey,),kind,value)
            tx,spent=signed(template,sequence=sequence)
            self.assertTrue(verify_spend(tx,0,spent))
            for seq,version in ((sequence-1,2),(sequence|(1<<31),2),(sequence,1),(sequence^(1<<22),2)):
                tx,spent=signed(template,sequence=seq,version=version)
                self.assertFalse(verify_spend(tx,0,spent))

    def test_noncanonical_scripts_and_invalid_keys_are_rejected(self):
        template = SpendingTemplate(1,(KEYS[0].pubkey,),'height',1)
        for raw in (b'\x01\x01'+template.script[1:],template.script+b'\x00',template.script[:-1],b'\0'*600):
            with self.assertRaises((ValueError,IndexError)): SpendingTemplate.parse(raw)
        for required,keys,kind,value in ((0,(KEYS[0].pubkey,),'none',0),(2,(KEYS[0].pubkey,),'none',0),
                                       (1,(KEYS[0].pubkey,)*2,'none',0),(1,(KEYS[0].pubkey,),'relative_time',513)):
            with self.assertRaises(ValueError): SpendingTemplate(required,keys,kind,value)

    def chain_case(self, *, activation, lock_kind='none', lock_value=0):
        directory=TemporaryDirectory(prefix='sumuww-spending-test-')
        self.addCleanup(directory.cleanup)
        chain=Chain(Path(directory.name)/'node.sqlite',clock=lambda:NOW,spending_activation=activation)
        self.addCleanup(chain.close)
        coinbase=chain.mine(KEYS[0].script_pubkey,100)[0].transactions[0]
        template=SpendingTemplate(2,tuple(k.pubkey for k in KEYS[:3]),lock_kind,lock_value)
        fund=Transaction(2,(TxInput(coinbase.txid(),0),),(TxOutput(coinbase.outputs[0].value-1000,template.script_pubkey),))
        fund=sign_p2wpkh(fund,0,coinbase.outputs[0],KEYS[0])
        chain.submit_transaction(fund);chain.mine(KEYS[0].script_pubkey)
        sequence=(2 if lock_kind=='relative_height' else ((1<<22)|(lock_value//512)) if lock_kind=='relative_time' else 0xfffffffe)
        lock=lock_value if lock_kind in ('height','time') else 0
        tx=Transaction(2,(TxInput(fund.txid(),0,sequence=sequence),),(TxOutput(fund.outputs[0].value-1000,KEYS[0].script_pubkey),),lock)
        witness=(b'',)+tuple(k.sign_digest(digest(tx,0,fund.outputs[0],template.script))+b'\x01' for k in KEYS[:2])+(template.script,)
        tx=replace(tx,inputs=(replace(tx.inputs[0],witness=witness),))
        return chain,tx

    def test_before_activation_rejected_then_valid_after_boundary(self):
        chain,tx=self.chain_case(activation=103)
        with self.assertRaises((ValidationError,UnsupportedFeature)):chain.submit_transaction(tx)
        chain.mine(KEYS[0].script_pubkey)
        chain.submit_transaction(tx)
        self.assertEqual(3,chain._transaction_sigops_cost(tx))
        chain.mine(KEYS[0].script_pubkey)
        self.assertEqual('confirmed',chain.transaction_status(tx.txid())['status'])
        self.assertTrue(chain.verify_persisted_state())

    def test_utxo_relative_age_and_absolute_finality_are_enforced(self):
        for kind,value,wait in (('relative_height',2,1),('height',103,2)):
            chain,tx=self.chain_case(activation=1,lock_kind=kind,lock_value=value)
            with self.assertRaises(ValidationError):chain.submit_transaction(tx)
            chain.mine(KEYS[0].script_pubkey,wait)
            chain.submit_transaction(tx)
            chain.mine(KEYS[0].script_pubkey)
            self.assertEqual('confirmed',chain.transaction_status(tx.txid())['status'])

    def test_public_activation_cannot_be_selected_by_one_installation(self):
        from types import SimpleNamespace
        from sumuww.spending_policy import SpendingPolicy
        with self.assertRaises(StorageError):
            SpendingPolicy(SimpleNamespace(network=SimpleNamespace(name='dora')),1)

    def test_absolute_and_relative_time_use_chain_median_time(self):
        for kind,value in (('time',NOW+1000),('relative_time',1024)):
            chain,tx=self.chain_case(activation=1,lock_kind=kind,lock_value=value)
            with self.assertRaises(ValidationError):chain.submit_transaction(tx)
            chain.clock=lambda:NOW+2000
            chain.mine(KEYS[0].script_pubkey,6)
            chain.submit_transaction(tx)
            chain.mine(KEYS[0].script_pubkey)
            self.assertEqual('confirmed',chain.transaction_status(tx.txid())['status'])

    def test_parser_rejects_bounded_malformed_data_without_unhandled_errors(self):
        import random
        rng=random.Random(43092)
        for _ in range(1000):
            raw=rng.randbytes(rng.randrange(601))
            try:
                value=SpendingTemplate.parse(raw)
                self.assertEqual(value.script,raw)
            except ValueError:
                pass

    def test_activation_config_cannot_silently_change_on_restart(self):
        chain,_=self.chain_case(activation=103)
        with self.assertRaises(StorageError):Chain(chain.database,clock=lambda:NOW,spending_activation=104)
        with self.assertRaises(StorageError):Chain(chain.database,clock=lambda:NOW)


if __name__=='__main__':unittest.main()
