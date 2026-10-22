"""Reader fixtures exercise display/indexing, not public-chain consensus."""
import csv,io,json,sqlite3,unittest
from contextlib import closing
from pathlib import Path
import test_explorer as fixtures
from server import Explorer,verify_merkle_proof
from witness_address import encode_address,decode_address,AddressError
from sumuww.profiles import SUMUWW
from sumuww.transaction import Transaction,TxInput,TxOutput
from sumuww.primitives import hash_to_display

class HtlcReaderTests(unittest.TestCase):
 setUp=fixtures.ExplorerTests.setUp
 tearDown=fixtures.ExplorerTests.tearDown
 make=fixtures.ExplorerTests.make
 add=fixtures.ExplorerTests.add

 def fund_output(self):
  script=b'\x00\x20'+bytes(range(32))
  tx=Transaction(2,(TxInput(self.tx.txid(),0),),(TxOutput(4800000000,script),),0)
  block=self.make(self.two,3,transactions=(tx,));self.add(block,3)
  self.c.execute('DELETE FROM utxos')
  self.c.execute('INSERT INTO utxos VALUES (?,?,?,?,?,?)',(tx.txid(),0,4800000000,script,3,0));self.c.commit()
  self.explorer.refresh(force=True)
  return tx,script

 def test_p2wsh_search_balance_transaction_and_proof(self):
  tx,script=self.fund_output();text=encode_address(script,network=SUMUWW)
  self.assertEqual(decode_address(text,network=SUMUWW),script)
  self.assertEqual(self.explorer.run('search',text)['type'],'address')
  result=self.explorer.run('address',text)
  self.assertEqual(result['confirmed'],'48.00000000')
  self.assertEqual(self.explorer.run('transaction',hash_to_display(tx.txid()))['outputs'][0]['address'],text)
  self.assertTrue(verify_merkle_proof(self.explorer.run('proof',hash_to_display(tx.txid()))))

 def test_existing_v2_index_null_address_is_backfilled(self):
  tx,script=self.fund_output();self.explorer.close()
  with closing(sqlite3.connect(self.root/'explorer.sqlite')) as c,c:
   c.execute('UPDATE outputs SET address=NULL WHERE txid=?',(hash_to_display(tx.txid()),));c.execute('PRAGMA user_version=2')
  before=self.db.read_bytes()
  self.explorer=Explorer(self.db,self.root/'explorer.sqlite')
  text=encode_address(script,network=SUMUWW)
  result=self.explorer.run('address',text)
  self.assertEqual(result['total_transactions'],1)
  self.assertEqual(before,self.db.read_bytes())
  with closing(sqlite3.connect(self.root/'explorer.sqlite')) as c:self.assertEqual(c.execute('PRAGMA user_version').fetchone()[0],3)

 def test_pending_spend_affects_contract_balance(self):
  funding,script=self.fund_output()
  spending=Transaction(2,(TxInput(funding.txid(),0),),(TxOutput(4799999000,self.script),),0)
  self.c.execute('INSERT INTO mempool(txid,raw) VALUES (?,?)',(spending.txid(),spending.serialize()));self.c.commit()
  self.explorer.refresh(force=True)
  result=self.explorer.run('address',encode_address(script,network=SUMUWW))
  self.assertEqual(result['available'],'0.00000000')

 def test_invalid_program_network_and_checksum_rejected(self):
  for size in (0,19,21,31,33):
   with self.assertRaises(AddressError):encode_address(bytes([0,size])+bytes(size),network=SUMUWW)
  text=encode_address(b'\x00\x20'+bytes(32),network=SUMUWW)
  with self.assertRaises(AddressError):decode_address(text,network='regtest')
  with self.assertRaises(AddressError):decode_address(text[:-1]+('q' if text[-1]!='q' else 'p'),network=SUMUWW)
