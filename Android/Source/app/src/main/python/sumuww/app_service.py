"""Future-based wallet service; Tk never owns a SQLite connection or a key.

PeerNode, wallet keys and ordinary commands live on one asyncio actor thread.
Mining uses a separate worker's own Chain connection, as a local CLI would,
and receives only a public script and a thread-safe cancellation signal.
"""

import asyncio
from concurrent.futures import Future, InvalidStateError, ThreadPoolExecutor
import os
import json
from pathlib import Path
import queue
import secrets
import threading
import time
import tempfile

from .__main__ import create_payment
from .address import AddressError, decode_address
from .chain import Chain
from .errors import StorageError, UnsupportedFeature, ValidationError
from .keystore import (WalletError, create_wallet as keystore_create,
                       load_wallet as keystore_load, backup_wallet as keystore_backup,
                       restore_wallet as keystore_restore, create_hd_wallet,
                       recover_hd_wallet, export_mnemonic)
from .compatibility import compatibility_fields
from .peer import PeerNode
from .peerd import endpoint, public_contact
from .primitives import coinbase_is_mature, format_amount, hash_to_display, parse_amount
from .profiles import get_network
from .network_settings import (SETTINGS_NAME, OWN_ADDRESS_SETTINGS_NAME, load_settings,
                               load_auto_address, normalize_settings, save_settings)
from .network_settings import _atomic_json
from .rpc import RpcServer, load_or_create_token, validate_rpc_endpoint
from .fees import estimate_payment_fee
from .bootstrap import load_bootstrap
from .wallet_history import WalletHistory
from . import hardware_mining
from . import privacy
from .wallet_paths import reject_wallet_overwrite, reserved_node_paths, same_path, is_managed_privacy_path


RPC_SETTINGS_NAME = 'rpc-settings.json'
RPC_TOKEN_NAME = 'rpc-token'
RPC_DEFAULT_PORT = 18443
PAYMENT_QUOTE_TTL = 120
PUBLIC_CONTACT_NAME = 'public-contact.json'
# SQLite releases the GIL while stepping rows. A continuously hashing Python
# thread can repeatedly win it back, stalling the network actor for seconds.
# Yield at the miner's bounded cancellation checkpoints, without changing PoW.
MINING_COOPERATIVE_YIELD_SECONDS = .001


def _load_public_contact(directory):
    path = Path(directory) / PUBLIC_CONTACT_NAME
    if not path.exists():
        return ''
    if path.stat().st_size > 4096:
        raise ValueError('Public contact settings are too large')
    def unique_fields(pairs):
        value = {}
        for name, item in pairs:
            if name in value:
                raise ValueError('Duplicate public contact settings field')
            value[name] = item
        return value
    value = json.loads(path.read_text(encoding='utf-8'), object_pairs_hook=unique_fields)
    if (type(value) is not dict or set(value) != {'schema_version', 'endpoint'}
            or type(value['schema_version']) is not int or value['schema_version'] != 1
            or type(value['endpoint']) is not str):
        raise ValueError('Invalid public contact settings')
    return value['endpoint']


def _restore_preference(path, original):
    """Restore exact prior bytes after a failed preference update."""
    reject_wallet_overwrite(path)
    if original is None:
        path.unlink(missing_ok=True)
        return
    temporary = None
    try:
        with tempfile.NamedTemporaryFile('wb', dir=path.parent,
                                         prefix=path.name + '.', suffix='.tmp', delete=False) as output:
            temporary = Path(output.name)
            output.write(original)
            output.flush()
            os.fsync(output.fileno())
        reject_wallet_overwrite(path)
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def _quote_clock():
    return time.monotonic()


def _rpc_settings(enabled=False, port=RPC_DEFAULT_PORT):
    if type(enabled) is not bool:
        raise ValueError('RPC enabled flag must be a bool')
    validate_rpc_endpoint('127.0.0.1', port)
    return {'schema_version': 1, 'enabled': enabled, 'port': port}


def _load_rpc_settings(directory):
    """A missing or malformed preference never enables a listener."""
    path = Path(directory) / RPC_SETTINGS_NAME
    try:
        if path.stat().st_size > 4096:
            return _rpc_settings()
        document = json.loads(path.read_text(encoding='utf-8'))
        if (isinstance(document, dict)
                and set(document) == {'schema_version', 'enabled', 'port'}
                and type(document['schema_version']) is int
                and document['schema_version'] == 1):
            return _rpc_settings(document['enabled'], document['port'])
    except (OSError, ValueError, TypeError, UnicodeError):
        pass
    return _rpc_settings()


class AppServiceError(RuntimeError):
    """A safe UI error without a traceback containing unlocked key material."""


def _safe_error(error):
    if isinstance(error, (AppServiceError, AddressError, WalletError, ValidationError,
                          StorageError, UnsupportedFeature)) or type(error) is ValueError:
        message = str(error)
    elif isinstance(error, OSError):
        message = 'File or network operation failed'
    else:
        message = 'Service operation failed'
    return AppServiceError(f'{type(error).__name__}: {message}')


def _finish(future, value=None, error=None):
    if future is None or future.done():
        return
    try:
        if error is None:
            future.set_result(compatibility_fields(value))
        else:
            future.set_exception(error)
    except InvalidStateError:
        # A caller may cancel a queued future while shutdown is completing it.
        pass


def _failed(message):
    result = Future()
    _finish(result, error=AppServiceError(message))
    return result


class _MiningInterruption:
    """A worker may stop for network pause or final cancellation, never keys."""

    def __init__(self, cancellation, pause):
        self.cancellation, self.pause = cancellation, pause

    def is_set(self):
        return self.cancellation.is_set() or self.pause.is_set()

    def wait(self, timeout=None):
        deadline = None if timeout is None else time.monotonic() + timeout
        while not self.is_set():
            remaining = .05 if deadline is None else min(.05, deadline - time.monotonic())
            if remaining <= 0:
                return self.is_set()
            self.cancellation.wait(remaining)
        return True


_MINING_CONTEXT = threading.local()


class _MiningSession:
    """One fully validated Chain, created/used/closed by one hash thread."""

    def __init__(self, database, network, *, boundary_activation=None):
        self.database = Path(database).resolve()
        self.network = get_network(network)
        self.boundary_activation = boundary_activation
        self._owner = None
        self._chain = None
        self.hardware_settings = hardware_mining.validate_settings()
        self._backend = None
        self._backend_settings = None

    def _check_owner(self):
        owner = threading.get_ident()
        if self._owner is None:
            self._owner = owner
        elif self._owner != owner:
            raise RuntimeError('Mining session must stay on its owning thread')

    def chain(self, database, network):
        self._check_owner()
        if Path(database).resolve() != self.database or get_network(network) != self.network:
            raise RuntimeError('Mining session database or network mismatch')
        if self._chain is None:
            # The ordinary constructor always verifies persisted active-chain
            # state in full; reusing its connection never disables validation.
            self._chain = Chain(self.database, network=self.network,boundary_activation=self.boundary_activation)
        return self._chain

    def run(self, database, network, public_script, cancellation):
        self._check_owner()
        previous = getattr(_MINING_CONTEXT, 'session', None)
        _MINING_CONTEXT.session = self
        try:
            if self._backend_settings != self.hardware_settings:
                if self._backend is not None:
                    self._backend.close()
                self._backend = None
                self._backend = hardware_mining.create_backend(self.hardware_settings)
                self._backend_settings = dict(self.hardware_settings)
            # Preserve the public four-argument worker contract and its mocks.
            return _mine_block(database, network, public_script, cancellation)
        except BaseException:
            self.close()
            raise
        finally:
            if cancellation.is_set() and self._backend is not None:
                self._backend.close()
                self._backend = None
                self._backend_settings = None
            _MINING_CONTEXT.session = previous

    def run_staged(self, public_script, parent, cancellation):
        """Hash a real next header while its parent's certificate completes."""
        self._check_owner()
        chain=self.chain(self.database,self.network)
        parent_hash=parent.block_hash(); previous=parent.header.previous_hash
        def interrupted():
            time.sleep(MINING_COOPERATIVE_YIELD_SECONDS)
            return cancellation.is_set() or chain.tip_hash not in (previous,parent_hash)
        if interrupted():return None
        try:
            return chain.make_block(public_script,parent_hash=parent_hash,
                staged_parent=parent,mining_cancel=interrupted,mining_backend=self._backend)
        except RuntimeError:
            if interrupted():return None
            raise

    def close(self):
        self._check_owner()
        chain, self._chain = self._chain, None
        if self._backend is not None:
            self._backend.close()
            self._backend = None
            self._backend_settings = None
        if chain is not None:
            try:
                chain.close()
            except BaseException:
                # Release the owned SQLite connection even if surrounding
                # cleanup reports an error. Never close it on the Tk/actor.
                try:
                    chain.connection.close()
                except BaseException:
                    pass
                raise


def _mine_block(database, network, public_script, cancellation):
    """Mine the current chain, renewing stale work without reporting a reward."""
    if cancellation.is_set():
        return None
    session = getattr(_MINING_CONTEXT, 'session', None)
    if session is not None:
        return _search_active_chain(session.chain(database, network), public_script, cancellation)
    with Chain(database, network=network) as chain:
        return _search_active_chain(chain, public_script, cancellation)


def _search_active_chain(chain, public_script, cancellation):
    while not cancellation.is_set():
        parent = chain.tip_hash
        next_tip_check = 0.0
        stale = False

        def interrupted():
            nonlocal next_tip_check, stale
            if cancellation.is_set():
                return True
            time.sleep(MINING_COOPERATIVE_YIELD_SECONDS)
            now = time.monotonic()
            if now >= next_tip_check:
                next_tip_check = now + .25
                stale = chain.tip_hash != parent
            return stale

        try:
            session = getattr(_MINING_CONTEXT, 'session', None)
            backend = session._backend if session is not None else None
            if backend is not None:
                hardware_mining.require_unlocked(backend.mode, chain._row(parent)[2])
                block = chain.make_block(public_script, parent_hash=parent,
                                         mining_cancel=interrupted, mining_backend=backend)
            else:
                block = chain.make_block(public_script, parent_hash=parent,
                                         mining_cancel=interrupted)
        except RuntimeError:
            if cancellation.is_set():
                return None
            if stale:
                continue
            raise
        if cancellation.is_set():
            return None
        if chain.tip_hash != parent:
            continue
        if chain.boundary.required(chain._row(parent)[2]+1,parent):
            # The actor collects the certificate. This worker never accepts
            # an unsigned activated candidate or reports it as a reward.
            chain.validate_boundary_candidate(block)
            return block
        # The write transaction decides activation. A competing block
        # cannot make an inactive branch look like a successful reward.
        if chain.accept_block(block):
            return block.block_hash()
    return None


from .managed_privacy import ManagedRouter


class AppService:
    def __init__(self, directory, network='dora', listen=None, allow_lan=None,
                 allow_internet=None, peers=None, bootstrap=False, advertise=None,
                 bootstrap_manifest=None, bootstrap_scope='public', auto_address=None,
                 privacy_router_factory=ManagedRouter, network_provider=None):
        self.directory = Path(directory).expanduser().resolve()
        self.database = self.directory / 'node.sqlite'
        self.network = get_network(network)
        self._privacy_options = privacy.load(self.directory)
        self._privacy_router_factory = privacy_router_factory
        self._network_provider = network_provider
        if bootstrap_scope not in ('public', 'loopback') or (self.network.name == 'dora' and bootstrap_scope != 'public'):
            raise ValueError('The main network requires public bootstrap scope')
        self._bootstrap_manifest = bootstrap_manifest
        self._bootstrap_scope = bootstrap_scope
        self._bootstrap_error = None
        saved = load_settings(self.directory, bootstrap=bootstrap and self.network.name == 'dora')
        requested_listen = saved['listen'] if listen is None else listen
        selected_lan = saved['allow_lan'] if allow_lan is None else allow_lan
        selected_internet = saved['allow_internet'] if allow_internet is None else allow_internet
        supplied_contact = _load_public_contact(self.directory) if advertise is None else advertise
        saved_automatic = load_auto_address(self.directory)
        if auto_address is not None:
            if type(auto_address) is not bool:
                raise ValueError('Automatic address mode must be a bool')
            self._auto_address = auto_address
        elif listen is not None or advertise is not None:
            # An explicit advanced invocation overrides a previously selected
            # GUI mode. Passing auto_address=True opts back into automatic mode.
            self._auto_address = False
        elif saved_automatic is not None:
            self._auto_address = saved_automatic
        else:
            self._auto_address = (self.network.name == 'dora' and listen is None
                                  and requested_listen == '127.0.0.1:0'
                                  and advertise is None and not supplied_contact)
        self._settings = normalize_settings(self._requested_listener(requested_listen, self._auto_address,
                                            allow_lan=selected_lan, allow_internet=selected_internet),
                                            saved['peers'] if peers is None else peers,
                                            allow_lan=selected_lan, allow_internet=selected_internet)
        self.listen = self._settings['listen']
        self.allow_lan = self._settings['allow_lan']
        self.allow_internet = self._settings['allow_internet']
        self._public_contact = self._normalize_contact(supplied_contact, self._settings,
                                                       automatic=self._auto_address)
        self._control = threading.Lock()
        self._inbox = queue.Queue()
        self._state = 'new'
        self._thread = None
        self._loop = None
        self._wake = None
        self._start_future = None
        self._stop_future = None
        self._shutdown_error = None
        self._node = None
        self._key = None
        self._address = None
        self._script = None
        self._wallet_path = None
        self._wallet_kind = None
        self._mining_cancel = threading.Event()
        self._mining_pause = threading.Event()
        self._mining_cancel_reason = None
        self._mining_state = 'idle'
        self._mining_network_pauses = 0
        self._mining_wait_seconds = 0.0
        self._mining_wait_started = None
        self._mining_reserved = False
        self._mining_task = None
        self._mining_guard_task = None
        self._mining_executor = None
        self._mining_session = None
        self._boundary_pending = None
        self._history = None
        self._rpc_settings = _load_rpc_settings(self.directory)
        self._rpc = None
        self._rpc_error = None
        self._payment_quote = None
        self._hardware_settings = hardware_mining.load_settings(self.directory)

    def start(self):
        with self._control:
            if self._state in ('starting', 'running'):
                return self._start_future
            if self._state != 'new':
                return _failed('Service is closed; construct a new service to restart')
            self._state = 'starting'
            self._start_future = Future()
            self._thread = threading.Thread(target=self._thread_main, name='sumuww-app-actor', daemon=True)
            try:
                self._thread.start()
            except Exception as error:
                self._state = 'stopped'
                _finish(self._start_future, error=_safe_error(error))
            return self._start_future

    def _submit(self, operation, *arguments):
        with self._control:
            if self._state not in ('starting', 'running'):
                return _failed('Start the service before issuing commands, or wait for shutdown')
            if operation == 'mine':
                if self._mining_reserved:
                    return _failed('Mining is already running')
                self._mining_reserved = True
                # Clear on submission, so a cancellation before actor dispatch
                # cannot be accidentally erased when the worker starts.
                self._mining_cancel.clear()
                self._mining_pause.clear()
                self._mining_cancel_reason = None
                self._mining_state = 'queued'
                self._mining_network_pauses = 0
                self._mining_wait_seconds = 0.0
                self._mining_wait_started = None
            result = Future()
            self._inbox.put((operation, result, arguments))
            if self._loop is not None and self._wake is not None:
                self._loop.call_soon_threadsafe(self._wake.set)
            return result

    def status(self):
        return self._submit('status')

    def block_history(self, offset=0, limit=50, height=None):
        return self._submit('block_history', offset, limit, height)

    def transaction_history(self, offset=0, limit=50):
        return self._submit('transaction_history', offset, limit)

    def create_wallet(self, path, password):
        return self._submit('create', path, password)

    def create_seed_wallet(self, path, password):
        return self._submit('create_seed', path, password)

    def recover_seed_wallet(self, path, password, mnemonic):
        return self._submit('recover_seed', path, password, mnemonic)

    def recovery_phrase(self, password):
        return self._submit('recovery_phrase', password)

    def open_wallet(self, path, password):
        return self._submit('open', path, password)

    def lock_wallet(self):
        return self._submit('lock')

    def send(self, address, amount_string, fee_string=None):
        return self._submit('send', address, amount_string, fee_string)

    def prepare_payment(self, address, amount_string, fee_string=None):
        return self._submit('prepare_payment', address, amount_string, fee_string)

    def submit_payment(self, quote_id):
        return self._submit('submit_payment', quote_id)

    def backup_wallet(self, path, password):
        return self._submit('backup', path, password)

    def restore_wallet(self, source, destination, password):
        return self._submit('restore', source, destination, password)

    def configure_mining_hardware(self, mode, host="127.0.0.1", port=3333, password=""):
        return self._submit("mining_hardware", mode, host, port, password)

    def mine_one(self):
        return self._submit('mine')

    def add_peer(self, endpoint_string):
        return self._submit('peer', endpoint_string)

    def configure_network(self, listen, peers, allow_internet=False, allow_lan=False,
                          advertise=None, auto_address=None):
        return self._submit('configure_network', listen, peers, allow_internet, allow_lan,
                            advertise, auto_address)

    def configure_rpc(self, enabled, port=RPC_DEFAULT_PORT):
        return self._submit('configure_rpc', enabled, port)

    def configure_privacy(self, mode, port=None):
        return self._submit('configure_privacy', mode, port)

    def cancel_mining(self):
        self._request_mining_stop('user_stop')
        result = Future()
        _finish(result, {})
        return result

    def stop(self):
        self._request_mining_stop('shutdown')
        with self._control:
            if self._stop_future is not None:
                return self._stop_future
            result = self._stop_future = Future()
            thread = self._thread
            if thread is None or not thread.is_alive():
                self._state = 'stopped'
                _finish(result, {'stopped': True}, self._shutdown_error)
                return result
            self._state = 'stopping'
            self._inbox.put(('stop', None, ()))
            if self._loop is not None and self._wake is not None:
                self._loop.call_soon_threadsafe(self._wake.set)
        # Joining here would freeze Tk. Complete only after the actor and its
        # dedicated mining executor have closed, rather than merely scheduling it.
        try:
            threading.Thread(target=self._join_actor, args=(thread, result),
                             name='sumuww-app-close', daemon=True).start()
        except Exception as error:
            _finish(result, error=_safe_error(error))
        return result

    def _join_actor(self, thread, result):
        thread.join()
        _finish(result, {'stopped': True}, self._shutdown_error)

    def _request_mining_stop(self, reason):
        with self._control:
            if not self._mining_cancel.is_set():
                self._mining_cancel_reason = reason
            self._mining_cancel.set()
            if self._boundary_pending is not None:
                self._boundary_pending['cancel'].set()

    async def _halt_wallet_mining(self):
        self._request_mining_stop('wallet_change')
        if self._mining_reserved:
            if self._mining_task is not None and not self._mining_task.done():
                await self._mining_task
        await self._discard_boundary_pending()

    async def _close_mining_session(self):
        await self._discard_boundary_pending()
        executor, session = self._mining_executor, self._mining_session
        if executor is None:
            return
        try:
            await asyncio.get_running_loop().run_in_executor(executor, session.close)
        except BaseException as error:
            self._shutdown_error = _safe_error(error)
        finally:
            # All searches have settled before this call. The join happens on
            # the service actor while Tk awaits its separate shutdown Future.
            executor.shutdown(wait=True, cancel_futures=True)
            self._mining_executor = self._mining_session = None

    async def _discard_boundary_pending(self):
        pending,self._boundary_pending=self._boundary_pending,None
        if pending is not None:
            pending['cancel'].set()
            await asyncio.gather(pending['future'],return_exceptions=True)

    async def _boundary_result(self, awaitable, parent):
        task=asyncio.ensure_future(awaitable)
        try:
            while not task.done():
                if (self._mining_cancel.is_set() or self._mining_pause.is_set()
                        or self._node.chain.tip_hash!=parent):
                    return None
                await asyncio.wait((task,),timeout=.1)
            return task.result()
        finally:
            if not task.done():task.cancel()
            await asyncio.gather(task,return_exceptions=True)

    def _thread_main(self):
        loop = None
        failure = None
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            with self._control:
                self._loop = loop
                self._wake = asyncio.Event()
            loop.run_until_complete(self._run())
        except BaseException as error:
            failure = _safe_error(error)
        finally:
            self._request_mining_stop('shutdown')
            self._key = None
            self._payment_quote = None
            if loop is not None:
                try:
                    tasks = asyncio.all_tasks(loop)
                    for task in tasks:
                        task.cancel()
                    if tasks:
                        loop.run_until_complete(asyncio.gather(*tasks, return_exceptions=True))
                    loop.run_until_complete(loop.shutdown_asyncgens())
                    loop.run_until_complete(loop.shutdown_default_executor())
                except BaseException as error:
                    self._shutdown_error = _safe_error(error)
                finally:
                    with self._control:
                        self._loop = self._wake = None
                        self._state = 'stopped'
                        self._mining_reserved = False
                    loop.close()
                    asyncio.set_event_loop(None)
            else:
                with self._control:
                    self._state = 'stopped'
            if self._start_future is not None and not self._start_future.done():
                _finish(self._start_future, error=failure or AppServiceError('Service startup did not complete'))
            while True:
                try:
                    _, future, _ = self._inbox.get_nowait()
                except queue.Empty:
                    break
                _finish(future, error=failure or AppServiceError('Service is stopped'))

    async def _run(self):
        try:
            self._node = self._make_node(self._settings)
            await self._node.start()
            self._mining_session = _MiningSession(self.database, self.network,
                boundary_activation=self._node.chain.boundary.activation)
            self._mining_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix='sumuww-app-hash')
            if self._rpc_settings['enabled']:
                try:
                    self._rpc = await self._make_rpc(self._rpc_settings['port'])
                except Exception:
                    # An occupied API port must not prevent normal wallet use.
                    self._rpc_error = 'RPC listener could not start'
            self._mining_guard_task = asyncio.create_task(self._monitor_mining(), name='sumuww-mining-guard')
            self._persist_network(self._settings, self._public_contact)
            with self._control:
                if self._state == 'starting':
                    self._state = 'running'
            _finish(self._start_future, self._status())
            self._wake.set()
            while True:
                await self._wake.wait()
                self._wake.clear()
                while True:
                    try:
                        operation, future, arguments = self._inbox.get_nowait()
                    except queue.Empty:
                        break
                    if operation == 'stop':
                        return
                    if not future.set_running_or_notify_cancel():
                        if operation == 'mine':
                            with self._control:
                                self._mining_reserved = False
                        arguments = None
                        continue
                    if self._state == 'stopping':
                        _finish(future, error=AppServiceError('Service is stopping'))
                        if operation == 'mine':
                            with self._control:
                                self._mining_reserved = False
                    elif operation == 'mine':
                        self._mining_task = asyncio.create_task(self._mine(future), name='sumuww-app-mine')
                    else:
                        try:
                            _finish(future, await self._execute(operation, arguments))
                        except Exception as error:
                            _finish(future, error=_safe_error(error))
                    arguments = None
        finally:
            self._request_mining_stop('shutdown')
            self._payment_quote = None
            if self._mining_guard_task is not None:
                self._mining_guard_task.cancel()
                await asyncio.gather(self._mining_guard_task, return_exceptions=True)
            if self._mining_task is not None:
                try:
                    await self._mining_task
                except BaseException as error:
                    self._shutdown_error = _safe_error(error)
            await self._close_mining_session()
            self._key = None
            if self._rpc is not None:
                try:
                    await self._rpc.stop()
                except BaseException as error:
                    self._shutdown_error = _safe_error(error)
                finally:
                    self._rpc = None
            if self._node is not None:
                try:
                    await self._node.stop()
                except BaseException as error:
                    self._shutdown_error = _safe_error(error)
                    # Peer cleanup can fail while reading damaged persisted
                    # state. Release its connection in the owning actor too.
                    try:
                        self._node.chain.close()
                    except Exception:
                        pass

    async def _mine(self, future):
        value = None
        error = None
        try:
            if self._script is None:
                raise AppServiceError('Select a wallet before mining')
            if self.network.name == 'dora' and not self._node.synchronization_info()['mining_ready']:
                raise AppServiceError('Connect and synchronize with a peer before SUMUWW mining')
            hardware_mining.require_unlocked(self._hardware_settings['mode'], self._node.chain._row(self._node.chain.tip_hash)[2])
            self._mining_session.hardware_settings = dict(self._hardware_settings)
            script = self._script
            digest = None
            interruption = _MiningInterruption(self._mining_cancel, self._mining_pause)
            while not self._mining_cancel.is_set():
                while (self.network.name == 'dora' and not self._mining_cancel.is_set()
                       and not self._node.synchronization_info()['mining_ready']):
                    self._mining_state = 'waiting'
                    if self._mining_wait_started is None:
                        self._mining_wait_started = time.monotonic()
                    await asyncio.sleep(.1)
                if self._mining_cancel.is_set():
                    break
                # Only the actor clears a pause, after the previous worker has
                # fully returned and a fresh readiness check succeeds.
                self._finish_mining_wait()
                self._mining_pause.clear()
                self._mining_state = 'running'
                pending=self._boundary_pending
                if pending is not None and (pending['parent']!=self._node.chain.tip_hash
                        or pending['script']!=script or pending['settings']!=self._hardware_settings
                        or pending['cancel'].is_set()):
                    await self._discard_boundary_pending();pending=None
                if pending is not None:
                    digest=await self._boundary_result(pending['future'],pending['parent'])
                    if digest is None:await self._discard_boundary_pending()
                    else:self._boundary_pending=None
                else:
                    runtime=self._node.boundary_runtime
                    digest=runtime.pending_candidate() if runtime is not None else None
                    if digest is not None and not any(output.script_pubkey==script for output in digest.transactions[0].outputs):
                        raise AppServiceError('Resume the wallet used for the pending signed mining candidate')
                    if digest is None:
                        digest = await asyncio.get_running_loop().run_in_executor(
                            self._mining_executor, self._mining_session.run,
                            self.database, self.network, script, interruption)
                from .block import Block
                if isinstance(digest,Block):
                    block=digest;digest=None;parent=block.header.previous_hash
                    if self._node.chain.tip_hash!=parent:continue
                    if not self._node.chain.boundary.required(self._node.chain._row(parent)[2]+1,parent):
                        # A staged next header can be an ordinary PoW block.
                        # Accept the original winner without a signing RPC.
                        if not self._mining_cancel.is_set() and self._node.chain.accept_block(block):
                            digest=block.block_hash()
                        if digest is not None:break
                        if interruption.is_set():continue
                        raise AppServiceError('Ordinary staged block was not accepted')
                    cancel=threading.Event()
                    self._boundary_pending={'parent':block.block_hash(),'script':script,
                        'settings':dict(self._hardware_settings),'cancel':cancel,
                        'future':asyncio.get_running_loop().run_in_executor(self._mining_executor,
                            self._mining_session.run_staged,script,block,
                            _MiningInterruption(cancel,self._mining_pause))}
                    runtime=self._node.boundary_runtime
                    if runtime is None:raise AppServiceError('Boundary signing runtime unavailable')
                    proof=await self._boundary_result(runtime.complete(block),parent)
                    if proof is not None and not self._mining_cancel.is_set():
                        if self._node.chain.accept_block(block,boundary_envelope=proof):
                            digest=block.block_hash()
                    if digest is None:
                        await self._discard_boundary_pending()
                        if not interruption.is_set():continue
                if digest is not None:
                    break
                if self._mining_cancel.is_set():
                    break
                if self._mining_pause.is_set():
                    self._mining_network_pauses += 1
                    self._mining_state = 'waiting'
                    continue
                raise AppServiceError('Mining ended without an accepted block')
            value = {'node': self._node.info(include_state=False), 'cancelled': digest is None,
                     'cancel_reason': self._mining_cancel_reason if digest is None else None,
                     'network_pauses': self._mining_network_pauses,
                      'network_wait_seconds': self._mining_wait_seconds +
                          (time.monotonic() - self._mining_wait_started if self._mining_wait_started is not None else 0.0)}
            if digest is not None:
                value['block_hash'] = hash_to_display(digest)
        except RuntimeError as caught:
            if self._mining_cancel.is_set():
                value = {'node': self._node.info(include_state=False), 'cancelled': True,
                         'cancel_reason': self._mining_cancel_reason,
                         'network_pauses': self._mining_network_pauses,
                      'network_wait_seconds': self._mining_wait_seconds +
                          (time.monotonic() - self._mining_wait_started if self._mining_wait_started is not None else 0.0)}
            else:
                error = _safe_error(caught)
        except Exception as caught:
            error = _safe_error(caught)
        finally:
            self._finish_mining_wait()
            with self._control:
                self._mining_reserved = False
                self._mining_state = 'idle'
            _finish(future, value, error)

    def _finish_mining_wait(self):
        if self._mining_wait_started is not None:
            self._mining_wait_seconds += time.monotonic() - self._mining_wait_started
            self._mining_wait_started = None

    async def _monitor_mining(self):
        while True:
            if (self.network.name == 'dora' and self._mining_reserved
                    and not self._node.synchronization_info()['mining_ready']):
                self._mining_pause.set()
                if not self._mining_cancel.is_set():
                    self._mining_state = 'waiting'
            await asyncio.sleep(.1)

    def _path(self, value):
        path = Path(value).expanduser()
        return path.absolute() if path.is_absolute() else (self.directory / path).absolute()

    @staticmethod
    def _same_path(left, right):
        return same_path(left, right)

    def _guard_paths(self, *paths, destination=None):
        reserved = reserved_node_paths(self.database, bootstrap_manifest=self._bootstrap_manifest)
        for index, path in enumerate(paths):
            if (is_managed_privacy_path(path, self.database)
                    or any(self._same_path(path, item) for item in reserved)):
                raise AppServiceError('Wallet and backup paths must differ from the node database and its sidecars')
            if any(self._same_path(path, other) for other in paths[index + 1:]):
                raise AppServiceError('Wallet source and destination paths must differ')
        if destination is not None:
            if self._wallet_path is not None and self._same_path(destination, self._wallet_path):
                raise AppServiceError('Destination must differ from the selected wallet')
            if os.path.lexists(destination):
                raise AppServiceError('Destination already exists; choose a new path')

    def _public_wallet(self):
        return {'address': self._address, 'path': str(self._wallet_path),
                'unlocked': self._key is not None, 'kind': self._wallet_kind}

    def _select_wallet(self, key, path):
        self._payment_quote = None
        self._key, self._wallet_path = key, path
        self._wallet_kind = 'hd' if key.is_hd else 'single_key'
        self._address, self._script = key.address, key.script_pubkey
        self._history = WalletHistory(self._script)
        return self._public_wallet()

    async def _execute(self, operation, arguments):
        if operation == 'status':
            return self._status()
        if operation == 'mining_hardware':
            if self._mining_reserved:
                raise AppServiceError('Stop mining before changing the device')
            settings = hardware_mining.validate_settings(*arguments)
            hardware_mining.require_unlocked(settings['mode'], self._node.chain._row(self._node.chain.tip_hash)[2])
            hardware_mining.save_settings(self.directory, settings)
            self._hardware_settings = settings
            return hardware_mining.public_settings(settings, self._node.chain._row(self._node.chain.tip_hash)[2])
        if operation == 'block_history':
            from .block_history import block_history
            runtime = self._node.boundary_runtime
            own_id = runtime.keys.node_id if runtime else None
            return await asyncio.to_thread(block_history, self.database, *arguments, own_id)
        if operation == 'transaction_history':
            if self._address is None:
                raise AppServiceError('Select a wallet before reading transaction history')
            result = self._history.page(self._node.chain, *arguments)
            result['address'] = self._address
            return result
        if operation == 'lock':
            await self._halt_wallet_mining()
            self._payment_quote = None
            self._key = None
            return self._public_wallet() if self._address is not None else None
        if operation in ('create', 'open', 'create_seed', 'recover_seed'):
            await self._halt_wallet_mining()
            self._payment_quote = None
            path, password = self._path(arguments[0]), arguments[1]
            self._guard_paths(path, destination=path if operation != 'open' else None)
            if operation == 'recover_seed':
                key = recover_hd_wallet(path, password, arguments[2], network=self.network)
            else:
                loader = {'create': keystore_create, 'open': keystore_load,
                          'create_seed': create_hd_wallet}[operation]
                key = loader(path, password, network=self.network)
            return self._select_wallet(key, path)
        if operation == 'recovery_phrase':
            if self._wallet_path is None or self._wallet_kind != 'hd':
                raise AppServiceError('Select a seed wallet to view its recovery phrase')
            self._guard_paths(self._wallet_path)
            password = arguments[0]
            return export_mnemonic(self._wallet_path, password, network=self.network,
                                   expected_script=self._script)
        if operation == 'restore':
            await self._halt_wallet_mining()
            self._payment_quote = None
            source, destination, password = self._path(arguments[0]), self._path(arguments[1]), arguments[2]
            self._guard_paths(source, destination, destination=destination)
            return self._select_wallet(keystore_restore(source, destination, password, network=self.network), destination)
        if operation == 'backup':
            if self._wallet_path is None:
                raise AppServiceError('Select a wallet before backup')
            destination, password = self._path(arguments[0]), arguments[1]
            self._guard_paths(self._wallet_path, destination, destination=destination)
            keystore_backup(self._wallet_path, destination, password, network=self.network,
                            expected_script=self._script)
            return {'backup_path': str(destination)}
        if operation == 'send':
            quote = self._prepare_payment(*arguments)
            return self._submit_payment(quote['quote_id'])
        if operation == 'prepare_payment':
            return self._prepare_payment(*arguments)
        if operation == 'submit_payment':
            return self._submit_payment(*arguments)
        if operation == 'peer':
            host, port = endpoint(arguments[0], allow_zero=False, allow_lan=self.allow_lan,
                                  allow_internet=self.allow_internet)
            target = f'[{host}]:{port}' if ':' in host else f'{host}:{port}'
            settings = normalize_settings(self.listen,
                                          self._settings['peers'] + ([] if target in self._settings['peers'] else [target]),
                                          allow_lan=self.allow_lan, allow_internet=self.allow_internet)
            save_settings(self.directory, settings)
            await self._node.add_peer(host, port)
            self._settings = settings
            return {'host': host, 'port': port, 'registered': True}
        if operation == 'configure_network':
            return await self._configure_network(*arguments)
        if operation == 'configure_rpc':
            return await self._configure_rpc(*arguments)
        if operation == 'configure_privacy':
            return await self._configure_privacy(*arguments)
        raise AppServiceError('Unknown service command')

    def _prepare_payment(self, address, amount_string, fee_string):
        # Only this actor retains signed bytes. A second quote replaces the first.
        self._payment_quote = None
        if self._key is None:
            raise AppServiceError('Unlock a wallet before sending')
        script = decode_address(address, network=self.network)
        amount = parse_amount(amount_string)
        with self._node.chain.read_snapshot():
            if fee_string is None:
                estimate = estimate_payment_fee(self._node.chain, self._script, script, amount)
                fee = estimate['fee_units']
                source, capped = estimate['source'], estimate['capped']
                estimated_vsize = estimate['estimated_vsize']
            else:
                fee = parse_amount(fee_string)
                source, capped, estimated_vsize = 'manual', False, None
            transaction = create_payment(self._node.chain, self._key, script, amount, fee)
        quote_id = secrets.token_hex(16)
        self._payment_quote = {'id': quote_id, 'transaction': transaction,
                               'key': self._key, 'node': self._node,
                               'expires': _quote_clock() + PAYMENT_QUOTE_TTL,
                               'fee': fee}
        return {'quote_id': quote_id, 'amount_smw': format_amount(amount),
                'fee_smw': format_amount(fee), 'total_smw': format_amount(amount + fee),
                'estimated_vsize': estimated_vsize or (transaction.weight() + 3) // 4,
                'source': source, 'capped': capped}

    def _submit_payment(self, quote_id):
        quote = self._payment_quote
        # Consume before validation: rejected or expired quotes cannot be replayed.
        self._payment_quote = None
        if (quote is None or type(quote_id) is not str or quote['id'] != quote_id
                or self._key is None or quote['key'] is not self._key
                or quote['node'] is not self._node):
            raise AppServiceError('Payment quote is no longer valid; prepare again')
        if _quote_clock() >= quote['expires']:
            raise AppServiceError('Payment quote expired; prepare again')
        # The normal write-lock validation rejects a conflicting spend or reorg.
        digest = self._node.chain.submit_transaction(quote['transaction'])
        return {'txid': hash_to_display(digest), 'fee_smw': format_amount(quote['fee']),
                'status': 'local mempool'}

    @staticmethod
    def _requested_listener(value, automatic, *, allow_lan, allow_internet):
        # Automatic mode does not depend on the disabled manual listener field.
        # Keep a still-permitted request for a later manual selection; stale,
        # empty, or newly disallowed requests become a local-only placeholder.
        if automatic:
            try:
                host, port = endpoint(value, allow_lan=allow_lan,
                                      allow_internet=allow_internet, for_listen=True)
                return f'{host}:{port}'
            except (ValueError, TypeError, AttributeError):
                return '127.0.0.1:0'
        return value

    @staticmethod
    def _normalize_contact(value, settings, *, automatic=False):
        # Retain an advanced manual contact as an inactive preference while
        # automatic mode is selected. It is never advertised in that mode.
        target = public_contact(value, '0.0.0.0:18444' if automatic else settings['listen'],
                                allow_internet=True if automatic else settings['allow_internet'],
                                allow_lan=settings['allow_lan'])
        return f'{target[0]}:{target[1]}' if target is not None else ''

    def _persist_network(self, settings, contact, automatic=None):
        """A write failure restores all prior preference documents exactly.

        Individual publications are atomic; this is failure rollback, not a
        claim of filesystem-wide atomicity across power loss. Startup always
        validates the preference documents before constructing any listener.
        """
        automatic = self._auto_address if automatic is None else automatic
        if type(automatic) is not bool:
            raise ValueError('Automatic address mode must be a bool')
        paths = (self.directory / SETTINGS_NAME, self.directory / PUBLIC_CONTACT_NAME,
                 self.directory / OWN_ADDRESS_SETTINGS_NAME)
        prior = {}
        for path in paths:
            if path.exists():
                if path.stat().st_size > 16384:
                    raise ValueError('Connection settings file is too large')
                prior[path] = path.read_bytes()
            else:
                prior[path] = None
        try:
            save_settings(self.directory, settings)
            if contact or prior[paths[1]] is not None:
                _atomic_json(paths[1], {'schema_version': 1, 'endpoint': contact})
            _atomic_json(paths[2], {'schema_version': 1, 'automatic': automatic})
        except Exception:
            for path in paths:
                if (path.read_bytes() if path.exists() else None) != prior[path]:
                    _restore_preference(path, prior[path])
            raise

    def _make_node(self, settings, contact=None, auto_address=None):
        automatic = self._auto_address if auto_address is None else auto_address
        if type(automatic) is not bool:
            raise ValueError('Automatic address mode must be a bool')
        automatic_active = automatic and (settings['allow_internet'] or settings['allow_lan'])
        # Preserve the requested schema-1 listener. The runtime binding and
        # address-in-use fallback belong to PeerNode and are reported separately.
        effective_listen = '0.0.0.0:18444' if automatic_active else settings['listen']
        host, port = endpoint(effective_listen, allow_lan=settings['allow_lan'],
                              allow_internet=settings['allow_internet'], for_listen=True)
        peers = [endpoint(item, allow_zero=False, allow_lan=settings['allow_lan'],
                          allow_internet=settings['allow_internet']) for item in settings['peers']]
        if self._privacy_options['mode'] == 'i2p':
            peers = [peer for peer in peers if peer[0].endswith('.b32.i2p')]
        # Initial contacts are independent of saved manual peers. Existing empty
        # settings gain provider discovery without rewriting any preference or
        # overriding an explicit internet opt-out.
        sources = {}
        self._bootstrap_error = None
        if settings['allow_internet'] and (self.network.name == 'dora' or self._bootstrap_manifest is not None):
            try:
                config = load_bootstrap(self.network, path=self._bootstrap_manifest, scope=self._bootstrap_scope)
                sources = {'bootstrap_seeds': config.dns_seeds,
                           'bootstrap_peers': config.fallback_peers,
                           'bootstrap_scope': self._bootstrap_scope,
                           'discovery_scope': self._bootstrap_scope}
            except (OSError, ValueError, TypeError, UnicodeError):
                # A corrupt optional address source must not disable the user's
                # valid manual connections, chain, or wallet.
                self._bootstrap_error = 'Invalid initial discovery configuration'
        return PeerNode(self.database, host=host, port=port, peers=peers,
                        max_peers=None,
                        outgoing_target=None,
                        privacy=self._privacy_options,
                        privacy_router_factory=self._privacy_router_factory,
                        network_provider=self._network_provider,
                        network=self.network, allow_lan=settings['allow_lan'],
                        allow_internet=settings['allow_internet'],
                        auto_address=automatic_active,
                        **sources,
                        advertised_endpoint=None if automatic else public_contact(self._public_contact if contact is None else contact,
                            settings['listen'], allow_lan=settings['allow_lan'],
                            allow_internet=settings['allow_internet']))

    async def _configure_privacy(self, mode, port):
        with self._control:
            if self._mining_reserved:
                raise AppServiceError('Stop mining before changing privacy settings')
        new = privacy.settings(mode, port)
        old = self._privacy_options
        if new == old:
            return self._connection()
        self._payment_quote = None
        await self._node.stop()
        candidate = None
        try:
            self._privacy_options = new
            candidate = self._make_node(self._settings)
            await candidate.start()
            _atomic_json(self.directory / privacy.SETTINGS_NAME, new)
        except BaseException:
            if candidate is not None:
                await candidate.stop()
            self._privacy_options = old
            self._node = self._make_node(self._settings)
            await self._node.start()
            raise
        self._node = candidate
        return self._connection()

    async def _configure_network(self, listen, peers, allow_internet, allow_lan,
                                 advertise=None, auto_address=None):
        self._payment_quote = None
        with self._control:
            if self._mining_reserved:
                raise AppServiceError('Stop mining before changing connection settings')
        old = self._settings
        # Legacy callers explicitly supply a listener and therefore retain
        # their manual binding behavior. The GUI supplies its selected mode.
        new_automatic = False if auto_address is None else auto_address
        if type(new_automatic) is not bool:
            raise ValueError('Automatic address mode must be a bool')
        new = normalize_settings(self._requested_listener(listen, new_automatic,
                                  allow_lan=allow_lan, allow_internet=allow_internet),
                                  peers, allow_internet=allow_internet, allow_lan=allow_lan)
        old_automatic = self._auto_address
        new_contact = self._normalize_contact(self._public_contact if advertise is None else advertise,
                                              new, automatic=new_automatic)
        old_contact = self._public_contact
        if new == old and new_contact == old_contact and new_automatic == old_automatic:
            return self._status()
        await self._node.stop()
        candidate = None
        try:
            candidate = self._make_node(new, new_contact, auto_address=new_automatic)
            await candidate.start()
            self._persist_network(new, new_contact, new_automatic)
        except Exception:
            if candidate is not None:
                await candidate.stop()
            self._node = self._make_node(old, old_contact, auto_address=old_automatic)
            await self._node.start()
            raise
        self._node = candidate
        self._settings = new
        self._public_contact = new_contact
        self._auto_address = new_automatic
        self.listen, self.allow_internet, self.allow_lan = new['listen'], new['allow_internet'], new['allow_lan']
        return self._status()

    async def _make_rpc(self, port):
        token = load_or_create_token(self.directory / RPC_TOKEN_NAME)
        candidate = RpcServer(lambda: self._node, token, host='127.0.0.1', port=port)
        try:
            await candidate.start()
        except BaseException:
            await candidate.stop()
            raise
        return candidate

    async def _configure_rpc(self, enabled, port):
        new = _rpc_settings(enabled, port)
        if new == self._rpc_settings and ((self._rpc is not None) == enabled):
            return self._status()
        previous = self._rpc
        candidate = None
        try:
            if enabled:
                candidate = await self._make_rpc(port)
            _atomic_json(self.directory / RPC_SETTINGS_NAME, new)
        except BaseException:
            if candidate is not None:
                await candidate.stop()
            raise
        # Publish the candidate only after persistence has succeeded. Failed
        # reconfiguration leaves an existing listener and wallet intact.
        self._rpc, self._rpc_settings, self._rpc_error = candidate, new, None
        if previous is not None:
            await previous.stop()
        return self._status()

    def _rpc_status(self):
        address = self._rpc.address if self._rpc is not None else None
        return {'enabled': self._rpc is not None,
                'configured_enabled': self._rpc_settings['enabled'],
                'port': self._rpc_settings['port'],
                'active_port': address[1] if address else None,
                'endpoint': f'http://{address[0]}:{address[1]}/rpc' if address else None,
                'token_file': str(self.directory / RPC_TOKEN_NAME),
                'error': self._rpc_error}

    def _status(self):
        with self._node.chain.read_snapshot():
            node = self._node.info(include_state=False)
            mining = {'state': self._mining_state, 'reserved': self._mining_reserved,
                      'wait_reason': 'network' if self._mining_state == 'waiting' else None,
                      'network_pauses': self._mining_network_pauses,
                      'network_wait_seconds': self._mining_wait_seconds +
                          (time.monotonic() - self._mining_wait_started if self._mining_wait_started is not None else 0.0)}
            mining['hardware'] = hardware_mining.public_settings(self._hardware_settings, node['height'])
            if self._address is None:
                return {'node': node, 'wallet': None, 'connection': self._connection(node),
                        'rpc': self._rpc_status(), 'transactions': [], 'mining': mining}
            confirmed = dict(self._node.chain.list_utxos(self._script))
            pool = self._node.chain.mempool_transactions()
            spent = {(item.prev_txid, item.prev_index)
                     for transaction in pool for item in transaction.inputs}
            mature = {outpoint: coin for outpoint, coin in confirmed.items()
                      if not coin.coinbase or coinbase_is_mature(coin.height, node['height'] + 1)}
            total = sum(coin.output.value for coin in confirmed.values())
            spendable = sum(coin.output.value for coin in mature.values())
            available = sum(coin.output.value for outpoint, coin in mature.items() if outpoint not in spent)
            pending_outputs = {(transaction.txid(), index): output.value
                               for transaction in pool for index, output in enumerate(transaction.outputs)
                               if output.script_pubkey == self._script}
            inputs = {outpoint: coin.output.value for outpoint, coin in confirmed.items()}
            inputs.update(pending_outputs)
            # Signed net mempool change, including change and unconfirmed
            # parent/child spends; it is not an available-to-spend balance.
            pending = sum(pending_outputs.values()) - sum(inputs.get(outpoint, 0) for outpoint in spent)
            wallet = self._public_wallet()
            wallet.update({'total_smw': format_amount(total), 'spendable_smw': format_amount(spendable),
                           'available_smw': format_amount(available),
                           'pending_smw': ('-' if pending < 0 else '') + format_amount(abs(pending)),
                           'immature_smw': format_amount(total - spendable)})
            return {'node': node, 'wallet': wallet, 'connection': self._connection(node),
                    'rpc': self._rpc_status(), 'transactions': self._history.recent(self._node.chain),
                    'mining': mining}

    def _connection(self, node=None):
        snapshot = node if node is not None else (self._node.info(include_state=False) if self._node is not None else {})
        listener = snapshot.get('listen') or {}
        return {'listen': self.listen, 'peers': list(self._settings['peers']),
                'privacy': dict(self._privacy_options,
                                i2p_address=(snapshot.get('privacy') or {}).get('i2p_address'),
                                router=(snapshot.get('privacy') or {}).get('router'),
                                router_error=(snapshot.get('privacy') or {}).get('router_error')),
                'allow_internet': self.allow_internet, 'allow_lan': self.allow_lan,
                'public_contact': self._public_contact,
                'auto_address': self._auto_address,
                'effective_listen': ((f'[{listener["host"]}]:{listener["port"]}' if ':' in listener['host'] else
                                      f'{listener["host"]}:{listener["port"]}')
                                     if 'host' in listener and 'port' in listener else None),
                'own_addresses': list(snapshot.get('own_addresses') or []),
                'self_address': dict(snapshot.get('self_address') or {}),
                'bootstrap_error': self._bootstrap_error}
