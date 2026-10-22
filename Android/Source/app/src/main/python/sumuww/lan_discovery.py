"""Opt-in, bounded local multicast hints; TCP validation remains authoritative.

No DNS, public addresses, chain state or key material is sent. A matching UDP
beacon supplies only its actual source IPv4 and a TCP listening port. That hint
must subsequently pass the ordinary network handshake and full block checks.
"""

import asyncio
import ipaddress
import socket
import struct
import time

from .profiles import get_network


GROUP = '239.255.68.79'
PORT = 18445
INTERVAL = 30
MAX_INTERFACES = 8
MAX_BEACON_BYTES = 119
MAX_TRACKED_SOURCES = 128
MAX_DATAGRAMS_PER_SECOND = 40
SOURCE_INTERVAL = 5
_PREFIX = b'DORALAN\x01'
_LAN = tuple(ipaddress.IPv4Network(value) for value in
             ('10.0.0.0/8', '172.16.0.0/12', '192.168.0.0/16'))


def lan_host(host):
    if not isinstance(host, str):
        raise ValueError('LAN discovery needs a numeric RFC1918 IPv4 address')
    address = ipaddress.IPv4Address(host)
    if not any(address in network for network in _LAN):
        raise ValueError('LAN discovery source is outside RFC1918')
    return str(address)


def encode_beacon(network, port, nonce):
    network = get_network(network)
    if type(port) is not int or not 1 <= port <= 65535:
        raise ValueError('LAN beacon needs an actual TCP listening port')
    if type(nonce) is not int or not 0 <= nonce <= 0xFFFFFFFFFFFFFFFF:
        raise ValueError('Invalid LAN discovery nonce')
    profile = network.profile_id.encode('utf-8')
    return (_PREFIX + network.message_magic + network.genesis.block_hash()
            + bytes([len(profile)]) + profile + struct.pack('<HQ', port, nonce))


def decode_beacon(payload, network):
    network = get_network(network)
    if not isinstance(payload, bytes) or not 55 <= len(payload) <= MAX_BEACON_BYTES:
        raise ValueError('Invalid LAN beacon size')
    if payload[:8] != _PREFIX or payload[8:12] != network.message_magic:
        raise ValueError('LAN beacon protocol or network mismatch')
    if payload[12:44] != network.genesis.block_hash():
        raise ValueError('LAN beacon genesis mismatch')
    count = payload[44]
    if not 1 <= count <= 64 or len(payload) != 55 + count:
        raise ValueError('Invalid LAN profile or trailing bytes')
    if payload[45:45 + count] != network.profile_id.encode('utf-8'):
        raise ValueError('LAN beacon profile mismatch')
    port, nonce = struct.unpack('<HQ', payload[45 + count:])
    if not port:
        raise ValueError('LAN beacon TCP port must be nonzero')
    return port, nonce


class LanDiscovery(asyncio.DatagramProtocol):
    def __init__(self, network, tcp_port, nonce, on_hint, interfaces, *, clock=time.monotonic):
        self.network = get_network(network)
        self.payload = encode_beacon(self.network, tcp_port, nonce)
        if not callable(on_hint) or not callable(clock):
            raise ValueError('LAN discovery requires a hint callback and clock')
        if not isinstance(interfaces, (tuple, list)):
            raise ValueError('LAN interface input must be a bounded sequence')
        selected = []
        for host in interfaces[:32]:
            try:
                host = lan_host(host)
            except ValueError:
                continue
            if host not in selected:
                selected.append(host)
            if len(selected) == MAX_INTERFACES:
                break
        self.interfaces = tuple(selected)
        self.nonce = nonce
        self.on_hint = on_hint
        self.clock = clock
        self.transport = None
        self._socket = None
        self._task = None
        self._sources = {}
        self._window = None
        self._window_count = 0
        self._stopped = False
        self.state = 'not_started'
        self.stats = {'datagrams_received': 0, 'beacons_sent': 0, 'hints_received': 0,
                      'rejected': 0, 'rate_limited': 0, 'socket_errors': 0}

    async def start(self):
        if self._stopped:
            raise RuntimeError('A stopped LAN discovery instance cannot restart')
        if self.transport is not None:
            return self
        if not self.interfaces:
            self.state = 'no_lan_interface'
            return self
        sock = None
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 1)
            sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_LOOP, 1)
            sock.bind(('0.0.0.0', PORT))
            joined = []
            for host in self.interfaces:
                try:
                    sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP,
                                    socket.inet_aton(GROUP) + socket.inet_aton(host))
                    joined.append(host)
                except OSError:
                    self.stats['socket_errors'] += 1
            if not joined:
                raise OSError('No permitted LAN interface could join multicast')
            self.interfaces = tuple(joined)
            sock.setblocking(False)
            self._socket = sock
            self.transport, _ = await asyncio.get_running_loop().create_datagram_endpoint(
                lambda: self, sock=sock)
            if self._stopped:
                self.transport.close()
                self.transport = None
                self._socket = None
                self.state = 'stopped'
                return self
        except OSError:
            if sock is not None:
                sock.close()
            self._socket = None
            self.state = 'unavailable'
            self.stats['socket_errors'] += 1
            return self
        except BaseException:
            if sock is not None:
                sock.close()
            self._socket = None
            raise
        self.state = 'active'
        self._task = asyncio.create_task(self._announce())
        return self

    def datagram_received(self, payload, address):
        if self._stopped:
            return
        self.stats['datagrams_received'] += 1
        now = self.clock()
        window = int(now)
        if window != self._window:
            self._window, self._window_count = window, 0
        self._window_count += 1
        if self._window_count > MAX_DATAGRAMS_PER_SECOND:
            self.stats['rate_limited'] += 1
            return
        try:
            if not isinstance(address, (tuple, list)) or len(address) < 2:
                raise ValueError('Invalid UDP source')
            host = lan_host(address[0])
            port, nonce = decode_beacon(payload, self.network)
            if nonce == self.nonce:
                raise ValueError('Self LAN beacon')
        except (ValueError, TypeError):
            self.stats['rejected'] += 1
            return
        previous = self._sources.get(host)
        if previous is not None and now - previous < SOURCE_INTERVAL:
            self.stats['rate_limited'] += 1
            return
        if host not in self._sources and len(self._sources) == MAX_TRACKED_SOURCES:
            self._sources.pop(next(iter(self._sources)))
        self._sources[host] = now
        try:
            self.on_hint((host, port))
        except (ValueError, OSError):
            self.stats['rejected'] += 1
            return
        self.stats['hints_received'] += 1

    def error_received(self, error):
        self.stats['socket_errors'] += 1

    async def _announce(self):
        while not self._stopped:
            for host in self.interfaces:
                try:
                    self._socket.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_IF,
                                            socket.inet_aton(host))
                    self.transport.sendto(self.payload, (GROUP, PORT))
                    self.stats['beacons_sent'] += 1
                except OSError:
                    self.stats['socket_errors'] += 1
            await asyncio.sleep(INTERVAL)

    async def stop(self):
        self._stopped = True
        if self._task is not None:
            self._task.cancel()
            await asyncio.gather(self._task, return_exceptions=True)
            self._task = None
        if self.transport is not None:
            self.transport.close()
            self.transport = None
            await asyncio.sleep(0)
        self._socket = None
        self._sources.clear()
        self.state = 'stopped'

    def info(self):
        return {'enabled': True, 'state': self.state, 'interface_count': len(self.interfaces),
                'hint_only': True, 'multicast_ttl': 1, 'interval_seconds': INTERVAL,
                'tracked_sources': len(self._sources), 'stats': dict(self.stats)}
