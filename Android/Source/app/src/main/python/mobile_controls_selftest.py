"""Owned fixtures for the new host adapter; never use the live service."""
import importlib.util
import json
from pathlib import Path
import tempfile
import time
import unittest
from concurrent.futures import Future

def run():
    import pc_runtime
    spec=importlib.util.find_spec('pc_runtime')
    import types
    host=types.ModuleType('owned_mobile_host')
    exec(spec.loader.get_code('pc_runtime'),host.__dict__)
    def ready(value):
        f=Future();f.set_result(value);return f
    class Fake:
        network='regtest'
        def __init__(self):self.locks=0;self.prepares=0;self.submits=0;self.wallet=None
        def status(self):return ready({'node':{'height':100,'peers':1},'wallet':self.wallet})
        def lock_wallet(self):
            self.locks+=1
            if self.wallet:self.wallet['unlocked']=False
            return ready(self.wallet)
        def open_wallet(self,path,password):
            host.keystore.load_wallet(path,password,network=self.network)
            self.wallet['unlocked']=True;return ready(self.wallet)
        def prepare_payment(self,*args):self.prepares+=1;return ready({'quote_id':'owned'})
        def submit_payment(self,*args):self.submits+=1;return ready({'txid':'owned'})
        def transaction_history(self,offset,limit):
            rows=[{'txid':f'{i:064x}','coinbase':i%3==0,'net_amount':-1 if i%3==1 else 1,'height':i+1,'status':'confirmed'} for i in range(450)]
            return ready({'tip':'owned-tip','address':'owned-wallet','height':500,'transactions':rows[offset:offset+limit],'total':len(rows)})
    class Checks(unittest.TestCase):
        def setUp(self):
            host._security['timeout']=300;host._service=Fake();host._batch['running']=False;host._session_opened()
        def expire(self):host._security['activity']=time.monotonic()-301
        def test_idle_lock_once(self):
            self.expire();self.assertTrue(host._security_check()['key_locked']);host._security_check();self.assertEqual(1,host._service.locks)
        def test_mining_continues_locked_spending(self):
            host._batch['running']=True;self.expire();state=host._security_check()
            self.assertTrue(state['locked']);self.assertFalse(state['key_locked']);self.assertEqual(0,host._service.locks)
            with self.assertRaises(Exception):host.prepare_payment('owned','1')
            self.assertEqual(0,host._service.prepares)
            host.user_activity();self.assertTrue(host._security['locked'])
            host._batch['running']=False;host._security_check();self.assertEqual(1,host._service.locks)
        def test_touch_cannot_bypass_timeout(self):
            self.expire();host.user_activity();self.assertTrue(host._security['locked'])
        def test_settings_cannot_unlock(self):
            self.expire();host._security_check();host.security_settings('900');self.assertTrue(host._security['locked'])
        def test_submission_gate(self):
            self.expire();value=json.loads(host.submit_payment_result('owned'))
            self.assertEqual('rejected',value['outcome']);self.assertEqual(0,host._service.submits)
        def test_wrong_password_does_not_unlock(self):
            with tempfile.TemporaryDirectory() as directory:
                path=Path(directory)/'wallet.json';key=host.keystore.create_wallet(path,'owned-test-password',network='regtest')
                host._service.wallet={'path':str(path),'address':key.address,'unlocked':True}
                host._batch['running']=True;self.expire();host._security_check()
                with self.assertRaises(Exception):host.unlock_spending('wrong-password')
                self.assertTrue(host._security['locked']);self.assertEqual(0,host._service.locks)
                host.unlock_spending('owned-test-password');self.assertFalse(host._security['locked']);self.assertEqual(0,host._service.locks)
        def test_filtered_history_all_pages(self):
            value=json.loads(host.filtered_history('100','50','receive',''))
            self.assertEqual(150,value['total']);self.assertEqual(50,len(value['transactions']))
            self.assertTrue(all(tx['net_amount']>0 and not tx['coinbase'] for tx in value['transactions']))
        def test_search_and_invalid_requests(self):
            value=json.loads(host.filtered_history('0','50','all',f'{449:064x}'))
            self.assertEqual(1,value['total'])
            for args in [('-1','50','all',''),('0','201','all',''),('0','50','unknown','')]:
                with self.assertRaises(ValueError):host.filtered_history(*args)
        def test_unstable_snapshot_rejected(self):
            call=0
            original=host._service.transaction_history
            def changed(offset,limit):
                nonlocal call
                call+=1;value=original(offset,limit).result();value['tip']=str(call);return ready(value)
            host._service.transaction_history=changed
            with self.assertRaises(RuntimeError):host.filtered_history()
        def test_settings_bounds(self):
            host.security_settings('60');self.assertEqual(60,host._security['timeout'])
            with self.assertRaises(ValueError):host.security_settings('0')
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(Checks)
    result=unittest.TestResult();suite.run(result)
    return json.dumps({'tests':result.testsRun,'failures':[str(x) for x in result.failures],'errors':[str(x) for x in result.errors],'success':result.wasSuccessful()})
