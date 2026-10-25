"""Android transport adapter over SUMUWW AppService.

No mobile node/consensus/miner/wallet implementation is imported here.
Platform file publication, network lifecycle and presentation/batch calls are adapted.
"""
import ctypes
import errno
import json
import os
from pathlib import Path
import threading
import time
from sumuww.app_service import AppService
from sumuww import keystore
from sumuww.primitives import format_amount, subsidy
from mobile_mining_metrics import metrics as mining_metrics, install as install_mining_metrics

_service=None
_guard=threading.RLock()
_batch_guard=threading.Lock()
_cancel=threading.Event()
_worker=None
_runtime_state='stopped'
_runtime_error=None
_batch={'running':False,'target':0,'completed':0,'last_error':None,'last_result':None,
        'started_at':None,'ended_at':None,'finished_wait_seconds':0.0,'finished_network_pauses':0}
_security={'locked':False,'timeout':300,'activity':time.monotonic(),'key_locked':False}
_security_guard=threading.RLock()

def set_foreground(value):
    mining_metrics.foreground=str(value).lower()=='true'
    return '{}'

def security_settings(seconds):
    seconds=int(seconds)
    if seconds not in (60,300,900): raise ValueError('Invalid lock timeout')
    with _security_guard: _security['timeout']=seconds
    return _json({'timeout':seconds})

def user_activity():
    _security_check()
    with _security_guard:
        if not _security['locked']: _security['activity']=time.monotonic()
    return '{}'

def _security_check():
    # A mining session holds only the original service's existing key. The UI
    # gate blocks new spending; when the batch ends the original lock clears it.
    with _security_guard:
        if time.monotonic()-_security['activity']>=_security['timeout']:
            _security['locked']=True
        with _batch_guard: running=_batch['running']
        if _security['locked'] and not running and not _security['key_locked'] and _service is not None:
            _result(_service.lock_wallet(),30)
            _security['key_locked']=True
        return {'locked':_security['locked'],'timeout':_security['timeout'],
                'key_locked':_security['key_locked']}

def _require_spending():
    if _security_check()['locked']:
        from sumuww.app_service import AppServiceError
        raise AppServiceError('Unlock spending with your wallet password')

def unlock_spending(password):
    with _security_guard:
        value=_result(_get().status())
        wallet=value.get('wallet')
        if not wallet: raise RuntimeError('Select a wallet first')
        # Authenticate the existing encrypted keystore without changing the
        # selected key, address, mining work or network connection.
        key=keystore.load_wallet(wallet['path'],password,network=_get().network)
        if key.address!=wallet['address']: raise RuntimeError('Selected wallet changed')
        if not wallet.get('unlocked'): _result(_get().open_wallet(wallet['path'],password))
        _security.update(locked=False,key_locked=False,activity=time.monotonic())
    return status()

def _session_opened():
    with _security_guard: _security.update(locked=False,key_locked=False,activity=time.monotonic())

def _publish_android(source,destination):
    """Same no-overwrite guarantee using Android's supported Linux syscall."""
    platform=ctypes.CDLL('libsumuww_platform.so')
    rename=platform.sumuww_publish_no_replace
    rename.argtypes=[ctypes.c_char_p,ctypes.c_char_p]
    rename.restype=ctypes.c_int
    code=rename(os.fsencode(source),os.fsencode(destination))
    if code!=0:
        raise OSError(code,os.strerror(code),str(destination))

def _get():
    if _service is None: raise RuntimeError('SUMUWW node has not started')
    return _service
def _result(future,timeout=120): return future.result(timeout=timeout)
def _json(value):
    from sumuww.compatibility import public_view
    return json.dumps(public_view(value),ensure_ascii=False)
def start(directory):
    global _service,_runtime_state,_runtime_error
    with _guard:
        if _service is None:
            install_mining_metrics()
            if os.name=='posix':
                if os.environ.get('SUMUWW_MOBILE_PEER_TRACE') == '1':
                    from mobile_peer_trace import install as install_peer_trace
                    install_peer_trace()
                from mobile_interfaces import install as install_interfaces
                install_interfaces()
                keystore._publish_no_replace=_publish_android
            network_provider=None
            if os.name=='posix':
                from mobile_interfaces import network_identity
                network_provider=network_identity
            service=AppService(directory,network='dora',bootstrap=True,allow_lan=True,allow_internet=True,
                               network_provider=network_provider)
            _runtime_state='starting'
            _runtime_error=None
            try:
                _result(service.start())
            except Exception as error:
                _runtime_error=str(error)
                _runtime_state='failed'
                try:
                    _result(service.stop(),60)
                except Exception:
                    # Retain a cleanup reference, preventing a second actor
                    # from opening this database until shutdown succeeds.
                    _service=service
                    _runtime_state='stopping'
                raise
            else:
                _service=service
                _runtime_state='running'
        elif _runtime_state in ('stopping','failed'):
            raise RuntimeError('Previous SUMUWW node must finish shutdown before restarting')
    return status()
def status():
    service=_service
    if service is None:
        value={'node':{'running':False,'peers':0,'height':-1,'mining_ready':False,
                       'sync_state':_runtime_state},'wallet':None,'transactions':[]}
    else:
        value=_result(service.status(),30)
    value['security']=_security_check()
    if _security['key_locked'] and service is not None:
        value=_result(service.status(),30)|{'security':value['security']}
    value['runtime_state']=_runtime_state
    value['runtime_error']=_runtime_error
    value['current_subsidy_smw']=format_amount(subsidy(max(0,value['node'].get('height',-1)+1)))+' SUMUWW'
    with _batch_guard:
        value['mobile_batch']=dict(_batch)
        beginning=_batch['started_at']
        ending=_batch['ended_at'] if _batch['ended_at'] is not None else time.monotonic()
        value['mobile_batch']['elapsed_seconds']=max(0,ending-beginning) if beginning is not None else 0
        current=value.get('mining',{}) if _batch['running'] else {}
        # A result is copied before the next mine_one submission resets its
        # per-block counters. Count a running reservation only once.
        active=current if current.get('reserved') else {}
        wait=_batch['finished_wait_seconds']+float(active.get('network_wait_seconds',0))
        value['mobile_batch']['network_wait_seconds']=wait
        value['mobile_batch']['network_pauses']=_batch['finished_network_pauses']+int(active.get('network_pauses',0))
    value['mobile_mining']=mining_metrics.snapshot()
    if value['mobile_batch']['last_error']: value['last_mining_error']=value['mobile_batch']['last_error']
    return _json(value)
def create_wallet(password):
    value=_result(_get().create_wallet('wallet.json',password))
    _session_opened()
    return _json(value)
def create_seed_wallet(password):
    value=_result(_get().create_seed_wallet('wallet.json',password))
    _session_opened()
    return _json(value)
def open_wallet(password):
    value=_result(_get().open_wallet('wallet.json',password))
    _session_opened()
    return _json(value)
def lock_wallet():
    value=_result(_get().lock_wallet())
    with _security_guard: _security.update(locked=True,key_locked=True)
    return _json(value)
def recovery_phrase(password): return _result(_get().recovery_phrase(password))
def recover_seed_wallet(password,words):
    value=_result(_get().recover_seed_wallet('wallet.json',password,words))
    _session_opened()
    return _json(value)
def restore_wallet(source,password):
    value=_result(_get().restore_wallet(source,'wallet.json',password))
    _session_opened()
    return _json(value)
def transaction_history(offset='0',limit='50'): return _json(_result(_get().transaction_history(int(offset),int(limit))))
def prepare_payment(address,amount,fee=""):
    with _security_guard:
        _require_spending()
        return _json(_result(_get().prepare_payment(address,amount,fee if fee else None)))
def submit_payment(quote):
    with _security_guard:
        _require_spending()
        return _json(_result(_get().submit_payment(quote)))
def submit_payment_result(quote):
    from sumuww.app_service import AppServiceError
    from sumuww.errors import ValidationError
    try:
        return _json({'outcome':'accepted','result':json.loads(submit_payment(quote))})
    except (AppServiceError,ValidationError) as error:
        return _json({'outcome':'rejected','error':str(error)})
    except Exception as error:
        # Timeout/storage/interruption must not be advertised as an unspent payment.
        return _json({'outcome':'unknown','error':str(error)})
def add_peer(address): return _json(_result(_get().add_peer(address)))

def configure_privacy(mode, port):
    _result(_get().configure_privacy(mode, int(port)))
    return status()
def _run_batch(service,count):
    try:
        for _ in range(count):
            if _cancel.is_set(): break
            value=_result(service.mine_one(),None)
            with _batch_guard:
                _batch['finished_wait_seconds']+=float(value.get('network_wait_seconds',0))
                _batch['finished_network_pauses']+=int(value.get('network_pauses',0))
            if value.get('cancelled'): break
            with _batch_guard:
                _batch['completed']+=1
                _batch['last_result']=value
    except Exception as error:
        with _batch_guard: _batch['last_error']=str(error)
    finally:
        with _batch_guard:
            _batch['running']=False
            _batch['ended_at']=time.monotonic()
def mine_blocks(count):
    global _worker
    _require_spending()
    count=int(count)
    if not 1<=count<=10000: raise ValueError('Block count must be1–10000')
    with _guard:
        service=_get()
        if _runtime_state=='stopping': raise RuntimeError('SUMUWW node is shutting down')
        with _batch_guard: already_running=_batch['running']
        if not already_running and _worker is not None and _worker.is_alive():
            # The previous worker may be returning just after publishing its
            # final snapshot; do not reset its cancellation event prematurely.
            _worker.join(timeout=.1)
        with _batch_guard:
            if _batch['running'] or (_worker is not None and _worker.is_alive()):
                raise RuntimeError('Mining is already running')
            _cancel.clear()
            mining_metrics.reset()
            _batch.update(running=True,target=count,completed=0,last_error=None,last_result=None,protection_reason=None,
                          started_at=time.monotonic(),ended_at=None,finished_wait_seconds=0.0,finished_network_pauses=0)
            _worker=threading.Thread(target=_run_batch,args=(service,count),daemon=True,name='pc042-batch')
            _worker.start()
    return _json({'started':True})
def stop_mining():
    with _guard:
        _cancel.set()
        service=_service
        if service is not None: _result(service.cancel_mining(),30)
        worker=_worker
        if worker and worker is not threading.current_thread():
            worker.join(timeout=30)
            if worker.is_alive(): raise RuntimeError('Mining worker has not finished stopping')
        return status()
def stop():
    global _service,_runtime_state
    with _guard:
        if _service:
            _runtime_state='stopping'
            _cancel.set()
            # Always run actor shutdown even if the preliminary cancellation
            # times out; actor.stop also cancels mining and closes the DB.
            try: _result(_service.cancel_mining(),30)
            except Exception: pass
            _result(_service.stop(),60)
            if _worker and _worker is not threading.current_thread():
                _worker.join(timeout=30)
                if _worker.is_alive(): raise RuntimeError('Mining worker has not exited')
            _service=None
        _runtime_state='stopped'
    return _json({'stopped':True})


def stop_mining_for_safety(reason):
    stop_mining()
    with _batch_guard: _batch['protection_reason']=str(reason)
    return status()

def block_history(offset='0',limit='50',height=''):
    height = int(height) if height.strip() else None
    return _json(_result(_service.block_history(int(offset), int(limit), height)))

def filtered_history(offset='0',limit='50',kind='all',query=''):
    offset,limit=int(offset),int(limit)
    if offset<0 or not 1<=limit<=200 or kind not in ('all','receive','send','mining'):
        raise ValueError('Invalid history request')
    query=query.strip().lower()
    if len(query)>64: raise ValueError('Transaction ID is too long')
    for attempt in range(2):
        selected=[];matched=0;position=0;tip=None;owner=None
        while True:
            page=_result(_get().transaction_history(position,200))
            if tip is None: tip,owner=page['tip'],page['address']
            if page['tip']!=tip or page['address']!=owner: break
            for tx in page['transactions']:
                txkind='mining' if tx['coinbase'] else 'receive' if tx['net_amount']>=0 else 'send'
                if (kind=='all' or txkind==kind) and query in tx['txid'].lower():
                    if offset<=matched<offset+limit: selected.append(tx)
                    matched+=1
            position+=len(page['transactions'])
            if position>=page['total']:
                page.update(transactions=selected,total=matched,offset=offset,limit=limit)
                return _json(page)
    raise RuntimeError('History changed during search; refresh and try again')
