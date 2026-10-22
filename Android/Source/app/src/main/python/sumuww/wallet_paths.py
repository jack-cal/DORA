"""Shared reserved node paths for wallet and secret-file operations.

Path comparisons inspect names and file identity without reading contents. The
writer safeguard reads only a bounded encrypted envelope without passwords,
KDF or decryption. Ordinary wallet locations remain independent of the node.
"""

import json
import os
from pathlib import Path

from .node_policy import policy_filename


NODE_PREFERENCE_NAMES = (
    'network-settings.json', 'monitor-settings.json', 'public-contact.json',
    'own-address-settings.json', 'rpc-settings.json', 'rpc-token', 'ui-language.json', 'mining-hardware.json',
    'privacy-settings.json',
)
DATABASE_SUFFIXES = ('.link-keys.sqlite', '.link-keys.sqlite-wal', '.link-keys.sqlite-shm', '.link-keys.sqlite-journal', '', '-wal', '-shm', '-journal', '.peers.json', '.peers.json.tmp',
                    '.boundary-keys.sqlite', '.boundary-keys.sqlite-wal',
                    '.boundary-keys.sqlite-shm', '.boundary-keys.sqlite-journal')
_WALLET_FORMATS = ('sumuww-single-key-wallet', 'sumuww-hd-wallet',
                   'dora-single-key-wallet', 'dora-hd-wallet')
_MAX_WALLET_BYTES = 4096


def same_path(left, right):
    """Match normalized paths and existing hard-link/symlink aliases."""
    if os.path.normcase(str(Path(left).resolve())) == os.path.normcase(str(Path(right).resolve())):
        return True
    try:
        return os.path.samefile(left, right)
    except OSError:
        return False


def is_managed_privacy_path(path, database):
    """Router-owned state must never be a wallet, backup or secret-file path."""
    candidate = Path(path).absolute()
    directory = Path(database).absolute().parent / 'privacy'
    return (candidate.is_relative_to(directory)
            or candidate.resolve().is_relative_to(directory.resolve()))


def reserved_node_paths(database, *, bootstrap_manifest=None):
    """List node files and the Windows helper record without reading them."""
    database = Path(database).absolute()
    directory = database.resolve().parent
    policy = policy_filename(database.name)
    paths = [Path(str(database) + suffix) for suffix in DATABASE_SUFFIXES]
    paths.extend(directory / name for name in NODE_PREFERENCE_NAMES)
    paths.extend(directory / name for name in (policy, policy + '.tmp', policy + '.lock'))
    # The firewall helper uses the Windows profile, even when the node database
    # lives on another drive. same_path also protects existing link aliases.
    local_app_data = os.environ.get('LOCALAPPDATA')
    if local_app_data:
        paths.append(Path(local_app_data) / 'DORA' / 'public-firewall.json')
        paths.append(Path(local_app_data) / 'SUMUWW' / 'public-firewall.json')
    if bootstrap_manifest is not None:
        paths.append(Path(bootstrap_manifest))
    return tuple(paths)


def reject_wallet_overwrite(path):
    """Refuse replacing a recognizable encrypted wallet from an older CLI.

    Read only a bounded encrypted envelope. No password, KDF, decryption or key
    extraction is involved, and malformed ordinary settings remain repairable.
    """
    try:
        with Path(path).open('rb') as source:
            raw = source.read(_MAX_WALLET_BYTES + 1)
    except FileNotFoundError:
        return
    if not raw or len(raw) > _MAX_WALLET_BYTES:
        return
    try:
        value = json.loads(raw.decode('utf-8'))
    except (UnicodeError, ValueError, RecursionError):
        return
    if type(value) is dict and value.get('format') in _WALLET_FORMATS:
        raise ValueError('Node settings must not overwrite an encrypted wallet file')
