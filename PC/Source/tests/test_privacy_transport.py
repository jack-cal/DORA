import asyncio
import base64
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from types import SimpleNamespace

from sumuww.peer import PeerNode
from sumuww.privacy import Transport, load, settings
from sumuww.app_service import AppService


class PrivacyTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.writers = []
        self.servers = []
        self.nodes = []
        self.directory = tempfile.TemporaryDirectory()

    async def asyncTearDown(self):
        await asyncio.gather(*(n.stop() for n in self.nodes))
        for writer in self.writers:
            writer.close()
        for server in self.servers:
            server.close()
            await server.wait_closed()
        self.directory.cleanup()

    async def server(self, handler):
        server = await asyncio.start_server(handler, '127.0.0.1', 0)
        self.servers.append(server)
        return server.sockets[0].getsockname()[1]

    def node(self, name, **options):
        n = PeerNode(Path(self.directory.name)/(name+'.sqlite'), poll_interval=.05, timeout=1, **options)
        self.nodes.append(n)
        return n

    async def test_tor_carries_actual_peer_sync_without_dns_dht_or_address_publication(self):
        source = self.node('source', discover_peers=False)
        await source.start()
        requests = []
        async def socks(reader, writer):
            self.writers.append(writer)
            await reader.readexactly(3)
            writer.write(b'\x05\x00'); await writer.drain()
            header = await reader.readexactly(4)
            kind = header[3]
            count = 4 if kind == 1 else 16 if kind == 4 else (await reader.readexactly(1))[0]
            requests.append(await reader.readexactly(count+2))
            other_reader, other_writer = await asyncio.open_connection(*source.address)
            self.writers.append(other_writer)
            writer.write(b'\x05\x00\x00\x01'+bytes(6)); await writer.drain()
            async def copy(r,w):
                try:
                    while data := await r.read(65536):
                        w.write(data); await w.drain()
                except OSError:
                    pass
                finally:
                    w.close()
            await asyncio.gather(copy(reader,other_writer),copy(other_reader,writer))
        port = await self.server(socks)
        client = self.node('private', host='0.0.0.0', allow_lan=True, allow_internet=True,
                           auto_address=True, peers=(('example.com',18444),),
                           privacy=settings('tor',port))
        with patch('socket.getaddrinfo', side_effect=AssertionError('Local DNS leak')):
            await client.start()
            for _ in range(200):
                if client.synchronization_info()['mining_ready']:
                    break
                await asyncio.sleep(.02)
        self.assertTrue(client.synchronization_info()['mining_ready'])
        self.assertEqual('127.0.0.1',client.address[0])
        self.assertIsNone(client._dht_discovery)
        self.assertIsNone(client._lan_discovery)
        self.assertIsNone(client._own_listener())
        self.assertEqual([],client.info()['own_addresses'])
        self.assertEqual(b'example.com', requests[0][:-2])
        self.assertEqual('example.com',next(iter(client._sessions.values())).remote_ip)

    async def test_failed_tor_never_dials_target_directly(self):
        async def reject(reader,writer):
            self.writers.append(writer)
            await reader.readexactly(3)
            writer.write(b'\x05\xff'); await writer.drain()
        port = await self.server(reject)
        transport = Transport(settings('tor',port))
        original = asyncio.open_connection
        addresses = []
        async def dial(host,port,**kwargs):
            addresses.append((host,port))
            return await original(host,port,**kwargs)
        with patch('asyncio.open_connection',dial):
            with self.assertRaises(OSError):
                await transport.open(('example.com',18444))
        self.assertEqual([('127.0.0.1',port)], addresses)
        with self.assertRaises(ValueError):
            await transport.open(('192.168.1.2',18444))

    async def test_anonymous_inbound_offender_is_dropped_without_banning_local_router(self):
        node = self.node('inbound-policy', allow_internet=True, privacy=settings('tor'))
        writer = SimpleNamespace(closed=False)
        writer.close = lambda: setattr(writer, 'closed', True)
        session = SimpleNamespace(remote_ip=None, writer=writer, synchronized=True)
        for _ in range(3):
            node._record_invalid_peer(session)
        self.assertTrue(writer.closed)
        self.assertFalse(node._cooling_down('127.0.0.1'))

    async def test_i2p_sam_session_lookup_stream_and_accept(self):
        destination = base64.b64encode(bytes(387)).decode().replace('+','-').replace('/','~')
        host = Transport._destination_address(destination)
        commands = []
        async def sam(reader,writer):
            self.writers.append(writer)
            while raw := await reader.readline():
                command = raw.decode().strip(); commands.append(command)
                if command.startswith('HELLO'):
                    reply = 'HELLO REPLY RESULT=OK VERSION=3.1'
                elif command.startswith('SESSION CREATE'):
                    reply = 'SESSION STATUS RESULT=OK DESTINATION='+destination
                elif command.startswith('NAMING'):
                    reply = 'NAMING REPLY RESULT=OK VALUE='+destination
                elif command.startswith('STREAM CONNECT'):
                    reply = 'STREAM STATUS RESULT=OK'
                else:
                    reply = 'STREAM STATUS RESULT=OK\n'+destination
                writer.write((reply+'\n').encode()); await writer.drain()
                if command.startswith('STREAM'):
                    writer.write(b'peer-data'); await writer.drain()
                    await reader.read(); break
        port = await self.server(sam)
        transport = Transport(settings('i2p',port))
        with patch('socket.getaddrinfo', side_effect=AssertionError('I2P DNS leak')):
            r,w = await transport.open((host,18444)); self.writers.append(w)
            self.assertEqual(b'peer-data', await r.readexactly(9))
            r,w = await transport.accept(); self.writers.append(w)
            self.assertEqual(host,w._sumuww_peer_identity)
            self.assertEqual(b'peer-data', await r.readexactly(9))
        self.assertEqual(host,transport.address)
        self.assertEqual(1,sum(c.startswith('SESSION CREATE') for c in commands))
        with self.assertRaises(ValueError):
            await transport.open(('example.com',18444))
        await transport.stop()

    async def test_service_settings_persist_and_corruption_does_not_enable_direct_mode(self):
        service = AppService(self.directory.name,network='regtest',listen='127.0.0.1:0')
        await asyncio.wrap_future(service.start())
        try:
            result = await asyncio.wrap_future(service.configure_privacy('tor',19050))
            self.assertEqual('tor',result['privacy']['mode'])
            self.assertEqual(settings('tor',19050),load(self.directory.name))
        finally:
            await asyncio.wrap_future(service.stop())
        Path(self.directory.name,'privacy-settings.json').write_text('{broken')
        with self.assertRaises(ValueError):
            AppService(self.directory.name,network='regtest')
        Path(self.directory.name,'privacy-settings.json').write_text('{"mode":"tor","mode":"direct","port":9050}')
        with self.assertRaises(ValueError):
            load(self.directory.name)

    async def test_dangling_settings_link_never_selects_direct_connection(self):
        with patch.object(Path, 'exists', return_value=False), patch.object(Path, 'is_symlink', return_value=True):
            with self.assertRaises(ValueError):
                load(self.directory.name)
