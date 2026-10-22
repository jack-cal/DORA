"""Bounded Electrum 1.4 TLS transport and independently checked header chain.

Servers supply data, never keys or signing commands. Consistent responses do not
prove that an operator is honest, nor prove the absence of a hidden spend.
"""
import concurrent.futures
import ipaddress
import json
import socket
import ssl
import threading
import time
from urllib.parse import urlsplit
from .light_headers import HeaderChain, GENESIS, sha256d


# Replaceable public endpoints from Electrum's mainnet server directory.
# These are independent connection addresses, not guaranteed independent owners.
DEFAULT_SERVERS = (
    'ssl://electrum.blockstream.info:50002',
    'ssl://electrum.jhoenicke.de:50002',
    'ssl://blackie.c3-soft.com:57002',
)
MAX_FRAME = 8_100_000
# Bitcoin Core v31.0 mainnet minimum chainwork. This only sets a work floor;
# every header is still checked from genesis, with no assume-valid shortcut.
MINIMUM_MAINNET_WORK = int('0000000000000000000000000000000000000001128750f82f4c366153a3a030', 16)


def endpoint(value, network):
    parsed = urlsplit(value)
    if parsed.scheme not in ('ssl', 'tcp') or not parsed.hostname or parsed.username or parsed.password or parsed.path or parsed.query or parsed.fragment:
        raise ValueError('Use ssl://hostname:port for Bitcoin light servers.')
    if not parsed.port or not 0 < parsed.port < 65536:
        raise ValueError('Invalid Bitcoin light-server port.')
    host = parsed.hostname.lower().rstrip('.')
    if network == 'mainnet' and parsed.scheme != 'ssl':
        raise ValueError('Public Bitcoin light connections require verified TLS.')
    if parsed.scheme == 'tcp':
        try:
            if not ipaddress.ip_address(host).is_loopback:
                raise ValueError('Plaintext transport is only allowed on local test servers.')
        except ValueError:
            raise ValueError('Plaintext transport is only allowed on local test servers.') from None
    return parsed.scheme, host, parsed.port


class ElectrumPeer:
    def __init__(self, url, network='mainnet', timeout=12):
        self.url = url
        self.network = network
        self.scheme, self.host, self.port = endpoint(url, network)
        self.timeout = timeout
        self.lock = threading.RLock()
        self.socket = None
        self.stream = None
        self.serial = 0
        self.received = 0
        self.sent = 0
        self.address = None
        self.buffer = bytearray()

    def close(self):
        with self.lock:
            if self.stream:
                self.stream.close()
            if self.socket:
                self.socket.close()
            self.stream = self.socket = None
            self.buffer.clear()

    def _open(self):
        raw = socket.create_connection((self.host, self.port), timeout=self.timeout)
        try:
            if self.scheme == 'ssl':
                raw = ssl.create_default_context().wrap_socket(raw, server_hostname=self.host)
            self.socket = raw
            self.address = raw.getpeername()[0]
            version = self._request('server.version', ['SUMUWW-P2P-Light/0.3.0', '1.4'])
            if not isinstance(version, list) or len(version) != 2 or not str(version[1]).startswith('1.4'):
                raise ValueError('Bitcoin server does not support Electrum protocol 1.4.')
            features = self._request('server.features', [])
            if not isinstance(features,dict) or features.get('genesis_hash') != sha256d(GENESIS[self.network])[::-1].hex():
                raise ValueError('Wrong Bitcoin light-server network.')
        except BaseException:
            raw.close()
            self.close()
            raise

    def _request(self, method, params):
        self.serial += 1
        serial = self.serial
        packet = json.dumps({'jsonrpc': '2.0', 'id': serial, 'method': method, 'params': params}, separators=(',', ':')).encode() + b'\n'
        if len(packet) > MAX_FRAME:
            raise ValueError('Bitcoin request exceeds the size limit.')
        self.socket.sendall(packet)
        self.sent += len(packet)
        deadline = time.monotonic() + self.timeout
        for _ in range(128):
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise ValueError('Bitcoin light-server response deadline exceeded.')
            while b'\n' not in self.buffer:
                remaining = deadline - time.monotonic()
                if remaining <= 0:raise ValueError('Bitcoin light-server response deadline exceeded.')
                self.socket.settimeout(remaining)
                chunk = self.socket.recv(min(65536, MAX_FRAME + 1 - len(self.buffer)))
                if not chunk:raise ValueError('Bitcoin light server closed the connection.')
                self.received += len(chunk);self.buffer.extend(chunk)
                if len(self.buffer)>MAX_FRAME:raise ValueError('Oversized Bitcoin light-server response.')
            end=self.buffer.index(b'\n')+1;raw=bytes(self.buffer[:end]);del self.buffer[:end]
            value = json.loads(raw)
            if not isinstance(value, dict):
                raise ValueError('Invalid Bitcoin light-server message.')
            if value.get('id') is None:
                continue  # Notifications are not evidence for a payment decision.
            if value.get('id') != serial:
                raise ValueError('Mismatched Bitcoin response ID.')
            if value.get('error') is not None:
                # Do not surface untrusted remote HTML, URLs, or wallet instructions.
                raise ValueError('Bitcoin server could not supply the requested data.')
            if 'result' not in value:
                raise ValueError('Missing Bitcoin response result.')
            return value['result']
        raise ValueError('Too many Bitcoin server notifications.')

    def call(self, method, *params):
        with self.lock:
            try:
                if self.socket is None:
                    self._open()
                return self._request(method, list(params))
            except (OSError, ValueError, KeyError, TypeError, RecursionError) as exc:
                self.close()
                raise ValueError('Bitcoin light connection failed: ' + str(exc)) from exc


class LightNetwork:
    def __init__(self, path, urls, network='mainnet', progress=None):
        if not isinstance(urls, (list, tuple)) or not 3 <= len(urls) <= 8:
            raise ValueError('Configure three to eight Bitcoin light servers.')
        parsed = [endpoint(url, network) for url in urls]
        identities = [(p[1], p[2]) for p in parsed] if network == 'test' else [p[1] for p in parsed]
        if len(set(identities)) != len(identities):
            raise ValueError('Use different Bitcoin light-server hosts.')
        self.network = network
        self.path=path;self.progress=progress;self._chain=None
        self.peers = [ElectrumPeer(url, network) for url in urls]
        self.active = []
        self.errors = {}
        self.last_sync = 0
        self.lock = threading.RLock()

    @property
    def chain(self):
        if self._chain is None:self._chain=HeaderChain(self.path,self.network,self.progress)
        return self._chain

    def close(self):
        for peer in self.peers:
            peer.close()

    @staticmethod
    def parallel(peers, function):
        results, errors = [], {}
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(peers) or 1) as pool:
            futures = {pool.submit(function, peer): peer for peer in peers}
            for future, peer in futures.items():
                try:
                    results.append((peer, future.result()))
                except (OSError, ValueError, KeyError, TypeError) as exc:
                    errors[peer.url] = str(exc)
        return results, errors

    def sync(self, force=False):
        with self.lock:
            if not force and self.network == 'mainnet' and len(self.active)>=2 and time.monotonic() - self.last_sync < 5:
                return self.chain.height
            self.active = []
            tips, self.errors = self.parallel(self.peers, lambda p: p.call('blockchain.headers.subscribe'))
            valid = []
            for peer, tip in tips:
                try:
                    if not isinstance(tip, dict) or type(tip.get('height')) is not int:
                        raise ValueError('Invalid Bitcoin tip response.')
                    valid.append((peer, tip))
                except ValueError as exc:
                    self.errors[peer.url] = str(exc)
            for peer, tip in sorted(valid, key=lambda p: p[1]['height'], reverse=True):
                try:
                    self.chain.update(peer, tip)
                except (OSError, ValueError, KeyError, TypeError) as exc:
                    self.errors[peer.url] = str(exc)
            seen = set()
            for peer, tip in valid:
                if peer.url in self.errors or tip['height'] < self.chain.height:
                    continue
                try:
                    if bytes.fromhex(peer.call('blockchain.block.header', self.chain.height)) != self.chain.header(self.chain.height):
                        continue
                    identity = peer.address if self.network == 'mainnet' else (peer.host, peer.port)
                    if identity in seen:
                        continue
                    seen.add(identity)
                    self.active.append(peer)
                except (ValueError, OSError):
                    continue
            if len(self.active) < 2:
                self.active=[]
                raise ValueError('Two distinct Bitcoin servers must confirm the same verified header tip. Check connections and retry.')
            if self.network == 'mainnet':
                import struct
                if self.chain.work[-1] < MINIMUM_MAINNET_WORK:
                    self.active=[]
                    raise ValueError('Bitcoin headers have insufficient cumulative work for the public network.')
                timestamp = struct.unpack_from('<I', self.chain.header(self.chain.height), 68)[0]
                if timestamp < time.time() - 24 * 3600:
                    self.active=[]
                    raise ValueError('Bitcoin light-client tip is stale. No payment is allowed.')
            self.last_sync = time.monotonic()
            return self.chain.height

    def consistent(self, method, *params, normalize=lambda v: v):
        self.sync()
        responses, errors = self.parallel(self.active, lambda p: normalize(p.call(method, *params)))
        self.errors.update(errors)
        if len(responses) < 2:
            raise ValueError('Not enough Bitcoin servers supplied the requested transaction data.')
        first = responses[0][1]
        if any(value != first for _, value in responses[1:]):
            raise ValueError('Bitcoin servers disagree. Retry after synchronization or replace the faulty server; no payment is allowed.')
        return first

    def broadcast(self, raw, digest):
        self.sync(force=True)
        replies, errors = self.parallel(self.active, lambda p: p.call('blockchain.transaction.broadcast', raw))
        self.errors.update(errors)
        if not any(value == digest for _, value in replies):
            raise ValueError('Bitcoin broadcast was not acknowledged. The saved transaction can be retried unchanged.')
        return digest
