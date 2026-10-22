"""Discovery recovery and parser fairness with owned caches and loopback UDP."""

import asyncio
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from sumuww import dht_discovery as dht
from sumuww.peer_discovery import PeerAddressBook
from sumuww.profiles import REGTEST
from tests.test_dht_discovery_v29 import KrpcFixture, compact, eventually, fixture_encode


FIXTURE_CONTACT_COUNT=128  # Test input size, not a product limit.

class StaleAddressBookTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='sumuww-stale-cache-v37-')
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'node.sqlite.peers.json'
        self.now = [10000.0]
        self.old = tuple(('127.0.0.1', 10000 + index) for index in range(FIXTURE_CONTACT_COUNT))
        self.path.write_text(json.dumps({'version': 1, 'network': REGTEST.profile_id,
            'genesis': REGTEST.genesis.block_hash().hex(),
            'peers': [{'host': host, 'port': port, 'last_success': 1.0} for host, port in self.old]}), encoding='utf-8')
        self.book = PeerAddressBook(self.path, REGTEST.profile_id, REGTEST.genesis.block_hash(),
            scope='loopback', clock=lambda: self.now[0], retry_clock=lambda: self.now[0])

    def test_full_persisted_failed_verified_cache_can_discover_a_new_healthy_peer(self):
        for _ in range(10):
            for endpoint in self.old:
                self.book.attempted(endpoint)
            self.now[0] += 301
        healthy = ('127.0.0.1', 34567)
        # Current stale-contact policy expires repeated failures, freeing slots.
        self.assertEqual(FIXTURE_CONTACT_COUNT, self.book.expired)
        self.assertEqual(0, len(self.book._entries))
        self.assertTrue(self.book.add_hint(healthy))
        self.assertEqual(1, len(self.book._entries))
        self.assertEqual(healthy, self.book.candidate(excluded=self.old))
        self.book.verified(healthy)
        reloaded = PeerAddressBook(self.path, REGTEST.profile_id, REGTEST.genesis.block_hash(),
                                  scope='loopback', clock=lambda: self.now[0])
        self.assertIn(healthy, reloaded.known(FIXTURE_CONTACT_COUNT))
        self.assertEqual((healthy,), reloaded.known(FIXTURE_CONTACT_COUNT))
        self.assertEqual(1, len(reloaded._entries))

    def test_zero_one_or_two_failed_attempts_do_not_evict_working_verified_contacts(self):
        self.assertTrue(self.book.add_hint(('127.0.0.1',34567)))
        self.assertTrue(set(self.old).issubset(self.book._entries))
        self.assertEqual(FIXTURE_CONTACT_COUNT+1,len(self.book._entries))
        self.book.attempted(self.old[0])
        self.assertNotIn(self.old[0],self.book._entries)
        self.assertTrue(set(self.old[1:]).issubset(self.book._entries))

    def test_replacement_prefers_worst_failures_and_retains_good_contacts_and_128_cap(self):
        self.book.attempted(self.old[0]);self.book.attempted(self.old[1])
        target=('127.0.0.1',34567)
        self.assertTrue(self.book.add_hint(target))
        self.assertNotIn(self.old[0],self.book._entries)
        self.assertNotIn(self.old[1],self.book._entries)
        self.book.attempted(target)
        self.assertNotIn(target,self.book._entries)
        self.assertTrue(self.book.add_hint(('127.0.0.1',34568)))
        self.assertEqual(FIXTURE_CONTACT_COUNT-1,len(self.book._entries))
        self.assertTrue(set(self.old[2:]).issubset(self.book._entries))


class DhtReplyFairnessTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.services, self.transports = [], []
    async def asyncTearDown(self):
        await asyncio.gather(*(service.stop() for service in self.services), return_exceptions=True)
        for transport in self.transports:
            transport.close()
        await asyncio.sleep(.01)

    def service(self, **options):
        options.setdefault('routers', [('127.0.0.1', 1)])
        options.setdefault('query_timeout', .03)
        options.setdefault('round_timeout', .8)
        service = dht.DhtDiscovery(REGTEST, options.pop('on_hints', lambda values: None), scope='loopback', **options)
        self.services.append(service)
        return service

    async def test_real_noisy_router_does_not_consume_other_routers_correlated_reply(self):
        def noise(server, request, source):
            def burst():
                for _ in range(50):
                    server.transport.sendto(b'not-a-response', source)
            for delay in (0, .005, .01):
                asyncio.get_running_loop().call_later(delay, burst)
        healthy = ('127.0.0.1', 34567)
        def reply(server, request, source):
            asyncio.get_running_loop().call_later(.08, server.reply, request, source,
                {b'values': [compact(healthy)]})
        routers = [KrpcFixture(responder=noise), KrpcFixture(responder=reply)]
        for router in routers:
            transport, _ = await asyncio.get_running_loop().create_datagram_endpoint(
                lambda router=router: router, local_addr=('127.0.0.1', 0))
            self.transports.append(transport)
        received = []
        service = self.service(routers=[router.address for router in routers], on_hints=received.extend,
            query_timeout=.3, clock=lambda: 1000.0)
        await service.start()
        await eventually(lambda: healthy in received)
        self.assertGreater(service._stats['rate_rejections'], 0)
        self.assertEqual(1, service._stats['responses'])
        self.assertEqual({}, service._pending)
        self.assertEqual({}, service._reserved_reply_packets)
        self.assertTrue(all(not router.errors for router in routers))

    async def test_reserved_parser_quota_is_small_source_specific_and_one_shot(self):
        service = self.service(clock=lambda: 1000.0)
        service._active = True
        loop = asyncio.get_running_loop()
        rogue, healthy = loop.create_future(), loop.create_future()
        service._pending = {b'rogue': (('127.0.0.1', 10001), rogue),
                            b'healthy': (('127.0.0.1', 10002), healthy)}
        service._reserved_reply_packets = {b'rogue': 0, b'healthy': 0}
        with patch.object(dht, 'decode_bencode', wraps=dht.decode_bencode) as decoder:
            for _ in range(dht.MAX_DATAGRAMS_PER_SECOND):
                service._received(b'junk', ('127.0.0.1', 10003))
            for _ in range(1000):
                service._received(b'junk', ('127.0.0.1', 10001))
                service._received(b'junk', ('127.0.0.1', 10003))
            self.assertEqual(dht.MAX_DATAGRAMS_PER_SECOND + dht.MAX_RESERVED_REPLY_PACKETS, decoder.call_count)
            service._received(b'x' * (dht.MAX_PACKET_BYTES + 1), ('127.0.0.1', 10002))
            self.assertEqual(0, service._reserved_reply_packets[b'healthy'])
            packet = fixture_encode({b't': b'healthy', b'y': b'r', b'r': {b'id': b'h' * 20}})
            service._received(packet, ('127.0.0.1', 10002))
            self.assertTrue(healthy.done())
            self.assertFalse(rogue.done())
            count = decoder.call_count
            for _ in range(100):
                service._received(packet, ('127.0.0.1', 10002))
            self.assertEqual(count, decoder.call_count)
        self.assertEqual(dht.MAX_RESERVED_REPLY_PACKETS, service._reserved_reply_packets[b'rogue'])
        self.assertEqual(1, service._reserved_reply_packets[b'healthy'])
        await service.stop()
        self.assertEqual({}, service._reserved_reply_packets)

    async def test_timeout_cancellation_capacity_and_stop_clear_reserved_query_state(self):
        service = self.service()
        class Transport:
            def sendto(self, packet, address):
                pass
            def close(self):
                pass
        service._active, service._transport = True, Transport()
        tasks = [asyncio.create_task(service._query(('127.0.0.1', 10000 + index), b'get_peers',
            {b'info_hash': service.key})) for index in range(3)]
        await asyncio.sleep(.005)
        self.assertEqual(3, len(service._pending))
        self.assertEqual(3, len(service._reserved_reply_packets))
        with self.assertRaises(OSError):
            await service._query(('127.0.0.1', 10004), b'get_peers', {b'info_hash': service.key})
        tasks[0].cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        self.assertEqual({}, service._pending)
        self.assertEqual({}, service._reserved_reply_packets)
        task = asyncio.create_task(service._query(('127.0.0.1', 10005), b'get_peers', {b'info_hash': service.key}))
        await asyncio.sleep(.005)
        await service.stop()
        await asyncio.gather(task, return_exceptions=True)
        self.assertEqual({}, service._pending)
        self.assertEqual({}, service._reserved_reply_packets)


if __name__ == '__main__':
    unittest.main()
