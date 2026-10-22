"""Local mining-device policy. Not a consensus rule or hardware attestation."""
import ipaddress
import json
from pathlib import Path
from .network_settings import _atomic_json
from .wallet_paths import reject_wallet_overwrite

SETTINGS_NAME = 'mining-hardware.json'
UNLOCK_HEIGHTS = {'cpu': 0, 'gpu': 12_000, 'asic': 12_000}

def validate_settings(mode='cpu', host='127.0.0.1', port=3333, password=''):
    if mode not in UNLOCK_HEIGHTS:
        raise ValueError('Select CPU, GPU or ASIC')
    address = ipaddress.IPv4Address(host)
    if not (address.is_loopback or address.is_private or address.is_unspecified):
        raise ValueError('ASIC listener must use a local or LAN address')
    if type(port) is not int or not 1024 <= port <= 65535:
        raise ValueError('ASIC port must be between 1024 and 65535')
    if type(password) is not str or len(password) > 128:
        raise ValueError('Invalid ASIC connection password')
    if mode == 'asic' and len(password) < 16:
        raise ValueError('ASIC connection password must have at least 16 characters')
    return {'schema_version': 1, 'mode': mode, 'host': str(address), 'port': port, 'password': password}

def require_unlocked(mode, height):
    if mode not in UNLOCK_HEIGHTS or type(height) is not int or height < 0:
        raise ValueError('Invalid mining mode or verified height')
    if height < UNLOCK_HEIGHTS[mode]:
        raise ValueError(f'{mode.upper()} becomes available at chain height {UNLOCK_HEIGHTS[mode]:,}')

def load_settings(directory):
    p = Path(directory) / SETTINGS_NAME
    try:
        if p.stat().st_size > 4096:
            return validate_settings()
        v = json.loads(p.read_text(encoding='utf-8'))
        if set(v) != {'schema_version','mode','host','port','password'} or type(v['schema_version']) is not int or v['schema_version'] != 1:
            return validate_settings()
        return validate_settings(v['mode'], v['host'], v['port'], v['password'])
    except (OSError, ValueError, TypeError, UnicodeError, RecursionError):
        return validate_settings()

def save_settings(directory, settings):
    path = Path(directory) / SETTINGS_NAME
    reject_wallet_overwrite(path)
    _atomic_json(path, settings)

def public_settings(settings, height):
    return {'mode': settings['mode'], 'unlock_heights': dict(UNLOCK_HEIGHTS),
            'available_modes': [m for m,h in UNLOCK_HEIGHTS.items() if height >= h],
            'host': settings['host'], 'port': settings['port'],
            'asic_password_configured': bool(settings['password'])}

def create_backend(settings):
    if settings['mode'] == 'cpu':
        return None
    if settings['mode'] == 'gpu':
        from .opencl_mining import OpenCLMiner
        return OpenCLMiner()
    from .stratum_mining import StratumMiner
    return StratumMiner(settings['host'], settings['port'], settings['password'])
