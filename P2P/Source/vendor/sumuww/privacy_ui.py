"""Non-security UI preference: hide explanations, never skip confirmation."""
import json
import os
from pathlib import Path
import tempfile

from .i18n import preference_path
from .wallet_paths import reject_wallet_overwrite

MODES = ('direct', 'tor', 'i2p')


def help_path():
    return preference_path().with_name('privacy-help.json')


def load_hidden(path=None):
    path = Path(path) if path is not None else help_path()
    try:
        if path.is_symlink() or path.stat().st_size > 4096:
            return {}
        value = json.loads(path.read_text(encoding='utf-8'))
        if type(value) is dict and all(k in MODES and type(v) is bool for k, v in value.items()):
            return value
    except (OSError, ValueError):
        pass
    return {}


def save_hidden(mode, hidden, path=None):
    if mode not in MODES or type(hidden) is not bool:
        raise ValueError('Invalid privacy help preference')
    path = Path(path) if path is not None else help_path()
    reject_wallet_overwrite(path)
    if path.is_symlink():
        raise ValueError('Invalid privacy help preference path')
    values = load_hidden(path)
    values[mode] = hidden
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile('w', encoding='utf-8', dir=path.parent,
                                         prefix=path.name+'.', suffix='.tmp', delete=False) as out:
            temporary = Path(out.name)
            json.dump(values, out)
            out.write('\n'); out.flush(); os.fsync(out.fileno())
        reject_wallet_overwrite(path)
        if path.is_symlink():
            raise ValueError('Invalid privacy help preference path')
        os.replace(temporary, path)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()
