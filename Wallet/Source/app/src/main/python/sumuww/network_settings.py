"""Local connection preferences, independent of consensus and wallet keys."""

import json
import os
from pathlib import Path
import tempfile

from .peerd import endpoint
from .wallet_paths import reject_wallet_overwrite

SETTINGS_NAME = 'network-settings.json'
OWN_ADDRESS_SETTINGS_NAME = 'own-address-settings.json'
DEFAULT_PORT = 18444
# Compatibility constant only. Automatic bootstrap contacts come from the
# network-bound shipped manifest and are supplied to PeerNode separately.
# They never become user-saved manual peers or override an internet opt-out.
BOOTSTRAP_PEERS = []


def _state_directory():
    local = os.environ.get('LOCALAPPDATA')
    current = Path(local) / 'SUMUWW' if local else Path.home() / '.sumuww'
    legacy = Path(local) / 'DORA' if local else Path.home() / '.dora'
    # Never strand an already deployed SUMUWW chain behind a new empty folder.
    if (current / 'active-node.json').exists() or (current / 'data' / 'node.sqlite').exists(): return current
    if (legacy / 'active-node.json').exists() or (legacy / 'data' / 'node.sqlite').exists():
        return legacy
    return current


def default_directory():
    """Reuse the active chain; extracting an update must not reset it."""
    override = os.environ.get('SUMUWW_DATA_DIR') or os.environ.get('DORA_DATA_DIR')
    if override:
        return Path(override).expanduser().resolve()
    marker = _state_directory() / 'active-node.json'
    if marker.exists():
        if marker.stat().st_size > 4096:
            raise ValueError('Active node path file is too large')
        value = json.loads(marker.read_text(encoding='utf-8'))
        if not isinstance(value, dict) or set(value) != {'directory'} or not isinstance(value['directory'], str):
            raise ValueError('Invalid active node path file')
        return Path(value['directory']).expanduser().resolve()
    legacy = Path(__file__).resolve().parents[2] / 'DORA_APP_v0_12' / 'data' / 'local'
    if (legacy / 'node.sqlite').is_file():
        return legacy.resolve()
    return (_state_directory() / 'data').resolve()


def _atomic_json(path, value):
    path = Path(path)
    reject_wallet_overwrite(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile('w', encoding='utf-8', dir=path.parent,
                                         prefix=path.name + '.', suffix='.tmp', delete=False) as output:
            temporary = Path(output.name)
            json.dump(value, output, ensure_ascii=False, indent=2)
            output.write('\n')
            output.flush()
            os.fsync(output.fileno())
        reject_wallet_overwrite(path)
        os.replace(temporary, path)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def remember_directory(directory):
    _atomic_json(_state_directory() / 'active-node.json', {'directory': str(Path(directory).resolve())})


def normalize_settings(listen, peers, *, allow_internet=False, allow_lan=False):
    if type(allow_internet) is not bool or type(allow_lan) is not bool:
        raise ValueError('Connection permission flags must be bools')
    host, port = endpoint(listen, allow_lan=allow_lan, allow_internet=allow_internet, for_listen=True)
    if not isinstance(peers, (list, tuple)):
        raise ValueError('Configured peers must be a list')
    normalized = []
    for item in peers:
        peer_host, peer_port = endpoint(item, allow_zero=False, allow_lan=allow_lan,
                                        allow_internet=allow_internet)
        value = f'[{peer_host}]:{peer_port}' if ':' in peer_host else f'{peer_host}:{peer_port}'
        if value not in normalized:
            normalized.append(value)
    return {'schema_version': 1, 'listen': f'[{host}]:{port}' if ':' in host else f'{host}:{port}', 'peers': normalized,
            'allow_internet': allow_internet, 'allow_lan': allow_lan}


def load_settings(directory, *, bootstrap=False):
    """Reuse exact schema-1 user choices; fresh main UI opts into internet.

    The caller supplies network bootstrap contacts separately to PeerNode.
    Neither reading old preferences nor creating defaults copies shipped
    contacts into the manual peer list or changes a saved permission flag.
    """
    path = Path(directory) / SETTINGS_NAME
    if not path.exists():
        return normalize_settings('127.0.0.1:0', [],
                                  allow_internet=bootstrap)
    settings = json.loads(path.read_text(encoding='utf-8'))
    expected = {'schema_version', 'listen', 'peers', 'allow_internet', 'allow_lan'}
    if not isinstance(settings, dict) or set(settings) != expected or type(settings['schema_version']) is not int or settings['schema_version'] != 1:
        raise ValueError('Invalid connection settings file')
    return normalize_settings(settings['listen'], settings['peers'],
                              allow_internet=settings['allow_internet'], allow_lan=settings['allow_lan'])


def save_settings(directory, settings):
    normalized = normalize_settings(settings['listen'], settings['peers'],
                                    allow_internet=settings['allow_internet'], allow_lan=settings['allow_lan'])
    _atomic_json(Path(directory) / SETTINGS_NAME, normalized)


def load_auto_address(directory):
    """Return an explicit saved mode, or None for compatible default selection."""
    path = Path(directory) / OWN_ADDRESS_SETTINGS_NAME
    if not path.exists():
        return None
    if path.stat().st_size > 4096:
        raise ValueError('Automatic address settings are too large')

    def unique_fields(pairs):
        value = {}
        for key, item in pairs:
            if key in value:
                raise ValueError('Duplicate automatic address settings field')
            value[key] = item
        return value

    value = json.loads(path.read_text(encoding='utf-8'), object_pairs_hook=unique_fields)
    if (type(value) is not dict or set(value) != {'schema_version', 'automatic'}
            or type(value['schema_version']) is not int or value['schema_version'] != 1
            or type(value['automatic']) is not bool):
        raise ValueError('Invalid automatic address settings')
    return value['automatic']
