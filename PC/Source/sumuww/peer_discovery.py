"""Peer hints and a cache containing only successfully synced endpoints.

Hints never establish chain validity or mining readiness. This module does not
resolve names, scan addresses, or open sockets. Private fixture/LAN discovery
requires an explicit scope; the default rejects remotely supplied private IPs.
"""

from dataclasses import dataclass
import ipaddress
import json
import math
from pathlib import Path
import time

from .wallet_paths import reject_wallet_overwrite


STALE_RETRY_SUPPRESSION = 60
CACHE_MAX_AGE = 30 * 24 * 3600
_SPECIAL_PUBLIC = tuple(ipaddress.IPv4Network(value) for value in
                        ('0.0.0.0/8', '100.64.0.0/10', '169.254.0.0/16', '192.0.0.0/24',
                         '192.0.2.0/24', '192.88.99.0/24', '198.18.0.0/15',
                         '198.51.100.0/24', '203.0.113.0/24', '224.0.0.0/4', '240.0.0.0/4'))


def discovery_endpoint(host, port, *, scope='public', validator=None):
    if scope not in ('public', 'lan', 'loopback'):
        raise ValueError('Discovery scope must be public, lan, or loopback')
    if not isinstance(host, str) or type(port) is not int or not 1 <= port <= 65535:
        raise ValueError('Invalid discovered endpoint')
    host = host.lower()
    address = ipaddress.ip_address(host)
    if address.version == 6 and ("%" in host or address.ipv4_mapped is not None):
        raise ValueError("Scoped and mapped IPv6 hints are not supported")
    allowed = (address.is_global and not address.is_multicast and not address.is_reserved
               and not any(address in value for value in _SPECIAL_PUBLIC))
    if scope in ('lan', 'loopback'):
        allowed = allowed or any(address in ipaddress.IPv4Network(value) for value in
                                 ('10.0.0.0/8', '172.16.0.0/12', '192.168.0.0/16'))
        if address.version == 6:
            allowed = allowed or address in ipaddress.IPv6Network('fc00::/7')
    if scope == 'loopback':
        allowed = allowed or address.is_loopback
    if not allowed:
        raise ValueError('Discovered address is outside the explicit discovery scope')
    host = str(address)
    return validator(host, port) if validator is not None else (host, port)


@dataclass
class _Candidate:
    endpoint: tuple
    verified_at: float = 0
    retry_at: float = 0
    failures: int = 0
    attempted_at: float = 0


class PeerAddressBook:
    """Unverified failures expire; verified contacts survive temporary outages."""

    def __init__(self, path, network_id, genesis, *, scope='public', validator=None,
                 clock=time.time, retry_clock=time.monotonic):
        self.path = Path(path)
        self.network_id = network_id
        self.genesis = genesis.hex()
        self.scope = scope
        self.validator = validator
        self.clock = clock
        self.retry_clock = retry_clock
        self._entries = {}
        self._suppressed = {}
        self.expired = 0
        self.load_error = None
        self.write_error = None
        self._load()

    def validate(self, endpoint):
        if not isinstance(endpoint, (tuple, list)) or len(endpoint) != 2:
            raise ValueError('Discovered endpoint must have host and port')
        return discovery_endpoint(*endpoint, scope=self.scope, validator=self.validator)

    def add_hint(self, endpoint):
        target = self.validate(endpoint)
        now = self.retry_clock()
        self._suppressed = {key: until for key, until in self._suppressed.items() if until > now}
        if target in self._suppressed:
            return False
        if target in self._entries:
            return False
        self._entries[target] = _Candidate(target)
        return True

    def verified(self, endpoint):
        target = self.validate(endpoint)
        entry = self._entries.setdefault(target, _Candidate(target))
        self._suppressed.pop(target, None)
        entry.verified_at = self.clock()
        entry.failures = 0
        entry.attempted_at = self.retry_clock()
        entry.retry_at = entry.attempted_at + 10
        self._save()

    def attempted(self, endpoint, *, success=False):
        entry = self._entries.get(endpoint)
        if entry is not None:
            if success:
                entry.failures = 0
            else:
                entry.failures = min(entry.failures + 1, 10)
            if not success and (not entry.verified_at or self.clock()-entry.verified_at>CACHE_MAX_AGE):
                self._entries.pop(endpoint, None)
                self.prune()
                self._suppressed[endpoint] = self.retry_clock() + STALE_RETRY_SUPPRESSION
                self.expired += 1
                if entry.verified_at:self._save()
                return
            entry.attempted_at = self.retry_clock()
            entry.retry_at = entry.attempted_at + min(300, 5 * 2 ** entry.failures)

    def candidate(self, excluded=(), *, retry_cap=None):
        excluded = set(excluded)
        now = self.retry_clock()
        entries = [entry for key, entry in self._entries.items()
                   if key not in excluded and
                   (entry.retry_at if retry_cap is None else
                    min(entry.retry_at, entry.attempted_at + retry_cap)) <= now]
        entries.sort(key=lambda entry: (entry.failures, -entry.verified_at))
        return entries[0].endpoint if entries else None

    def prune(self):
        now=self.retry_clock()
        self._suppressed={key:until for key,until in self._suppressed.items() if until>now}
        stale=[key for key,value in self._entries.items()
               if value.verified_at and self.clock()-value.verified_at>CACHE_MAX_AGE]
        for key in stale:
            self._entries.pop(key,None)
            self.expired+=1
        if stale:self._save()

    def known(self, maximum=32):
        entries = sorted((entry for entry in self._entries.values() if entry.verified_at),
                         key=lambda entry: -entry.verified_at)
        return tuple(entry.endpoint for entry in entries[:maximum])

    def info(self):
        return {'candidates': len(self._entries),
                'verified': sum(bool(value.verified_at) for value in self._entries.values()),
                'maximum': None, 'scope': self.scope,
                'expired': self.expired, 'suppressed': sum(until > self.retry_clock() for until in self._suppressed.values()),
                'cache_read_error': self.load_error, 'cache_write_error': self.write_error}

    def _load(self):
        try:
            if not self.path.exists():
                return
            if self.path.is_symlink():
                raise ValueError('Peer cache must not be a link')
            data = json.loads(self.path.read_text(encoding='utf-8'))
            if (not isinstance(data, dict) or set(data) != {'version', 'network', 'genesis', 'peers'}
                    or type(data['version']) is not int or data['version'] != 1
                    or data['network'] != self.network_id or data['genesis'] != self.genesis
                    or not isinstance(data['peers'], list)):
                raise ValueError('Invalid or foreign peer cache')
            entries = {}
            for value in data['peers']:
                if not isinstance(value, dict) or set(value) != {'host', 'port', 'last_success'}:
                    raise ValueError('Invalid peer cache entry')
                target = self.validate((value['host'], value['port']))
                when = value['last_success']
                if type(when) not in (float, int) or not math.isfinite(when) or when <= 0:
                    raise ValueError('Invalid peer cache timestamp')
                if target in entries:
                    raise ValueError('Duplicate peer cache entry')
                if self.clock() - when > CACHE_MAX_AGE:
                    self.expired += 1
                    continue
                entries[target] = _Candidate(target, min(when, self.clock()))
            self._entries = entries
        except (OSError, UnicodeError, ValueError, TypeError) as error:
            self.load_error = type(error).__name__
            self._entries.clear()

    def _save(self):
        try:
            if self.path.is_symlink():
                raise ValueError('Peer cache must not be a symbolic link')
            reject_wallet_overwrite(self.path)
            data = {'version': 1, 'network': self.network_id, 'genesis': self.genesis,
                    'peers': [{'host': host, 'port': port,
                               'last_success': self._entries[(host, port)].verified_at}
                              for host, port in self.known(None)]}
            raw = json.dumps(data, sort_keys=True, separators=(',', ':')).encode('utf-8')
            temporary = self.path.with_name(self.path.name + '.tmp')
            if temporary.is_symlink():
                raise ValueError('Temporary peer cache must not be a symbolic link')
            reject_wallet_overwrite(temporary)
            temporary.write_bytes(raw)
            reject_wallet_overwrite(self.path)
            temporary.replace(self.path)
            self.write_error = None
        except (OSError, ValueError) as error:
            self.write_error = type(error).__name__
