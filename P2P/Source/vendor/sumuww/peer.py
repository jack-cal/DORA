"""IPv4/IPv6 TCP peers, with explicit LAN and internet opt-ins.

Internet discovery may publish a runtime public listening contact to DHT.
Headers and advertised tips are hints. Only Chain.accept_block can
store a validated block or choose the active chain. SQLite calls stay in this
asyncio actor's thread; separate local CLI connections are observed by polling.
"""

import asyncio
from collections import deque
from dataclasses import dataclass, field
import errno
import ipaddress
import math
import json
import os
from pathlib import Path
import re
import secrets
import socket
import time

from .block import Block
from .boundary_runtime import BoundaryPolicyMismatch
from .chain import Chain
from .errors import InvalidBlock, UnsupportedFeature, ValidationError
from .primitives import check_pow
from .profiles import get_network
from .privacy import Transport, overlay_host, settings as privacy_settings
from .lan_discovery import LanDiscovery
from .dht_discovery import DhtDiscovery, DEFAULT_ROUTERS
from .peer_discovery import PeerAddressBook
from .bootstrap import (DNS_DEADLINE, MAX_BOOTSTRAP_HINTS, MAX_DNS_WORKERS,
                        MIN_QUERY_INTERVAL, MAX_QUERY_INTERVAL, SeedResult,
                        lookup_seed, normalize_fallbacks, normalize_seeds)
from .self_address import (DEFAULT_PORT, REFRESH_INTERVAL, InterfaceAddress, SelfAddressState,
                           async_enumerate_ipv4_interfaces as enumerate_ipv4_interfaces,
                           resolve_self_address)
from .transaction import Transaction
from .wire import (
    INV_BLOCK, INV_TRANSACTION, MAX_HEADERS, MAX_INV, PROTOCOL_VERSION,
    DISCOVERY_PROTOCOL_VERSION, IPV6_PROTOCOL_VERSION, BOUNDARY_PROTOCOL_VERSION, MAX_ADDRESSES, PeerAddress, decode_addresses, encode_addresses,
    Inventory, MalformedWireData, PeerDisconnected, ProtocolError, Version, decode_getheaders, decode_headers,
    decode_inventory, decode_ping, decode_version, encode_getheaders,
    encode_headers, encode_inventory, encode_ping, encode_version,
    read_frame, write_frame,
)


_RFC1918 = tuple(ipaddress.IPv4Network(value) for value in (
    '10.0.0.0/8', '172.16.0.0/12', '192.168.0.0/16',
))
_SPECIAL_PUBLIC = tuple(ipaddress.IPv4Network(value) for value in (
    '0.0.0.0/8', '100.64.0.0/10', '169.254.0.0/16', '192.0.0.0/24',
    '192.0.2.0/24', '192.88.99.0/24', '198.18.0.0/15',
    '198.51.100.0/24', '203.0.113.0/24', '224.0.0.0/4', '240.0.0.0/4',
))

INVALID_PEER_THRESHOLD = 3
INVALID_PEER_WINDOW = 600
INVALID_PEER_COOLDOWN = 300
MAX_INVALID_PEER_IPS = 128
DISCONNECTED_PEER_RETRY_CAP = 15
LISTENER_RETRY_INTERVAL = 5
LISTENER_POLL_INTERVAL = 1
CONNECTED_REPLY_TIMEOUT = 30
MAX_HINT_BLOCKS = MAX_HEADERS
MAX_HINT_BLOCK_BYTES = 8 * 1024 * 1024
HEADER_REFRESH_INTERVAL = 10
KEEPALIVE_INTERVAL = 10
VERIFIED_PEER_FRESHNESS = 25
MAX_PENDING_TRANSACTIONS = 1000
MAX_RECENT_INVENTORY = MAX_PENDING_TRANSACTIONS + MAX_INV
TRANSACTION_RETRY_INTERVAL = 15
PEER_WORK_BURST = 4096
PEER_WORK_RATE = 512
PEER_INVENTORY_BURST = 64 * MAX_INV
PEER_INVENTORY_RATE = 4096
PEER_VALIDATION_BURST = 4 * 1024 * 1024
PEER_VALIDATION_RATE = 2 * 1024 * 1024
PEER_EGRESS_BURST = 8 * 1024 * 1024
PEER_EGRESS_RATE = 8 * 1024 * 1024
MAX_QUOTA_DELAY = 10
PEER_EXPLORATION_INTERVAL = 300
PUBLIC_CONNECTION_LIMIT = None
PUBLIC_OUTGOING_TARGET = None
INCOMING_PROBE_INTERVAL = .25
INCOMING_SOURCE_PROBE_INTERVAL = 5
INCOMING_ROTATION_INTERVAL = 60


@dataclass
class _InvalidPeer:
    incidents: deque = field(default_factory=lambda: deque(maxlen=INVALID_PEER_THRESHOLD))
    cooldown_until: float = 0
    last_seen: float = 0


def _decode_payload(decoder, payload):
    """Payload shape errors are distinct from missing contextual chain data."""
    try:
        return decoder(payload)
    except ProtocolError as exc:
        raise MalformedWireData(str(exc)) from exc


def _endpoint(host, port, *, allow_zero=False, allow_lan=False,
              allow_internet=False, for_listen=False):
    """Validate scope without resolving DNS or opening a database/socket.

    Internet mode includes loopback/RFC1918 and global unicast IPv4/IPv6. DNS is
    outbound only and its results still require the same numeric scope check.
    Wildcard 0.0.0.0 is exclusively an opted-in LAN/internet listener address.
    """
    for label, flag in (('allow_lan', allow_lan), ('allow_internet', allow_internet),
                        ('for_listen', for_listen), ('allow_zero', allow_zero)):
        if type(flag) is not bool:
            raise ValueError(f'{label} must be a bool')
    if type(port) is not int or not (0 if allow_zero else 1) <= port <= 65535:
        raise ValueError('Port must be 1..65535; zero is allowed only when explicitly requested')
    if not isinstance(host, str) or not host:
        raise ValueError('Host must be a permitted IPv4 address or an enabled outbound DNS name')
    try:
        address = ipaddress.ip_address(host)
    except ValueError as exc:
        name = host[:-1] if host.endswith('.') else host
        labels = name.split('.')
        if (allow_internet and not for_listen and len(name) <= 253
                and not re.fullmatch(r'[0-9.]+', name)
                and all(re.fullmatch(r'[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?', label)
                        for label in labels)):
            return name.lower(), port
        raise ValueError('DNS names require internet outbound mode; listeners require numeric IP') from exc
    if address.is_unspecified:
        if (allow_internet or allow_lan) and for_listen and host in ('0.0.0.0', '::'):
            return str(address), port
        raise ValueError('Unspecified IP is allowed only for an opted-in LAN/internet listener')
    if address.version == 6 and ('%' in host or address.ipv4_mapped is not None or address.is_link_local):
        raise ValueError('Scoped, mapped and link-local IPv6 endpoints are unsupported')
    lan = (any(address in network for network in _RFC1918) or
           (address.version == 6 and address in ipaddress.IPv6Network('fc00::/7')))
    public = (address.is_global and not address.is_multicast and not address.is_reserved
              and not any(address in network for network in _SPECIAL_PUBLIC))
    permitted = address.is_loopback or ((allow_lan or allow_internet) and lan) or (allow_internet and public)
    if not permitted:
        raise ValueError('IP address is outside the enabled loopback, RFC1918 or global unicast scope')
    return str(address), port


@dataclass(eq=False)
class _Session:
    reader: asyncio.StreamReader
    writer: asyncio.StreamWriter
    outgoing: tuple | None = None
    remote_ip: str | None = None
    ready: bool = False
    boundary_id: str | None = None
    boundary_policy: str | None = None
    boundary_hello_sent: bool = False
    boundary_part_send_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    nonce: int | None = None
    outgoing_aliases: set = field(default_factory=set)
    send_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    # One header batch and a window of ordered block requests. A stale tip can require
    # bounded ancestor bodies after a fully validated replacement branch.
    headers: deque = field(default_factory=deque)
    branch_tip: bytes | None = None
    header_requested: bool = False
    headers_continuing: bool = False
    header_requested_at: float = 0
    block_requested_at: float = 0
    block_requests: set = field(default_factory=set)
    tx_requests: dict = field(default_factory=dict)
    pending_transactions: dict = field(default_factory=dict)
    recent_inventory: dict = field(default_factory=dict)
    last_headers_at: float = 0
    last_inventory_at: float = 0
    last_announced_tip: bytes | None = None
    last_announced_pool: frozenset = field(default_factory=frozenset)
    last_keepalive_at: float = field(default_factory=time.monotonic)
    # A handshake is not synchronization. Completion requires a terminal
    # headers response after every matching full block has been validated.
    synchronized: bool = False
    verified_once: bool = False
    # A live extension does not revoke the last fully validated mining anchor.
    live_update_pending: bool = False
    last_verified_at: float = -math.inf
    unknown_blocks: set = field(default_factory=set)
    requested_block_hints: set = field(default_factory=set)
    hint_branch_progress: bool = False
    hint_requested: bytes | None = None
    hint_requested_at: float = 0
    hint_blocks: dict = field(default_factory=dict)
    hint_block_bytes: int = 0
    protocol: int = PROTOCOL_VERSION
    attempted_protocol: int = PROTOCOL_VERSION
    handshake_stage: str = "not_started"
    local_close_reason: str | None = None
    version_rejected: bool = False
    legacy_candidate: bool = False
    discovery_requested: bool = False
    discovery_reply_pending: bool = False
    last_discovery_request: float = -math.inf
    last_discovery_response: float = -math.inf
    address_reply_sent: bool = False
    remote_listener: tuple | None = None
    last_address_response: tuple = ()
    address_response_count: int = 0
    cached: bool = False
    failed: bool = False
    completed_contacts: set = field(default_factory=set)
    replacement: '_Session | None' = None
    work_credit: float = PEER_WORK_BURST
    work_updated: float = 0
    inventory_credit: float = PEER_INVENTORY_BURST
    inventory_updated: float = 0
    validation_credit: float = PEER_VALIDATION_BURST
    validation_updated: float = 0
    egress_credit: float = PEER_EGRESS_BURST
    egress_updated: float = 0


class PeerNode:
    def __init__(self, database, host='127.0.0.1', port=0, peers=(),
                 poll_interval=.5, timeout=5, max_peers=None, clock=None,
                 allow_lan=False, network='regtest', allow_internet=False,
                 discover_peers=True, discovery_scope='public', discovery_interval=30,
                 advertised_endpoint=None, bootstrap_seeds=(), bootstrap_peers=(),
                 bootstrap_scope='public', auto_address=False,
                 dht_enabled=None, dht_scope='public', dht_routers=None,
                 dht_resolver=None, dht_interval=300, dht_query_timeout=2,
                 dht_round_timeout=20, dht_clock=None, privacy=None, privacy_router_factory=None,
                 outgoing_target=None, boundary_activation=None):
        self._privacy = Transport(privacy_settings() if privacy is None else privacy)
        private = self._privacy.mode != 'direct'
        if private:
            host, allow_lan, auto_address, advertised_endpoint = '127.0.0.1', False, False, None
            bootstrap_seeds, dht_enabled = (), False
        if self._privacy.mode == 'i2p':
            discover_peers = False
        if type(auto_address) is not bool:
            raise ValueError('Automatic own-address flag must be a bool')
        self.auto_address = auto_address
        self._self_state = SelfAddressState()
        self._self_refresh_error = None
        self._self_next_refresh = 0
        self._self_refresh_task = None
        self._self_clock = time.monotonic
        self._port_fallback = False
        self._lan_discovery = None
        self._lan_interface_hosts = ()
        self.address = _endpoint(host, port, allow_zero=True, allow_lan=allow_lan,
                                 allow_internet=allow_internet, for_listen=True)
        self.allow_lan = allow_lan
        self.allow_internet = allow_internet
        if type(discover_peers) is not bool:
            raise ValueError('Discovery flag must be a bool')
        if discovery_scope not in ('public', 'lan', 'loopback'):
            raise ValueError('Discovery scope must be public, lan, or loopback')
        if (type(discovery_interval) not in (int, float) or not math.isfinite(discovery_interval)
                or not 1 <= discovery_interval <= 300):
            raise ValueError('Discovery interval must be 1..300 finite seconds')
        self.discover_peers = discover_peers
        # LAN opt-in permits private automatic hints while preserving public
        # candidates. The existing LAN book scope includes both classes.
        self.discovery_scope = 'lan' if allow_lan and discovery_scope == 'public' else discovery_scope
        self.discovery_interval = float(discovery_interval)
        self.advertised_endpoint = advertised_endpoint
        # Validate optional first-contact input before creating/opening a DB.
        # No profile receives hidden seed defaults inside PeerNode itself.
        self._bootstrap_seeds = normalize_seeds(bootstrap_seeds, scope=bootstrap_scope)
        self._bootstrap_peers = normalize_fallbacks(bootstrap_peers, scope=bootstrap_scope)
        self._bootstrap_scope = bootstrap_scope
        self._bootstrap_enabled = bool(allow_internet and discover_peers)
        self._bootstrap_clock = time.monotonic
        self._bootstrap_next_query = 0
        self._bootstrap_failures = 0
        self._bootstrap_stats = {'query_rounds': 0, 'provider_attempts': 0,
                                 'accepted_hints': 0, 'provider_errors': 0, 'last_error': None}
        if max_peers is not None and (type(max_peers) is not int or max_peers < 1):
            raise ValueError('max_peers must be None or a positive integer')
        if outgoing_target is not None and (type(outgoing_target) is not int
                                           or outgoing_target < 1 or
                                           max_peers is not None and outgoing_target > max_peers):
            raise ValueError('outgoing_target must be positive and fit any explicit connection limit')
        for label, value, maximum in [('poll_interval', poll_interval, 5), ('timeout', timeout, 30)]:
            if type(value) not in (int, float) or not 0 < value <= maximum or not math.isfinite(value):
                raise ValueError(f'{label} must be finite, positive and <= {maximum}')
        if not isinstance(peers, (tuple, list)) or max_peers is not None and len(peers) > max_peers:
            raise ValueError('Configured peers must fit max_peers')
        configured = []
        for endpoint in peers:
            if not isinstance(endpoint, (tuple, list)) or len(endpoint) != 2:
                raise ValueError('Each configured peer must be a (host, port) pair')
            target = _endpoint(*endpoint, allow_lan=allow_lan, allow_internet=allow_internet)
            if target not in configured:
                configured.append(target)
        self.database = Path(database)
        self._managed_router = (privacy_router_factory(self._privacy.mode, self.database.parent)
                                if private and allow_internet and privacy_router_factory is not None else None)
        self._router_error = None
        self.poll_interval = float(poll_interval)
        self.timeout = float(timeout)
        self._dial_timeout = 90 if self._privacy.mode == 'i2p' else 30 if private else self.timeout
        self.max_peers = max_peers
        self.healthy_peer_target = outgoing_target or max_peers
        self._outgoing_target = outgoing_target
        self._peer_clock = time.monotonic
        self._next_exploration = self._peer_clock() + PEER_EXPLORATION_INTERVAL
        self._exploration_target = None
        self._exploration_deadline = 0
        self._incoming_probe = None
        self._incoming_probe_deadline = 0
        self._next_incoming_probe = 0
        self._next_incoming_rotation = 0
        self._incoming_probe_sources = {}
        self.network = get_network(network)
        self.genesis = self.network.genesis.block_hash()
        if dht_enabled is not None and type(dht_enabled) is not bool:
            raise ValueError('DHT flag must be a bool or default None')
        if dht_scope not in ('public', 'loopback') or (self.network.name == 'dora' and dht_scope != 'public'):
            raise ValueError('DHT loopback scope requires an explicit non-main fixture')
        default_dht = (self.network.name == 'dora' and bootstrap_scope == 'public'
                       and discovery_scope != 'loopback')
        self._dht_enabled = bool(allow_internet and discover_peers
                                 and (default_dht if dht_enabled is None else dht_enabled))
        self._dht_scope = dht_scope
        self._dht_discovery = (DhtDiscovery(
            self.network, self._received_dht_hints, contact_provider=self._dht_contact,
            self_endpoints=self._connected_endpoints,
            connected_provider=self._has_dht_connected_peer,
            settled_provider=self._discovery_settled,
            routers=DEFAULT_ROUTERS if dht_routers is None else dht_routers,
            resolver=dht_resolver, scope=dht_scope, clock=dht_clock,
            interval=dht_interval, query_timeout=dht_query_timeout, round_timeout=dht_round_timeout)
            if self._dht_enabled else None)
        self._dht_discovery6 = (DhtDiscovery(
            self.network, self._received_dht_hints, family=socket.AF_INET6,
            contact_provider=self._dht_contact_ipv6, source_provider=self._dht_source_ipv6,
            self_endpoints=self._connected_endpoints,
            connected_provider=self._has_dht_connected_peer,
            settled_provider=self._discovery_settled,
            routers=DEFAULT_ROUTERS if dht_routers is None else dht_routers,
            resolver=dht_resolver, scope=dht_scope, clock=dht_clock,
            interval=dht_interval, query_timeout=dht_query_timeout, round_timeout=dht_round_timeout)
            if self._dht_enabled and dht_scope == 'public' else None)
        self._addresses = PeerAddressBook(
            self.database.with_name(self.database.name + '.peers.json'),
            self.network.profile_id, self.genesis, scope=self.discovery_scope,
            validator=self._discovery_endpoint)
        if advertised_endpoint is not None:
            self.advertised_endpoint = self._addresses.validate(advertised_endpoint)
        self.chain = Chain(self.database, clock=clock, network=self.network,boundary_activation=boundary_activation)
        self.boundary_runtime = None
        self.nonce = secrets.randbits(64)
        self._configured = {target: asyncio.Event() for target in configured}
        self._workers = {}
        self._discovery_workers = {}
        self._legacy_targets = set()
        self._v2_targets = set()
        self._v3_targets = set()
        self._sessions = {}
        self._tasks = set()
        self._server = None
        self._server6 = None
        self._ipv6_next_retry = 0
        self._ipv6_error = None
        self._listener_lock = asyncio.Lock()
        self._listener_next_retry = 0
        self._listener_error = None
        self._listener_restarts = 0
        self._start_lock = asyncio.Lock()
        self._start_task = None
        self._stopping = False
        self._stop_lock = asyncio.Lock()
        self._running = False
        self._closed = False
        self._last_chain_info = None
        self._invalid_peers = {}
        self._enforcement_clock = time.monotonic
        self._stats = {name: 0 for name in (
            'connections', 'handshakes', 'reconnect_attempts', 'peer_limit_rejections',
            'address_rejections', 'duplicate_connection_rejections',
            'incoming_evictions', 'incoming_probes', 'incoming_probe_expirations',
            'incoming_replacements', 'incoming_handoffs',
            'protocol_errors', 'connection_errors', 'disconnects', 'validation_rejections',
            'unsupported_features', 'headers_received', 'blocks_received',
            'blocks_stored', 'transactions_received', 'transactions_accepted',
            'requests_expired', 'frames_sent', 'frames_received', 'internal_errors',
            'invalid_peer_incidents', 'peer_cooldowns', 'cooldown_rejections',
            'address_hints_received', 'address_hints_rejected', 'address_requests_sent',
            'address_responses_sent', 'address_rate_rejections', 'legacy_fallbacks',
            'quota_work_waits', 'quota_inventory_waits', 'quota_validation_waits', 'quota_egress_waits',
            'quota_wait_seconds', 'quota_rejections', 'transaction_hint_drops',
        )}
        self._last_error = None
        self._recent_peer_attempts = deque(maxlen=16)
        # Opt-in local execution trace for diagnosing real sessions. It is
        # disabled in ordinary use and never transmitted to another node.
        self._trace_file = os.environ.get('SUMUWW_PEER_TRACE_FILE')
        self._trace_next = 0

    def _trace_event(self,event,session=None,**details):
        if not self._trace_file:return
        row={'time':time.time(),'event':event,**details}
        if session is not None:
            row.update(remote=session.remote_ip,outgoing=session.outgoing,nonce=session.nonce,
                       stage=session.handshake_stage,protocol=session.protocol,
                       boundary_policy=session.boundary_policy,ready=session.ready,
                       synchronized=session.synchronized)
        try:
            with open(self._trace_file,'a',encoding='utf-8') as output:
                output.write(json.dumps(row,ensure_ascii=False)+'\n')
        except OSError:
            # Diagnostic storage failure must never terminate a peer session.
            self._trace_file=None

    def _record_peer_attempt(self, target, outcome, error=None, *, session=None):
        self._trace_event(outcome,session,target=target,error=str(error) if error is not None else None)
        if target is None:
            return
        # Local diagnostics only: bounded, in memory, never sent to peers.
        row = {'host': target[0], 'port': target[1], 'outcome': outcome,
               'at': self._peer_clock()}
        if session is not None:
            row['attempted_protocol'] = session.attempted_protocol
            row['handshake_stage'] = session.handshake_stage
            row['local_close_reason'] = session.local_close_reason
        if error is not None:
            row['error'] = type(error).__name__ + (': ' + str(error)[:160] if str(error) else '')
        self._recent_peer_attempts.append(row)

    @property
    def running(self):
        return self._running

    def _spawn(self, coroutine, name):
        task = asyncio.create_task(coroutine, name=f'sumuww-peer:{name}')
        self._tasks.add(task)
        task.add_done_callback(self._task_done)
        return task

    def _task_done(self, task):
        self._tasks.discard(task)
        if not task.cancelled():
            error = task.exception()
            if error is not None:
                self._stats['internal_errors'] += 1
                self._last_error = f'{type(error).__name__}: {error}'

    async def start(self):
        async with self._start_lock:
            return await self._start()

    async def _start(self):
        if self._closed:
            raise RuntimeError('A stopped PeerNode cannot be restarted; construct a new one')
        if self._stopping:
            raise RuntimeError('Node is stopping')
        if self._running:
            return self
        self._start_task = asyncio.current_task()
        self._running = True
        try:
            if self.chain.boundary.activation is not None:
                from .boundary_runtime import BoundaryRuntime
                self.boundary_runtime=BoundaryRuntime(self)
            async with self._listener_lock:
                try:
                    candidate = await asyncio.start_server(
                        self._accepted, *self.address, family=socket.AF_INET6 if ':' in self.address[0] else socket.AF_INET,
                        limit=64 * 1024, backlog=socket.SOMAXCONN if self.max_peers is None else self.max_peers, start_serving=False,
                    )
                except OSError as error:
                    # Only the automatic standard port can select an OS-assigned
                    # replacement. A fixed advertised contact cannot move ports.
                    if not (self.auto_address and self.address[1] == DEFAULT_PORT
                            and self.advertised_endpoint is None
                            and (error.errno == errno.EADDRINUSE or getattr(error, 'winerror', None) == 10048)):
                        raise
                    candidate = await asyncio.start_server(
                        self._accepted, self.address[0], 0, family=socket.AF_INET6 if ':' in self.address[0] else socket.AF_INET,
                        limit=64 * 1024, backlog=socket.SOMAXCONN if self.max_peers is None else self.max_peers, start_serving=False,
                    )
                    self._port_fallback = True
                # Own the server before activation's final serving yield. A
                # cancelled initial start must release its selected TCP port.
                self._server = candidate
                bound = candidate.sockets[0].getsockname()
                self.address = bound[0], bound[1]
                try:
                    await candidate.start_serving()
                except BaseException:
                    candidate.close()
                    if self._server is candidate:
                        self._server = None
                    raise
            await self._ensure_ipv6_listener()
            await self._refresh_own_addresses()
            await self._refresh_lan_discovery()
            if self._dht_discovery is not None:
                await self._dht_discovery.start()
            if self._dht_discovery6 is not None:
                await self._dht_discovery6.start()
            if self._bootstrap_enabled and (self._bootstrap_seeds or self._bootstrap_peers):
                # Fixed contacts remain independent of a slow or failed DNS
                # provider and are available before any dial/handshake task.
                self._add_bootstrap_hints(self._bootstrap_peers)
                self._spawn(self._bootstrap(), 'bootstrap')
            self._spawn(self._poll(), 'poll')
            self._spawn(self._maintain_listener(), 'listener')
            if self._managed_router is not None:
                self._spawn(self._maintain_privacy_router(), 'privacy-router')
            for target in self._configured:
                self._workers[target] = self._spawn(self._outgoing(target), f'outgoing:{target[1]}')
            if self.discover_peers:
                self._spawn(self._discover(), 'discovery')
            if self._privacy.mode == 'i2p' and self.allow_internet:
                self._spawn(self._accept_i2p(), 'i2p-listener')
            return self
        except BaseException:
            # An external stop owns cleanup and waits for this cancelled start.
            # Re-entering its stop lock here would deadlock both callers.
            if not self._stopping:
                await self.stop()
            raise
        finally:
            self._start_task = None

    async def stop(self):
        """Close listeners, cancel tasks, close sockets/SQLite; safe before start."""
        self._stopping = True
        async with self._stop_lock:
            await self._stop()

    async def _stop(self):
        if self._closed:
            return
        self._running = False
        current = asyncio.current_task()
        tasks = [task for task in self._tasks if task is not current]
        startup = self._start_task
        if startup is not None and startup is not current and not startup.done():
            tasks.append(startup)
        for task in tasks:
            task.cancel()
        # In Python 3.12 Server.wait_closed also waits for active transports.
        # Stop accepting first, but release those transports before waiting.
        async with self._listener_lock:
            server, self._server = self._server, None
            if server is not None:
                server.close()
        server6, self._server6 = self._server6, None
        if server6 is not None:
            server6.close()
        writers = [session.writer for session in self._sessions.values()]
        for writer in writers:
            writer.close()
        if self._dht_discovery is not None:
            await self._dht_discovery.stop()
        if self._dht_discovery6 is not None:
            await self._dht_discovery6.stop()
        if self._lan_discovery is not None:
            await self._lan_discovery.stop()
        await self._privacy.stop()
        if self._managed_router is not None:
            await self._managed_router.stop()
        self._lan_interface_hosts = ()
        self._self_state = SelfAddressState()
        if tasks:
            # Every I/O path also has a deadline. The final cancellation budget
            # is independent of peer count and of reconnect backoff duration.
            done, pending = await asyncio.wait(tasks, timeout=min(self.timeout + 1, 3))
            for task in pending:
                task.cancel()
            for task in done:
                if not task.cancelled():
                    task.exception()
        if writers:
            await asyncio.gather(*(self._close_writer(writer) for writer in writers), return_exceptions=True)
        if server is not None:
            try:
                await asyncio.wait_for(server.wait_closed(), timeout=min(self.timeout, 1))
            except (OSError, TimeoutError):
                # A late rejected connection cannot prevent owned DB cleanup.
                # _reserve refuses new sessions once _running is false.
                pass
        if server6 is not None:
            try:
                await asyncio.wait_for(server6.wait_closed(), timeout=min(self.timeout, 1))
            except (OSError, TimeoutError):
                pass
        self._sessions.clear()
        self._incoming_probe = None
        self._incoming_probe_sources.clear()
        self._workers.clear()
        self._discovery_workers.clear()
        self._last_chain_info = self.chain.info()
        if self.boundary_runtime is not None:
            await self.boundary_runtime.close()
        self.chain.close()
        self._closed = True

    def _listener_active(self):
        server = self._server
        if server is None or not server.is_serving():
            return False
        try:
            sockets = server.sockets
            return bool(sockets) and all(sock.fileno() >= 0 for sock in sockets)
        except OSError:
            return False

    async def _ensure_ipv6_listener(self):
        if self._privacy.mode != 'direct':
            return
        # Separate v6-only socket: keep the existing IPv4 listener and sessions.
        if not self._running or not (self.allow_internet or self.allow_lan) or self.address[0] != '0.0.0.0':
            return
        if (self._server6 is not None and self._server6.is_serving()
                and self._server6.sockets and all(s.fileno() >= 0 for s in self._server6.sockets)):
            return
        now = asyncio.get_running_loop().time()
        if now < self._ipv6_next_retry:
            return
        self._ipv6_next_retry = now + LISTENER_RETRY_INTERVAL
        sock = None
        candidate = None
        try:
            if self._server6 is not None:
                self._server6.close()
                self._server6 = None
            sock = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
            sock.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 1)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind(('::', self.address[1]))
            sock.setblocking(False)
            candidate = await asyncio.start_server(self._accepted, sock=sock, limit=64*1024,
                                                  backlog=socket.SOMAXCONN if self.max_peers is None else self.max_peers, start_serving=False)
            sock = None
            self._server6 = candidate
            await candidate.start_serving()
            self._ipv6_error = None
        except (OSError, asyncio.CancelledError) as error:
            if candidate is not None:
                candidate.close()
                self._server6 = None
            if sock is not None:
                sock.close()
            self._ipv6_error = type(error).__name__
            if isinstance(error, asyncio.CancelledError):
                raise

    async def _maintain_listener(self):
        while self._running:
            if not self._listener_active():
                await self._recover_listener()
            await self._ensure_ipv6_listener()
            await asyncio.sleep(LISTENER_POLL_INTERVAL)

    async def _recover_listener(self):
        # Windows Proactor may close an accept socket without closing its
        # Server. Rebind only the actual selected address; established streams
        # stay attached to their original Server and keep their sessions.
        async with self._listener_lock:
            if not self._running or self._listener_active():
                return
            now = asyncio.get_running_loop().time()
            if now < self._listener_next_retry:
                return
            self._listener_next_retry = now + LISTENER_RETRY_INTERVAL
            self._listener_error = 'TCP listener unavailable'
            previous, self._server = self._server, None
            if previous is not None:
                previous.close()

            async def bind():
                # Own the bound socket before start_serving yields. Cancelling
                # Python 3.12 create_server during its final serving yield can
                # otherwise leave a listener whose Server was never returned.
                candidate = await asyncio.start_server(
                    self._accepted, *self.address, family=socket.AF_INET6 if ':' in self.address[0] else socket.AF_INET,
                    limit=64 * 1024, backlog=socket.SOMAXCONN if self.max_peers is None else self.max_peers, start_serving=False,
                )
                if not self._running:
                    candidate.close()
                    return None
                self._server = candidate
                try:
                    await candidate.start_serving()
                except BaseException:
                    candidate.close()
                    if self._server is candidate:
                        self._server = None
                    raise
                return candidate

            try:
                candidate = await asyncio.wait_for(bind(), timeout=min(self.timeout, LISTENER_RETRY_INTERVAL))
            except (OSError, TimeoutError) as error:
                self._listener_error = f'{type(error).__name__}: {error}'
                return
            if candidate is None:
                return
            if not self._running or not self._listener_active():
                candidate.close()
                if self._server is candidate:
                    self._server = None
                return
            self._listener_error = None
            self._listener_restarts += 1

    async def add_peer(self, host, port):
        """Register one permitted manual IP/DNS peer; reconnect while running."""
        if self._closed:
            raise RuntimeError('Node is stopped')
        target = _endpoint(host, port, allow_lan=self.allow_lan, allow_internet=self.allow_internet)
        if target not in self._configured:
            if self.max_peers is not None and len(self._configured) >= self.max_peers:
                raise ValueError('Configured outgoing peer limit reached')
            self._configured[target] = asyncio.Event()
            # Only an explicitly requested connection budget reserves slots.
            if self.max_peers is not None and (self.allow_internet or self.allow_lan):
                incoming = [session for session in self._sessions.values() if session.outgoing is None]
                capacity = self._incoming_capacity()
                for session in incoming[capacity:]:
                    self._stats['incoming_evictions'] += 1
                    session.writer.close()
            if self._running:
                self._workers[target] = self._spawn(self._outgoing(target), f'outgoing:{port}')
        return target

    async def connect(self, host, port):
        """Register a peer and wait for its first completed handshake."""
        if not self._running:
            raise RuntimeError('Start the node before connecting')
        target = await self.add_peer(host, port)
        await asyncio.wait_for(self._configured[target].wait(), timeout=self.timeout * 2)
        return target

    def _incoming_capacity(self):
        if self.max_peers is None:return None
        if not (self.allow_internet or self.allow_lan):
            return self.max_peers
        # A one-session limit cannot reserve both directions; keep its listener
        # usable, while limits >= 2 reserve up to half for outbound workers.
        reserved = min(len(self._configured), self.max_peers // 2)
        # Automatic hints may arrive after incoming sessions. Keep at least one
        # outbound slot so those sessions cannot prevent every discovery dial.
        if self.discover_peers and self.max_peers >= 2:
            reserved = max(reserved, min(self._outgoing_target or 1, self.max_peers - 1))
        return self.max_peers - reserved

    def _healthy_sessions(self):
        now = self._peer_clock()
        return self._unique_peer_sessions(session for session in self._sessions.values()
                     if session.ready and not session.writer.is_closing()
                     and (session.synchronized or session.live_update_pending) and session.verified_once
                     and now - session.last_verified_at <= VERIFIED_PEER_FRESHNESS)

    def _can_probe_incoming(self, remote_ip):
        # Full listeners must still let a newcomer negotiate and learn peers.
        # Share the one extra exploration slot; never displace an anchor for
        # an unvalidated socket, and never open an unbounded handshake queue.
        now = self._peer_clock()
        self._incoming_probe_sources = {key: until for key, until in
                                       self._incoming_probe_sources.items() if until > now}
        return (self.max_peers is not None and self.discover_peers and (self.allow_internet or self.allow_lan)
                and self.max_peers >= 2 and self._incoming_probe is None
                and len(self._sessions) < self.max_peers + 1
                and now >= self._next_incoming_probe
                and now >= self._incoming_probe_sources.get(remote_ip, 0)
                and bool(self._healthy_sessions()))

    def _maintain_incoming_probe(self):
        if self.max_peers is None:return
        candidate = self._incoming_probe
        if candidate is None:
            return
        if candidate.writer.is_closing() or id(candidate.writer) not in self._sessions:
            self._incoming_probe = None
            return
        now = self._peer_clock()
        healthy = self._healthy_sessions()
        if candidate in healthy:
            live = [s for s in self._sessions.values() if not s.writer.is_closing()]
            incoming = [s for s in live if s.outgoing is None]
            if len(live) <= self.max_peers and len(incoming) <= self._incoming_capacity():
                self._incoming_probe = None
                return
            if now >= self._next_incoming_rotation:
                victims = [s for s in incoming if s is not candidate]
                if not victims and len(incoming) <= self._incoming_capacity():
                    # Small/full nodes can have every slot occupied by learned
                    # outgoing paths. Promote a validated newcomer by releasing
                    # only an excess learned route, preserving the outgoing
                    # reservation and every explicitly configured preference.
                    outgoing = [s for s in live if s.outgoing is not None]
                    reserved = self.max_peers - self._incoming_capacity()
                    if len(outgoing) > reserved:
                        victims = [s for s in outgoing
                                   if not ((s.outgoing_aliases | {s.outgoing})
                                           & self._configured.keys())]
                if victims:
                    victim = min(victims, key=lambda s: (s in healthy,
                                                       s.last_verified_at))
                    victim.writer.close()
                    if victim.outgoing is None:
                        self._stats['incoming_evictions'] += 1
                    self._stats['incoming_replacements'] += 1
                    self._next_incoming_rotation = now + INCOMING_ROTATION_INTERVAL
                    self._incoming_probe = None
                    return
            elif candidate.address_reply_sent:
                # A synchronized newcomer received alternate contacts, but
                # replacement is cooling down. Release the temporary slot
                # immediately rather than occupying it for the whole timeout.
                candidate.writer.close()
                self._stats['incoming_handoffs'] += 1
                self._incoming_probe = None
                return
        if now >= self._incoming_probe_deadline:
            candidate.writer.close()
            self._stats['incoming_probe_expirations'] += 1
            self._incoming_probe = None

    def _unique_peer_sessions(self, sessions):
        """Count process identities, retaining the best validated transport."""
        identities = {}
        now = self._peer_clock()

        def quality(item):
            validated = item.verified_once and (item.synchronized or item.live_update_pending)
            return (validated and now - item.last_verified_at <= VERIFIED_PEER_FRESHNESS,
                    validated, item.synchronized, item.verified_once)

        for session in sessions:
            identity = ('nonce', session.nonce) if session.nonce is not None else ('session', id(session))
            previous = identities.get(identity)
            if previous is None or quality(session) > quality(previous):
                identities[identity] = session
        return tuple(identities.values())

    def _retire_duplicate_transports(self):
        """Repair redundant live routes after a validated route is available."""
        connected = tuple(session for session in self._sessions.values()
                          if session.ready and not session.writer.is_closing())
        keepers = {session.nonce: session for session in self._unique_peer_sessions(connected)
                   if session.nonce is not None and session.verified_once
                   and (session.synchronized or session.live_update_pending)}
        for session in connected:
            keeper = keepers.get(session.nonce)
            if keeper is None or keeper is session:
                continue
            aliases = session.outgoing_aliases | ({session.outgoing} if session.outgoing else set())
            keeper.outgoing_aliases.update(aliases)
            # Preserve the alternate, completed TCP route for reconnection.
            contacts = keeper.completed_contacts | session.completed_contacts
            if session.outgoing is not None:
                contacts.add((session.remote_ip, session.outgoing[1]))
            keeper.completed_contacts = set(contacts)
            if keeper.synchronized:
                self._cache_synchronized_endpoint(keeper)
            session.writer.close()
            self._stats['duplicate_connection_rejections'] += 1

    def _discovery_outgoing_target(self):
        if self.max_peers is None:return self.healthy_peer_target
        # Incoming anchors stay connected, but must not consume the reserved
        # opportunity to verify a durable outbound backup address.
        incoming = sum(session.outgoing is None and session is not self._incoming_probe
                       and not session.writer.is_closing()
                       for session in self._sessions.values())
        return min(self.healthy_peer_target, max(0, self.max_peers - incoming))

    def _discovery_settled(self):
        # Unlimited discovery keeps looking for new live contacts; it never
        # declares a fixed-size target full and suppresses address requests.
        if self.healthy_peer_target is None:return False
        healthy = self._healthy_sessions()
        # Different IPs/ports can lead to the same live node. Count identities
        # for backup coverage, while preserving every established transport.
        identities = {session.nonce for session in healthy}
        outgoing_identities = {session.nonce for session in healthy if session.outgoing is not None}
        return (self._running and len(identities) >= self.healthy_peer_target
                and len(outgoing_identities)
                >= self._discovery_outgoing_target())

    def synchronization_info(self):
        """A fresh fully validated anchor, independent of unverified backups."""
        connected = self._unique_peer_sessions(session for session in self._sessions.values()
                          if session.ready and not session.writer.is_closing())
        anchors = self._healthy_sessions()
        synchronized = sum(session.synchronized for session in anchors)
        live_updates = sum(session.live_update_pending for session in anchors)
        mining_ready = self._running and bool(anchors)
        return {'synchronized_peers': synchronized, 'mining_ready': mining_ready,
                'validated_mining_anchors': len(anchors), 'live_block_updates': live_updates,
                'healthy_peer_target': self.healthy_peer_target,
                'automatic_search_settled': self._discovery_settled(),
                'sync_state': ('updating' if mining_ready and live_updates else
                               'ready' if mining_ready else 'syncing' if connected else 'disconnected')}

    def info(self, *, include_state=True):
        state = dict(self._last_chain_info if self._closed else
                     self.chain.info() if include_state else self.chain.summary())
        state.update(self.synchronization_info())
        self._expire_invalid_peers(self._enforcement_clock())
        state.update({
            'running': self._running,
            'listen': {'host': self.address[0], 'port': self.address[1]},
            'ipv6_listener': {'active': bool(self._server6 is not None and self._server6.is_serving()) or ':' in self.address[0], 'error': self._ipv6_error},
            'listener_active': self._listener_active(),
            'privacy': {'mode': self._privacy.mode,
                        'local_router_port': self._privacy.options['port'],
                        'i2p_address': self._privacy.address,
                        'router': self._managed_router.info() if self._managed_router is not None else None,
                        'router_error': self._router_error,
                        'direct_fallback': False},
            'listener_error': (self._listener_error or
                               ('TCP listener unavailable' if self._running and not self._listener_active() else None)),
            'listener_restarts': self._listener_restarts,
            'own_addresses': [f'[{host}]:{port}' if ':' in host else f'{host}:{port}' for host, port in self._self_state.own_addresses],
            'self_address': {
                'automatic': self.auto_address,
                'status': self._self_state.status,
                'public_contact': (None if self._self_state.advertised_endpoint is None else
                                   ('[{}]:{}' if ':' in self._self_state.advertised_endpoint[0] else '{}:{}')
                                   .format(*self._self_state.advertised_endpoint)),
                'external_reachability': self._self_state.external_reachability,
                'port_fallback': self._port_fallback,
                'refresh_error': self._self_refresh_error,
            },
            'peers': len(self._unique_peer_sessions(session for session in self._sessions.values()
                        if session.ready and not session.writer.is_closing())),
            'peer_connections': [self._connection_status(session) for session in
                                 self._unique_peer_sessions(session for session in self._sessions.values()
                                     if session.ready and not session.writer.is_closing())],
            'active_connections': sum(session.ready and not session.writer.is_closing()
                                      for session in self._sessions.values()),
            'sessions': len(self._sessions),
            'configured_peers': len(self._configured),
            'configured_peer_endpoints': [{'host': host, 'port': port} for host, port in self._configured],
            'peer_discovery': dict(self._addresses.info(), enabled=self.discover_peers,
                                   learned_workers=len(self._discovery_workers),
                                   healthy_target=self.healthy_peer_target,
                                   settled=self._discovery_settled(),
                                   advertised_listener=(None if self._own_listener() is None else
                                                        {'host': self._own_listener()[0],
                                                         'port': self._own_listener()[1]})),
            'lan_discovery': (self._lan_discovery.info() if self._lan_discovery is not None else
                              {'enabled': self.allow_lan and self.discover_peers,
                               'state': 'not_running' if self.allow_lan and self.discover_peers else 'disabled',
                               'hint_only': True}),
            'dht_discovery': (self._dht_discovery.info() if self._dht_discovery is not None else
                              {'enabled': False, 'state': 'disabled', 'hint_only': True}),
            'dht_discovery_ipv6': (self._dht_discovery6.info() if self._dht_discovery6 is not None else
                                  {'enabled': False, 'state': 'disabled', 'hint_only': True}),
            'bootstrap': dict(self._bootstrap_stats, enabled=self._bootstrap_enabled,
                              dns_seed_providers=len(self._bootstrap_seeds),
                              fallback_peers=len(self._bootstrap_peers),
                              dns_worker_limit=MAX_DNS_WORKERS,
                              next_query_seconds=(max(0, math.ceil(self._bootstrap_next_query - self._bootstrap_clock()))
                                                  if self._running and self._bootstrap_enabled else 0)),
            'peer_tasks': len(self._tasks),
            'allow_lan': self.allow_lan,
            'allow_internet': self.allow_internet,
            'internet_connectivity_enabled': self.allow_internet,
            'incoming_capacity': self._incoming_capacity(),
            'incoming_admission': {
                'probe_active': self._incoming_probe is not None,
                'steady_connection_limit': self.max_peers,
                'transient_connection_limit': None if self.max_peers is None else self.max_peers + 1,
                'minimum_probe_interval_seconds': INCOMING_PROBE_INTERVAL,
                'minimum_source_probe_interval_seconds': INCOMING_SOURCE_PROBE_INTERVAL,
                'minimum_replacement_interval_seconds': INCOMING_ROTATION_INTERVAL,
            },
            'network': self.network.name,
            'network_magic': self.network.message_magic.hex(),
            'endpoint_scope': ('IPv4/IPv6 loopback, private and global unicast; checked outbound DNS; wildcard listen'
                               if self.allow_internet else
                               'IPv4 loopback and RFC1918' if self.allow_lan else 'IPv4 loopback only'),
            'transport': ('opt-in IPv4/IPv6 internet/manual DNS TCP; public deployment not inferred'
                          if self.allow_internet else
                          'numeric IP loopback + opt-in RFC1918 TCP' if self.allow_lan
                          else 'numeric IP loopback TCP only') + ' / SUMUWW wire v1/v2',
            'stats': dict(self._stats),
            'peer_limits': {'work_burst': PEER_WORK_BURST, 'work_per_second': PEER_WORK_RATE,
                            'inventory_burst_items': PEER_INVENTORY_BURST,
                            'inventory_items_per_second': PEER_INVENTORY_RATE,
                            'validation_burst_bytes': PEER_VALIDATION_BURST,
                            'validation_bytes_per_second': PEER_VALIDATION_RATE,
                            'egress_burst_bytes': PEER_EGRESS_BURST,
                            'egress_bytes_per_second': PEER_EGRESS_RATE,
                            'header_refresh_seconds': HEADER_REFRESH_INTERVAL,
                            'verified_freshness_seconds': VERIFIED_PEER_FRESHNESS,
                            'transaction_hints': MAX_PENDING_TRANSACTIONS},
            'last_peer_error': self._last_error,
            'recent_peer_attempts': [dict(row) for row in self._recent_peer_attempts],
            'peer_enforcement': {
                'threshold': INVALID_PEER_THRESHOLD,
                'window_seconds': INVALID_PEER_WINDOW,
                'cooldown_seconds': INVALID_PEER_COOLDOWN,
                'maximum_tracked_ips': MAX_INVALID_PEER_IPS,
                'tracked_ips': len(self._invalid_peers),
                'cooling_down_ips': sum(bool(value.cooldown_until) for value in self._invalid_peers.values()),
                'identity': 'actual socket remote IP; shared NAT addresses share the limit',
                'persistent': False,
            },
        })
        state['boundary']=(self.boundary_runtime.info() if self.boundary_runtime is not None else
                           {'activation_height':self.chain.boundary.activation if not self._closed else None})
        return state

    def _connection_status(self, session):
        """Private local monitor view; no remote-claimed listener is promoted."""
        target = session.outgoing
        host = target[0] if target is not None else session.remote_ip
        port = target[1] if target is not None else None
        transport = 'TCP'
        try:
            address = ipaddress.ip_address(host)
            if address.is_loopback:
                host = 'Local peer'
            elif not address.is_global:
                host = 'LAN peer'
        except ValueError:
            pass
        return {'host': host, 'port': port, 'transport': transport,
                'peer_id': f'{session.nonce:016x}' if session.nonce is not None else None,
                'direction': 'outgoing' if target is not None else 'incoming',
                'synchronized': session.synchronized,
                'sync_state': 'ready' if session.synchronized else 'syncing',
                'protocol': session.protocol,
                'address_response_count': session.address_response_count,
                'last_address_response': [dict(row) for row in session.last_address_response]}

    def _expire_invalid_peers(self, now):
        for address, value in tuple(self._invalid_peers.items()):
            if value.cooldown_until:
                if now >= value.cooldown_until:
                    self._invalid_peers.pop(address, None)
                continue
            while value.incidents and now - value.incidents[0] >= INVALID_PEER_WINDOW:
                value.incidents.popleft()
            if not value.incidents:
                self._invalid_peers.pop(address, None)

    def _cooling_down(self, address):
        self._expire_invalid_peers(self._enforcement_clock())
        value = self._invalid_peers.get(address)
        return value is not None and bool(value.cooldown_until)

    def _record_invalid_peer(self, session):
        """Bounded, temporary transport protection; never a chainwork rule."""
        address = session.remote_ip
        if address is None:
            # Tor inbound streams share the router's socket address. Keep
            # enforcement per connection instead of banning the local router.
            address = ('connection', id(session))
        now = self._enforcement_clock()
        self._expire_invalid_peers(now)
        value = self._invalid_peers.get(address)
        if value is None:
            if len(self._invalid_peers) >= MAX_INVALID_PEER_IPS:
                oldest = min(self._invalid_peers, key=lambda key: self._invalid_peers[key].last_seen)
                self._invalid_peers.pop(oldest)
            value = self._invalid_peers[address] = _InvalidPeer()
        self._stats['invalid_peer_incidents'] += 1
        if value.cooldown_until:
            return
        value.incidents.append(now)
        value.last_seen = now
        if len(value.incidents) >= INVALID_PEER_THRESHOLD:
            value.cooldown_until = now + INVALID_PEER_COOLDOWN
            self._stats['peer_cooldowns'] += 1
            # Shared NAT addresses do not identify an established peer. Drop
            # this offender; subsequent new attempts observe the IP cooldown.
            session.synchronized = False
            session.writer.close()

    def _reserve(self, reader, writer, outgoing=None):
        # Discovery and manual registration can race for one outbound target.
        # Reservation runs synchronously on the node loop.
        if outgoing is not None and self._outgoing_session(outgoing) is not None:
            self._stats['duplicate_connection_rejections'] += 1
            writer.close()
            return None
        remote = writer.get_extra_info('peername')
        try:
            remote_ip = str(ipaddress.ip_address(remote[0]))
        except (ValueError, TypeError, IndexError):
            self._stats['address_rejections'] += 1
            writer.close()
            return None
        if self._privacy.mode != 'direct':
            # Never aggregate independent overlay peers under the local router
            # socket's 127.0.0.1 address. Tor inbound has no authenticated
            # transport identity and retains per-session resource limits.
            remote_ip = getattr(writer, '_sumuww_peer_identity', None)
        if self._cooling_down(remote_ip):
            self._stats['cooldown_rejections'] += 1
            writer.close()
            return None
        if outgoing is not None:
            existing = next((session for session in self._sessions.values()
                             if session.outgoing is not None and session.remote_ip == remote_ip
                             and session.outgoing[1] == outgoing[1]
                             and not session.writer.is_closing()), None)
            if existing is not None:
                # A checked DNS alias resolving to the very same TCP endpoint
                # shares its existing connection. No remote listener claim is used.
                existing.outgoing_aliases.add(outgoing)
                if existing.ready and outgoing in self._configured:
                    self._configured[outgoing].set()
                self._stats['duplicate_connection_rejections'] += 1
                writer.close()
                return None
        incoming_full = (self.max_peers is not None and (self.allow_internet or self.allow_lan) and outgoing is None
                         and sum(session.outgoing is None for session in self._sessions.values())
                         >= self._incoming_capacity())
        # One locally initiated probe may temporarily use an extra slot. No
        # inbound peer or ordinary dial can claim this reservation.
        limit = None if self.max_peers is None else self.max_peers + int(outgoing is not None and
                                    (outgoing == self._exploration_target
                                     or self._incoming_probe is not None))
        probing_incoming = (self._running and outgoing is None
                            and limit is not None and (len(self._sessions) >= limit or incoming_full)
                            and self._can_probe_incoming(remote_ip))
        if not self._running or ((limit is not None and len(self._sessions) >= limit or incoming_full)
                                 and not probing_incoming):
            self._stats['peer_limit_rejections'] += 1
            writer.close()
            return None
        session = _Session(reader, writer, outgoing)
        session.remote_ip = remote_ip
        self._sessions[id(writer)] = session
        if probing_incoming:
            self._incoming_probe = session
            now = self._peer_clock()
            self._next_incoming_probe = now + INCOMING_PROBE_INTERVAL
            if len(self._incoming_probe_sources) >= MAX_INVALID_PEER_IPS:
                self._incoming_probe_sources.pop(min(self._incoming_probe_sources,
                                                     key=self._incoming_probe_sources.get))
            self._incoming_probe_sources[remote_ip] = now + INCOMING_SOURCE_PROBE_INTERVAL
            self._incoming_probe_deadline = now + max(30, self.timeout * 6)
            self._stats['incoming_probes'] += 1
        self._stats['connections'] += 1
        return session

    def _accepted(self, reader, writer):
        # Filter the actual socket source before reserving session resources.
        # Private addresses are a scope restriction, not peer authentication.
        remote = writer.get_extra_info('peername')
        try:
            _endpoint(str(ipaddress.ip_address(remote[0])), remote[1], allow_lan=self.allow_lan,
                      allow_internet=self.allow_internet)
        except (ValueError, TypeError, IndexError):
            self._stats['address_rejections'] += 1
            writer.close()
            return
        session = self._reserve(reader, writer)
        if session is not None:
            self._spawn(self._run_session(session), 'incoming')

    async def _close_writer(self, writer):
        writer.close()
        try:
            await asyncio.wait_for(writer.wait_closed(), timeout=min(self.timeout, 1))
        except (OSError, TimeoutError, asyncio.CancelledError):
            # close() can keep flushing forever if a peer stops reading. Abort
            # after the graceful deadline to release the socket/server count.
            writer.transport.abort()

    async def _resolve_target(self, target):
        """Return a bounded checked numeric list; never dial the DNS string."""
        host, port = _endpoint(*target, allow_lan=self.allow_lan, allow_internet=self.allow_internet)
        if overlay_host(host):
            raise OSError('An overlay peer requires its matching privacy transport')
        try:
            ipaddress.ip_address(host)
        except ValueError:
            records = await asyncio.get_running_loop().getaddrinfo(
                host, port, family=socket.AF_UNSPEC, type=socket.SOCK_STREAM,
                proto=socket.IPPROTO_TCP,
            )
            permitted = []
            for record in records[:64]:
                try:
                    family, kind, protocol, _, address = record
                    if (family not in (socket.AF_INET, socket.AF_INET6) or kind != socket.SOCK_STREAM
                            or protocol not in (0, socket.IPPROTO_TCP)):
                        raise ValueError('Resolver returned a non-IP TCP address')
                    endpoint = _endpoint(str(ipaddress.ip_address(address[0])), port,
                                         allow_lan=self.allow_lan, allow_internet=self.allow_internet)
                    if (family == socket.AF_INET6) != (ipaddress.ip_address(endpoint[0]).version == 6):
                        raise ValueError('Resolver family does not match its numeric address')
                except (ValueError, TypeError, IndexError):
                    self._stats['address_rejections'] += 1
                    continue
                if endpoint not in permitted:
                    permitted.append(endpoint)
                if len(permitted) >= 8:
                    break
            if not permitted:
                raise OSError('DNS returned no permitted IP addresses')
            return tuple(permitted)
        return (_endpoint(host, port, allow_lan=self.allow_lan, allow_internet=self.allow_internet),)

    async def _open_target(self, target):
        if self._privacy.mode != 'direct':
            if not self.allow_internet:
                raise OSError('Internet connections are disabled')
            try:
                await self._ensure_privacy_router()
                return await self._privacy.open(target)
            except (ValueError, asyncio.IncompleteReadError) as error:
                raise OSError('Privacy transport could not connect to this peer') from error
        addresses = await self._resolve_target(target)
        last_error = None
        for address in addresses:
            if self._cooling_down(address[0]):
                self._stats['cooldown_rejections'] += 1
                continue
            try:
                # Only a checked numeric IP address reaches open_connection;
                # a DNS answer cannot change in a second hostname resolution.
                return await asyncio.wait_for(
                    asyncio.open_connection(*address, family=socket.AF_INET6 if ':' in address[0] else socket.AF_INET, limit=64 * 1024),
                    timeout=self.timeout / len(addresses),
                )
            except OSError as error:
                last_error = error
        raise last_error or OSError('No permitted peer address could be connected; an address may be temporarily cooling down')

    def _outgoing_session(self, target):
        return next((session for session in self._sessions.values()
                     if (session.outgoing == target or target in session.outgoing_aliases)
                     and not session.writer.is_closing()), None)

    async def _outgoing(self, target):
        delay = min(self.poll_interval, .25)
        while self._running:
            # Retain a healthy discovered session when registered manually.
            existing = self._outgoing_session(target)
            if existing is not None:
                if existing.ready:
                    self._configured[target].set()
                else:
                    self._configured[target].clear()
                await asyncio.sleep(min(self.poll_interval, .25))
                continue
            self._configured[target].clear()
            if self.max_peers is None or len(self._sessions) < self.max_peers + int(self._incoming_probe is not None):
                self._stats['reconnect_attempts'] += 1
                try:
                    reader, writer = await asyncio.wait_for(
                        self._open_target(target),
                        timeout=self._dial_timeout,
                    )
                    session = self._reserve(reader, writer, target)
                    if session is None:
                        await self._close_writer(writer)
                    else:
                        await self._run_session(session)
                        if session.version_rejected and target not in self._legacy_targets:
                            self._remember_legacy(target)
                            self._stats['legacy_fallbacks'] += 1
                            continue
                        if session.ready:
                            delay = min(self.poll_interval, .25)
                except (OSError, TimeoutError) as exc:
                    self._stats['connection_errors'] += 1
                    self._last_error = f'{type(exc).__name__}: {exc}'
                    self._record_peer_attempt(target, 'connect_timeout' if isinstance(exc, TimeoutError)
                                              else 'connect_failed', exc)
            if self._running:
                await asyncio.sleep(delay)
                delay = min(delay * 2, 10)

    def _discovery_endpoint(self, host, port):
        """Scope is checked by the book; transport validation is checked here."""
        return _endpoint(host, port, allow_lan=self.allow_lan, allow_internet=self.allow_internet)

    def _remember_legacy(self, target):
        if self.boundary_runtime is not None and target not in self._v3_targets:
            self._v3_targets.add(target)
            return
        if target not in self._v2_targets:
            self._v2_targets.add(target)
            return
        self._legacy_targets.add(target)

    def _own_listener(self):
        if self._privacy.mode != 'direct':
            return None
        if self.advertised_endpoint is not None:
            return self.advertised_endpoint
        if self.auto_address:
            return self._self_state.advertised_endpoint
        try:
            return self._addresses.validate(self.address)
        except ValueError:
            return None

    async def _refresh_own_addresses(self):
        """Replace runtime local hints, never persist adapter or own-IP data."""
        self._self_next_refresh = self._self_clock() + REFRESH_INTERVAL
        if self._privacy.mode != 'direct':
            self._self_state = SelfAddressState()
            self._lan_interface_hosts = ()
            return
        self._self_refresh_error = None
        interfaces = ()
        if (self.auto_address or (self.allow_lan and self.discover_peers)) and self.address[0] in ('0.0.0.0', '::'):
            try:
                interfaces = await enumerate_ipv4_interfaces()
            except OSError:
                self._self_refresh_error = 'interface_lookup_failed'
        self._lan_interface_hosts = tuple(item.host for item in interfaces[:32]
                                          if isinstance(item, InterfaceAddress))
        self._self_state = resolve_self_address(
            self.address, allow_internet=self.allow_internet, allow_lan=self.allow_lan,
            automatic=self.auto_address, manual_endpoint=self.advertised_endpoint,
            interfaces=interfaces, include_ipv6=self._server6 is not None,
        )
        if self._self_refresh_error and self.advertised_endpoint is None:
            self._self_state = SelfAddressState(self._self_state.own_addresses, None,
                                                'interface_lookup_failed')
        if self._running and self._lan_discovery is not None:
            await self._refresh_lan_discovery()
        if self._running and self._dht_discovery6 is not None:
            # Retry when IPv6 becomes available after startup or a network switch.
            await self._dht_discovery6.start()

    def _received_lan_hint(self, endpoint):
        # UDP grants no ready session, balance or block authority. Only the
        # existing TCP discovery worker can promote a fully synchronized peer.
        if endpoint not in self._self_state.own_addresses and endpoint != self.address:
            self._addresses.add_hint(endpoint)

    def _dht_contact(self):
        if not self._running or not self.allow_internet:
            return None
        if self._dht_scope == 'loopback':
            # Constructor-only non-main fixture: never a production endpoint.
            return self.address
        # Each DHT publishes only the contact matching its UDP address family.
        own = self._own_listener()
        if own is not None and ':' not in own[0]:
            return own
        return next((target for target in self._self_state.own_addresses
                     if ':' not in target[0] and ipaddress.ip_address(target[0]).is_global), None)

    def _dht_source_ipv6(self):
        if not self._running or not self.allow_internet or self._privacy.mode != 'direct':
            return None
        own = self._own_listener()
        if own is not None and ':' in own[0] and ipaddress.ip_address(own[0]).is_global:
            return own[0]
        return next((host for host, port in self._self_state.own_addresses
                     if ':' in host and ipaddress.ip_address(host).is_global), None)

    def _dht_contact_ipv6(self):
        if not (self._server6 is not None and self._server6.is_serving()
                or ':' in self.address[0] and self._listener_active()):
            return None
        source = self._dht_source_ipv6()
        return (source, self.address[1]) if source is not None else None

    def _has_dht_connected_peer(self):
        # A verified handshake is a connection. Temporary block-sync progress
        # does not mean the connection was lost or grant mining readiness.
        return self._running and any(session.ready and not session.writer.is_closing()
                                     for session in self._sessions.values())

    def _received_dht_hints(self, endpoints):
        own = self._connected_endpoints()
        for endpoint in endpoints[:MAX_BOOTSTRAP_HINTS]:
            if endpoint in own:
                continue
            try:
                self._addresses.add_hint(endpoint)
            except ValueError:
                continue

    async def _refresh_lan_discovery(self):
        if not (self.allow_lan and self.discover_peers and self._running):
            return
        interfaces = self._lan_interface_hosts + tuple(host for host, _ in self._self_state.own_addresses)
        candidate = LanDiscovery(self.network, self.address[1], self.nonce,
                                 self._received_lan_hint, interfaces)
        if self._lan_discovery is not None:
            if (self._lan_discovery.interfaces == candidate.interfaces
                    and self._lan_discovery.state in ('active', 'no_lan_interface')):
                return
            await self._lan_discovery.stop()
        self._lan_discovery = candidate
        await candidate.start()

    def _connected_endpoints(self):
        values = {session.outgoing for session in self._sessions.values() if session.outgoing is not None}
        for session in self._sessions.values():
            if not session.writer.is_closing():
                values.update(session.outgoing_aliases)
        values.add(self.address)
        values.update(self._self_state.own_addresses)
        if self.advertised_endpoint is not None:
            values.add(self.advertised_endpoint)
        return values

    def _add_bootstrap_hints(self, endpoints):
        accepted = 0
        for endpoint in endpoints[:MAX_BOOTSTRAP_HINTS]:
            if endpoint in self._connected_endpoints():
                continue
            try:
                if self._addresses.add_hint(endpoint):
                    accepted += 1
            except ValueError:
                # DNS/manifest addresses do not bypass the ordinary book's
                # numeric scope check or transport permission validation.
                continue
        self._bootstrap_stats['accepted_hints'] += accepted
        return accepted

    async def _refresh_bootstrap(self):
        self._bootstrap_stats['query_rounds'] += 1
        self._bootstrap_stats['provider_attempts'] += len(self._bootstrap_seeds)
        lookups = [asyncio.create_task(lookup_seed(seed, scope=self._bootstrap_scope, timeout=DNS_DEADLINE),
                                      name='sumuww-peer:bootstrap-dns') for seed in self._bootstrap_seeds]
        try:
            done, _ = await asyncio.wait(lookups, timeout=DNS_DEADLINE) if lookups else (set(), set())
            results = []
            for task in lookups:
                if task not in done or task.cancelled():
                    results.append(SeedResult(error='timeout'))
                else:
                    try:
                        results.append(task.result())
                    except Exception:
                        results.append(SeedResult(error='resolution_failed'))
        finally:
            for task in lookups:
                if not task.done():
                    task.cancel()
            if lookups:
                await asyncio.gather(*lookups, return_exceptions=True)
        errors = sum(result.error is not None for result in results)
        self._bootstrap_stats['provider_errors'] += errors
        endpoints = []
        # Interleave providers so one source cannot occupy the whole 128-hint
        # result budget ahead of every other independent source.
        for index in range(32):
            for result in results:
                if index < len(result.endpoints) and result.endpoints[index] not in endpoints:
                    endpoints.append(result.endpoints[index])
                if len(endpoints) == MAX_BOOTSTRAP_HINTS:
                    break
            if len(endpoints) == MAX_BOOTSTRAP_HINTS:
                break
        for endpoint in self._bootstrap_peers:
            if endpoint not in endpoints and len(endpoints) < MAX_BOOTSTRAP_HINTS:
                endpoints.append(endpoint)
        self._add_bootstrap_hints(tuple(endpoints))
        usable_dns = any(result.endpoints for result in results)
        if errors:
            self._bootstrap_stats['last_error'] = ('Some DNS seed providers failed' if usable_dns
                                                   else 'DNS seed providers did not return permitted addresses')
        else:
            self._bootstrap_stats['last_error'] = None
        if self._bootstrap_seeds and not usable_dns:
            self._bootstrap_failures = min(self._bootstrap_failures + 1, 4)
        else:
            self._bootstrap_failures = 0
        interval = min(MAX_QUERY_INTERVAL, MIN_QUERY_INTERVAL * 2 ** max(0, self._bootstrap_failures - 1))
        self._bootstrap_next_query = self._bootstrap_clock() + interval

    async def _bootstrap(self):
        while self._running:
            if (not self._discovery_settled()
                    and self._bootstrap_clock() >= self._bootstrap_next_query):
                await self._refresh_bootstrap()
            await asyncio.sleep(min(1, self.poll_interval * 2))

    async def _discover(self):
        """Dial discovered contacts; only explicit budgets require slot rotation."""
        worker_limit = self.healthy_peer_target
        while self._running:
            completed = [target for target, task in self._discovery_workers.items() if task.done()]
            for target in completed:
                self._discovery_workers.pop(target, None)
            self._explore_peer_path()
            healthy = self._healthy_sessions()
            healthy_targets = {session.outgoing for session in healthy if session.outgoing is not None}
            pending = sum(target not in healthy_targets for target in self._discovery_workers)
            healthy_identities = {session.nonce for session in healthy if session.outgoing is not None}
            goal=self._discovery_outgoing_target()
            missing = None if goal is None else goal - len(healthy_identities) - pending
            # Established learned workers already have a reserved session.
            # Count only workers which have not reserved a socket yet.
            unreserved = sum(self._outgoing_session(target) is None
                             for target in self._discovery_workers)
            self._addresses.prune()
            while ((missing is None or missing > 0) and
                    (worker_limit is None or len(self._discovery_workers) < worker_limit) and
                    (self.max_peers is None or len(self._sessions) + unreserved < self.max_peers
                    + int(self._incoming_probe is not None))):
                excluded = self._connected_endpoints() | set(self._configured) | set(self._discovery_workers)
                retry_cap = None if self._has_dht_connected_peer() else DISCONNECTED_PEER_RETRY_CAP
                target = self._addresses.candidate(excluded, retry_cap=retry_cap)
                if target is None:
                    break
                self._discovery_workers[target] = self._spawn(self._discovered_connection(target), 'learned-peer')
                unreserved += 1
                if missing is not None:missing -= 1
                await asyncio.sleep(0)
            await asyncio.sleep(min(1, self.poll_interval * 2))

    def _exploration_victims(self):
        # Prefer learned outgoing paths, then incoming paths, then manually
        # configured paths. Manual preferences remain saved for reconnection.
        # A verified replacement must already exist before any path is retired.
        candidates = [s for s in self._healthy_sessions()
                      if s.outgoing != self._exploration_target
                      or self._exploration_target is None]
        return sorted(candidates, key=lambda s: (2 if s.outgoing in self._configured
                                                 else 1 if s.outgoing is None else 0))

    def _explore_peer_path(self):
        if self.max_peers is None:return
        now = self._peer_clock()
        target = self._exploration_target
        if target is not None:
            task = self._discovery_workers.get(target)
            candidate = self._outgoing_session(target)
            healthy = self._healthy_sessions()
            if candidate is not None and candidate in healthy:
                victims = self._exploration_victims()
                if len(self._sessions) > self.max_peers and victims:
                    # A fully validated replacement already exists. Closing
                    # one old connection cannot remove the last anchor.
                    victims[0].writer.close()
                elif len(self._sessions) > self.max_peers:
                    candidate.writer.close()
                self._exploration_target = None
            elif task is None or task.done() or now >= self._exploration_deadline:
                if task is not None and not task.done():
                    task.cancel()
                if candidate is not None:
                    candidate.writer.close()
                self._exploration_target = None
            return
        if now < self._next_exploration:
            return
        self._next_exploration = now + PEER_EXPLORATION_INTERVAL
        if (len(self._sessions) != self.max_peers or not self._exploration_victims()
                or any(not task.done() and self._outgoing_session(peer) is None
                       for peer, task in self._discovery_workers.items())):
            return
        excluded = self._connected_endpoints() | set(self._configured) | set(self._discovery_workers)
        target = self._addresses.candidate(excluded)
        if target is None:
            return
        self._exploration_target = target
        self._exploration_deadline = now + max(30, self._dial_timeout + self.timeout * 6)
        self._discovery_workers[target] = self._spawn(self._discovered_connection(target), 'peer-exploration')

    async def _discovered_connection(self, target):
        session = None
        compatibility_retry = False
        transport_failed = False
        try:
            self._stats['reconnect_attempts'] += 1
            reader, writer = await asyncio.wait_for(self._open_target(target), timeout=self._dial_timeout)
            session = self._reserve(reader, writer, target)
            if session is None:
                await self._close_writer(writer)
                return
            await self._run_session(session)
            if session.version_rejected and target not in self._legacy_targets:
                self._remember_legacy(target)
                self._stats['legacy_fallbacks'] += 1
                compatibility_retry = True
                # Count this negotiated retry once; it is not a verified peer.
                return
        except (OSError, TimeoutError) as error:
            transport_failed = True
            self._stats['connection_errors'] += 1
            self._last_error = f'{type(error).__name__}: {error}'
            self._record_peer_attempt(target, 'connect_timeout' if isinstance(error, TimeoutError)
                                      else 'connect_failed', error)
        finally:
            if self._running and not compatibility_retry:
                if transport_failed or session is not None and session.failed:
                    self._forget_failed_contact(target)
                elif session is not None and session.cached:
                    self._addresses.attempted(target,success=True)

    def _forget_failed_contact(self,target):
        # Do not erase a healthy alternate transport to the same endpoint.
        if target in self._connected_endpoints():return
        self._addresses.attempted(target,success=False)
        self._v3_targets.discard(target)
        self._v2_targets.discard(target)
        self._legacy_targets.discard(target)
        for session in self._sessions.values():
            session.outgoing_aliases.discard(target)
            session.completed_contacts.discard(target)

    async def _ensure_privacy_router(self):
        if self._managed_router is not None:
            try:
                self._privacy.options['port'] = await self._managed_router.ensure_running()
                self._router_error = None
            except (OSError, ValueError, KeyError):
                self._router_error = 'Embedded privacy router unavailable; no direct fallback'
                raise OSError(self._router_error) from None

    async def _maintain_privacy_router(self):
        delay = 1
        while self._running:
            try:
                await self._ensure_privacy_router()
                delay = 1
            except OSError:
                delay = min(30, max(5, delay*2))
            await asyncio.sleep(delay)

    async def _accept_i2p(self):
        while self._running:
            try:
                # Waiting for an incoming overlay stream does not block polling
                # or other connections. Cancelling shutdown closes its socket.
                await self._ensure_privacy_router()
                reader, writer = await self._privacy.accept()
                self._accepted(reader, writer)
            except (OSError, ValueError, asyncio.IncompleteReadError, UnicodeError):
                self._last_error = 'I2P router unavailable; no direct fallback'
                await asyncio.sleep(5)

    async def _request_addresses(self, session, now=None):
        if not self.discover_peers or session.protocol < DISCOVERY_PROTOCOL_VERSION:
            return
        if (self._discovery_settled()
                and self._peer_clock() < self._next_exploration - self.discovery_interval):
            return
        now = asyncio.get_running_loop().time() if now is None else now
        if session.discovery_requested or now - session.last_discovery_request < self.discovery_interval:
            return
        session.discovery_requested = True
        session.discovery_reply_pending = True
        session.last_discovery_request = now
        await self._send(session, 'getaddr')
        self._stats['address_requests_sent'] += 1

    async def _serve_addresses(self, session, payload):
        if payload:
            raise MalformedWireData('getaddr must have an empty payload')
        now = asyncio.get_running_loop().time()
        if now - session.last_discovery_response < self.discovery_interval:
            self._stats['address_rate_rejections'] += 1
            return
        session.last_discovery_response = now
        own = self._own_listener()
        if session.protocol < IPV6_PROTOCOL_VERSION and own is not None and ':' in own[0]:
            own = next((item for item in self._self_state.own_addresses if ':' not in item[0]
                        and ipaddress.ip_address(item[0]).is_global), None)
        own_alternates = tuple(endpoint for endpoint in self._self_state.own_addresses
                               if ipaddress.ip_address(endpoint[0]).is_global)
        # A full hub cannot reverse-dial every incoming peer before sharing
        # its listener. Forward only current validated peers' scoped listener
        # claims as hints. Recipients still dial, handshake and validate them;
        # no claim is persisted as verified or grants chain/mining authority.
        live_listeners = tuple(other.remote_listener for other in self._healthy_sessions()
                               if other is not session and other.remote_listener is not None)
        contacts = tuple(dict.fromkeys(own_alternates + live_listeners
                                      + self._addresses.known(MAX_ADDRESSES)))
        known = tuple(PeerAddress(*endpoint) for endpoint in contacts
                      if endpoint != own and (session.protocol >= IPV6_PROTOCOL_VERSION or ':' not in endpoint[0]))
        await self._send(session, 'addr', encode_addresses(
            PeerAddress(*own) if own is not None else None,
            known[:MAX_ADDRESSES - bool(own)]))
        self._stats['address_responses_sent'] += 1
        session.address_reply_sent = True

    def _received_addresses(self, session, payload):
        if not session.discovery_requested and not session.discovery_reply_pending:
            self._stats['address_rate_rejections'] += 1
            if math.isfinite(session.last_discovery_request):
                # This wire has no request IDs. A delayed duplicate from an
                # expired/retried round cannot be matched to a newer query.
                # Ignore it without admitting hints or evicting a valid peer.
                self._trace_event('stale_address_reply_ignored',session)
                return
            raise ProtocolError('Unsolicited peer address response')
        listener, peers = _decode_payload(decode_addresses, payload)
        session.discovery_requested = False
        session.discovery_reply_pending = False
        # Count from the completed round trip: decreasing one-way latency must
        # not make our next request violate an older peer's receive interval.
        session.last_discovery_request = asyncio.get_running_loop().time()
        values = ((listener,) if listener is not None else ()) + peers
        response = []
        session.address_response_count += 1
        for item in values:
            row = {'host': item.host, 'port': item.port, 'listener': item is listener}
            response.append(row)
            try:
                if ':' in item.host and session.protocol < IPV6_PROTOCOL_VERSION:
                    raise ValueError('IPv6 exchange requires protocol v3')
                target = self._addresses.validate((item.host, item.port))
                if target in self._self_state.own_addresses or target in (self.address, self.advertised_endpoint):
                    row['result'] = 'self_address'
                    continue
                if item is listener:
                    session.remote_listener = target
                if self._addresses.add_hint(target):
                    row['result'] = 'added_candidate'
                    self._stats['address_hints_received'] += 1
                else:
                    row['result'] = 'already_known_or_retry_suppressed'
            except ValueError:
                row['result'] = 'rejected_scope_or_protocol'
                self._stats['address_hints_rejected'] += 1
        session.last_address_response = tuple(response)

    def _cache_synchronized_endpoint(self, session):
        if not session.synchronized:
            return
        # Compatibility probes describe one connection attempt, not a durable
        # peer capability. A transient pre-version close must not pin a modern
        # listener to v1/v2 on every later connection and suppress IPv6 exchange.
        protocol_targets = (session.outgoing_aliases | session.completed_contacts
                            | ({session.outgoing} if session.outgoing else set()))
        self._v2_targets.difference_update(protocol_targets)
        self._v3_targets.difference_update(protocol_targets)
        self._legacy_targets.difference_update(protocol_targets)
        targets = set(session.completed_contacts)
        if not session.cached and session.outgoing is not None:
            targets.add((session.remote_ip, session.outgoing[1]))
            self._record_peer_attempt(session.outgoing, 'synchronized')
        # Persist the actual resolved listening address, not a DNS claim or
        # an incoming connection's ephemeral source port.
        for target in targets:
            try:
                self._addresses.verified(target)
                session.cached = True
            except ValueError:
                pass
        session.completed_contacts.clear()
        # An alternate direction must finish full synchronization before it
        # can retire an unfinished original route. The remote node may reject
        # the alternate to preserve its already synchronized original route.
        if session.replacement is not None:
            previous, session.replacement = session.replacement, None
            previous.cached = True
            previous.writer.close()

    async def _take_quota(self, session, kind, amount):
        """Reserve bounded per-peer credits atomically before yielding.

        There is one incoming actor and the existing poll actor per session.
        Negative credits reserve their finite future allowance; there is no
        request queue or new task here, and another peer has separate credits.
        """
        capacity, rate = {'work': (PEER_WORK_BURST, PEER_WORK_RATE),
                          'inventory': (PEER_INVENTORY_BURST, PEER_INVENTORY_RATE),
                          'validation': (PEER_VALIDATION_BURST, PEER_VALIDATION_RATE),
                          'egress': (PEER_EGRESS_BURST, PEER_EGRESS_RATE)}[kind]
        if amount > capacity:
            self._stats['quota_rejections'] += 1
            raise ProtocolError('Peer operation exceeds its bounded allowance')
        now = asyncio.get_running_loop().time()
        updated = getattr(session, kind + '_updated')
        credit = min(capacity, getattr(session, kind + '_credit') + max(0, now - updated) * rate)
        credit -= amount
        setattr(session, kind + '_credit', credit)
        setattr(session, kind + '_updated', now)
        delay = max(0, -credit / rate)
        if delay > MAX_QUOTA_DELAY:
            self._stats['quota_rejections'] += 1
            raise ProtocolError('Peer quota backpressure deadline exceeded')
        if delay:
            self._stats['quota_' + kind + '_waits'] += 1
            self._stats['quota_wait_seconds'] += delay
            await asyncio.sleep(delay)

    async def _send(self, session, command, payload=b''):
        from .boundary_transport import COMMANDS,PART_BYTES,send_parts
        from .wire import _payload_limit
        if command in COMMANDS and len(payload)>min(PART_BYTES,_payload_limit(command)):
            if self.boundary_runtime is None or not session.boundary_id:
                raise ProtocolError('Authenticated boundary multipart transport required')
            return await send_parts(self,session,command,payload)
        # Concurrent polling and response handling share one bounded writer.
        await self._take_quota(session, 'egress', len(payload) + 24)
        try:
            await asyncio.wait_for(session.send_lock.acquire(), timeout=self.timeout)
        except TimeoutError as exc:
            raise ProtocolError('Peer send-lock deadline exceeded') from exc
        try:
            await write_frame(session.writer, command, payload, timeout=self.timeout,
                              magic=self.network.message_magic)
            self._stats['frames_sent'] += 1
        finally:
            session.send_lock.release()

    async def _read(self, session):
        reader=session.reader
        if self._trace_file and not session.ready:
            # Observe exactly the bytes read by the ordinary decoder. Never
            # consume additional stream bytes or relax its network checks.
            original=reader
            node=self
            class HeaderTraceReader:
                async def readexactly(self,size):
                    data=await original.readexactly(size)
                    if size==24 and data[:4]!=node.network.message_magic:
                        node._trace_event('network_header_mismatch',session,
                                          received_magic=data[:4].hex(),expected_magic=node.network.message_magic.hex(),
                                          header_hex=data.hex())
                    return data
            reader=HeaderTraceReader()
        frame = await read_frame(reader, timeout=self.timeout, magic=self.network.message_magic,
                                 idle_timeout=max(self.timeout, CONNECTED_REPLY_TIMEOUT) if session.ready else None)
        self._stats['frames_received'] += 1
        return frame

    async def _handshake(self, session):
        requested = ((DISCOVERY_PROTOCOL_VERSION if session.outgoing in self._v2_targets else IPV6_PROTOCOL_VERSION) if self.discover_peers and session.outgoing is not None
                     and session.outgoing not in self._legacy_targets else PROTOCOL_VERSION)
        if (self.boundary_runtime is not None and session.outgoing is not None and
                session.outgoing not in self._v3_targets and session.outgoing not in self._v2_targets and session.outgoing not in self._legacy_targets):
            requested=BOUNDARY_PROTOCOL_VERSION
        session.attempted_protocol = requested
        own = Version(requested, self.genesis, self.nonce, self.network.profile_id, self.chain.tip_hash)
        session.handshake_stage = 'sending_version'
        await self._send(session, 'version', encode_version(own))
        session.handshake_stage = 'waiting_version'
        frame = await self._read(session)
        if frame.command != 'version':
            raise ProtocolError('Expected version as the first peer message')
        remote = _decode_payload(decode_version, frame.payload)
        if remote.genesis != self.genesis or remote.profile != self.network.profile_id:
            raise ProtocolError('Peer protocol/profile/genesis mismatch')
        if remote.protocol not in (PROTOCOL_VERSION, DISCOVERY_PROTOCOL_VERSION, IPV6_PROTOCOL_VERSION, 4, BOUNDARY_PROTOCOL_VERSION):
            raise ProtocolError('Unsupported peer protocol version')
        if remote.protocol in (4,BOUNDARY_PROTOCOL_VERSION) and self.boundary_runtime is None:
            raise ProtocolError('Boundary protocol is not enabled on this node')
        if remote.nonce == self.nonce:
            raise ProtocolError('Self connection nonce')
        session.nonce = remote.nonce
        session.legacy_candidate = (requested >= DISCOVERY_PROTOCOL_VERSION and
                                    remote.protocol == PROTOCOL_VERSION)
        if not self.chain.has_block(remote.tip):
            session.unknown_blocks.add(remote.tip)
        session.handshake_stage = 'waiting_verack'
        await self._send(session, 'verack')
        frame = await self._read(session)
        if frame.command != 'verack' or frame.payload:
            raise ProtocolError('Expected an empty verack')
        # A process nonce is a session identity hint, not an authenticated key.
        # Never let a new nonce claim replace an established synchronized peer.
        duplicates = [other for other in self._sessions.values()
                      if other is not session and other.ready and other.nonce == remote.nonce
                      and not other.writer.is_closing()]
        if duplicates:
            existing = duplicates[0]
            preferred_outgoing = self.nonce < remote.nonce
            if (not existing.synchronized and
                    (session.outgoing is not None) == preferred_outgoing and
                    (existing.outgoing is not None) != preferred_outgoing):
                survivor, redundant = session, existing
            else:
                survivor, redundant = existing, session
            aliases = redundant.outgoing_aliases | ({redundant.outgoing} if redundant.outgoing else set())
            survivor.outgoing_aliases.update(aliases)
            # Retain proof of the actual alternate TCP handshake until the
            # surviving session finishes validating its chain. A cross-dial
            # can finish before either route has synchronized.
            contacts = redundant.completed_contacts | survivor.completed_contacts
            for completed in (session, existing):
                if completed.outgoing is not None:
                    contacts.add((completed.remote_ip, completed.outgoing[1]))
            survivor.completed_contacts = set(contacts)
            existing.completed_contacts.update(contacts)
            # A completed alternate TCP contact remains a reconnect hint;
            # the address cache never grants chain readiness.
            if survivor.synchronized:
                self._cache_synchronized_endpoint(survivor)
            self._stats['duplicate_connection_rejections'] += 1
            if redundant is existing:
                session.replacement = existing
            else:
                redundant.cached = True
                self._record_peer_attempt(redundant.outgoing, 'duplicate_node')
                redundant.writer.close()
                return
        session.handshake_stage = 'established'
        session.ready = True
        session.last_keepalive_at = asyncio.get_running_loop().time()
        # Legacy listeners reject a v2 request before verack. Their new v1
        # identity is compatible; a successful acknowledgement explicitly
        # accepts the outgoing v2 request, without extending v1 payload bytes.
        session.protocol = max(requested, remote.protocol)
        self._stats['handshakes'] += 1
        if session.outgoing is not None:
            if session.outgoing in self._configured:
                self._configured[session.outgoing].set()
        await self._request_headers(session)
        await self._request_addresses(session)
        if session.protocol>=BOUNDARY_PROTOCOL_VERSION and session.outgoing is not None:
            await self.boundary_runtime.hello(session)
        self._trace_event('transport_ready',session)

    async def _run_session(self, session):
        try:
            await asyncio.wait_for(self._handshake(session), timeout=self.timeout)
            if not session.ready:
                return
            while self._running:
                await self._handle(session, await self._read(session))
        except asyncio.CancelledError:
            raise
        except BoundaryPolicyMismatch as exc:
            session.version_rejected=True
            self._record_peer_attempt(session.outgoing,'native_policy_fallback',exc,session=session)
        except UnsupportedFeature as exc:
            # This profile cannot evaluate the feature; do not cache its hash
            # as consensus-invalid. A future session may retry the same block.
            self._stats['unsupported_features'] += 1
            self._last_error = f'UnsupportedFeature: {exc}'
        except ValidationError as exc:
            self._stats['validation_rejections'] += 1
            self._last_error = f'ValidationError: {exc}'
            if isinstance(exc, InvalidBlock):
                self._record_invalid_peer(session)
        except PeerDisconnected:
            session.failed=not session.writer.is_closing()
            self._stats['disconnects'] += 1
            self._record_peer_attempt(session.outgoing, 'disconnected' if session.ready else 'handshake_closed', session=session)
            if (not session.ready and session.outgoing is not None
                    and session.attempted_protocol > PROTOCOL_VERSION
                    and (session.legacy_candidate or session.handshake_stage == 'waiting_version')):
                # A strict listener can close before returning its version.
                # Probe only the two supported older versions; genesis, profile,
                # full block validation and readiness checks remain mandatory.
                session.version_rejected = True
        except (ProtocolError, TimeoutError) as exc:
            session.failed=True
            self._stats['protocol_errors'] += 1
            self._last_error = f'{type(exc).__name__}: {exc}'
            self._record_peer_attempt(session.outgoing, 'session_rejected' if session.ready
                                      else 'handshake_failed', exc, session=session)
            if isinstance(exc, MalformedWireData):
                self._record_invalid_peer(session)
        except OSError as exc:
            session.failed=True
            self._stats['connection_errors'] += 1
            if (not session.ready and session.outgoing is not None
                    and session.attempted_protocol > PROTOCOL_VERSION
                    and (session.legacy_candidate or
                         isinstance(exc, (ConnectionResetError, BrokenPipeError))
                         and session.handshake_stage in ('sending_version', 'waiting_version'))):
                session.version_rejected = True
            if session.ready:
                self._stats['disconnects'] += 1
            self._last_error = f'{type(exc).__name__}: {exc}'
            self._record_peer_attempt(session.outgoing, 'session_failed' if session.ready
                                      else 'handshake_failed', exc, session=session)
        finally:
            self._trace_event('transport_closed',session,failed=session.failed,reason=session.local_close_reason)
            self._sessions.pop(id(session.writer), None)
            if self._running and (session.failed or session.local_close_reason) and not session.version_rejected:
                targets=session.outgoing_aliases | ({session.outgoing} if session.outgoing else set())
                if session.outgoing is not None:targets.add((session.remote_ip,session.outgoing[1]))
                for target in targets:self._forget_failed_contact(target)
            if self.boundary_runtime is not None:
                self.boundary_runtime.parts.discard(session)
            if self._incoming_probe is session:
                self._incoming_probe = None
            if session.outgoing is not None:
                if session.outgoing in self._configured:
                    self._configured[session.outgoing].clear()
            await self._close_writer(session.writer)

    async def _request_headers(self, session):
        if (not session.ready or session.header_requested or session.headers
                or session.hint_requested is not None or session.hint_blocks):
            return
        branch = session.branch_tip
        locator = self.chain.block_locator(branch) if branch is not None else self.chain.block_locator()
        now = asyncio.get_running_loop().time()
        session.header_requested = True
        session.requested_block_hints = set(session.unknown_blocks)
        session.header_requested_at = now
        session.last_headers_at = now
        await self._send(session, 'getheaders', encode_getheaders(locator))

    async def _received_headers(self, session, payload):
        headers = _decode_payload(decode_headers, payload)
        if not session.header_requested or session.headers:
            raise ProtocolError('Unsolicited or overlapping headers response')
        session.header_requested = False
        self._stats['headers_received'] += len(headers)
        if not headers:
            session.unknown_blocks.difference_update(
                digest for digest in tuple(session.unknown_blocks) if self.chain.has_block(digest))
            if session.unknown_blocks:
                session.synchronized = False
                # Inventory arriving during an already in-flight refresh may
                # be newer than its response. Give it a fresh locator cycle;
                # a peer withholding a previously promised tip is unusable.
                if session.unknown_blocks & session.requested_block_hints:
                    if not session.hint_branch_progress:
                        raise ProtocolError('Peer announced blocks absent from its completed headers cycle')
                    # A valid replacement branch may leave an earlier tip on
                    # an inactive branch. Require that tip's full body rather
                    # than treating an ordinary reorg as withholding.
                    await self._request_hint_block(session, min(session.unknown_blocks))
                    return
                await self._request_headers(session)
            else:
                session.headers_continuing = False
                session.synchronized = True
                session.live_update_pending = False
                session.verified_once = True
                session.last_verified_at = self._peer_clock()
                session.hint_branch_progress = False
                self._cache_synchronized_endpoint(session)
            return
        if not self.chain.has_block(headers[0].previous_hash):
            raise ProtocolError('Header batch is not anchored in a validated block')
        expected = headers[0].previous_hash
        seen = set()
        for header in headers:
            digest = header.digest()
            if (header.previous_hash != expected or digest in seen or header.version < 4
                    or not check_pow(digest, header.bits, self.network.pow_limit)):
                raise MalformedWireData('Invalid PoW/version/nBits/header order')
            seen.add(digest)
            expected = digest
        needs_bodies = any(not self.chain.has_block(header.digest()) for header in headers)
        session.headers_continuing = True
        if needs_bodies:
            first_unknown = next(header for header in headers if not self.chain.has_block(header.digest()))
            # Continue on the validated tip only during an ordinary extension.
            # Initial catchup, alternate forks and stale-tip body recovery still pause.
            session.live_update_pending = (session.live_update_pending and
                first_unknown.previous_hash == self.chain.tip_hash)
            session.synchronized = False
        session.headers.extend(headers)
        # Header PoW and linkage are bounded hints, not accepted chainwork.
        # Contextual expected nBits is derived from validated branch ancestors
        # by Chain.accept_block after the matching full body has been fetched.
        await self._advance_blocks(session, refresh=needs_bodies)

    async def _advance_blocks(self, session, *, refresh=True):
        while session.headers:
            header = session.headers[0]
            digest = header.digest()
            if self.chain.has_block(digest) and digest not in session.block_requests:
                session.hint_branch_progress = True
                session.unknown_blocks.discard(digest)
                session.branch_tip = digest
                session.headers.popleft()
            else:
                # Pipeline body downloads over the existing ordered TCP wire.
                # The window bounds transport memory, never witness discovery.
                requested=[]
                for candidate in session.headers:
                    key=candidate.digest()
                    if key not in session.block_requests and not self.chain.has_block(key):
                        requested.append(Inventory(INV_BLOCK,key))
                    if len(session.block_requests)+len(requested)>=16:break
                if requested:
                    if not session.block_requests:session.block_requested_at = asyncio.get_running_loop().time()
                    session.block_requests.update(item.digest for item in requested)
                    await self._send(session, 'getdata', encode_inventory(tuple(requested)))
                return
        # Continue from the validated branch tip even while it is shorter than
        # the active chain. Using only the active locator here breaks catchup.
        if not refresh:
            # A growing peer can repeatedly return a single header already
            # validated through another session. Coalesce that known-only
            # refresh until the next poll, measured from response completion.
            # Full-body progression and newly announced tips stay immediate.
            session.last_headers_at = asyncio.get_running_loop().time()
            return
        await self._request_headers(session)

    async def _received_block(self, session, payload):
        if not session.headers and session.hint_requested is None:
            raise ProtocolError('Unsolicited block')
        try:
            block = Block.deserialize(payload)
        except ValidationError as exc:
            raise MalformedWireData(str(exc)) from exc
        hint = session.hint_requested is not None
        if (block.serialize() != payload or
                (block.block_hash() != session.hint_requested if hint else block.header != session.headers[0])):
            raise MalformedWireData('Block is noncanonical or differs from its requested header')
        self._stats['blocks_received'] += 1
        if hint:
            await self._received_hint_block(session, block, len(payload))
            return
        known = self.chain.has_block(block.block_hash())
        previous_tip = self.chain.tip_hash
        envelope=self.boundary_runtime.proofs.get(block.block_hash()) if self.boundary_runtime is not None else None
        self.chain.accept_block(block,boundary_envelope=envelope)
        if not self.chain.has_block(block.block_hash()):
            raise ProtocolError('Block did not enter the validated block index')
        if not known:
            self._stats['blocks_stored'] += 1
        if (session.live_update_pending and block.header.previous_hash == previous_tip
                and self.chain.tip_hash == block.block_hash()):
            # Concrete full-body progress renews only an already verified live
            # anchor. Initial catchup and unknown forks remain gated.
            session.last_verified_at = self._peer_clock()
        session.branch_tip = block.block_hash()
        session.hint_branch_progress = True
        session.unknown_blocks.discard(block.block_hash())
        session.headers.popleft()
        session.block_requests.discard(block.block_hash())
        session.block_requested_at = asyncio.get_running_loop().time()
        await self._advance_blocks(session)

    async def _request_hint_block(self, session, digest):
        if session.hint_requested is not None:
            return
        session.synchronized = False
        session.live_update_pending = False
        session.hint_requested = digest
        session.hint_requested_at = asyncio.get_running_loop().time()
        await self._send(session, 'getdata', encode_inventory((Inventory(INV_BLOCK, digest),)))

    async def _received_hint_block(self, session, block, size):
        digest = block.block_hash()
        if (len(session.hint_blocks) >= MAX_HINT_BLOCKS or
                session.hint_block_bytes + size > MAX_HINT_BLOCK_BYTES):
            raise ProtocolError('Stale peer branch exceeds the bounded body budget')
        session.hint_requested = None
        session.hint_blocks[digest] = (block, size)
        session.hint_block_bytes += size
        # Walk ancestors one body at a time, then validate forward using the
        # ordinary contextual header, PoW, transaction and signature checks.
        while session.hint_blocks:
            progressed = False
            for candidate, (pending, pending_size) in tuple(session.hint_blocks.items()):
                if not self.chain.has_block(pending.header.previous_hash):
                    continue
                known = self.chain.has_block(candidate)
                envelope=self.boundary_runtime.proofs.get(candidate) if self.boundary_runtime is not None else None
                self.chain.accept_block(pending,boundary_envelope=envelope)
                if not self.chain.has_block(candidate):
                    raise ProtocolError('Stale block did not enter the validated block index')
                if not known:
                    self._stats['blocks_stored'] += 1
                session.unknown_blocks.discard(candidate)
                del session.hint_blocks[candidate]
                session.hint_block_bytes -= pending_size
                progressed = True
            if not progressed:
                parent = block.header.previous_hash
                if parent in session.hint_blocks:
                    raise MalformedWireData('Cyclic stale peer branch')
                await self._request_hint_block(session, parent)
                return
        await self._request_headers(session)

    async def _received_inventory(self, session, payload, *, items=None):
        items = _decode_payload(decode_inventory, payload) if items is None else items
        need_headers = False
        now = asyncio.get_running_loop().time()
        for item in items:
            if item.kind == INV_BLOCK:
                if not self.chain.has_block(item.digest):
                    session.unknown_blocks.add(item.digest)
                    if len(session.unknown_blocks) > MAX_INV:
                        raise ProtocolError('Too many unresolved block inventory hints')
                    need_headers = True
            elif (not self.chain.has_mempool_transaction(item.digest)
                    and item.digest not in session.tx_requests):
                self._queue_transaction(session, item.digest, now)
        if need_headers:
            if session.synchronized and session.verified_once:
                session.live_update_pending = True
            session.synchronized = False
        await self._fill_transaction_requests(session, now)
        if need_headers:
            await self._request_headers(session)

    def _queue_transaction(self, session, digest, due):
        if digest in session.tx_requests:
            return
        if digest in session.pending_transactions:
            session.pending_transactions[digest] = min(session.pending_transactions[digest], due)
            return
        if len(session.pending_transactions) + len(session.tx_requests) >= MAX_PENDING_TRANSACTIONS:
            # Prefer a fresh announcement over a previously rejected/expired
            # hint. The active 256 requests cannot be displaced by a flood.
            replaceable = next((value for value, retry in session.pending_transactions.items()
                                if retry > asyncio.get_running_loop().time()), None)
            if replaceable is None:
                self._stats['transaction_hint_drops'] += 1
                return
            session.pending_transactions.pop(replaceable)
        session.pending_transactions[digest] = due

    async def _fill_transaction_requests(self, session, now=None):
        now = asyncio.get_running_loop().time() if now is None else now
        wants = []
        for digest, due in tuple(session.pending_transactions.items()):
            if len(session.tx_requests) >= MAX_INV:
                break
            if due > now:
                continue
            session.pending_transactions.pop(digest)
            if self.chain.has_mempool_transaction(digest):
                continue
            session.tx_requests[digest] = now
            wants.append(Inventory(INV_TRANSACTION, digest))
        if wants:
            await self._send(session, 'getdata', encode_inventory(tuple(wants)))

    async def _serve_data(self, session, payload):
        missing = []
        seen = set()
        for item in _decode_payload(decode_inventory, payload):
            # Repeated items in one bounded request carry no new information.
            # Serve each body once so duplicate hashes cannot multiply DB
            # reads, serialization and outbound bytes by the inventory limit.
            if item in seen:
                continue
            seen.add(item)
            if item.kind == INV_BLOCK and self.chain.has_block(item.digest):
                block=self.chain.get_block(item.digest)
                envelope=self.chain.boundary.proof(item.digest)
                if envelope is not None and session.protocol>=BOUNDARY_PROTOCOL_VERSION:
                    from .boundary_runtime import encode_block
                    await self._send(session,'bblock',encode_block(block,envelope))
                else:
                    await self._send(session, 'block', block.serialize())
            elif item.kind == INV_TRANSACTION:
                transaction = self.chain.get_mempool_transaction(item.digest)
                if transaction is not None:
                    await self._send(session, 'tx', transaction.serialize())
                else:
                    missing.append(item)
            else:
                missing.append(item)
        if missing:
            await self._send(session, 'notfound', encode_inventory(tuple(missing)))

    async def _received_transaction(self, session, payload):
        try:
            transaction = Transaction.deserialize(payload)
        except ValidationError as exc:
            raise MalformedWireData(str(exc)) from exc
        digest = transaction.txid()
        if transaction.serialize() != payload or digest not in session.tx_requests:
            raise ProtocolError('Unsolicited or noncanonical transaction')
        del session.tx_requests[digest]
        self._stats['transactions_received'] += 1
        if self.chain.has_mempool_transaction(digest):
            await self._fill_transaction_requests(session)
            return
        try:
            self.chain.submit_transaction(transaction)
            self._stats['transactions_accepted'] += 1
            # A newly accepted parent can make a rejected child usable. Wake a
            # bounded subset; ordinary pending arrivals remain in FIFO order.
            woke = 0
            for value, due in tuple(session.pending_transactions.items()):
                if due > asyncio.get_running_loop().time():
                    session.pending_transactions[value] = 0
                    woke += 1
                    if woke == 32:
                        break
        except UnsupportedFeature:
            self._stats['unsupported_features'] += 1
        except ValidationError:
            # Missing parents, local pool limits and conflicting chain context
            # may change. Drop this attempt without an invalid-hash cache.
            self._stats['validation_rejections'] += 1
            self._queue_transaction(session, digest,
                                    asyncio.get_running_loop().time() + TRANSACTION_RETRY_INTERVAL)
        await self._fill_transaction_requests(session)

    def _inventory_work(self, session, payload):
        # The previous protocol periodically advertised its unchanged pool.
        # Decode at most 256 canonical hints before admission, with no DB work.
        # Recency only discounts work; every hint still uses the ordinary
        # request and full-validation path, even after a reorg or pool removal.
        items = _decode_payload(decode_inventory, payload)
        cost = 1 + sum(item not in session.recent_inventory for item in set(items))
        for item in items:
            if item not in session.recent_inventory:
                if len(session.recent_inventory) >= MAX_RECENT_INVENTORY:
                    session.recent_inventory.pop(next(iter(session.recent_inventory)))
                session.recent_inventory[item] = None
        return items, cost

    async def _handle(self, session, frame):
        command, payload = frame.command, frame.payload
        inventory = None
        cost = (256 if command == 'getheaders' else
                1 + len(payload) // 36 if command in ('getdata', 'inv', 'notfound') else
                1 + len(payload) // 80 if command == 'headers' else 1)
        if command == 'inv':
            inventory, cost = self._inventory_work(session, payload)
        await self._take_quota(session, 'work', cost)
        if inventory is not None:
            # Even an unchanged canonical inventory requires indexed DB
            # membership checks. Budget every item before that work begins.
            await self._take_quota(session, 'inventory', len(inventory))
        if command in ('block', 'tx','bblock','bcall','bquery','bresponse','bhello','bpart'):
            # Account at the byte boundary before deserialization/signatures.
            await self._take_quota(session, 'validation', len(payload))
        if command in ('bblock','bcall','bquery','bresponse','bhello','bpart'):
            if session.protocol == 4:
                # Old incoming v4 peers may continue native block/tx/address
                # synchronization. Do not send our incompatible hello to them.
                if command == 'bblock':
                    from .boundary_runtime import decode_block
                    raw,_=decode_block(payload)
                    await self._received_block(session,raw)
                return
            if self.boundary_runtime is None:raise ProtocolError('Boundary protocol is unavailable')
            try:await self.boundary_runtime.handle(session,command,payload)
            except (ValueError,KeyError,TypeError) as error:raise MalformedWireData(str(error)) from error
            if command=='bhello':self._trace_event('boundary_authenticated',session)
        elif command == 'getheaders':
            locator, stop = _decode_payload(decode_getheaders, payload)
            await self._send(session, 'headers', encode_headers(self.chain.headers_after(locator, stop, MAX_HEADERS)))
        elif command == 'headers':
            await self._received_headers(session, payload)
        elif command == 'inv':
            await self._received_inventory(session, payload, items=inventory)
        elif command == 'getdata':
            await self._serve_data(session, payload)
        elif command == 'block':
            await self._received_block(session, payload)
        elif command == 'tx':
            await self._received_transaction(session, payload)
        elif command == 'notfound':
            for item in _decode_payload(decode_inventory, payload):
                if item.kind == INV_TRANSACTION:
                    session.tx_requests.pop(item.digest, None)
                elif ((session.headers and session.headers[0].digest() == item.digest)
                      or session.hint_requested == item.digest):
                    # A header without its body cannot complete synchronization
                    # or prove spendable funds. Reconnect rather than promote
                    # this peer after a subsequent empty headers response.
                    session.synchronized = False
                    raise ProtocolError('Peer cannot provide its requested block body')
            await self._fill_transaction_requests(session)
        elif command == 'ping':
            await self._send(session, 'pong', encode_ping(_decode_payload(decode_ping, payload)))
        elif command == 'pong':
            _decode_payload(decode_ping, payload)
        elif command in ('getaddr', 'addr'):
            if session.protocol < DISCOVERY_PROTOCOL_VERSION:
                raise ProtocolError('Peer address exchange was not negotiated')
            if command == 'getaddr':
                await self._serve_addresses(session, payload)
            else:
                self._received_addresses(session, payload)
        else:
            raise ProtocolError(f'Unexpected command after handshake: {command}')

    async def _poll(self):
        while self._running:
            if self._trace_file and self._peer_clock()>=self._trace_next:
                self._trace_next=self._peer_clock()+10
                self._trace_event('snapshot',state=self.info(include_state=False),sessions=[{
                    'nonce':s.nonce,'remote':s.remote_ip,'outgoing':s.outgoing,'ready':s.ready,
                    'synchronized':s.synchronized,'verified_once':s.verified_once,
                    'last_verified_age':self._peer_clock()-s.last_verified_at,
                    'protocol':s.protocol,'boundary_policy':s.boundary_policy,
                } for s in self._sessions.values() if not s.writer.is_closing()])
            if self.boundary_runtime is not None:await self.boundary_runtime.refresh()
            self._retire_duplicate_transports()
            self._maintain_incoming_probe()
            if (self.auto_address or (self.allow_lan and self.discover_peers)) and self._self_clock() >= self._self_next_refresh:
                if self._self_refresh_task is None or self._self_refresh_task.done():
                    self._self_refresh_task = self._spawn(self._refresh_own_addresses(), 'self-address')
            with self.chain.read_snapshot():
                tip = self.chain.tip_hash
                # Read IDs without repeatedly deserializing an unchanged pool.
                pool = tuple(row[0] for row in self.chain.connection.execute(
                    'SELECT txid FROM mempool ORDER BY id LIMIT 1000'))
            now = asyncio.get_running_loop().time()
            # A peer's drain/send-lock deadline must not postpone another peer's
            # inventory or requests.
            await asyncio.gather(*(self._poll_session(session, tip, pool, now)
                                   for session in tuple(self._sessions.values()) if session.ready))
            await asyncio.sleep(self.poll_interval)

    async def _poll_session(self, session, tip, pool, now):
        if session.writer.is_closing() is True:
            return
        reply_timeout = max(self.timeout, CONNECTED_REPLY_TIMEOUT)
        if ((session.header_requested and now - session.header_requested_at > reply_timeout)
                or (session.headers and now - session.block_requested_at > reply_timeout)
                or (session.hint_requested is not None and now - session.hint_requested_at > reply_timeout)):
            self._stats['requests_expired'] += 1
            self._last_error = 'TimeoutError: Connected peer block response deadline expired'
            session.synchronized = False
            session.local_close_reason = 'block_response_timeout'
            await self._close_writer(session.writer)
            return
        expired = [digest for digest, requested in session.tx_requests.items() if now - requested > self.timeout]
        for digest in expired:
            session.tx_requests.pop(digest, None)
            self._queue_transaction(session, digest, now + TRANSACTION_RETRY_INTERVAL)
        self._stats['requests_expired'] += len(expired)
        if session.discovery_requested and now - session.last_discovery_request > self.timeout:
            # Discovery is optional; an unanswered hint query does not alter
            # validated chain state or the existing full-sync mining guard.
            # Retain the expectation of its reply: TCP can deliver it after
            # this local timer, and no request IDs exist on the v2/v3 wire.
            session.discovery_requested = False
        try:
            if session.last_announced_tip != tip:
                await self._send(session, 'inv', encode_inventory((Inventory(INV_BLOCK, tip),)))
                session.last_announced_tip = tip
            current_pool = frozenset(pool)
            if current_pool != session.last_announced_pool:
                additions = tuple(digest for digest in pool if digest not in session.last_announced_pool)
                for offset in range(0, len(additions), MAX_INV):
                    inventory = tuple(Inventory(INV_TRANSACTION, digest) for digest in additions[offset:offset + MAX_INV])
                    await self._send(session, 'inv', encode_inventory(inventory))
                session.last_announced_pool = current_pool
                session.last_inventory_at = now
            await self._fill_transaction_requests(session, now)
            refresh = (HEADER_REFRESH_INTERVAL if (session.synchronized and session.verified_once
                       and not session.headers_continuing)
                       else self.poll_interval)
            if now - session.last_headers_at >= refresh:
                await self._request_headers(session)
            if now - session.last_keepalive_at >= KEEPALIVE_INTERVAL:
                await self._send(session, 'ping', encode_ping(self.nonce))
                session.last_keepalive_at = now
            await self._request_addresses(session, now)
        except (ProtocolError, OSError) as error:
            session.local_close_reason = 'poll_send_failed: ' + type(error).__name__ + ': ' + str(error)[:160]
            self._last_error = session.local_close_reason
            await self._close_writer(session.writer)
