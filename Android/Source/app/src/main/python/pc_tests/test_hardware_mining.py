import json
import socket
import tempfile
import threading
import unittest
from pathlib import Path
from dataclasses import replace
from sumuww import hardware_mining as policy
from sumuww.chain import Chain
from sumuww.block import Block, mine_header
from sumuww.primitives import merkle_root
from sumuww.stratum_mining import StratumMiner, word_swap

class DevicePolicyTests(unittest.TestCase):
    def test_unlock_boundaries_and_cpu(self):
        for mode,minimum in [('gpu',12000),('asic',12000)]:
            with self.assertRaises(ValueError):policy.require_unlocked(mode,minimum-1)
            policy.require_unlocked(mode,minimum)
            policy.require_unlocked(mode,minimum+1)
        policy.require_unlocked('cpu',0)
        self.assertEqual(policy.public_settings(policy.validate_settings(),11999)['available_modes'],['cpu'])
        self.assertEqual(policy.public_settings(policy.validate_settings(),12000)['available_modes'],['cpu','gpu','asic'])
        self.assertEqual(policy.public_settings(policy.validate_settings(),12001)['available_modes'],['cpu','gpu','asic'])
    def test_preference_roundtrip_and_secret_not_in_status(self):
        with tempfile.TemporaryDirectory() as root:
            v=policy.validate_settings('asic','0.0.0.0',3333,'test-password-16chars')
            policy.save_settings(root,v)
            self.assertEqual(policy.load_settings(root),v)
            self.assertNotIn(v['password'],json.dumps(policy.public_settings(v,12000)))
    def test_bad_settings_cannot_enable_listener(self):
        for args in [('asic','127.0.0.1',3333,''),('gpu','8.8.8.8',3333,''),('asic','127.0.0.1',True,'test-password-16chars')]:
            with self.assertRaises(ValueError):policy.validate_settings(*args)
        with tempfile.TemporaryDirectory() as root:
            Path(root,policy.SETTINGS_NAME).write_text('{}')
            self.assertEqual(policy.load_settings(root)['mode'],'cpu')

class StratumSoloTests(unittest.TestCase):
    def test_authenticated_job_reconstruction_and_complete_block(self):
        self._exercise_authenticated_job('dora')

    def test_sumuww_worker_reconstructs_and_submits_a_valid_block(self):
        self._exercise_authenticated_job('sumuww')

    def _exercise_authenticated_job(self, worker_name):
        with tempfile.TemporaryDirectory() as root,Chain(Path(root)/'node.sqlite') as chain:
            template=chain._block_template(b'\x00\x14'+bytes(20))
            bridge=StratumMiner('127.0.0.1',0,'test-password-16chars')
            cancel=threading.Event();result=[];errors=[]
            def run():
                try:result.append(bridge.mine(template,chain.network.pow_limit,cancel.is_set))
                except BaseException as e:errors.append(e)
            worker=threading.Thread(target=run);worker.start()
            try:
                with socket.create_connection(bridge.endpoint,timeout=5) as client:
                    client.settimeout(5);reader=client.makefile('rb')
                    def send(method,params,number):client.sendall((json.dumps({'id':number,'method':method,'params':params})+'\n').encode())
                    def read():return json.loads(reader.readline())
                    send('mining.subscribe',[],1);subscription=read();extra1=bytes.fromhex(subscription['result'][1])
                    send('mining.authorize',[worker_name,'wrong-password'],2);self.assertFalse(read()['result'])
                    send('mining.submit',[worker_name,'invalid','00000000','00000000','00000000'],3);self.assertEqual(read()['error'][0],24)
                    send('mining.authorize',[worker_name,'test-password-16chars'],4);self.assertTrue(read()['result'])
                    self.assertEqual(read()['method'],'mining.set_difficulty');notify=read()['params']
                    self.assertEqual(word_swap(bytes.fromhex(notify[1])),template.header.previous_hash)
                    from sumuww.transaction import Transaction
                    extra2=bytes.fromhex('01020304')
                    cbraw=bytes.fromhex(notify[2])+extra1+extra2+bytes.fromhex(notify[3])
                    cb,end=Transaction.deserialize_from(cbraw);self.assertEqual(end,len(cbraw))
                    txs=(cb,)+template.transactions[1:];root_hash,_=merkle_root([t.txid() for t in txs])
                    header=mine_header(replace(template.header,merkle_root=root_hash),pow_limit=chain.network.pow_limit)
                    send('mining.submit',[worker_name,'old-job',extra2.hex(),notify[7],f'{header.nonce:08x}'],5);self.assertEqual(read()['error'][0],21)
                    send('mining.submit',[worker_name,notify[0],extra2.hex(),notify[7],f'{header.nonce:08x}'],6);self.assertTrue(read()['result'])
                worker.join(5);self.assertFalse(worker.is_alive());self.assertFalse(errors);self.assertEqual(len(result),1)
                self.assertTrue(chain.accept_block(result[0]))
                self.assertEqual(result[0].transactions[0].outputs,template.transactions[0].outputs)
            finally:
                cancel.set();worker.join(5);bridge.close()
    def test_cancellation_without_device(self):
        with tempfile.TemporaryDirectory() as root,Chain(Path(root)/'node.sqlite') as chain:
            bridge=StratumMiner('127.0.0.1',0,'test-password-16chars')
            try:
                with self.assertRaisesRegex(RuntimeError,'cancelled'):
                    bridge.mine(chain._block_template(b'\x00\x14'+bytes(20)),chain.network.pow_limit,lambda:True)
            finally:bridge.close()
    def test_listener_does_not_steal_occupied_port(self):
        first=StratumMiner('127.0.0.1',0,'test-password-16chars')
        try:
            with self.assertRaises(OSError):StratumMiner(*first.endpoint,'test-password-16chars')
        finally:first.close()

class HardwareServiceTests(unittest.TestCase):
    def test_service_uses_verified_height_and_preserves_cpu_after_rejected_device(self):
        from sumuww.app_service import AppService
        with tempfile.TemporaryDirectory() as root:
            service=AppService(root,network='regtest',bootstrap=False)
            try:
                service.start().result(timeout=10)
                for mode in ('gpu','asic'):
                    with self.assertRaisesRegex(Exception,'height'):
                        service.configure_mining_hardware(mode,'127.0.0.1',3333,'test-password-16chars').result(timeout=5)
                status=service.status().result(timeout=5)
                self.assertEqual(status['mining']['hardware']['mode'],'cpu')
                self.assertFalse(Path(root,policy.SETTINGS_NAME).exists())
                self.assertEqual(service.configure_mining_hardware('cpu').result(timeout=5)['mode'],'cpu')
            finally:service.stop().result(timeout=10)

    def test_branch_reconstructs_odd_and_even_transaction_sets(self):
        from sumuww.stratum_mining import coinbase_branch
        from sumuww.primitives import sha256d
        class Leaf:
            def __init__(self,n):self.value=sha256d(bytes([n]))
            def txid(self):return self.value
        for count in (1,2,3,4,5,9):
            txs=[Leaf(i) for i in range(count)];value=txs[0].txid()
            for sibling in coinbase_branch(txs):value=sha256d(value+sibling)
            self.assertEqual(value,merkle_root([t.txid() for t in txs])[0])
