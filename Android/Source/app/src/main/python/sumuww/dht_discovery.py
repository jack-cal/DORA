"""Bounded BEP5/BEP43 contact discovery; UDP hints have no chain authority.

The generic DHT routers below are documented by libtorrent. They are not SUMUWW
nodes. A SUMUWW-specific rendezvous key separates contact lookup from other
applications. Only a runtime public listening contact can be announced; no
operator address is bundled. Read-only DHT clients do not serve unsolicited
queries or act as a public routing/peer-storage server.
"""
from __future__ import annotations

import asyncio
from collections import Counter
import hashlib
import ipaddress
import math
import secrets
import socket
import time

from .bootstrap import _resolve_name, seed_endpoint
from .peer_discovery import discovery_endpoint
from .profiles import get_network


DEFAULT_ROUTERS = (('dht.libtorrent.org', 25401), ('dht.transmissionbt.com', 6881))
MAX_PACKET_BYTES = 8192
MAX_STRING_BYTES = 4096
MAX_DEPTH = 8
MAX_ITEMS = 256
MAX_NODES = 128
MAX_QUERIES = 48
MAX_HINTS = 128
MAX_CONCURRENT = 3
MAX_ANNOUNCEMENTS = 8
MAX_ROUTER_ADDRESSES = 8
ROUND_DEADLINE = 20
QUERY_TIMEOUT = 2
REFRESH_INTERVAL = 300
DISCONNECTED_RETRY_INTERVAL = 15
CONNECTION_POLL_INTERVAL = 1
MAX_DATAGRAMS_PER_SECOND = 100
MAX_RESERVED_REPLY_PACKETS = 4


def encode_bencode(value):
    """Encode canonical, bounded KRPC bytes without implicit object coercion."""
    items = 0
    def encode(item, depth):
        nonlocal items
        items += 1
        if items > MAX_ITEMS or depth > MAX_DEPTH:
            raise ValueError('Bencode nesting or item limit exceeded')
        if type(item) is int:
            if not -(1 << 63) <= item < (1 << 63):
                raise ValueError('Bencode integer exceeds signed 64-bit range')
            return b'i' + str(item).encode('ascii') + b'e'
        if type(item) is bytes:
            if len(item) > MAX_STRING_BYTES:
                raise ValueError('Bencode string exceeds limit')
            return str(len(item)).encode('ascii') + b':' + item
        if type(item) in (list, tuple):
            return b'l' + b''.join(encode(x, depth + 1) for x in item) + b'e'
        if type(item) is dict:
            if any(type(key) is not bytes for key in item):
                raise ValueError('Bencode dictionary keys must be bytes')
            return b'd' + b''.join(encode(key, depth + 1) + encode(item[key], depth + 1)
                                    for key in sorted(item)) + b'e'
        raise ValueError('Unsupported bencode value')
    result = encode(value, 0)
    if len(result) > MAX_PACKET_BYTES:
        raise ValueError('Bencode packet exceeds limit')
    return result


def decode_bencode(data, *, require_sorted_keys=True):
    """Decode bounded data; unordered unique keys are allowed only for KRPC input.

    Strict canonical decoding remains the default. Real routers can order KRPC
    dictionary keys differently; their unsigned contact hints do not depend on
    canonical serialization. Duplicate keys and every resource bound remain
    rejected in both modes.
    """
    if type(data) is not bytes or not 0 < len(data) <= MAX_PACKET_BYTES:
        raise ValueError('Invalid bencode packet size/type')
    position = 0
    items = 0
    def decode(depth):
        nonlocal position, items
        items += 1
        if items > MAX_ITEMS or depth > MAX_DEPTH or position >= len(data):
            raise ValueError('Invalid bencode nesting/items/truncation')
        kind = data[position]
        if kind == ord('i'):
            end = data.find(b'e', position + 1)
            if end < 0 or end - position > 21:
                raise ValueError('Invalid bencode integer')
            raw = data[position + 1:end]
            negative = raw.startswith(b'-')
            digits = raw[1:] if negative else raw
            if (not digits or any(x < 48 or x > 57 for x in digits)
                    or (len(digits) > 1 and digits.startswith(b'0')) or raw == b'-0'):
                raise ValueError('Noncanonical bencode integer')
            value = int(raw)
            if not -(1 << 63) <= value < (1 << 63):
                raise ValueError('Bencode integer exceeds signed 64-bit range')
            position = end + 1
            return value
        if kind in (ord('l'), ord('d')):
            position += 1
            result = [] if kind == ord('l') else {}
            previous = None
            while position < len(data) and data[position] != ord('e'):
                value = decode(depth + 1)
                if kind == ord('l'):
                    result.append(value)
                else:
                    if (type(value) is not bytes or value in result
                            or require_sorted_keys and previous is not None and value <= previous):
                        raise ValueError('Unsorted/duplicate/non-byte bencode dictionary key')
                    previous = value
                    result[value] = decode(depth + 1)
            if position >= len(data):
                raise ValueError('Truncated bencode container')
            position += 1
            return result
        if 48 <= kind <= 57:
            end = data.find(b':', position, min(len(data), position + 8))
            if end < 0:
                raise ValueError('Invalid bencode string length')
            raw = data[position:end]
            if (not raw or any(x < 48 or x > 57 for x in raw)
                    or (len(raw) > 1 and raw.startswith(b'0'))):
                raise ValueError('Noncanonical bencode string length')
            length = int(raw)
            if length > MAX_STRING_BYTES or end + 1 + length > len(data):
                raise ValueError('Oversized/truncated bencode string')
            position = end + 1 + length
            return data[end + 1:position]
        raise ValueError('Unknown bencode value')
    result = decode(0)
    if position != len(data):
        raise ValueError('Trailing bencode data')
    return result


def discovery_key(network):
    profile = get_network(network)
    return hashlib.sha256(b'DORA/MainlineDHT/contact/v1\x00' + profile.name.encode('ascii')
                          + b'\x00' + profile.profile_id.encode('ascii') + b'\x00'
                          + profile.genesis.block_hash()).digest()[:20]


def _scope_endpoint(host, port, scope):
    ipaddress.ip_address(host)
    return discovery_endpoint(host, port, scope=scope)


def _crc32c(data):
    value = 0xFFFFFFFF
    for byte in data:
        value ^= byte
        for _ in range(8):
            value = (value >> 1) ^ (0x82F63B78 if value & 1 else 0)
    return value ^ 0xFFFFFFFF


def make_node_id(host=None):
    """BEP42 prefix for the address family of the actual public source."""
    result = bytearray(secrets.token_bytes(20))
    if host is not None:
        address = ipaddress.ip_address(host)
        if address.is_global:
            random_byte = result[19]
            if address.version == 4:
                masked = (int(address) & 0x030F3FFF) | ((random_byte & 7) << 29)
                raw = masked.to_bytes(4, 'big')
            else:
                masked = ((int(address) >> 64) & 0x0103070F1F3F7FFF) | ((random_byte & 7) << 61)
                raw = masked.to_bytes(8, 'big')
            prefix = _crc32c(raw).to_bytes(4, 'big')
            result[0:2] = prefix[0:2]
            result[2] = (prefix[2] & 0xF8) | (result[2] & 7)
    return bytes(result)


class _Datagrams(asyncio.DatagramProtocol):
    def __init__(self, owner):
        self.owner = owner
        self.transport = None
    def connection_made(self, transport):
        self.transport = transport
    def datagram_received(self, data, address):
        self.owner._received(data, address)
    def error_received(self, error):
        self.owner._stats['socket_errors'] += 1
    def connection_lost(self, error):
        self.owner._transport_lost(self.transport, error)


class DhtDiscovery:
    def __init__(self, network, on_hints, *, contact_provider=None, self_endpoints=None, connected_provider=None,
                 settled_provider=None, family=socket.AF_INET, source_provider=None, network_provider=None,
                 routers=DEFAULT_ROUTERS, resolver=None, scope='public', clock=None,
                 interval=REFRESH_INTERVAL, query_timeout=QUERY_TIMEOUT, round_timeout=ROUND_DEADLINE):
        self.network = get_network(network)
        if family not in (socket.AF_INET, socket.AF_INET6):
            raise ValueError('DHT requires IPv4 or IPv6')
        if source_provider is not None and not callable(source_provider):
            raise ValueError('DHT source provider must be callable')
        if network_provider is not None and not callable(network_provider):
            raise ValueError('DHT network provider must be callable')
        self.family = family
        self.source_provider = source_provider or (lambda: None)
        self.network_provider = network_provider
        self._bound_host = None
        self._bound_network = None
        self._attempt_network = None
        self._transport_opened = False
        self._transport_interrupted = False
        if scope not in ('public', 'loopback') or (scope != 'public' and self.network.name == 'dora'):
            raise ValueError('DHT loopback scope is only an explicit non-main fixture')
        if not callable(on_hints):
            raise ValueError('DHT hints require a callback')
        if contact_provider is not None and not callable(contact_provider):
            raise ValueError('DHT contact provider must be callable')
        if self_endpoints is not None and not callable(self_endpoints):
            raise ValueError('DHT self endpoints must be callable')
        if connected_provider is not None and not callable(connected_provider):
            raise ValueError('DHT connected peer provider must be callable')
        if settled_provider is not None and not callable(settled_provider):
            raise ValueError('DHT settled peer provider must be callable')
        for name, value, maximum in (('interval', interval, 3600), ('query timeout', query_timeout, QUERY_TIMEOUT),
                                     ('round timeout', round_timeout, ROUND_DEADLINE)):
            if type(value) not in (int, float) or not math.isfinite(value) or not 0 < value <= maximum:
                raise ValueError('Invalid DHT ' + name)
        if interval < 60:
            raise ValueError('DHT interval must be at least 60 seconds')
        if not isinstance(routers, (tuple, list)) or not 1 <= len(routers) <= 8:
            raise ValueError('DHT requires one to eight generic router contacts')
        normalized = []
        for item in routers:
            if not isinstance(item, (tuple, list)) or len(item) != 2:
                raise ValueError('Invalid DHT router contact')
            host, port = item
            try:
                ipaddress.ip_address(host)
            except (ValueError, TypeError):
                target = seed_endpoint(host, port)
            else:
                target = _scope_endpoint(host, port, scope)
                if (':' in target[0]) != (family == socket.AF_INET6):
                    raise ValueError('DHT router address family mismatch')
            if target not in normalized:
                normalized.append(target)
        self.scope = scope
        self.routers = tuple(normalized)
        self.resolver = resolver or _resolve_name
        self.clock = clock or time.monotonic
        if not callable(self.resolver) or not callable(self.clock):
            raise ValueError('DHT resolver/clock must be callable')
        self.interval = float(interval)
        self.query_timeout = float(query_timeout)
        self.round_timeout = float(round_timeout)
        self.on_hints = on_hints
        self.contact_provider = contact_provider or (lambda: None)
        self.self_endpoints = self_endpoints or (lambda: ())
        self.connected_provider = connected_provider or (lambda: False)
        self.settled_provider = settled_provider or (lambda: False)
        self.key = discovery_key(self.network)
        self.node_id = make_node_id()
        self._node_ip = None
        self._transport = None
        self._task = None
        self._pending = {}
        self._reply_port_hints = {}
        self._reserved_reply_packets = {}
        self._round_lock = asyncio.Lock()
        self._closed = False
        self._active = False
        self.state = 'not_running'
        self.last_error = None
        self._receive_second = None
        self._receive_count = 0
        self._observed_ips = {}
        self._failed_rounds = 0
        self._next_query_at = 0
        self._last_lookup_result = None
        self._stats = {key: 0 for key in ('rounds', 'queries', 'responses', 'timeouts', 'router_errors',
                        'invalid_datagrams', 'uncorrelated_datagrams', 'rate_rejections', 'socket_errors',
                        'candidate_nodes', 'routing_replacements', 'accepted_hints', 'announce_attempts', 'announcements', 'round_errors',
                        'transport_restarts')}

    async def start(self):
        if self._closed:
            raise RuntimeError('Stopped DHT discovery cannot restart')
        if self._active:
            return self
        # A temporary absence of mobile connectivity must not permanently stop
        # discovery. The worker retries and notices a new default network.
        available = await self._ensure_transport()
        self._active = True
        if available:
            self.state = 'active'
        self._task = asyncio.create_task(self._run(), name='sumuww-dht-discovery')
        return self

    async def _ensure_transport(self):
        self._transport_interrupted = False
        network = None
        if self.network_provider is not None:
            try:
                network = self.network_provider()
                if network is not None and not isinstance(network, (str, int)):
                    raise ValueError('Invalid default network identity')
            except (OSError, RuntimeError, ValueError, TypeError):
                self.state, self.last_error = 'unavailable', 'Default network lookup unavailable'
                return False
            if network is None:
                self._attempt_network = None
                self._release_transport()
                self.state, self.last_error = 'unavailable', 'No active default network'
                return False
        self._attempt_network = network
        if self.family == socket.AF_INET:
            host = '127.0.0.1' if self.scope == 'loopback' else '0.0.0.0'
        elif self.scope == 'loopback':
            host = '::1'
        else:
            contact = self._contact()
            try:
                host = contact[0] if contact else self.source_provider()
                address = ipaddress.IPv6Address(host)
                if not address.is_global:
                    raise ValueError('No global IPv6 source')
                host = str(address)
            except (ValueError, TypeError, OSError, RuntimeError):
                self._release_transport()
                self.state, self.last_error = 'unavailable', 'No active global IPv6 source'
                return False
        if (self._transport is not None and not self._transport.is_closing()
                and self._bound_host == host and self._bound_network == network):
            return True
        try:
            transport, _ = await asyncio.get_running_loop().create_datagram_endpoint(
                lambda: _Datagrams(self), local_addr=(host, 0), family=self.family)
        except OSError:
            self.state, self.last_error = 'unavailable', 'UDP socket unavailable'
            return False
        previous, self._transport = self._transport, transport
        self._bound_network = network
        if self._transport_opened:
            self._stats['transport_restarts'] += 1
        self._transport_opened = True
        if previous is not None:
            previous.close()
        self._bound_host = host
        if self.family == socket.AF_INET6:
            self.node_id, self._node_ip = make_node_id(host), host
        self.state, self.last_error = 'active', None
        return True

    def _release_transport(self):
        previous, self._transport = self._transport, None
        self._bound_host = self._bound_network = None
        if previous is not None:
            previous.close()
        for _, future in tuple(self._pending.values()):
            if not future.done():
                future.set_result(None)

    def _transport_lost(self, transport, error):
        # A delayed callback from the old network must not erase its replacement.
        if self._transport is not transport:
            return
        self._release_transport()
        if self._active and not self._closed:
            self._transport_interrupted = True
            self.state, self.last_error = 'unavailable', 'DHT UDP transport closed'
            if error is not None:
                self._stats['socket_errors'] += 1

    async def stop(self):
        self._closed = True
        self._active = False
        if self._task is not None:
            self._task.cancel()
            await asyncio.gather(self._task, return_exceptions=True)
            self._task = None
        for _, future in tuple(self._pending.values()):
            future.cancel()
        self._pending.clear()
        self._reply_port_hints.clear()
        self._reserved_reply_packets.clear()
        if self._transport is not None:
            self._transport.close()
            self._transport = None
        self._bound_host = None
        self._observed_ips.clear()
        self._next_query_at = 0
        self._last_lookup_result = None
        self.state = 'not_running'

    def info(self):
        settled = self._active and self._search_settled()
        publication = self._active and self._contact() is not None
        return {'enabled': True, 'state': self.state, 'hint_only': True, 'read_only_dht': True,
                'address_family': 'ipv6' if self.family == socket.AF_INET6 else 'ipv4',
                'bound_source': self._bound_host,
                'generic_routers': len(self.routers), 'key': self.key.hex(),
                'pending_queries': len(self._pending), 'last_error': self.last_error,
                'round_in_progress': self._round_lock.locked(),
                'automatic_search_settled': settled,
                'public_contact_maintenance': publication,
                'maintenance_mode': ('not_running' if not self._active else
                    'public_contact_refresh' if publication else
                    'finish_round_then_idle' if settled and self._round_lock.locked() else
                    'settled_idle' if settled else 'search'),
                'last_lookup_result': self._last_lookup_result,
                'next_query_seconds': (max(0, math.ceil(self._next_query_at - self.clock()))
                                       if self._active and not (settled and not publication) else 0),
                'limits': {'packet_bytes': MAX_PACKET_BYTES, 'nodes': MAX_NODES, 'queries': MAX_QUERIES,
                           'concurrency': MAX_CONCURRENT, 'round_seconds': self.round_timeout,
                           'interval_seconds': self.interval, 'search_retry_seconds': DISCONNECTED_RETRY_INTERVAL,
                           'announcements': MAX_ANNOUNCEMENTS},
                'stats': dict(self._stats)}

    def _has_connected_peer(self):
        try:
            return bool(self.connected_provider())
        except (OSError, RuntimeError, ValueError, TypeError):
            return False

    def _search_settled(self):
        if not self._has_connected_peer():
            return False
        try:
            return bool(self.settled_provider())
        except (OSError, RuntimeError, ValueError, TypeError):
            return False

    async def _wait_for_next_query(self):
        # Compare with the socket's network, not a fresh sample: a handoff can
        # occur after the final reply but before this wait starts.
        network = self._attempt_network
        connected = self._has_connected_peer()
        settled = self._search_settled()
        self._next_query_at = self.clock() + (self.interval if settled else DISCONNECTED_RETRY_INTERVAL)
        while self._active:
            if self._transport_interrupted:
                self._next_query_at = self.clock()
                return
            if self.network_provider is not None:
                try:
                    if self.network_provider() != network:
                        self._next_query_at = self.clock()
                        return
                except (OSError, RuntimeError, ValueError, TypeError):
                    pass
            current = self._has_connected_peer()
            current_settled = self._search_settled()
            if current_settled and self._contact() is None:
                self._next_query_at = 0
                connected = current
                settled = current_settled
                await asyncio.sleep(CONNECTION_POLL_INTERVAL)
                continue
            if self._next_query_at == 0:
                return
            if connected and not current:
                self._next_query_at = self.clock()
                return
            if settled and not current_settled:
                self._next_query_at = self.clock()
                return
            if current_settled and not settled:
                self._next_query_at = self.clock() + self.interval
            connected = current
            settled = current_settled
            remaining = self._next_query_at - self.clock()
            if remaining <= 0:
                return
            await asyncio.sleep(min(CONNECTION_POLL_INTERVAL, remaining))

    def _contact(self):
        try:
            value = self.contact_provider()
            if not isinstance(value, (tuple, list)) or len(value) != 2:
                return None
            target = _scope_endpoint(*value, self.scope)
            return target if (':' in target[0]) == (self.family == socket.AF_INET6) else None
        except (ValueError, TypeError, OSError):
            return None

    def _received(self, data, address):
        # Ignore all unsolicited queries; ro=1 is sent in every outgoing query.
        if not self._active:
            return
        second = math.floor(self.clock())
        if second != self._receive_second:
            self._receive_second, self._receive_count = second, 0
        self._receive_count += 1
        if self._receive_count > MAX_DATAGRAMS_PER_SECOND:
            # One noisy router must not consume another pending reply's parser
            # allowance. Each of at most three live queries gets four bounded
            # extra packet attempts; the allowance ends with that query.
            reserved = next((transaction for transaction, (source, future) in self._pending.items()
                             if source == address[:2] and not future.done()
                             and self._reserved_reply_packets.get(transaction, 0) < MAX_RESERVED_REPLY_PACKETS), None)
            if reserved is None or type(data) is not bytes or not 0 < len(data) <= MAX_PACKET_BYTES:
                self._stats['rate_rejections'] += 1
                return
            self._reserved_reply_packets[reserved] = self._reserved_reply_packets.get(reserved, 0) + 1
        try:
            source = _scope_endpoint(address[0], address[1], self.scope)
            value = decode_bencode(data, require_sorted_keys=False)
            if type(value) is not dict or type(value.get(b't')) is not bytes or value.get(b'y') not in (b'r', b'e'):
                raise ValueError('Not a KRPC response')
            pending = self._pending.get(value[b't'])
            if pending is None or pending[1].done():
                self._stats['uncorrelated_datagrams'] += 1
                return
            if value[b'y'] == b'r':
                body = value.get(b'r')
                if type(body) is not dict or type(body.get(b'id')) is not bytes or len(body[b'id']) != 20:
                    raise ValueError('Invalid KRPC response ID')
            else:
                error = value.get(b'e')
                if type(error) is not list or len(error) != 2 or type(error[0]) is not int or type(error[1]) is not bytes:
                    raise ValueError('Invalid KRPC error')
            if pending[0] != source:
                # Some public routers reply from a different UDP port. Never
                # accept that reply or its peer values as the requested answer.
                # A matching unpredictable transaction from the same IP may
                # supply a bounded routing hint; query that port independently.
                if (pending[0][0] == source[0] and value[b'y'] == b'r'
                        and len(self._reply_port_hints) < MAX_ROUTER_ADDRESSES):
                    self._reply_port_hints[source] = value[b'r'][b'id']
                self._stats['uncorrelated_datagrams'] += 1
                return
            pending[1].set_result(value)
            self._stats['responses'] += 1
        except (ValueError, TypeError, IndexError, OverflowError):
            self._stats['invalid_datagrams'] += 1

    async def _query(self, endpoint, method, arguments):
        if not self._active or self._transport is None:
            raise OSError('DHT is not active')
        endpoint = _scope_endpoint(*endpoint, self.scope)
        if (':' in endpoint[0]) != (self.family == socket.AF_INET6):
            raise OSError('DHT query address family mismatch')
        if len(self._pending) >= MAX_CONCURRENT:
            raise OSError('DHT pending query capacity')
        transaction = secrets.token_bytes(8)
        while transaction in self._pending:
            transaction = secrets.token_bytes(8)
        future = asyncio.get_running_loop().create_future()
        self._pending[transaction] = (endpoint, future)
        self._reserved_reply_packets[transaction] = 0
        try:
            packet = encode_bencode({b't': transaction, b'y': b'q', b'q': method,
                                     b'a': {b'id': self.node_id, **arguments}, b'ro': 1})
            if len(packet) > 1024:
                raise OSError('DHT outgoing packet limit')
            destination = (*endpoint, 0, 0) if self.family == socket.AF_INET6 else endpoint
            self._transport.sendto(packet, destination)
            self._stats['queries'] += 1
            return await asyncio.wait_for(future, timeout=self.query_timeout)
        except TimeoutError:
            self._stats['timeouts'] += 1
            return None
        except OSError:
            self._stats['socket_errors'] += 1
            return None
        finally:
            self._pending.pop(transaction, None)
            self._reserved_reply_packets.pop(transaction, None)
            if not future.done():
                future.cancel()

    async def _router_addresses(self, router):
        host, port = router
        try:
            ipaddress.ip_address(host)
        except ValueError:
            try:
                records = await asyncio.wait_for(self.resolver(host, port), timeout=min(5, self.round_timeout))
            except (OSError, TimeoutError):
                self._stats['router_errors'] += 1
                return ()
            result = []
            if not isinstance(records, (tuple, list)):
                return ()
            for record in records[:64]:
                try:
                    if record[0] != self.family:
                        continue
                    endpoint = _scope_endpoint(record[4][0], port, self.scope)
                except (ValueError, TypeError, IndexError):
                    continue
                if endpoint not in result:
                    result.append(endpoint)
                if len(result) == MAX_ROUTER_ADDRESSES:
                    break
            return tuple(result)
        target = _scope_endpoint(host, port, self.scope)
        return (target,) if (':' in target[0]) == (self.family == socket.AF_INET6) else ()

    def _observe_ip(self, source, value):
        raw = value.get(b'ip')
        size = 16 if self.family == socket.AF_INET6 else 4
        if self.scope != 'public' or type(raw) is not bytes or len(raw) not in (size, size + 2):
            return
        try:
            host = _scope_endpoint(str(ipaddress.ip_address(raw[:size])), 1, 'public')[0]
        except ValueError:
            return
        # Independent source /16 groups vote only for lookup identity. These
        # claims never create a public TCP contact or authorize announcing one.
        source_ip = ipaddress.ip_address(source[0])
        group = (source_ip.version, int(source_ip) >> (96 if source_ip.version == 6 else 16))
        self._observed_ips[group] = host
        if len(self._observed_ips) > MAX_NODES:
            self._observed_ips.pop(next(iter(self._observed_ips)))
        winner = next((ip for ip, count in Counter(self._observed_ips.values()).items() if count >= 2), None)
        if winner is not None and self._contact() is None and self._node_ip != winner:
            self.node_id = make_node_id(winner)
            self._node_ip = winner

    def _parse_contacts(self, body):
        values = body.get(b'values', [])
        if not isinstance(values, list) or len(values) > MAX_HINTS:
            raise ValueError('Invalid DHT peer values')
        hints = []
        for raw in values:
            if type(raw) is not bytes or len(raw) not in (6, 18):
                raise ValueError('Invalid compact DHT peer')
            try:
                target = _scope_endpoint(str(ipaddress.ip_address(raw[:-2])), int.from_bytes(raw[-2:], 'big'), self.scope)
            except ValueError:
                continue
            if target not in hints:
                hints.append(target)
        nodes = []
        count = 0
        for key, size, family in ((b'nodes', 26, socket.AF_INET), (b'nodes6', 38, socket.AF_INET6)):
            raw_nodes = body.get(key, b'')
            if type(raw_nodes) is not bytes or len(raw_nodes) % size:
                raise ValueError('Invalid compact DHT nodes')
            count += len(raw_nodes) // size
            if count > MAX_NODES:
                raise ValueError('DHT node budget exceeded')
            if family != self.family:
                continue
            for offset in range(0, len(raw_nodes), size):
                node_id = raw_nodes[offset:offset + 20]
                try:
                    endpoint = _scope_endpoint(str(ipaddress.ip_address(raw_nodes[offset + 20:offset + size - 2])),
                                               int.from_bytes(raw_nodes[offset + size - 2:offset + size], 'big'), self.scope)
                except ValueError:
                    continue
                nodes.append((node_id, endpoint))
        token = body.get(b'token')
        if token is not None and (type(token) is not bytes or not 0 < len(token) <= 128):
            raise ValueError('Invalid DHT announcement token')
        return hints, nodes, token

    async def lookup_once(self):
        if not self._active:
            return ()
        async with self._round_lock:
            try:
                # _lookup enforces its own network deadline. Allow bounded
                # cancellation/cleanup time so its completed replies survive.
                return await asyncio.wait_for(self._lookup(), timeout=self.round_timeout + 1)
            except TimeoutError:
                self.last_error = 'DHT lookup deadline'
                self._last_lookup_result = 'deadline'
                self._stats['round_errors'] += 1
                return ()
            except (OSError, ValueError):
                self.last_error = 'DHT lookup unavailable'
                self._last_lookup_result = 'unavailable'
                self._stats['round_errors'] += 1
                return ()

    async def _batch(self, requests, deadline):
        """Keep completed replies when slow neighbors exhaust a phase budget."""
        tasks = [asyncio.create_task(self._query(*request)) for request in requests]
        result = [None] * len(tasks)
        try:
            remaining = max(0, deadline - asyncio.get_running_loop().time())
            done, _ = await asyncio.wait(tasks, timeout=remaining)
            for index, task in enumerate(tasks):
                if task in done and not task.cancelled():
                    try:
                        result[index] = task.result()
                    except (OSError, ValueError):
                        pass
        finally:
            for task in tasks:
                if not task.done():
                    task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
        return result

    def _retain_referral(self, frontier, visited, initial, node_id, target):
        """Keep closer unqueried routes within the existing total memory bound.

        Router bootstrap/fallback addresses keep their independent query slots.
        Referrals remain untrusted DHT routes, never validated SUMUWW peers.
        """
        if target in visited or target in frontier:
            return False
        if len(visited) + len(frontier) >= MAX_NODES:
            replaceable = [endpoint for endpoint in frontier if endpoint not in initial]
            if not replaceable:
                return False
            key = int.from_bytes(self.key, 'big')
            worst = max(replaceable, key=lambda endpoint: int.from_bytes(frontier[endpoint], 'big') ^ key)
            if (int.from_bytes(node_id, 'big') ^ key) >= (int.from_bytes(frontier[worst], 'big') ^ key):
                return False
            del frontier[worst]
            self._stats['routing_replacements'] += 1
        frontier[target] = node_id
        self._stats['candidate_nodes'] += 1
        return True

    async def _lookup(self):
        self._stats['rounds'] += 1
        self._reply_port_hints.clear()
        if not await self._ensure_transport():
            self._last_lookup_result = 'source_unavailable'
            return ()
        loop = asyncio.get_running_loop()
        started = loop.time()
        deadline = started + self.round_timeout
        # Publication gets real time as well as a query-count budget. A slow
        # node cannot prevent announcing already obtained legitimate tokens.
        contact = self._contact()
        lookup_deadline = started + self.round_timeout * (.6 if contact is not None else 1.0)
        if contact is not None and self._node_ip != contact[0]:
            self.node_id = make_node_id(contact[0])
            self._node_ip = contact[0]
        resolved = await asyncio.gather(*(self._router_addresses(router) for router in self.routers))
        frontier = {}
        for endpoints in resolved:
            for endpoint in endpoints:
                frontier.setdefault(endpoint, bytes(20))
        # Probe one initial address from every configured router before any
        # learned referrals. A dishonest close node ID must not monopolize
        # bootstrap work. Later batches reserve one slot for round-robin DNS
        # fallbacks; the remaining slots still walk nearest learned nodes.
        primary = []
        fallbacks = []
        initial = set()
        for offset in range(max((len(values) for values in resolved), default=0)):
            for values in resolved:
                if offset < len(values) and values[offset] not in initial:
                    target = values[offset]
                    initial.add(target)
                    (primary if offset == 0 else fallbacks).append(target)
        visited = set()
        hints = []
        tokens = {}
        query_count = 0
        responses = 0
        # The 48-query budget covers both lookup and publication. Reserve a
        # small publication budget when a real listening contact is available.
        lookup_budget = MAX_QUERIES - MAX_ANNOUNCEMENTS if contact is not None else MAX_QUERIES
        own = set(self.self_endpoints())
        if contact is not None:
            own.add(contact)
        while (frontier and query_count < lookup_budget and self._active
               and loop.time() < lookup_deadline):
            count = min(MAX_CONCURRENT, lookup_budget - query_count)
            candidates = []
            while primary and len(candidates) < count:
                endpoint = primary.pop(0)
                if endpoint in frontier:
                    candidates.append(endpoint)
            if fallbacks and len(candidates) < count:
                while fallbacks:
                    endpoint = fallbacks.pop(0)
                    if endpoint in frontier:
                        candidates.append(endpoint)
                        break
            learned = (endpoint for endpoint in frontier if endpoint not in initial and endpoint not in candidates)
            candidates.extend(sorted(learned, key=lambda endpoint: int.from_bytes(frontier[endpoint], 'big')
                                     ^ int.from_bytes(self.key, 'big'))[:count - len(candidates)])
            while fallbacks and len(candidates) < count:
                endpoint = fallbacks.pop(0)
                if endpoint in frontier and endpoint not in candidates:
                    candidates.append(endpoint)
            if not candidates:
                break
            for endpoint in candidates:
                frontier.pop(endpoint)
                visited.add(endpoint)
            query_count += len(candidates)
            arguments = {b'info_hash': self.key, b'want': [b'n6' if self.family == socket.AF_INET6 else b'n4']}
            replies = await self._batch([(endpoint, b'get_peers', arguments)
                                         for endpoint in candidates], lookup_deadline)
            new_hints = []
            for endpoint, value in zip(candidates, replies):
                if value is None:
                    continue
                self._observe_ip(endpoint, value)
                if value.get(b'y') != b'r':
                    continue
                body = value[b'r']
                try:
                    peer_values, nodes, token = self._parse_contacts(body)
                except ValueError:
                    self._stats['invalid_datagrams'] += 1
                    continue
                responses += 1
                if token is not None:
                    tokens[endpoint] = (body[b'id'], token)
                for target in peer_values:
                    if target not in own and target not in hints and len(hints) < MAX_HINTS:
                        hints.append(target)
                        new_hints.append(target)
                for node_id, target in nodes:
                    self._retain_referral(frontier, visited, initial, node_id, target)
            for target, node_id in tuple(self._reply_port_hints.items()):
                self._reply_port_hints.pop(target, None)
                self._retain_referral(frontier, visited, initial, node_id, target)
            # Do not withhold discovered contacts until slow later batches or
            # publication finish. These remain untrusted connection hints.
            if new_hints:
                self.on_hints(tuple(new_hints))
                self._stats['accepted_hints'] += len(new_hints)
        contact = self._contact()
        if contact is not None:
            nearest = sorted(tokens, key=lambda endpoint: int.from_bytes(tokens[endpoint][0], 'big')
                             ^ int.from_bytes(self.key, 'big'))[:min(MAX_ANNOUNCEMENTS, MAX_QUERIES - query_count)]
            for offset in range(0, len(nearest), MAX_CONCURRENT):
                if not self._active or loop.time() >= deadline:
                    break
                # A port change invalidates this round's previous contact. Use
                # the actual current selected TCP contact, never UDP's port.
                selected = self._contact()
                if selected is None or selected != contact:
                    break
                batch = nearest[offset:offset + MAX_CONCURRENT]
                self._stats['announce_attempts'] += len(batch)
                replies = await self._batch([(endpoint, b'announce_peer',
                                            {b'info_hash': self.key, b'token': tokens[endpoint][1],
                                             b'port': contact[1], b'implied_port': 0}) for endpoint in batch],
                                            deadline)
                self._stats['announcements'] += sum(reply is not None and reply.get(b'y') == b'r'
                                                   for reply in replies)
        self.last_error = None if responses else 'No DHT response'
        self._last_lookup_result = ('hints_received' if hints else
                                    'no_sumuww_contacts' if responses else 'no_router_reply')
        return tuple(hints)

    async def _run(self):
        while self._active:
            self._next_query_at = 0
            if self._search_settled() and self._contact() is None:
                await self._wait_for_next_query()
                continue
            before_hints = self._stats['accepted_hints']
            before_announcements = self._stats['announcements']
            try:
                await self.lookup_once()
            except asyncio.CancelledError:
                raise
            except Exception:
                self.last_error = 'DHT worker error'
                self._stats['round_errors'] += 1
            if self._active:
                useful = (self._stats['accepted_hints'] > before_hints
                          or self._stats['announcements'] > before_announcements)
                self._failed_rounds = 0 if useful else min(4, self._failed_rounds + 1)
                await self._wait_for_next_query()
