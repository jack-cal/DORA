"""Bounded, untrusted first-contact hints; never consensus or mining authority.

The shipped manifest may be empty. DNS providers and fixed contacts become
useful only when actual independent, reachable operators publish them.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
import ipaddress
import json
from pathlib import Path
import re
import socket
import sys
import threading

from .peer_discovery import discovery_endpoint
from .profiles import get_network


MAX_MANIFEST_BYTES = 64 * 1024
MAX_DNS_SEEDS = 8
MAX_SEED_ADDRESSES = 32
MAX_BOOTSTRAP_HINTS = 128
MAX_DNS_WORKERS = 8
DNS_DEADLINE = 5
MIN_QUERY_INTERVAL = 60
MAX_QUERY_INTERVAL = 300
_DNS_SLOTS = threading.BoundedSemaphore(MAX_DNS_WORKERS)
_LABEL = re.compile(r'[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\Z', re.ASCII)
_PRIVATE_SUFFIXES = ('localhost', 'local', 'localdomain', 'internal', 'lan', 'home.arpa', 'onion')


@dataclass(frozen=True)
class BootstrapConfig:
    dns_seeds: tuple = ()
    fallback_peers: tuple = ()


@dataclass(frozen=True)
class SeedResult:
    endpoints: tuple = ()
    error: str | None = None


def _scope(value):
    if value not in ('public', 'loopback'):
        raise ValueError('Bootstrap scope must be public or an explicit loopback fixture')
    return value


def seed_endpoint(host, port, *, scope='public'):
    """Validate a DNS provider name without resolving it or opening sockets."""
    _scope(scope)
    if not isinstance(host, str) or type(port) is not int or not 1 <= port <= 65535:
        raise ValueError('Invalid DNS seed endpoint')
    name = host[:-1] if host.endswith('.') else host
    name = name.lower()
    labels = name.split('.')
    if (len(name) > 253 or len(labels) < 2 or any(_LABEL.fullmatch(label) is None for label in labels)
            or re.fullmatch(r'[0-9.]+', name)
            or any(name == suffix or name.endswith('.' + suffix) for suffix in _PRIVATE_SUFFIXES)):
        raise ValueError('DNS seeds require a public multi-label DNS name')
    try:
        ipaddress.ip_address(name)
    except ValueError:
        return name, port
    raise ValueError('DNS seeds cannot be numeric IP addresses')


def normalize_seeds(values, *, scope='public'):
    _scope(scope)
    if not isinstance(values, (tuple, list)) or len(values) > MAX_DNS_SEEDS:
        raise ValueError('Use at most 8 DNS seed providers')
    result = []
    for value in values:
        if not isinstance(value, (tuple, list)) or len(value) != 2:
            raise ValueError('A DNS seed must contain host and port')
        target = seed_endpoint(*value, scope=scope)
        if target in result:
            raise ValueError('Duplicate DNS seed provider')
        result.append(target)
    return tuple(result)


def normalize_fallbacks(values, *, scope='public'):
    _scope(scope)
    if not isinstance(values, (tuple, list)) or len(values) > MAX_BOOTSTRAP_HINTS:
        raise ValueError('Use at most 128 numeric bootstrap contacts')
    result = []
    for value in values:
        if not isinstance(value, (tuple, list)) or len(value) != 2:
            raise ValueError('A bootstrap contact must contain host and port')
        target = discovery_endpoint(*value, scope=scope)
        if target in result:
            raise ValueError('Duplicate bootstrap contact')
        result.append(target)
    return tuple(result)


def manifest_path():
    base = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent.parent))
    return base / 'assets' / 'bootstrap-nodes.json'


def _unique_json_object(items):
    value = {}
    for key, entry in items:
        if key in value:
            raise ValueError('Duplicate bootstrap JSON key')
        value[key] = entry
    return value


def _manifest_entries(values):
    if not isinstance(values, list):
        raise ValueError('Bootstrap contacts must be lists')
    result = []
    for entry in values:
        if not isinstance(entry, dict) or set(entry) != {'host', 'port'}:
            raise ValueError('Bootstrap entries must contain only host and port')
        result.append((entry['host'], entry['port']))
    return result


def _legacy_entries(values):
    if not isinstance(values, list):
        raise ValueError('Legacy bootstrap contacts must be a list')
    result = []
    for value in values:
        if isinstance(value, str):
            fields = value.split(':')
            if len(fields) != 2 or re.fullmatch(r'[0-9]{1,5}', fields[1]) is None:
                raise ValueError('Legacy contact must be a numeric IPv4:port')
            result.append((fields[0], int(fields[1])))
        elif isinstance(value, dict) and set(value) == {'host', 'port'}:
            result.append((value['host'], value['port']))
        else:
            raise ValueError('Invalid legacy bootstrap contact')
    return result


def load_bootstrap(network='dora', *, path=None, scope='public'):
    """Load one strict manifest. Contacts are still unverified peer hints.

    An absent shipped manifest supplies no contacts. A malformed or foreign
    manifest raises ValueError so callers can keep manual node operation and
    report that first-contact configuration needs attention.
    """
    _scope(scope)
    profile = get_network(network)
    explicit = path is not None
    path = Path(path) if explicit else manifest_path()
    if not path.exists():
        if explicit:
            raise ValueError('The explicit bootstrap manifest does not exist')
        return BootstrapConfig()
    if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_MANIFEST_BYTES:
        raise ValueError('Bootstrap manifest is a link or exceeds 64 KiB')
    try:
        raw = path.read_bytes()
        if len(raw) > MAX_MANIFEST_BYTES:
            raise ValueError('Bootstrap manifest exceeds 64 KiB')
        value = json.loads(raw.decode('utf-8'), object_pairs_hook=_unique_json_object,
                           parse_constant=lambda _: (_ for _ in ()).throw(ValueError('Invalid JSON number')))
    except (UnicodeError, json.JSONDecodeError, RecursionError) as error:
        raise ValueError('Invalid bootstrap manifest encoding') from error
    if not isinstance(value, dict) or type(value.get('schema_version')) is not int:
        raise ValueError('Invalid bootstrap manifest schema')
    if value.get('network') != profile.name:
        raise ValueError('Bootstrap manifest network mismatch')
    if value['schema_version'] == 2:
        if set(value) != {'schema_version', 'network', 'genesis', 'dns_seeds', 'fallback_peers'}:
            raise ValueError('Unexpected bootstrap manifest fields')
        if value['genesis'] != profile.genesis.block_hash().hex():
            raise ValueError('Bootstrap manifest genesis mismatch')
        return BootstrapConfig(normalize_seeds(_manifest_entries(value['dns_seeds']), scope=scope),
                               normalize_fallbacks(_manifest_entries(value['fallback_peers']), scope=scope))
    if value['schema_version'] == 1:
        if set(value) not in ({'schema_version', 'network', 'peers'},
                              {'schema_version', 'network', 'genesis', 'peers'}):
            raise ValueError('Unexpected legacy bootstrap fields')
        if 'genesis' in value and value['genesis'] != profile.genesis.block_hash().hex():
            raise ValueError('Legacy bootstrap manifest genesis mismatch')
        return BootstrapConfig((), normalize_fallbacks(_legacy_entries(value['peers']), scope=scope))
    raise ValueError('Unsupported bootstrap manifest schema')


async def _resolve_name(host, port):
    """At most eight uncancellable OS lookups; timed-out jobs never block exit."""
    if not _DNS_SLOTS.acquire(blocking=False):
        raise OSError('resolver_capacity')
    loop = asyncio.get_running_loop()
    future = loop.create_future()

    def deliver(answers, error):
        if future.done():
            return
        if error is None:
            future.set_result(answers)
        else:
            future.set_exception(error)

    def worker():
        answers, error = None, None
        try:
            answers = socket.getaddrinfo(host, port, family=socket.AF_UNSPEC,
                                         type=socket.SOCK_STREAM, proto=socket.IPPROTO_TCP)
        except Exception:
            error = OSError('resolution_failed')
        finally:
            _DNS_SLOTS.release()
        try:
            loop.call_soon_threadsafe(deliver, answers, error)
        except RuntimeError:
            pass

    try:
        threading.Thread(target=worker, name='sumuww-bootstrap-dns', daemon=True).start()
    except Exception:
        _DNS_SLOTS.release()
        future.cancel()
        raise OSError('resolver_start_failed')
    return await future


async def lookup_seed(seed, *, scope='public', timeout=DNS_DEADLINE):
    """Return up to 32 checked numeric addresses under one <=5 second deadline."""
    import math
    if type(timeout) not in (float, int) or not math.isfinite(timeout) or not 0 < timeout <= DNS_DEADLINE:
        raise ValueError('DNS seed deadline must be finite, positive and at most 5 seconds')
    host, port = seed_endpoint(*seed, scope=scope)
    try:
        answers = await asyncio.wait_for(_resolve_name(host, port), timeout=timeout)
    except TimeoutError:
        return SeedResult(error='timeout')
    except OSError as error:
        return SeedResult(error=str(error) if str(error) == 'resolver_capacity' else 'resolution_failed')
    if not isinstance(answers, (tuple, list)):
        return SeedResult(error='invalid_resolution')
    result = []
    for answer in answers[:128]:
        try:
            family, kind, protocol, _, address = answer
            if family not in (socket.AF_INET, socket.AF_INET6) or kind != socket.SOCK_STREAM or protocol not in (0, socket.IPPROTO_TCP):
                continue
            target = discovery_endpoint(address[0], port, scope=scope)
        except (ValueError, TypeError, IndexError):
            continue
        if target not in result:
            result.append(target)
        if len(result) == MAX_SEED_ADDRESSES:
            break
    return SeedResult(tuple(result), None if result else 'no_permitted_addresses')
