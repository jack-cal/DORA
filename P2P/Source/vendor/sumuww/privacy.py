"""Fail-closed Tor SOCKS5 and I2P SAM transports using a local router.

The application never downloads a router, opens a firewall, or falls back to
direct TCP. Proxy responses and I2P destination keys are never logged.
"""
import asyncio
import base64
import hashlib
import ipaddress
import json
import re
import secrets
from pathlib import Path

SETTINGS_NAME = 'privacy-settings.json'

# Shared with the PC dialog and native Android confirmation. Choosing Cancel
# never invokes configure_privacy; these notices do not themselves start a router.
NOTICE_DIRECT = 'Direct connection uses neither Tor nor I2P. It usually connects faster and uses fewer resources. Other peers can see your connection IP.'
NOTICE_TOR = 'Benefit: Tor helps hide your real IP from other peers.\n\nTrade-offs: Connecting and syncing may be slower, and battery and data use may increase. Transaction records remain public. If Tor fails, direct connections stay disabled.'
NOTICE_I2P = 'Benefit: I2P helps hide your real IP from other I2P peers.\n\nTrade-offs: I2P peers are required. Connecting and syncing may be slower, and battery and data use may increase. Transaction records remain public. If I2P fails, direct connections stay disabled.'


def settings(mode='direct', port=None):
    if mode not in ('direct', 'tor', 'i2p'):
        raise ValueError('Privacy mode must be direct, tor, or i2p')
    port = (7656 if mode == 'i2p' else 9050) if port is None else port
    if type(port) is not int or not 1 <= port <= 65535:
        raise ValueError('Local privacy router port must be 1..65535')
    return {'mode': mode, 'port': port}


def load(directory):
    path = Path(directory)/SETTINGS_NAME
    if path.is_symlink():
        raise ValueError('Invalid privacy settings file')
    if not path.exists():
        return settings()
    # A damaged private-mode preference must not silently enable direct mode.
    if path.is_symlink() or path.stat().st_size > 1024:
        raise ValueError('Invalid privacy settings file')
    def unique(pairs):
        result = {}
        for key, item in pairs:
            if key in result:
                raise ValueError('Duplicate privacy settings field')
            result[key] = item
        return result
    value = json.loads(path.read_text(encoding='utf-8'), object_pairs_hook=unique)
    if type(value) is not dict or set(value) != {'mode', 'port'}:
        raise ValueError('Invalid privacy settings')
    return settings(**value)


def overlay_host(host):
    return host.endswith(('.onion', '.i2p'))


async def close(writer):
    if writer is None:
        return
    writer.close()
    try:
        await asyncio.wait_for(writer.wait_closed(), 1)
    except (OSError, TimeoutError):
        writer.transport.abort()


class Transport:
    def __init__(self, options):
        self.options = settings(**options)
        self.mode = self.options['mode']
        self._control = None
        self._control_reader = None
        self._session = None
        self._lock = asyncio.Lock()
        self.address = None

    async def stop(self):
        writer, self._control = self._control, None
        self._control_reader = self._session = None
        await close(writer)

    async def _socket(self):
        return await asyncio.open_connection('127.0.0.1', self.options['port'], limit=64*1024)

    async def open(self, target):
        if self.mode == 'tor':
            return await self._tor(target)
        if self.mode == 'i2p':
            return await self._i2p(target)
        raise ValueError('Direct TCP is managed by the checked peer resolver')

    async def _tor(self, target):
        host, port = target
        try:
            address = ipaddress.ip_address(host)
        except ValueError:
            encoded = host.encode('ascii')
            if (not 1 <= len(encoded) <= 253 or host.endswith('.i2p')
                    or not re.fullmatch(r'[a-zA-Z0-9.-]+', host)):
                raise ValueError('Invalid Tor destination')
            if host.endswith('.onion') and not re.fullmatch(r'[a-z2-7]{56}\.onion', host):
                raise ValueError('Tor requires a v3 onion address')
            destination = b'\x03' + bytes([len(encoded)]) + encoded
        else:
            if not address.is_global:
                raise ValueError('Tor does not dial private or local IP destinations')
            destination = bytes([1 if address.version == 4 else 4]) + address.packed
        reader, writer = await self._socket()
        try:
            writer.write(b'\x05\x01\x00'); await writer.drain()
            if await reader.readexactly(2) != b'\x05\x00':
                raise OSError('Tor SOCKS5 negotiation failed')
            writer.write(b'\x05\x01\x00' + destination + port.to_bytes(2, 'big'))
            await writer.drain()
            version, status, reserved, kind = await reader.readexactly(4)
            if version != 5 or status != 0 or reserved != 0:
                raise OSError('Tor SOCKS5 connection failed')
            if kind == 1:
                size = 4
            elif kind == 4:
                size = 16
            elif kind == 3:
                size = (await reader.readexactly(1))[0]
            else:
                raise OSError('Invalid Tor SOCKS5 response')
            await reader.readexactly(size+2)
            writer._sumuww_peer_identity = host
            return reader, writer
        except BaseException:
            await close(writer)
            raise

    async def _command(self, reader, writer, command, expected):
        writer.write((command+'\n').encode('ascii')); await writer.drain()
        raw = await asyncio.wait_for(reader.readline(), 75)
        if not raw.endswith(b'\n') or len(raw) > 4096:
            raise OSError('Invalid I2P SAM response')
        try:
            fields = raw.decode('ascii').strip().split()
        except UnicodeError:
            raise OSError('Invalid I2P SAM response') from None
        values = dict(item.split('=', 1) for item in fields[2:] if '=' in item)
        if fields[:2] != expected.split() or values.get('RESULT') != 'OK':
            raise OSError('I2P SAM request failed')
        return values

    async def _hello(self):
        reader, writer = await self._socket()
        try:
            await self._command(reader, writer, 'HELLO VERSION MIN=3.1 MAX=3.1', 'HELLO REPLY')
            return reader, writer
        except BaseException:
            await close(writer)
            raise

    async def _ensure_session(self):
        async with self._lock:
            if (self._control is not None and not self._control.is_closing()
                    and not self._control_reader.at_eof()):
                return
            await self.stop()
            reader, writer = await self._hello()
            try:
                session = 'sumuww'+secrets.token_hex(12)
                await self._command(reader, writer,
                    f'SESSION CREATE STYLE=STREAM ID={session} DESTINATION=TRANSIENT '
                    'SIGNATURE_TYPE=7 i2cp.leaseSetEncType=4 inbound.quantity=3 outbound.quantity=3',
                    'SESSION STATUS')
                me = await self._command(reader, writer, 'NAMING LOOKUP NAME=ME', 'NAMING REPLY')
                self.address = self._destination_address(me.get('VALUE', ''))
                self._session, self._control_reader, self._control = session, reader, writer
            except BaseException:
                await close(writer)
                raise

    @staticmethod
    def _destination_address(value):
        if not re.fullmatch(r'[A-Za-z0-9~=-]{516,2048}', value):
            raise OSError('Invalid I2P destination')
        try:
            raw = base64.b64decode(value.translate(str.maketrans('-~', '+/')), validate=True)
        except ValueError:
            raise OSError('Invalid I2P destination') from None
        return base64.b32encode(hashlib.sha256(raw).digest()).decode().lower().rstrip('=')+'.b32.i2p'

    async def _i2p(self, target):
        host, _port = target
        if not re.fullmatch(r'[a-z2-7]{52}\.b32\.i2p', host):
            raise ValueError('I2P requires a 52-character b32.i2p peer address')
        await self._ensure_session()
        reader, writer = await self._hello()
        try:
            answer = await self._command(reader, writer, 'NAMING LOOKUP NAME='+host, 'NAMING REPLY')
            destination = answer.get('VALUE', '')
            if self._destination_address(destination) != host:
                raise OSError('I2P destination does not match requested address')
            await self._command(reader, writer,
                f'STREAM CONNECT ID={self._session} DESTINATION={destination} SILENT=false',
                'STREAM STATUS')
            writer._sumuww_peer_identity = host
            return reader, writer
        except BaseException:
            await close(writer)
            raise

    async def accept(self):
        await self._ensure_session()
        reader, writer = await self._hello()
        try:
            await self._command(reader, writer,
                f'STREAM ACCEPT ID={self._session} SILENT=false', 'STREAM STATUS')
            raw = await reader.readline()
            if len(raw) > 4096 or not raw.endswith(b'\n'):
                raise OSError('Invalid I2P incoming destination')
            identity = self._destination_address(raw.decode('ascii').strip().split()[0])
            writer._sumuww_peer_identity = identity
            return reader, writer
        except BaseException:
            await close(writer)
            raise
