"""Provider contract and optional key-free reference tests."""
import asyncio,copy,json,sys,unittest
from pathlib import Path
from dataclasses import replace
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'sdk'))
from sumuww_integration import transactions as ref
from sumuww.address import encode_address
from sumuww.block import build_coinbase
from sumuww.wallet import RegtestKey
from sumuww.transaction import TxOutput
from sumuww.primitives import COIN,hash_to_display
from sumuww.rpc import METHODS,_REQUIRED
from examples.node_contract import demonstrate
A=RegtestKey.from_int(1);B=RegtestKey.from_int(2)

class ReferenceTests(unittest.TestCase):
    def setUp(self):
        self.previous=build_coinbase(1,A.script_pubkey)
        self.args=('regtest',[(self.previous.serialize().hex(),0)],
                   [{'address':encode_address(B.script_pubkey),'amount_units':3*COIN}],encode_address(A.script_pubkey))
        self.package=ref.create_package(*self.args,fee_units=100000)
    def entry(self,index=0,key=A,package=None):
        digest=ref.inspect_package(package or self.package,'regtest')['inputs'][index]['digest_hex']
        return {'input_index':index,'public_key':key.pubkey.hex(),'signature_der':key.sign_digest(bytes.fromhex(digest)).hex()}
    def test_external_signature_attachment_and_vector(self):
        view=ref.inspect_package(self.package,'regtest')
        self.assertEqual(100000,view['fee_units']);self.assertFalse(view['complete'])
        signed=ref.attach_signatures(self.package,'regtest',[self.entry()])
        tx=ref.finalize_package(signed,'regtest')
        self.assertEqual(view['txid'],hash_to_display(tx.txid()))
        self.assertLessEqual((tx.weight()+3)//4,view['estimated_vsize'])
        vector=json.loads((ROOT/'examples/exchange/vectors.json').read_text())
        self.assertEqual(vector['inspection'],ref.inspect_package(vector['unsigned_package'],'regtest'))
        self.assertEqual(vector['signed_hex'],ref.finalize_package(vector['signed_package'],'regtest').serialize().hex())
    def test_no_keys_network_or_operational_api(self):
        for name in ('sign_package','prepare_from_node','broadcast_package','scan_deposits','sweep'):
            self.assertFalse(hasattr(ref,name))
        self.assertRaises(TypeError,ref.create_package,*self.args,sweep=True,fee_units=100000)
        for name in ('sumuww/exchange.py','sumuww/exchange_cli.py','sumuww/exchange_watch.py','sumuww/exchange_demo.py'):
            self.assertFalse((ROOT/name).exists())
        text=(ROOT/'sumuww_node_entry.py').read_text()
        self.assertNotIn('exchange',text)
    def test_wrong_network_bad_signature_and_duplicate(self):
        self.assertRaises(ValueError,ref.inspect_package,self.package,'sumuww')
        self.assertRaises(ValueError,ref.finalize_package,self.package,'regtest')
        self.assertRaises(ValueError,ref.attach_signatures,self.package,'regtest',[self.entry(key=B)])
        entry=self.entry();signed=ref.attach_signatures(self.package,'regtest',[entry])
        self.assertRaises(ValueError,ref.attach_signatures,signed,'regtest',[entry])
    def test_tampered_request_and_previous_amount(self):
        bad=copy.deepcopy(self.package);bad['unsigned_tx']=bad['unsigned_tx'][:-2]+'01'
        self.assertRaises(ValueError,ref.inspect_package,bad,'regtest')
        bad=copy.deepcopy(self.package)
        forged=replace(self.previous,outputs=(TxOutput(100*COIN,A.script_pubkey),))
        bad['previous_transactions'][hash_to_display(self.previous.txid())]=forged.serialize().hex()
        bad['request_id']=ref._identifier({k:bad[k] for k in ref.BODY_FIELDS})
        self.assertRaises(ValueError,ref.inspect_package,bad,'regtest')
    def test_all_explicit_inputs_used_and_every_signature_required(self):
        second=build_coinbase(2,B.script_pubkey)
        package=ref.create_package('regtest',self.args[1]+[(second.serialize().hex(),0)],self.args[2],self.args[3],fee_units=100000)
        self.assertEqual(2,len(ref.inspect_package(package,'regtest')['inputs']))
        partial=ref.attach_signatures(package,'regtest',[self.entry(package=package)])
        self.assertRaises(ValueError,ref.finalize_package,partial,'regtest')
        complete=ref.attach_signatures(partial,'regtest',[self.entry(1,B,package)])
        self.assertEqual(2,len(ref.finalize_package(complete,'regtest').inputs))
    def test_amount_and_duplicate_input_bounds(self):
        rate=ref.create_package(*self.args,fee_rate=7)
        view=ref.inspect_package(rate,'regtest');self.assertEqual(view['fee_units'],7*view['estimated_vsize'])
        for value in (True,1.2,-1,0):
            self.assertRaises(ValueError,ref.create_package,'regtest',self.args[1],[{'address':self.args[2][0]['address'],'amount_units':value}],self.args[3],fee_units=100000)
        self.assertRaises(ValueError,ref.create_package,'regtest',self.args[1]*2,self.args[2],self.args[3],fee_units=100000)
    def test_contract_matches_implementation(self):
        c=json.loads((ROOT/'API_CONTRACT.json').read_text())
        self.assertEqual(28,c['rpc_method_count'])
        self.assertEqual({n:{'parameters':list(p),'required':_REQUIRED.get(n,0)} for n,p in METHODS.items()},c['methods'])

class NodeContractTests(unittest.TestCase):
    def test_real_authenticated_http_reorg_and_data_persistence(self):
        report=asyncio.run(demonstrate());self.assertEqual(8,report['passed'])
