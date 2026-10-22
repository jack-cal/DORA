"""Bounded binary messages for SUMUWW's private local prototype transport.

These bytes define a SUMUWW local-development protocol, not Bitcoin P2P or a
public-network launch identity. Digests are the 32-byte internal hash order.
Framing validity is separate from contextual block/transaction validity.
"""

import asyncio
from dataclasses import dataclass
import math
import ipaddress
import re
import struct

from .primitives import Header, decode_compact_size, encode_compact_size, sha256d

NETWORK_MAGIC = bytes.fromhex("d0524709")
PROTOCOL_VERSION = 1
# Version 1 framing and identity stay intact. A version-2 outgoing request
# explicitly opts in to address exchange; v1 peers receive no new commands.
DISCOVERY_PROTOCOL_VERSION = 2
IPV6_PROTOCOL_VERSION = 3
MAX_ADDRESSES = 32
MAX_PAYLOAD = 4_000_000
# Version 4 belongs to the previous, incompatible signing envelope. Sending
# the new hello on v4 makes old peers count it as malformed and ban our route.
BOUNDARY_PROTOCOL_VERSION = 5

def _payload_limit(command):
    if command=='bpart':
        from .boundary_transport import PART_FRAME_BYTES
        return PART_FRAME_BYTES
    if command=='bblock': return MAX_PAYLOAD+1024*1024+4
    if command=='bcall': return 9*1024*1024
    if command in ('bquery','bresponse','bhello'): return 1024*1024
    return MAX_PAYLOAD
MAX_HEADERS = 128
MAX_LOCATOR = 32
MAX_INV = 256
FRAME_HEADER_SIZE = 24
INV_TRANSACTION = 1
INV_BLOCK = 2
_COMMAND = re.compile(r"[a-z][a-z0-9]{0,11}\Z", re.ASCII)


class ProtocolError(ValueError):
    """Malformed, oversized, incomplete, or timed-out local wire message."""


class MalformedWireData(ProtocolError):
    """Definitively malformed bytes, separate from network loss or timeout."""


class PeerDisconnected(ProtocolError):
    """Clean EOF between frames, distinct from a truncated in-progress frame."""


def _integer(value, maximum, label):
    if type(value) is not int or not 0 <= value <= maximum:
        raise ProtocolError(f"{label} must be an unsigned integer <= {maximum}")
    return value


def _bytes(value, label, *, length=None, maximum=None):
    if not isinstance(value, bytes):
        raise ProtocolError(f"{label} must be bytes")
    if length is not None and len(value) != length:
        raise ProtocolError(f"{label} must contain exactly {length} bytes")
    if maximum is not None and len(value) > maximum:
        raise ProtocolError(f"{label} exceeds {maximum} bytes")
    return value


def _command(command):
    if not isinstance(command, str) or _COMMAND.fullmatch(command) is None:
        raise ProtocolError("Command must be 1..12 lowercase ASCII letters/digits, starting with a letter")
    return command.encode("ascii")


def _decode_command(raw):
    first_zero = raw.find(b"\x00")
    name = raw if first_zero < 0 else raw[:first_zero]
    if first_zero >= 0 and raw[first_zero:] != bytes(12 - first_zero):
        raise MalformedWireData("Command has non-NUL bytes after its padding")
    try:
        command = name.decode("ascii", errors="strict")
    except UnicodeDecodeError as exc:
        raise MalformedWireData("Command is not ASCII") from exc
    try:
        _command(command)
    except ProtocolError as exc:
        raise MalformedWireData(str(exc)) from exc
    return command


def _timeout(value):
    try:
        finite = type(value) in (int, float) and math.isfinite(value)
    except OverflowError:
        finite = False
    if not finite or value <= 0:
        raise ProtocolError("Timeout must be a finite positive number")
    return value


def _tuple(value, maximum, label, minimum=0):
    if not isinstance(value, tuple) or not minimum <= len(value) <= maximum:
        raise ProtocolError(f"{label} must be a tuple of {minimum}..{maximum} items")
    return value


def _count(raw, maximum, offset=0):
    try:
        return decode_compact_size(raw, maximum, offset)
    except (TypeError, ValueError) as exc:
        raise ProtocolError(str(exc)) from exc


def _exact_end(raw, expected, label):
    if len(raw) != expected:
        raise ProtocolError(f"{label} is truncated or has trailing bytes")


@dataclass(frozen=True)
class Frame:
    command: str
    payload: bytes

    def __post_init__(self):
        _command(self.command)
        _bytes(self.payload, "Payload", maximum=_payload_limit(self.command))


def encode_frame(command, payload, magic=NETWORK_MAGIC):
    """Serialize one frame after checking all bounds; no stream state changes."""
    name = _command(command)
    _bytes(payload, "Payload", maximum=_payload_limit(command))
    _bytes(magic, "Network magic", length=4)
    return magic + name.ljust(12, b"\x00") + struct.pack("<I", len(payload)) + sha256d(payload)[:4] + payload


def _decode_frame_header(raw, magic=NETWORK_MAGIC):
    _bytes(raw, "Frame header", length=FRAME_HEADER_SIZE)
    _bytes(magic, "Network magic", length=4)
    if raw[:4] != magic:
        raise ProtocolError("Network magic mismatch")
    command = _decode_command(raw[4:16])
    size = struct.unpack("<I", raw[16:20])[0]
    if size > _payload_limit(command):
        raise MalformedWireData("Payload size exceeds local transport limit")
    if command == 'getaddr' and size:
        raise MalformedWireData('getaddr payload must be empty')
    if command == 'addr' and size > 3 + MAX_ADDRESSES * 258:
        raise MalformedWireData('Peer address payload exceeds its bounded size')
    return command, size, raw[20:24]


async def read_frame(reader, timeout=5, *, magic=NETWORK_MAGIC, idle_timeout=None):
    """Bound a complete frame; optionally allow a longer wait for its first byte."""
    timeout = _timeout(timeout)
    _bytes(magic, "Network magic", length=4)
    if idle_timeout is not None:
        idle_timeout = _timeout(idle_timeout)

    async def read(first=b''):
        try:
            header = first + await reader.readexactly(FRAME_HEADER_SIZE - len(first))
        except asyncio.IncompleteReadError as exc:
            if not first and not exc.partial:
                raise PeerDisconnected("Peer closed connection between frames") from exc
            raise
        command, size, checksum = _decode_frame_header(header, magic)
        payload = await reader.readexactly(size)
        if sha256d(payload)[:4] != checksum:
            raise MalformedWireData("Payload checksum mismatch")
        return Frame(command, payload)

    try:
        if idle_timeout is not None:
            try:
                first = await asyncio.wait_for(reader.readexactly(1), timeout=idle_timeout)
            except asyncio.IncompleteReadError as exc:
                raise PeerDisconnected("Peer closed connection between frames") from exc
            return await asyncio.wait_for(read(first), timeout=timeout)
        return await asyncio.wait_for(read(), timeout=timeout)
    except asyncio.IncompleteReadError as exc:
        raise ProtocolError("Truncated frame") from exc
    except TimeoutError as exc:
        raise ProtocolError("Whole-frame read timed out") from exc


async def write_frame(writer, command, payload, timeout=5, *, magic=NETWORK_MAGIC):
    """Write one validated frame and bound the stream drain wait."""
    timeout = _timeout(timeout)
    encoded = encode_frame(command, payload, magic)
    writer.write(encoded)
    try:
        await asyncio.wait_for(writer.drain(), timeout=timeout)
    except TimeoutError as exc:
        raise ProtocolError("Frame drain timed out") from exc


@dataclass(frozen=True)
class Version:
    protocol: int
    genesis: bytes
    nonce: int
    profile: str
    tip: bytes

    def __post_init__(self):
        _integer(self.protocol, 0xFFFFFFFF, "Protocol version")
        _bytes(self.genesis, "Genesis digest", length=32)
        _integer(self.nonce, 0xFFFFFFFFFFFFFFFF, "Nonce")
        _profile_bytes(self.profile)
        _bytes(self.tip, "Tip digest", length=32)


def _profile_bytes(profile):
    if not isinstance(profile, str):
        raise ProtocolError("Profile must be text")
    try:
        raw = profile.encode("utf-8", errors="strict")
    except UnicodeEncodeError as exc:
        raise ProtocolError("Profile is not valid UTF-8 text") from exc
    if not 1 <= len(raw) <= 64:
        raise ProtocolError("Profile must contain 1..64 UTF-8 bytes")
    return raw


def encode_version(version):
    if not isinstance(version, Version):
        raise ProtocolError("Expected Version")
    profile = _profile_bytes(version.profile)
    return struct.pack("<I", version.protocol) + version.genesis + struct.pack("<Q", version.nonce) + encode_compact_size(len(profile)) + profile + version.tip


def decode_version(raw):
    _bytes(raw, "Version payload", maximum=4 + 32 + 8 + 1 + 64 + 32)
    if len(raw) < 44:
        raise ProtocolError("Truncated version payload")
    count, offset = _count(raw, 64, 44)
    if count == 0:
        raise ProtocolError("Profile cannot be empty")
    _exact_end(raw, offset + count + 32, "Version payload")
    try:
        profile = raw[offset:offset + count].decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise ProtocolError("Profile is not strict UTF-8") from exc
    return Version(struct.unpack("<I", raw[:4])[0], raw[4:36], struct.unpack("<Q", raw[36:44])[0], profile, raw[offset + count:])


@dataclass(frozen=True)
class Inventory:
    kind: int
    digest: bytes

    def __post_init__(self):
        _integer(self.kind, 0xFFFFFFFF, "Inventory kind")
        if self.kind not in (INV_TRANSACTION, INV_BLOCK):
            raise ProtocolError("Inventory kind must be transaction (1) or block (2)")
        _bytes(self.digest, "Inventory digest", length=32)


def encode_inventory(items):
    _tuple(items, MAX_INV, "Inventory")
    if any(not isinstance(item, Inventory) for item in items):
        raise ProtocolError("Inventory items must be Inventory objects")
    return encode_compact_size(len(items)) + b"".join(struct.pack("<I", item.kind) + item.digest for item in items)


def decode_inventory(raw):
    _bytes(raw, "Inventory payload", maximum=3 + MAX_INV * 36)
    count, offset = _count(raw, MAX_INV)
    _exact_end(raw, offset + count * 36, "Inventory payload")
    return tuple(Inventory(struct.unpack("<I", raw[offset + i * 36:offset + i * 36 + 4])[0], raw[offset + i * 36 + 4:offset + (i + 1) * 36]) for i in range(count))


def encode_getheaders(locator, stop=bytes(32)):
    _tuple(locator, MAX_LOCATOR, "Locator", minimum=1)
    for digest in locator:
        _bytes(digest, "Locator digest", length=32)
    _bytes(stop, "Stop digest", length=32)
    return encode_compact_size(len(locator)) + b"".join(locator) + stop


def decode_getheaders(raw):
    _bytes(raw, "Getheaders payload", maximum=1 + MAX_LOCATOR * 32 + 32)
    count, offset = _count(raw, MAX_LOCATOR)
    if not count:
        raise ProtocolError("Locator cannot be empty")
    _exact_end(raw, offset + (count + 1) * 32, "Getheaders payload")
    locator = tuple(raw[offset + i * 32:offset + (i + 1) * 32] for i in range(count))
    return locator, raw[offset + count * 32:]


def encode_headers(headers):
    _tuple(headers, MAX_HEADERS, "Headers")
    if any(not isinstance(header, Header) for header in headers):
        raise ProtocolError("Headers must contain Header objects")
    try:
        encoded = b"".join(header.serialize() for header in headers)
    except (TypeError, ValueError) as exc:
        raise ProtocolError("Malformed Header object") from exc
    return encode_compact_size(len(headers)) + encoded


def decode_headers(raw):
    _bytes(raw, "Headers payload", maximum=1 + MAX_HEADERS * 80)
    count, offset = _count(raw, MAX_HEADERS)
    _exact_end(raw, offset + count * 80, "Headers payload")
    return tuple(Header.deserialize(raw[offset + i * 80:offset + (i + 1) * 80]) for i in range(count))


def encode_ping(nonce):
    return struct.pack("<Q", _integer(nonce, 0xFFFFFFFFFFFFFFFF, "Ping nonce"))


def decode_ping(raw):
    _bytes(raw, "Ping payload", length=8)
    return struct.unpack("<Q", raw)[0]


@dataclass(frozen=True)
class PeerAddress:
    host: str
    port: int

    def __post_init__(self):
        if not isinstance(self.host, str):
            raise ProtocolError('Peer address host must be text')
        try:
            raw = self.host.encode('ascii', errors='strict')
        except UnicodeError as error:
            raise ProtocolError('Peer address host must be ASCII') from error
        if ':' in self.host:
            try:
                address = ipaddress.IPv6Address(self.host)
                if '%' in self.host or address.ipv4_mapped is not None:
                    raise ValueError('Scoped or mapped IPv6')
                object.__setattr__(self, 'host', str(address))
            except ValueError as exc:
                raise ProtocolError('Invalid IPv6 peer host') from exc
        elif not 1 <= len(raw) <= 253 or re.fullmatch(r'[A-Za-z0-9.-]+', self.host) is None:
            raise ProtocolError('Invalid peer address host encoding')
        if type(self.port) is not int or not 1 <= self.port <= 65535:
            raise ProtocolError('Peer address port must be 1..65535')


def encode_addresses(listener, peers=()):
    """One optional listening endpoint plus at most 32 total bounded hints."""
    if listener is not None and not isinstance(listener, PeerAddress):
        raise ProtocolError('Listener must be a PeerAddress or None')
    _tuple(peers, MAX_ADDRESSES - bool(listener), 'Peer addresses')
    items = ((listener,) if listener is not None else ()) + peers
    if any(not isinstance(item, PeerAddress) for item in items) or len(set(items)) != len(items):
        raise ProtocolError('Peer address entries must be unique PeerAddress objects')
    return bytes((bool(listener),)) + encode_compact_size(len(peers)) + b''.join(
        encode_compact_size(len(item.host)) + item.host.encode('ascii') + struct.pack('<H', item.port)
        for item in items)


def decode_addresses(raw):
    _bytes(raw, 'Peer address payload', maximum=3 + MAX_ADDRESSES * 258)
    if not raw or raw[0] not in (0, 1):
        raise ProtocolError('Invalid listener flag')
    count, offset = _count(raw, MAX_ADDRESSES - raw[0], 1)
    items = []
    for _ in range(count + raw[0]):
        length, offset = _count(raw, 253, offset)
        if not length or offset + length + 2 > len(raw):
            raise ProtocolError('Truncated peer address')
        try:
            host = raw[offset:offset + length].decode('ascii', errors='strict')
        except UnicodeError as error:
            raise ProtocolError('Peer address host is not ASCII') from error
        port = struct.unpack('<H', raw[offset + length:offset + length + 2])[0]
        items.append(PeerAddress(host, port))
        offset += length + 2
    _exact_end(raw, offset, 'Peer address payload')
    if len(set(items)) != len(items):
        raise ProtocolError('Duplicate peer addresses')
    return (items[0], tuple(items[1:])) if raw[0] else (None, tuple(items))
