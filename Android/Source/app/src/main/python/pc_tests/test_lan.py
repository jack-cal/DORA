"""Manual RFC1918 scope checks and actual sockets on this host only.

The optional NIC case never connects to another computer and makes no claim
about router, firewall, public deployment or multi-host operation.
"""

import asyncio
from contextlib import redirect_stderr
from io import StringIO
import ipaddress
import json
import os
from pathlib import Path
import socket
import tempfile
import unittest
from unittest.mock import Mock, patch

from sumuww.block import GENESIS_TIME, PROFILE_ID, genesis_block
from sumuww.peer import PeerNode, _endpoint
from sumuww import peerd
from sumuww.wallet import RegtestKey
from sumuww.wire import PROTOCOL_VERSION


PRIVATE = ('10.0.0.0', '10.255.255.255', '172.16.0.0', '172.31.255.255',
           '192.168.0.0', '192.168.255.255')
REJECTED = ('0.0.0.0', '8.8.8.8', '100.64.0.1', '169.254.1.1', '172.15.255.255',
            '172.32.0.0', '192.167.255.255', '192.169.0.0', '192.0.2.1',
            '198.18.0.1', '224.0.0.1', '240.0.0.1', '255.255.255.255',
            'localhost', '::ffff:127.0.0.1', '127.1', '', ' 10.0.0.1')
WORK = Path(os.environ.get('SUMUWW_TEST_WORKDIR', tempfile.gettempdir()))
NOW = GENESIS_TIME + 1000


def local_private_addresses():
    """Inspect only this host's resolved interfaces; no probe or remote socket."""
    try:
        records = socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET, socket.SOCK_STREAM)
    except OSError:
        return ()
    addresses = []
    for item in records:
        host = item[4][0]
        try:
            _endpoint(host, 1, allow_lan=True)
        except ValueError:
            continue
        if not ipaddress.IPv4Address(host).is_loopback and host not in addresses:
            addresses.append(host)
    return tuple(addresses)


class LanAddressTests(unittest.TestCase):
    def setUp(self):
        WORK.mkdir(parents=True, exist_ok=True)
        self.directory = tempfile.TemporaryDirectory(prefix='sumuww-lan-address-', dir=WORK)
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)

    def test_rfc1918_exact_range_boundaries_require_opt_in(self):
        for host in PRIVATE:
            with self.subTest(host=host):
                with self.assertRaises(ValueError):
                    _endpoint(host, 1234)
                self.assertEqual((host, 1234), _endpoint(host, 1234, allow_lan=True))
                self.assertEqual((host, 0), peerd.endpoint(host + ':0', allow_lan=True))

    def test_special_public_dns_ipv6_and_wildcard_rejected_even_with_opt_in(self):
        for host in REJECTED:
            with self.subTest(host=host), self.assertRaises(ValueError):
                _endpoint(host, 1234, allow_lan=True)
            with self.subTest(cli_host=host), self.assertRaises(ValueError):
                peerd.endpoint(host + ':1234', allow_lan=True)

    def test_ports_option_types_and_loopback_remain_strict(self):
        for host in ('127.0.0.1', '127.0.0.2', '127.255.255.254', '::1'):
            for allow_lan in (False, True):
                with self.subTest(host=host, allow_lan=allow_lan):
                    self.assertEqual((host, 65535), _endpoint(host, 65535, allow_lan=allow_lan))
        for port in (0, -1, 65536, True, 1.0, '1234'):
            with self.subTest(port=port), self.assertRaises(ValueError):
                _endpoint('10.0.0.1', port, allow_lan=True)
        for option in (1, 0, 'yes', None):
            with self.subTest(option=option), self.assertRaises(ValueError):
                _endpoint('127.0.0.1', 1, allow_lan=option)
        for host in (None, 1234):
            with self.subTest(host=host), self.assertRaises(ValueError):
                _endpoint(host, 1, allow_lan=True)

    def test_node_invalid_endpoint_or_flag_does_not_create_database(self):
        database = self.root / 'not-created.sqlite'
        # Opted-in wildcard listeners are valid. Remote wildcard peers and
        # wildcard listeners without networking permission remain invalid.
        choices = [dict(host=host, allow_lan=True) for host in REJECTED if host != '0.0.0.0']
        choices += [dict(host='0.0.0.0')]
        choices += [dict(peers=((host, 1234),), allow_lan=True) for host in REJECTED]
        choices += [dict(host='10.0.0.1'), dict(peers=(('192.168.1.1', 1234),)), dict(allow_lan=1)]
        for options in choices:
            with self.subTest(options=options), self.assertRaises(ValueError):
                PeerNode(database, **options)
        self.assertFalse(database.exists())

    def test_cli_forbidden_addresses_rejected_before_database_open(self):
        database = self.root / 'existing.sqlite'
        database.write_bytes(b'keep bytes')
        cases = [(['--listen', host + ':1234', '--allow-lan']) for host in REJECTED if host != '0.0.0.0']
        cases += [['--listen', '0.0.0.0:1234']]
        cases += [['--listen', '192.168.1.1:1234'], ['--peer', '10.0.0.1:1234'],
                  ['--peer', '169.254.1.1:1234', '--allow-lan'],
                  ['--peer', '10.0.0.1:0', '--allow-lan']]
        for arguments in cases:
            error = StringIO()
            with self.subTest(arguments=arguments), patch.object(peerd, 'PeerNode') as constructor, redirect_stderr(error):
                self.assertEqual(2, peerd.main(['--database', str(database), *arguments]))
                constructor.assert_not_called()
                self.assertEqual('ValueError', json.loads(error.getvalue())['error'])
        self.assertEqual(b'keep bytes', database.read_bytes())

    def test_cli_opt_in_is_forwarded_and_default_options_compatible(self):
        async def fake_serve(options):
            self.assertTrue(options.allow_lan)
            self.assertEqual('192.168.1.123:0', options.listen)
        with patch.object(peerd, 'serve', side_effect=fake_serve):
            self.assertEqual(0, peerd.main(['--database', str(self.root / 'node.sqlite'),
                                          '--listen', '192.168.1.123:0', '--allow-lan']))
        self.assertFalse((self.root / 'node.sqlite').exists())

    def test_accepted_source_address_filtered_before_reserving_session(self):
        for allow_lan in (False, True):
            node = PeerNode(self.root / f'node-{allow_lan}.sqlite', allow_lan=allow_lan)
            self.addCleanup(node.chain.close)
            for host in REJECTED + PRIVATE + ('127.0.0.1',):
                writer = Mock()
                writer.get_extra_info.return_value = (host, 1234)
                allowed = host == '127.0.0.1' or (allow_lan and host in PRIVATE)
                with self.subTest(host=host, allow_lan=allow_lan), patch.object(node, '_reserve', return_value=None) as reserve:
                    node._accepted(Mock(), writer)
                    if allowed:
                        reserve.assert_called_once()
                        writer.close.assert_not_called()
                    else:
                        reserve.assert_not_called()
                        writer.close.assert_called_once()
            for remote in (None, (), ('10.0.0.1',), ('127.0.0.1', True)):
                writer = Mock()
                writer.get_extra_info.return_value = remote
                with patch.object(node, '_reserve') as reserve:
                    node._accepted(Mock(), writer)
                    reserve.assert_not_called()
                    writer.close.assert_called_once()


class LanSocketTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        WORK.mkdir(parents=True, exist_ok=True)
        self.directory = tempfile.TemporaryDirectory(prefix='sumuww-lan-socket-', dir=WORK)
        self.root = Path(self.directory.name)
        self.nodes = []

    async def asyncTearDown(self):
        await asyncio.gather(*(node.stop() for node in self.nodes), return_exceptions=True)
        self.directory.cleanup()

    def node(self, host='127.0.0.1', allow_lan=False):
        node = PeerNode(self.root / f'node-{len(self.nodes)}.sqlite', host=host,
                        allow_lan=allow_lan, poll_interval=.1, timeout=2, clock=lambda: NOW)
        self.nodes.append(node)
        return node

    async def sync(self, source, target):
        source.chain.mine(RegtestKey.from_int(1).script_pubkey, 3)
        await source.start()
        await target.start()
        await target.connect(*source.address)
        deadline = asyncio.get_running_loop().time() + 8
        while target.chain.tip_hash != source.chain.tip_hash:
            if asyncio.get_running_loop().time() >= deadline:
                self.fail('Local host nodes failed to synchronize within the deadline')
            await asyncio.sleep(.02)
        self.assertEqual(source.info()['utxo_commitment'], target.info()['utxo_commitment'])
        self.assertEqual(3, target.info()['height'])
        self.assertEqual(3, target.info()['stats']['blocks_stored'])

    async def test_opt_in_loopback_interoperates_with_default_node(self):
        source, target = self.node(), self.node(allow_lan=True)
        await self.sync(source, target)
        self.assertFalse(source.info()['allow_lan'])
        self.assertTrue(target.info()['allow_lan'])
        self.assertEqual('IPv4 loopback only', source.info()['endpoint_scope'])
        self.assertEqual('IPv4 loopback and RFC1918', target.info()['endpoint_scope'])
        self.assertEqual(genesis_block().block_hash(), target.genesis)
        self.assertEqual('dora-local-regtest-v0.8-p2wpkh', PROFILE_ID)
        self.assertEqual(1, PROTOCOL_VERSION)

    async def test_default_node_connects_to_opt_in_loopback_listener(self):
        source, target = self.node(allow_lan=True), self.node()
        await self.sync(source, target)
        self.assertEqual(1, source.info()['peers'])
        self.assertEqual(0, source.info()['stats']['address_rejections'])

    async def test_default_add_peer_rejects_lan_and_opt_in_add_peer_accepts_it(self):
        default, enabled = self.node(), self.node(allow_lan=True)
        # Register before starting; this test makes no outgoing connection.
        with self.assertRaises(ValueError):
            await default.add_peer('10.1.2.3', 1234)
        self.assertEqual(('10.1.2.3', 1234), await enabled.add_peer('10.1.2.3', 1234))
        self.assertEqual(1, enabled.info()['configured_peers'])
        with self.assertRaises(ValueError):
            await enabled.add_peer('8.8.8.8', 1234)

    async def test_real_private_nic_same_host_connection_when_available(self):
        addresses = local_private_addresses()
        if not addresses:
            self.skipTest('No RFC1918 IPv4 NIC address found on this host; multi-host LAN remains untested')
        selected = None
        for host in addresses:
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
                    probe.bind((host, 0))
                selected = host
                break
            except OSError:
                continue
        if selected is None:
            self.skipTest('Resolved RFC1918 addresses could not be bound locally; multi-host LAN remains untested')
        source, target = self.node(selected, True), self.node(selected, True)
        await self.sync(source, target)
        self.assertEqual(selected, source.address[0])
        self.assertEqual(selected, target.address[0])
        self.assertEqual(0, source.info()['stats']['address_rejections'])


if __name__ == '__main__':
    unittest.main()
