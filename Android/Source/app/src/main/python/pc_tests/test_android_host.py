"""New host lifecycle failure/race tests. No real wallet or public network."""
from concurrent.futures import Future
import json
import threading
import time
import unittest
from unittest.mock import patch
import pc_runtime as host

def done(value=None,error=None):
    future=Future()
    if error:future.set_exception(error)
    else:future.set_result(value)
    return future

class FakeService:
    def __init__(self,*args,**kwargs):
        self.pending=[];self.lock=threading.Lock();self.closed=False
        self.started=False;self.fail_start=False;self.fail_close=False
        self.gate=None
    def start(self):
        self.started=True
        return done(error=OSError('Owned startup failure')) if self.fail_start else done({})
    def stop(self):
        if self.fail_close:return done(error=OSError('Owned close failure'))
        self.closed=True;self.cancel_mining();return done({})
    def status(self):return done({'node':{'height':0,'running':not self.closed,'peers':0},'wallet':None})
    def mine_one(self):
        future=Future()
        with self.lock:self.pending.append(future)
        return future
    def cancel_mining(self):
        if self.gate:self.gate.wait(timeout=2)
        with self.lock:
            for future in self.pending:
                if not future.done():future.set_result({'cancelled':True})
        return done({})

class HostLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.saved_cancel=host._cancel
        host._cancel=threading.Event()
        self.saved=(host._service,host._worker,host._runtime_state,host._runtime_error)
        host._service=None;host._worker=None;host._runtime_state='stopped';host._runtime_error=None
        with host._batch_guard:
            self.batch=dict(host._batch)
            host._batch.update(running=False,target=0,completed=0,last_error=None,last_result=None,started_at=None,ended_at=None)
    def tearDown(self):
        if host._service is not None:
            host._service.gate=None;host._service.fail_close=False
            host.stop()
        host._service,host._worker,host._runtime_state,host._runtime_error=self.saved
        host._cancel=self.saved_cancel
        with host._batch_guard:host._batch.update(self.batch)
    def attach(self):
        service=FakeService();host._service=service;host._runtime_state='running';return service
    def wait_pending(self,service,count=1):
        deadline=time.monotonic()+2
        while len(service.pending)<count:
            self.assertLess(time.monotonic(),deadline);time.sleep(.005)
    def test_stopped_status_never_reports_ready(self):
        result=json.loads(host.status())
        self.assertEqual(result['runtime_state'],'stopped')
        self.assertFalse(result['node']['mining_ready'])
        self.assertEqual(result['node']['peers'],0)
    def test_failed_start_cleans_actor_before_retry(self):
        failed=FakeService();failed.fail_start=True;healthy=FakeService()
        with patch.object(host,'AppService',side_effect=[failed,healthy]):
            with self.assertRaises(OSError):host.start('owned')
            self.assertTrue(failed.closed)
            self.assertIsNone(host._service)
            host.start('owned')
            self.assertIs(host._service,healthy)
    def test_failed_cleanup_blocks_second_actor(self):
        failed=FakeService();failed.fail_start=True;failed.fail_close=True
        with patch.object(host,'AppService',return_value=failed) as factory:
            with self.assertRaises(OSError):host.start('owned')
            with self.assertRaises(RuntimeError):host.start('owned')
            self.assertEqual(factory.call_count,1)
            self.assertEqual(host._runtime_state,'stopping')
        failed.fail_close=False;host.stop()
        self.assertIsNone(host._service)
    def test_double_start_is_rejected(self):
        service=self.attach();host.mine_blocks('2');self.wait_pending(service)
        with self.assertRaises(RuntimeError):host.mine_blocks('1')
        host.stop_mining();self.assertFalse(host._worker.is_alive())
    def test_stop_and_restart_cannot_share_cancel_event(self):
        service=self.attach();host.mine_blocks('2');self.wait_pending(service)
        service.gate=threading.Event()
        stopped=threading.Thread(target=host.stop_mining);stopped.start();time.sleep(.02)
        restarted=threading.Event();errors=[]
        def restart():
            try:host.mine_blocks('1');restarted.set()
            except Exception as error:errors.append(error)
        new=threading.Thread(target=restart);new.start();time.sleep(.02)
        self.assertFalse(restarted.is_set())
        service.gate.set();stopped.join(2);new.join(2)
        self.assertFalse(errors);self.assertTrue(restarted.is_set())
        self.wait_pending(service,2);host.stop_mining()
    def test_elapsed_time_stops_after_cancellation(self):
        service=self.attach();host.mine_blocks('1');self.wait_pending(service);time.sleep(.02)
        host.stop_mining()
        first=json.loads(host.status())['mobile_batch']['elapsed_seconds'];time.sleep(.03)
        second=json.loads(host.status())['mobile_batch']['elapsed_seconds']
        self.assertGreater(first,0);self.assertEqual(first,second)
    def test_bad_batch_counts_have_no_side_effects(self):
        service=self.attach()
        for value in ['0','10001','not-a-number','-1']:
            with self.assertRaises(ValueError):host.mine_blocks(value)
        self.assertFalse(service.pending)
        self.assertFalse(json.loads(host.status())['mobile_batch']['running'])
    def test_publication_never_overwrites_existing_file(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as folder:
            source=Path(folder)/'source';destination=Path(folder)/'destination'
            source.write_bytes(b'new');destination.write_bytes(b'original')
            with self.assertRaises(FileExistsError):host._publish_android(source,destination)
            self.assertEqual(destination.read_bytes(),b'original')
            self.assertEqual(source.read_bytes(),b'new')
