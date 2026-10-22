"""Persistent, non-mining P2P observer. Only genesis is advertised as owned.

The observer has no wallet or chain database. Returned tip bodies are checked
for hash, PoW and Merkle consistency, not contextual consensus validity.
"""
import asyncio
import ipaddress
import socket
import time

from .block import Block
from .peer_discovery import discovery_endpoint
from .primitives import check_pow, hash_to_display, merkle_root
from .wire import (Version, Inventory, PeerAddress, INV_BLOCK, ProtocolError,
                   PeerDisconnected, encode_version, decode_version,
                   encode_inventory, decode_inventory, encode_headers,
                   decode_getheaders, encode_addresses, decode_addresses,
                   decode_ping, encode_ping, read_frame, write_frame)

HEARTBEAT_SECONDS = 10
RESPONSE_SECONDS = 30
MAX_MESSAGES_PER_SECOND = 64
MAX_BYTES_PER_SECOND = 8_000_000


class ObserverConnection:
    def __init__(self, survey, target, *, reader=None, writer=None, protocol=3):
        self.survey = survey
        self.target = target
        self.reader = reader
        self.writer = writer
        self.outgoing = writer is None
        self.protocol = protocol
        self.peer_id = None
        self.ready = False
        self.handshake_completed = False
        self.listener = None
        self.row = None
        self.last_reply = 0
        self.address_request = 0
        self.pending_block = None
        self.pending_since = 0
        self.next_tip = None
        self.ping = None
        self.ping_since = 0
        self._write_lock = asyncio.Lock()
        self._window = 0
        self._messages = 0
        self._bytes = 0
        self._address_pending = False
        self._last_address_response = 0

    async def send(self, command, payload=b''):
        async with self._write_lock:
            await write_frame(self.writer, command, payload, 8,
                              magic=self.survey.profile.message_magic)

    async def run(self):
        heartbeat = None
        try:
            if self.outgoing:
                self.reader, self.writer = await asyncio.wait_for(
                    asyncio.open_connection(*self.target,
                        family=socket.AF_INET6 if ':' in self.target[0] else socket.AF_INET,
                        limit=64*1024), 8)
            await asyncio.wait_for(self.handshake(), 8)
            if not self.ready:
                return
            heartbeat = asyncio.create_task(self.heartbeat())
            while not self.survey._stop.is_set():
                frame = await read_frame(self.reader, 8,
                    magic=self.survey.profile.message_magic, idle_timeout=RESPONSE_SECONDS)
                second = int(time.monotonic())
                if second != self._window:
                    self._window, self._messages, self._bytes = second, 0, 0
                self._messages += 1
                self._bytes += len(frame.payload)
                if self._messages > MAX_MESSAGES_PER_SECOND or self._bytes > MAX_BYTES_PER_SECOND:
                    raise ProtocolError('Observer message rate exceeded')
                await self.handle(frame)
                self.last_reply = time.monotonic()
                self.row['seen'] = time.time()
        finally:
            if heartbeat is not None:
                heartbeat.cancel()
                await asyncio.gather(heartbeat, return_exceptions=True)
            self.ready = False
            if self.writer is not None:
                self.writer.close()
                try:
                    await asyncio.wait_for(self.writer.wait_closed(), .5)
                except (OSError, TimeoutError, asyncio.CancelledError):
                    self.writer.transport.abort()

    async def handshake(self):
        profile = self.survey.profile
        own = Version(self.protocol, profile.genesis.block_hash(), self.survey.nonce,
                      profile.profile_id, profile.genesis.block_hash())
        await self.send('version', encode_version(own))
        frame = await read_frame(self.reader, 8, magic=profile.message_magic)
        if frame.command != 'version':
            raise ProtocolError('Expected version')
        remote = decode_version(frame.payload)
        if remote.genesis != profile.genesis.block_hash() or remote.profile != profile.profile_id:
            raise ProtocolError('Wrong network')
        if remote.protocol not in (1, 2, 3) or remote.nonce == self.survey.nonce:
            raise ProtocolError('Unsupported protocol or self connection')
        self.peer_id = f'{remote.nonce:016x}'
        self.protocol = max(self.protocol, remote.protocol)
        await self.send('verack')
        frame = await read_frame(self.reader, 8, magic=profile.message_magic)
        if frame.command != 'verack' or frame.payload:
            raise ProtocolError('Invalid acknowledgement')
        self.handshake_completed = True
        existing = next((connection for connection in self.survey.connections.values()
                         if connection is not self and connection.ready
                         and connection.peer_id == self.peer_id), None)
        if existing is not None:
            # Aliases are learned only after an actual completed handshake.
            if self.outgoing:
                existing.row['aliases'].add(self.target)
                self.survey.observe(self.target, existing.row)
            return
        self.ready = True
        self.last_reply = time.monotonic()
        old = self.survey.observations.get(self.target, {})
        self.row = {'endpoint': self.target, 'responding': True, 'peer_id': self.peer_id,
                    'tip': hash_to_display(remote.tip), 'height': None,
                    'tip_pow_merkle_checked': False, 'latency_ms': None, 'contacts': [],
                    'error': None, 'seen': time.time(), 'tip_updates': old.get('tip_updates', 0),
                    'aliases': {self.target}, 'direction': 'outgoing' if self.outgoing else 'incoming'}
        self.survey.observe(self.target, self.row)
        self.survey.failures.pop(self.target, None)
        await self.request_addresses()
        await self.request_tip(remote.tip)

    async def request_addresses(self):
        if self.protocol >= 2:
            self.address_request = time.monotonic()
            self._address_pending = True
            await self.send('getaddr')

    async def request_tip(self, digest):
        if self.pending_block is not None:
            self.next_tip = digest
            return
        self.pending_block = digest
        self.pending_since = time.monotonic()
        await self.send('getdata', encode_inventory((Inventory(INV_BLOCK, digest),)))

    async def heartbeat(self):
        try:
            while True:
                await asyncio.sleep(HEARTBEAT_SECONDS)
                now = time.monotonic()
                if now - self.last_reply > RESPONSE_SECONDS:
                    raise ProtocolError('Peer stopped responding')
                if self.pending_block is not None and now - self.pending_since > RESPONSE_SECONDS:
                    raise ProtocolError('Tip block response deadline expired')
                if self.ping is not None and now - self.ping_since > RESPONSE_SECONDS:
                    raise ProtocolError('Peer keepalive deadline expired')
                if self.ping is None:
                    self.ping = int(now * 1000000) & ((1 << 64) - 1)
                    self.ping_since = now
                    await self.send('ping', encode_ping(self.ping))
                if self.protocol >= 2 and now - self.address_request > 35:
                    await self.request_addresses()
        except (OSError, ProtocolError):
            self.writer.close()

    async def handle(self, frame):
        command, payload = frame.command, frame.payload
        profile = self.survey.profile
        if command == 'ping':
            await self.send('pong', encode_ping(decode_ping(payload)))
        elif command == 'pong':
            nonce = decode_ping(payload)
            if nonce != self.ping:
                raise ProtocolError('Unmatched keepalive')
            self.row['latency_ms'] = round((time.monotonic() - self.ping_since) * 1000, 1)
            self.ping = None
        elif command == 'getheaders':
            decode_getheaders(payload)
            # The observer owns genesis only and advertises exactly that tip.
            # Its truthful headers-after-genesis answer is empty; no fake chain.
            await self.send('headers', encode_headers(()))
        elif command == 'getdata':
            missing = []
            for item in decode_inventory(payload):
                if item.kind == INV_BLOCK and item.digest == profile.genesis.block_hash():
                    await self.send('block', profile.genesis.serialize())
                else:
                    missing.append(item)
            if missing:
                await self.send('notfound', encode_inventory(tuple(missing)))
        elif command == 'getaddr':
            if payload or self.protocol < 2:
                raise ProtocolError('Invalid address request')
            if time.monotonic()-self._last_address_response<5:
                raise ProtocolError('Address request rate exceeded')
            self._last_address_response=time.monotonic()
            contacts = self.survey.shareable_contacts(self.protocol)
            own = self.survey.listener_for(self.target[0], self.protocol)
            peers = tuple(PeerAddress(*target) for target in contacts if target != own)[:32-bool(own)]
            await self.send('addr', encode_addresses(PeerAddress(*own) if own else None, peers))
        elif command == 'addr':
            if self.protocol < 2 or not self._address_pending:
                raise ProtocolError('Unrequested address response')
            self._address_pending = False
            listener, contacts = decode_addresses(payload)
            for item in ((listener,) if listener else ()) + contacts:
                if ':' in item.host and self.protocol < 3:
                    raise ProtocolError('IPv6 address requires protocol 3')
                try:
                    target = discovery_endpoint(item.host, item.port, scope=self.survey.scope)
                except ValueError:
                    continue
                # Public peers cannot turn discovery into requests to arbitrary
                # private devices on the observer's unrelated local network.
                if ipaddress.ip_address(self.target[0]).is_global and not ipaddress.ip_address(target[0]).is_global:
                    continue
                if item is listener:
                    self.listener = target
                self.survey.add(target, 'P2P address exchange')
        elif command == 'inv':
            blocks = [item.digest for item in decode_inventory(payload) if item.kind == INV_BLOCK]
            if blocks and hash_to_display(blocks[-1]) != self.row['tip']:
                await self.request_tip(blocks[-1])
        elif command == 'block':
            block = Block.deserialize(payload)
            digest = block.block_hash()
            if digest != self.pending_block:
                raise ProtocolError('Unrequested tip block')
            if not check_pow(digest, block.header.bits, profile.pow_limit):
                raise ProtocolError('Invalid tip PoW')
            root, mutated = merkle_root([tx.txid() for tx in block.transactions])
            if root != block.header.merkle_root or mutated:
                raise ProtocolError('Invalid tip Merkle root')
            from .network_monitor import tip_height
            tip = hash_to_display(digest)
            self.row['tip_updates'] += self.row['tip'] != tip
            self.row.update(tip=tip, height=tip_height(block, profile), tip_pow_merkle_checked=True)
            self.pending_block = None
            if self.next_tip is not None:
                tip, self.next_tip = self.next_tip, None
                if hash_to_display(tip) != self.row['tip']:
                    await self.request_tip(tip)
        elif command == 'notfound':
            if any(item.kind == INV_BLOCK and item.digest == self.pending_block
                   for item in decode_inventory(payload)):
                self.pending_block = None
        else:
            raise ProtocolError('Unexpected observer message: ' + command)
