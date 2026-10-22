"""BEP 3/5 fixtures and bounded SUMUWW DHT hints; no public UDP or real wallets.

Loopback is an explicit non-main testing scope. Production public-address
validation remains enabled and is tested separately; fixtures do not establish
public Internet reachability. Responses are encoded independently of SUMUWW.
"""
import asyncio
import socket
import struct
import time
import unittest

from sumuww import dht_discovery as dht
from sumuww.profiles import SUMUWW, REGTEST, RETARGET_LAB


def fixture_encode(value):
    """Independent minimal BEP fixture writer, for trusted test data only."""
    if type(value) is int:
        return b'i' + str(value).encode('ascii') + b'e'
    if isinstance(value, bytes):
        return str(len(value)).encode('ascii') + b':' + value
    if isinstance(value, list):
        return b'l' + b''.join(fixture_encode(item) for item in value) + b'e'
    if isinstance(value, dict):
        return b'd' + b''.join(fixture_encode(key) + fixture_encode(value[key])
                               for key in sorted(value)) + b'e'
    raise TypeError('Fixture bencode type unsupported')


def compact(endpoint):
    return socket.inet_aton(endpoint[0]) + struct.pack('!H', endpoint[1])


async def eventually(predicate, timeout=4):
    deadline = time.monotonic() + timeout
    while not predicate():
        if time.monotonic() >= deadline:
            raise AssertionError('Isolated DHT fixture deadline exceeded')
        await asyncio.sleep(.01)


class KrpcFixture(asyncio.DatagramProtocol):
    """Owned loopback KRPC server with independently encoded responses."""
    def __init__(self, peers=(), token=b'owned-fixture-token', responder=None, nodes=b''):
        self.peers, self.token, self.responder, self.nodes = tuple(peers), token, responder, nodes
        self.transport = None
        self.messages, self.errors = [], []
        self.identifier = b'owned-fixture-nodeid'  # Exactly 20 bytes.

    def connection_made(self, transport):
        self.transport = transport

    @property
    def address(self):
        return self.transport.get_extra_info('sockname')[:2]

    def reply(self, request, source, fields=None, *, transaction=None, sender=None):
        response = {b't': request[b't'] if transaction is None else transaction,
                    b'y': b'r', b'r': {b'id': self.identifier, **(fields or {})}}
        (sender or self.transport).sendto(fixture_encode(response), source)

    def datagram_received(self, data, source):
        try:
            request = dht.decode_bencode(data)
            self.messages.append((request, source))
            if self.responder is not None:
                self.responder(self, request, source)
            elif request.get(b'q') == b'get_peers':
                fields = {b'token': self.token}
                if self.peers:
                    fields[b'values'] = [compact(value) for value in self.peers]
                else:
                    fields[b'nodes'] = self.nodes
                self.reply(request, source, fields)
            elif request.get(b'q') == b'announce_peer':
                self.reply(request, source)
        except Exception as error:
            self.errors.append(type(error).__name__)


class BencodeSecurityTests(unittest.TestCase):
    def test_official_bep5_ping_wire_vector_and_binary_payload_roundtrip(self):
        # https://www.bittorrent.org/beps/bep_0005.html, public-domain example.
        raw = b'd1:ad2:id20:abcdefghij0123456789e1:q4:ping1:t2:aa1:y1:qe'
        value = {b't': b'aa', b'y': b'q', b'q': b'ping',
                 b'a': {b'id': b'abcdefghij0123456789'}}
        self.assertEqual(value, dht.decode_bencode(raw))
        self.assertEqual(raw, dht.encode_bencode(value))
        binary = {b'a': [b'\x00\xff:\r\n', -42, 0], b'z': b''}
        self.assertEqual(binary, dht.decode_bencode(fixture_encode(binary)))

    def test_malformed_noncanonical_truncated_and_trailing_encodings_rejected(self):
        for raw in (b'', b'i-0e', b'i00e', b'i+1e', b'ie', b'i1', b'01:a',
                    b'3:ab', b'1:a0:', b'letrailing', b'd1:bi1e1:ai2ee',
                    b'd1:ai1e1:ai2ee', b'di1e1:ae', b'd1:ae', b'x'):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                dht.decode_bencode(raw)

    def test_datagram_string_depth_item_and_integer_budgets_fail_closed(self):
        oversized = (b'1:x' + b' ' * 8192, b'4097:' + b'x' * 4097,
                     b'l' * 10 + b'0:' + b'e' * 10,
                     b'l' + b'i0e' * 257 + b'e',
                     b'i9223372036854775808e', b'i-9223372036854775809e',
                     b'9' * 100 + b':x')
        for raw in oversized:
            with self.subTest(length=len(raw)), self.assertRaises(ValueError):
                dht.decode_bencode(raw)
        for number in (-2**63, 2**63 - 1):
            self.assertEqual(number, dht.decode_bencode(fixture_encode(number)))

    def test_encoder_rejects_unsupported_types_and_unbounded_inputs(self):
        for value in (True, False, 1.5, 'unicode', None, {1: b'wrong-key'},
                      2**63, -(2**63)-1, b'x' * 4097):
            with self.subTest(kind=type(value).__name__), self.assertRaises(ValueError):
                dht.encode_bencode(value)

    def test_discovery_keys_are_deterministic_and_profile_genesis_separated(self):
        keys = [dht.discovery_key(profile) for profile in (SUMUWW, REGTEST, RETARGET_LAB)]
        self.assertEqual(3, len(set(keys)))
        self.assertTrue(all(isinstance(key, bytes) and len(key) == 20 for key in keys))
        self.assertEqual(keys[0], dht.discovery_key('dora'))
        self.assertEqual(keys[1], dht.discovery_key('regtest'))

    def test_mainnet_never_permits_loopback_fixture_scope(self):
        with self.assertRaises(ValueError):
            dht.DhtDiscovery(SUMUWW, lambda hints: None, scope='loopback',
                             routers=[('127.0.0.1', 12345)])

    def test_production_public_scope_filters_all_non_global_ipv4_and_bad_ports(self):
        service = dht.DhtDiscovery(SUMUWW, lambda hints: None)
        excluded = ('127.0.0.1', '10.1.2.3', '192.168.1.2', '172.16.1.2',
                    '100.64.1.2', '169.254.1.2', '0.0.0.0', '192.0.2.1',
                    '198.51.100.1', '203.0.113.1', '224.0.0.1', '255.255.255.255')
        valid = [('8.8.8.8', 34567), ('1.1.1.1', 34568)]
        values = [compact(endpoint) for endpoint in valid + valid]
        values += [compact((host, 34567)) for host in excluded]
        values += [compact(('8.8.4.4', 0))]
        hints, nodes, token = service._parse_contacts({b'values': values})
        self.assertEqual(valid, hints)
        self.assertEqual([], nodes)
        self.assertIsNone(token)
        for host in excluded + ('::1', 'peer.fixture.invalid'):
            with self.subTest(host=host), self.assertRaises(ValueError):
                dht._scope_endpoint(host, 34567, 'public')
        for port in (0, -1, 65536, True, '34567'):
            with self.subTest(port=port), self.assertRaises(ValueError):
                dht._scope_endpoint('8.8.8.8', port, 'public')

    def test_compact_peer_node_and_token_payloads_are_strict_and_bounded(self):
        service = dht.DhtDiscovery(SUMUWW, lambda hints: None)
        malformed = ({b'values': b'not-a-list'}, {b'values': [b'12345']},
                     {b'values': [b'1234567']}, {b'values': [123]},
                     {b'values': [compact(('8.8.8.8', 34567))] * 129},
                     {b'nodes': b'x' * 25}, {b'nodes': b'x' * (129 * 26)},
                     {b'nodes': []}, {b'token': b''}, {b'token': b'x' * 129},
                     {b'token': 7})
        for body in malformed:
            with self.subTest(fields=list(body)), self.assertRaises(ValueError):
                service._parse_contacts(body)
        nodes = b'1' * 20 + compact(('8.8.8.8', 34567))
        hints, parsed, token = service._parse_contacts({b'nodes': nodes, b'token': b'x' * 128})
        self.assertEqual([], hints)
        self.assertEqual([(b'1' * 20, ('8.8.8.8', 34567))], parsed)
        self.assertEqual(b'x' * 128, token)


class DatagramSecurityTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.servers, self.services, self.transports = [], [], []

    async def asyncTearDown(self):
        await asyncio.gather(*(service.stop() for service in self.services), return_exceptions=True)
        for transport in self.transports:
            transport.close()
        await asyncio.sleep(.01)

    async def server(self, **options):
        protocol = KrpcFixture(**options)
        transport, _ = await asyncio.get_running_loop().create_datagram_endpoint(
            lambda: protocol, local_addr=('127.0.0.1', 0))
        self.servers.append(protocol)
        self.transports.append(transport)
        return protocol

    def service(self, server, callback, **options):
        options.setdefault('scope', 'loopback')
        options.setdefault('routers', [server.address])
        options.setdefault('query_timeout', .2)
        options.setdefault('round_timeout', 2)
        service = dht.DhtDiscovery(REGTEST, callback, **options)
        self.services.append(service)
        return service

    async def test_real_udp_response_yields_only_deduplicated_nonself_tcp_hints(self):
        remote, myself = ('127.0.0.1', 34567), ('127.0.0.1', 34568)
        server = await self.server(peers=(remote, remote, myself))
        received = []
        service = self.service(server, received.extend, self_endpoints=lambda: (myself,))
        await service.start()
        await eventually(lambda: bool(received))
        self.assertEqual([remote], received)
        self.assertFalse(server.errors)
        query, _ = server.messages[0]
        self.assertEqual(b'get_peers', query[b'q'])
        self.assertEqual(dht.discovery_key(REGTEST), query[b'a'][b'info_hash'])
        self.assertEqual(20, len(query[b'a'][b'id']))
        self.assertTrue(service.info()['hint_only'])
        self.assertFalse(any(name in service.info() for name in ('height', 'balance', 'chainwork', 'mining_ready')))

    async def test_read_only_lookup_accepts_reply_after_unused_announcement_reserve(self):
        remote = ('127.0.0.1', 34567)
        def respond(server, request, source):
            fields = {b'values': [compact(remote)], b'token': b'owned-token'}
            asyncio.get_running_loop().call_later(.75, server.reply, request, source, fields)
        server = await self.server(responder=respond)
        received = []
        service = self.service(server, received.extend, query_timeout=1, round_timeout=1)
        await service.start()
        await eventually(lambda: bool(received), timeout=1.3)
        self.assertEqual([remote], received)
        self.assertEqual(0, service.info()['stats']['announce_attempts'])

    async def test_read_only_round_delivers_before_silent_referrals_and_finishes_at_deadline(self):
        silent = [await self.server(responder=lambda *args: None) for _ in range(8)]
        records = b''.join(index.to_bytes(20, 'big') + compact(server.address)
                           for index, server in enumerate(silent))
        remote = ('127.0.0.1', 34569)
        router = await self.server(peers=[remote], nodes=records,
            responder=lambda server, request, source: server.reply(request, source,
                {b'values': [compact(remote)], b'nodes': records}))
        received = []
        service = self.service(router, received.extend, round_timeout=.4, query_timeout=.3)
        await service.start()
        await eventually(lambda: bool(received), timeout=.2)
        self.assertTrue(service.info()['round_in_progress'])
        await eventually(lambda: not service.info()['round_in_progress'], timeout=.7)
        self.assertEqual([remote], received)
        self.assertEqual('hints_received', service.info()['last_lookup_result'])
        self.assertEqual(0, service.info()['stats']['round_errors'])
        self.assertEqual(0, service.info()['pending_queries'])

    async def test_wrong_transaction_and_wrong_udp_source_cannot_complete_pending_query(self):
        remote = ('127.0.0.1', 34567)
        rogue = await self.server()
        observations = []
        def respond(server, request, source):
            if request.get(b'q') != b'get_peers':
                server.reply(request, source)
                return
            fields = {b'values': [compact(remote)], b'token': b'good-token'}
            server.reply(request, source, fields, transaction=b'wrong-transaction')
            server.reply(request, source, fields, sender=rogue.transport)
            def valid():
                observations.append(list(received))
                server.reply(request, source, fields)
            asyncio.get_running_loop().call_later(.07, valid)
        server = await self.server(responder=respond)
        received = []
        service = self.service(server, received.extend)
        await service.start()
        await eventually(lambda: bool(received))
        self.assertEqual([[]], observations)
        self.assertEqual([remote], received)
        self.assertFalse(server.errors)

    async def test_only_correlated_response_with_exact_node_identifier_can_add_hint(self):
        remote = ('127.0.0.1', 34567)
        captured = []
        def respond(server, request, source):
            wrong = {b't': request[b't'], b'y': b'r',
                     b'r': {b'id': b'too-short', b'values': [compact(remote)]}}
            server.transport.sendto(fixture_encode(wrong), source)
            captured.append(True)
        server = await self.server(responder=respond)
        received = []
        service = self.service(server, received.extend)
        await service.start()
        await eventually(lambda: bool(captured))
        await asyncio.sleep(.25)
        self.assertFalse(received)

    async def test_announce_uses_same_router_token_explicit_tcp_port_and_implied_port_zero(self):
        server = await self.server(peers=(('127.0.0.1', 34568),), token=b'router-bound-token')
        service = self.service(server, lambda hints: None,
                               contact_provider=lambda: ('127.0.0.1', 34567))
        await service.start()
        await eventually(lambda: any(message.get(b'q') == b'announce_peer'
                                      for message, source in server.messages))
        announces = [(message, source) for message, source in server.messages
                     if message.get(b'q') == b'announce_peer']
        self.assertEqual(1, len(announces))
        message, source = announces[0]
        self.assertEqual(34567, message[b'a'][b'port'])
        self.assertEqual(0, message[b'a'][b'implied_port'])
        self.assertNotEqual(source[1], message[b'a'][b'port'])
        self.assertEqual(b'router-bound-token', message[b'a'][b'token'])
        self.assertEqual(dht.discovery_key(REGTEST), message[b'a'][b'info_hash'])
        self.assertNotIn(b'ip', message[b'a'])

    async def test_empty_or_oversized_token_cannot_authorize_announcement(self):
        for token in (b'', b'x' * 4097):
            with self.subTest(token_length=len(token)):
                server = await self.server(peers=(('127.0.0.1', 34568),), token=token)
                service = self.service(server, lambda hints: None,
                                       contact_provider=lambda: ('127.0.0.1', 34567))
                await service.start()
                await eventually(lambda: bool(server.messages))
                await asyncio.sleep(.25)
                self.assertFalse(any(message.get(b'q') == b'announce_peer' for message, source in server.messages))
                await service.stop()

    async def test_no_contact_never_announces_udp_source_port_as_tcp_listener(self):
        server = await self.server(peers=(('127.0.0.1', 34568),))
        service = self.service(server, lambda hints: None, contact_provider=lambda: None)
        await service.start()
        await eventually(lambda: bool(server.messages))
        await asyncio.sleep(.08)
        self.assertFalse(any(message.get(b'q') == b'announce_peer' for message, source in server.messages))

    async def test_nodes_response_traverses_real_udp_router_before_delivering_sumuww_contact(self):
        remote = ('127.0.0.1', 34567)
        next_router = await self.server(peers=(remote,))
        first = await self.server(nodes=next_router.identifier + compact(next_router.address))
        received = []
        service = self.service(first, received.extend)
        await service.start()
        await eventually(lambda: bool(received))
        self.assertEqual([remote], received)
        self.assertEqual(1, len(first.messages))
        self.assertEqual(1, len(next_router.messages))
        self.assertEqual(2, service.info()['stats']['queries'])
        self.assertFalse(first.errors or next_router.errors)

    async def test_router_specific_tokens_are_never_sent_to_another_udp_endpoint(self):
        first = await self.server(token=b'first-router-token')
        second = await self.server(token=b'second-router-token')
        service = self.service(first, lambda hints: None, routers=[first.address, second.address],
                               contact_provider=lambda: ('127.0.0.1', 34567))
        await service.start()
        await eventually(lambda: all(any(message.get(b'q') == b'announce_peer'
                                        for message, source in server.messages) for server in (first, second)))
        for server, expected in ((first, b'first-router-token'), (second, b'second-router-token')):
            announces = [message for message, source in server.messages if message.get(b'q') == b'announce_peer']
            self.assertEqual([expected], [message[b'a'][b'token'] for message in announces])

    async def test_unsolicited_krpc_query_gets_no_reply_or_hint_and_requests_are_readonly(self):
        server = await self.server(peers=(('127.0.0.1', 34567),))
        received = []
        service = self.service(server, received.extend)
        await service.start()
        await eventually(lambda: bool(received))
        query, source = server.messages[0]
        self.assertEqual(1, query[b'ro'])
        before = len(server.messages)
        unsolicited = {b't': b'unsolicited', b'y': b'q', b'q': b'get_peers',
                       b'a': {b'id': server.identifier, b'info_hash': dht.discovery_key(REGTEST)}}
        server.transport.sendto(fixture_encode(unsolicited), source)
        await asyncio.sleep(.06)
        self.assertEqual(before, len(server.messages))
        self.assertEqual([('127.0.0.1', 34567)], received)

    async def test_real_udp_query_fanout_including_announces_stays_within_total_budget(self):
        # Fifty owned UDP routers make the 48-query budget meaningful. A small
        # response delay measures actual concurrent requests rather than just
        # asserting exported constants. No public destination is involved.
        pending = [0]
        maximum = [0]
        requests = []
        node_records = [b'']
        def respond(server, request, source):
            requests.append(request[b'q'])
            pending[0] += 1
            maximum[0] = max(maximum[0], pending[0])
            def finish():
                fields = ({b'nodes': node_records[0], b'token': b'bounded-router-token'}
                          if request[b'q'] == b'get_peers' else {})
                server.reply(request, source, fields)
                pending[0] -= 1
            asyncio.get_running_loop().call_later(.01, finish)
        routers = [await self.server(responder=respond) for _ in range(50)]
        node_records[0] = b''.join(index.to_bytes(20, 'big') + compact(server.address)
                                  for index, server in enumerate(routers))
        service = self.service(routers[0], lambda hints: None,
                               contact_provider=lambda: ('127.0.0.1', 34567))
        await service.start()
        await eventually(lambda: len(requests) >= 48 and service.info()['pending_queries'] == 0, timeout=4)
        await asyncio.sleep(.03)
        self.assertEqual(48, len(requests))
        self.assertEqual(48, service.info()['stats']['queries'])
        self.assertLessEqual(maximum[0], 3)
        self.assertGreaterEqual(maximum[0], 2)
        self.assertGreater(requests.count(b'announce_peer'), 0)
        self.assertLessEqual(requests.count(b'announce_peer'), 8)
        self.assertLessEqual(service.info()['stats']['candidate_nodes'], 128)
        self.assertFalse(any(server.errors for server in routers))

    async def test_silent_routing_nodes_cannot_erase_received_hints_or_starve_announcement(self):
        # This models a real DHT round: a good router supplies contacts/token,
        # then dead routing contacts use their timeouts. Existing results must
        # survive while publication has its own share of the whole deadline.
        silent = [await self.server(responder=lambda *arguments: None) for _ in range(8)]
        node_records = b''.join(index.to_bytes(20, 'big') + compact(server.address)
                                for index, server in enumerate(silent))
        remote = ('127.0.0.1', 34568)
        def respond(server, request, source):
            fields = ({b'values': [compact(remote)], b'nodes': node_records, b'token': b'good-round-token'}
                      if request[b'q'] == b'get_peers' else {})
            server.reply(request, source, fields)
        router = await self.server(responder=respond)
        received = []
        service = self.service(router, received.extend, round_timeout=.4, query_timeout=.2,
                               contact_provider=lambda: ('127.0.0.1', 34567))
        begin = time.monotonic()
        await service.start()
        await eventually(lambda: bool(received) and service.info()['stats']['announcements'] > 0, timeout=1.2)
        self.assertLess(time.monotonic() - begin, .65)
        self.assertEqual([remote], received)
        self.assertGreater(sum(len(server.messages) for server in silent), 0)
        announce = [request for request, source in router.messages if request.get(b'q') == b'announce_peer']
        self.assertEqual([b'good-round-token'], [request[b'a'][b'token'] for request in announce])
        self.assertLessEqual(service.info()['stats']['queries'], 48)
        await service.stop()
        self.assertEqual(0, service.info()['pending_queries'])

    async def test_timeout_is_bounded_and_stop_leaves_no_dht_background_tasks(self):
        server = await self.server(responder=lambda *arguments: None)
        received = []
        service = self.service(server, received.extend)
        start = time.monotonic()
        await service.start()
        await eventually(lambda: bool(server.messages))
        await asyncio.sleep(.3)
        self.assertFalse(received)
        stop = time.monotonic()
        await service.stop()
        self.assertLess(time.monotonic() - stop, .5)
        self.assertLess(time.monotonic() - start, 2)
        self.assertLessEqual(len(server.messages), 48)
        self.assertFalse(any(not task.done() and 'dht' in task.get_name().lower()
                             for task in asyncio.all_tasks() if task is not asyncio.current_task()))


if __name__ == '__main__':
    unittest.main()
