"""Wallet-only UI facade over the unchanged SUMUWW validation/wallet service.

Only explicit, single-use quotes can be submitted. No mining command, key upload,
automatic payment retry, balance override or existing-app data migration exists.
"""
import base64
import ctypes
import json
import os
from pathlib import Path
import tempfile
import threading
import time

from sumuww.app_service import AppService, AppServiceError
from sumuww import keystore
from sumuww.address import AddressError, decode_address
from sumuww.errors import ValidationError
from sumuww.primitives import parse_amount

_service = None
_guard = threading.RLock()
_last_activity = 0.0
_timeout = 300
_foreground = False


def _publish_android(source, destination):
    library = ctypes.CDLL('libsumuww_platform.so')
    publish = library.sumuww_publish_no_replace
    publish.argtypes = [ctypes.c_char_p, ctypes.c_char_p]
    publish.restype = ctypes.c_int
    code = publish(os.fsencode(source), os.fsencode(destination))
    if code:
        raise OSError(code, os.strerror(code))


def _result(future):
    return future.result(timeout=60)


def start(directory, *, mobile=True, network='dora', bootstrap=True):
    global _service
    with _guard:
        if _service is None:
            if mobile:
                from mobile_interfaces import install
                install()
                keystore._publish_no_replace = _publish_android
            network_provider = None
            if mobile:
                from mobile_interfaces import network_identity
                network_provider = network_identity
            service = AppService(directory, network=network, bootstrap=bootstrap,
                                 allow_lan=True, allow_internet=True,
                                 **({'network_provider': network_provider} if mobile else {}))
            try:
                _result(service.start())
            except Exception:
                try:
                    _result(service.stop())
                except Exception:
                    _service = service
                raise
            _service = service
        return _status()


def _service_required():
    if _service is None:
        raise AppServiceError('Wallet service is not running')
    return _service


def _lock():
    if _service is not None:
        _result(_service.lock_wallet())
    return {}


def _expire():
    if not _foreground or time.monotonic() - _last_activity >= _timeout:
        _lock()


def _touch():
    global _last_activity
    _last_activity = time.monotonic()


def _status():
    _expire()
    service = _service_required()
    value = _result(service.status())
    value.pop('mining', None)
    value.pop('rpc', None)
    value['wallet_exists'] = (service.directory / 'wallet.json').exists()
    wallet = value.get('wallet')
    if wallet:
        wallet.pop('path', None)
    return value


def _dispatch(method, args):
    global _foreground, _timeout
    service = _service_required()
    if method == 'foreground':
        _foreground = args[0] == 'true'
        if not _foreground:
            _lock()
        return {}
    if method == 'status':
        return _status()
    if method == 'activity':
        _expire()
        _touch()
        return {}
    if method == 'lock':
        return _lock()
    if method == 'timeout':
        seconds = int(args[0])
        if seconds not in (60, 300, 900):
            raise AppServiceError('Invalid lock timeout')
        _timeout = seconds
        return {}
    if method == 'history':
        return _result(service.transaction_history(int(args[0]), 50))
    if method == 'peer':
        return _result(service.add_peer(args[0].strip()))
    if method == 'privacy':
        return _result(service.configure_privacy(args[0]))
    if method == 'parse_address':
        value = args[0].strip()
        # Accept an address or a plain SUMUWW URI; reject unfamiliar parameters.
        if value.lower().startswith('sumuww:'):
            value = value[7:]
        if '?' in value or '#' in value or '//' in value:
            raise AppServiceError('Use a SUMUWW address without URI parameters')
        decode_address(value, network=service.network)
        return {'address': value}
    if not _foreground:
        raise AppServiceError('Open the wallet app before continuing')
    _expire()
    if method in ('create', 'recover', 'restore'):
        if (service.directory / 'wallet.json').exists():
            raise AppServiceError('A wallet already exists; it will not be overwritten')
        password = args[0]
        if method == 'create':
            result = _result(service.create_seed_wallet('wallet.json', password))
        elif method == 'recover':
            result = _result(service.recover_seed_wallet('wallet.json', password, args[1]))
        else:
            raw = base64.b64decode(args[1], validate=True)
            if not 0 < len(raw) <= keystore.MAX_WALLET_BYTES:
                raise AppServiceError('Encrypted backup exceeds the supported size')
            with tempfile.TemporaryDirectory(dir=service.directory) as directory:
                path = Path(directory) / 'import.json'
                path.write_bytes(raw)
                result = _result(service.restore_wallet(path, 'wallet.json', password))
        _touch()
        return {'address': result['address']}
    if method == 'unlock':
        result = _result(service.open_wallet('wallet.json', args[0]))
        _touch()
        return {'address': result['address']}
    if method == 'backup':
        # Password authentication happens before any encrypted data leaves the app.
        with tempfile.TemporaryDirectory(dir=service.directory) as directory:
            path = Path(directory) / 'backup.json'
            keystore.backup_wallet(service.directory / 'wallet.json', path, args[0], network=service.network)
            raw = path.read_bytes()
            return {'encrypted': base64.b64encode(raw).decode('ascii')}
    if method == 'phrase':
        if not _result(service.status()).get('wallet'):
            _result(service.open_wallet('wallet.json', args[0]))
        result = _result(service.recovery_phrase(args[0]))
        _touch()
        return {'words': result}
    if method in ('prepare', 'submit'):
        state = _result(service.status())
        if not (state.get('wallet') or {}).get('unlocked'):
            raise AppServiceError('Unlock the wallet before sending')
        if method == 'prepare':
            address, amount, fee = args
            if parse_amount(amount) <= 0:
                raise AppServiceError('The amount must be greater than zero')
            _touch()
            return _result(service.prepare_payment(address.strip(), amount, fee or None))
        _touch()
        try:
            return {'outcome': 'accepted', **_result(service.submit_payment(args[0]))}
        except (AppServiceError, ValidationError) as error:
            return {'outcome': 'rejected', 'error': str(error)}
        except Exception:
            # An uncertain outcome must never trigger an automatic second spend.
            return {'outcome': 'unknown'}
    raise AppServiceError('Unsupported wallet command')


def call(method, *args):
    with _guard:
        try:
            result = _dispatch(method, args)
            return json.dumps({'ok': True, 'data': result}, ensure_ascii=False)
        except (AppServiceError, keystore.WalletError, AddressError, ValidationError, ValueError) as error:
            return json.dumps({'ok': False, 'error': str(error)}, ensure_ascii=False)
        except Exception:
            return json.dumps({'ok': False, 'error': 'Operation could not be completed. Check history before retrying a transfer.'})


def stop():
    global _service
    with _guard:
        if _service is not None:
            _result(_service.stop())
            _service = None
