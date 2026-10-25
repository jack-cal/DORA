"""Reader fixtures establish decoding, never consensus acceptance."""
import unittest
from dataclasses import replace
import server
from sumuww.wallet import RegtestKey
from sumuww.spending import SpendingTemplate
from sumuww.transaction import Transaction, TxInput, TxOutput
from sumuww.primitives import hash_to_display
import test_explorer as support

class SpendingReaderTests(unittest.TestCase):
    setUp = support.ExplorerTests.setUp
    tearDown = support.ExplorerTests.tearDown
    make = support.ExplorerTests.make
    add = support.ExplorerTests.add

    def case(self, mismatched=False, malformed=False):
        keys=tuple(RegtestKey.from_int(45200+i).pubkey for i in range(3))
        template=SpendingTemplate(2,keys,'relative_height',7)
        funding=Transaction(2,(TxInput(self.tx.txid(),0),),(TxOutput(100000,template.script_pubkey),))
        block=self.make(self.two,3,transactions=(funding,)); self.add(block,3)
        witness=template.script + (b'\0' if malformed else b'')
        if mismatched: witness=SpendingTemplate(1,(keys[0],)).script
        spending=Transaction(2,(TxInput(funding.txid(),0,witness=(b'',b'fixture',witness)),),(TxOutput(99000,self.script),))
        self.c.execute('INSERT INTO mempool(txid,raw) VALUES (?,?)',(spending.txid(),spending.serialize())); self.c.commit()
        return template,spending,block

    def test_pending_and_confirmed_expose_revealed_template(self):
        template,tx,parent=self.case()
        for confirmed in (False,True):
            if confirmed:
                block=self.make(parent,4,transactions=(tx,)); self.add(block,4)
                self.c.execute('DELETE FROM mempool'); self.c.commit()
            self.explorer.refresh(force=True)
            result=self.explorer.run('transaction',hash_to_display(tx.txid()))
            info=result['inputs'][0]['spending_conditions']
            self.assertEqual(2,info['required_signatures']); self.assertEqual(7,info['lock_value'])
            self.assertEqual('relative_height',info['lock_kind']); self.assertTrue(info['decoded_only'])

    def test_mismatched_witness_is_not_reported_as_an_output_condition(self):
        _,tx,_=self.case(mismatched=True)
        self.explorer.refresh(force=True)
        self.assertNotIn('spending_conditions',self.explorer.run('transaction',hash_to_display(tx.txid()))['inputs'][0])

    def test_unrevealed_funding_output_does_not_claim_known_conditions(self):
        _,_,block=self.case()
        self.explorer.refresh(force=True)
        result=self.explorer.run('transaction',hash_to_display(block.transactions[1].txid()))
        self.assertNotIn('spending_conditions',result['outputs'][0])
