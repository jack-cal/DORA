"""Bounded fair router fallback and honest settled directory maintenance.

All discovery endpoints are loopback fixtures; no external DNS/UDP or user state.
"""
import asyncio
import socket
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from sumuww import dht_discovery as dht
from sumuww.profiles import REGTEST
from tests.test_dht_discovery_v29 import KrpcFixture, eventually


class DiscoverySettleTests(unittest.IsolatedAsyncioTestCase):
    def service(self, **extra):
        result = dht.DhtDiscovery(REGTEST, lambda hints: None, scope='loopback',
            routers=[('127.0.0.1', 1)], round_timeout=2, **extra)
        result._active = True
        return result

    @staticmethod
    def sleep_module(sleep):
        return SimpleNamespace(**{**vars(asyncio), 'sleep': sleep})

    async def test_closest_referrals_cannot_starve_other_router_or_dns_fallback(self):
        result = dht.DhtDiscovery(REGTEST, lambda hints: None, scope='loopback',
            routers=[('first.owned.invalid', 10001), ('second.owned.invalid', 20001)], round_timeout=2)
        result._active = True
        first = [('127.0.0.1', 10001 + index) for index in range(8)]
        second = [('127.0.0.1', 20001), ('127.0.0.1', 20002)]
        hint = ('127.0.0.1', 21001)
        calls = []
        nodes = b''.join(result.key + socket.inet_aton('127.0.0.1') + (30001 + index).to_bytes(2, 'big')
                         for index in range(64))
        async def addresses(router):
            return tuple(first if router[0].startswith('first.') else second)
        async def query(endpoint, method, arguments):
            calls.append(endpoint)
            if endpoint == second[1]:
                return {b'y': b'r', b'r': {b'id': result.key,
                    b'values': [socket.inet_aton(hint[0]) + hint[1].to_bytes(2, 'big')]}}
            if endpoint == second[0]:
                return None
            return {b'y': b'r', b'r': {b'id': result.key, b'nodes': nodes}}
        result._router_addresses = addresses
        result._query = query
        hints = await result.lookup_once()
        self.assertEqual((hint,), hints)
        self.assertEqual([first[0], second[0], first[1]], calls[:3])
        self.assertEqual(second[1], calls[3])
        self.assertEqual(dht.MAX_QUERIES, len(calls))
        self.assertEqual(len(calls), len(set(calls)))
        self.assertEqual('hints_received', result.info()['last_lookup_result'])

    async def test_eight_configured_routers_are_probed_before_closer_referrals(self):
        routers = [(f'router{index}.owned.invalid', 10000 + index) for index in range(8)]
        result = dht.DhtDiscovery(REGTEST, lambda hints: None, scope='loopback', routers=routers, round_timeout=2)
        result._active = True
        calls = []
        endpoints = [('127.0.0.1', port) for _, port in routers]
        node = result.key + socket.inet_aton('127.0.0.1') + (30001).to_bytes(2, 'big')
        async def addresses(router):
            return (('127.0.0.1', router[1]),)
        async def query(endpoint, method, arguments):
            calls.append(endpoint)
            return {b'y': b'r', b'r': {b'id': result.key, b'nodes': node}}
        result._router_addresses = addresses
        result._query = query
        await result.lookup_once()
        self.assertEqual(endpoints, calls[:8])
        self.assertEqual(9, len(calls))

    async def test_settled_nonadvertising_client_skips_rounds_then_resumes_on_backup_loss(self):
        now = [1000.]
        settled = [True]
        result = self.service(clock=lambda: now[0], connected_provider=lambda: True,
                              settled_provider=lambda: settled[0])
        snapshots = []
        calls = []
        async def sleep(delay):
            snapshots.append(result.info())
            self.assertEqual('settled_idle', snapshots[-1]['maintenance_mode'])
            self.assertEqual(0, snapshots[-1]['next_query_seconds'])
            self.assertEqual(0, len(calls))
            now[0] += delay
            settled[0] = False
        async def lookup():
            calls.append(now[0])
            result._active = False
            return ()
        result._lookup = lookup
        with patch.object(dht, 'asyncio', self.sleep_module(sleep)):
            await result._run()
        self.assertEqual([1001.], calls)
        self.assertEqual(1, len(snapshots))

    async def test_public_advertising_node_keeps_refresh_despite_settled_backups(self):
        now = [1000.]
        result = self.service(clock=lambda: now[0], connected_provider=lambda: True,
            settled_provider=lambda: True, contact_provider=lambda: ('127.0.0.1', 21001))
        calls = []
        async def lookup():
            self.assertEqual('public_contact_refresh', result.info()['maintenance_mode'])
            calls.append(now[0])
            if len(calls) == 2:
                result._active = False
            return ()
        async def sleep(delay):
            now[0] += delay
        result._lookup = lookup
        with patch.object(dht, 'asyncio', self.sleep_module(sleep)):
            await result._run()
        self.assertEqual([1000., 1300.], calls)

    async def test_settled_callback_cannot_suppress_disconnected_search(self):
        result = self.service(connected_provider=lambda: False, settled_provider=lambda: True)
        calls = []
        async def lookup():
            calls.append(1)
            result._active = False
            return ()
        result._lookup = lookup
        await result._run()
        self.assertEqual([1], calls)

    async def test_real_owned_udp_resumes_after_settled_and_reports_zero_sumuww_contacts(self):
        settled = [True]
        router = KrpcFixture()
        transport, _ = await asyncio.get_running_loop().create_datagram_endpoint(
            lambda: router, local_addr=('127.0.0.1', 0))
        result = dht.DhtDiscovery(REGTEST, lambda hints: None, scope='loopback', routers=[router.address],
            connected_provider=lambda: True, settled_provider=lambda: settled[0], query_timeout=.1, round_timeout=.5)
        try:
            await result.start()
            await eventually(lambda: result.info()['maintenance_mode'] == 'settled_idle')
            await asyncio.sleep(.02)
            self.assertEqual(0, result.info()['stats']['queries'])
            self.assertEqual([], router.messages)
            settled[0] = False
            await eventually(lambda: result.info()['last_lookup_result'] == 'no_sumuww_contacts', timeout=1.5)
            self.assertGreater(result.info()['stats']['responses'], 0)
            self.assertEqual(0, result.info()['stats']['accepted_hints'])
            self.assertIsNone(result.info()['last_error'])
            settled[0] = True
            await result.stop()
            self.assertIsNone(result.info()['last_lookup_result'])
            self.assertEqual(0, result.info()['pending_queries'])
        finally:
            await result.stop()
            transport.close()

    async def test_no_router_reply_and_deadline_are_distinct_from_no_sumuww_contacts(self):
        result = self.service()
        async def addresses(router):
            return (router,)
        async def query(endpoint, method, arguments):
            return None
        result._router_addresses = addresses
        result._query = query
        self.assertEqual((), await result.lookup_once())
        self.assertEqual('no_router_reply', result.info()['last_lookup_result'])
        self.assertEqual('No DHT response', result.info()['last_error'])
        result.round_timeout = .01
        async def blocked():
            await asyncio.sleep(1)
        result._lookup = blocked
        self.assertEqual((), await result.lookup_once())
        self.assertEqual('deadline', result.info()['last_lookup_result'])

    async def test_settled_callback_validation_failure_and_stop_cleanup(self):
        with self.assertRaises(ValueError):
            dht.DhtDiscovery(REGTEST, lambda hints: None, settled_provider=True)
        def faulty():
            raise ValueError('owned provider fault')
        result = self.service(connected_provider=lambda: True, settled_provider=faulty)
        self.assertFalse(result.info()['automatic_search_settled'])
        result.settled_provider = lambda: True
        result._task = asyncio.create_task(result._run())
        await eventually(lambda: result.info()['maintenance_mode'] == 'settled_idle')
        await asyncio.wait_for(result.stop(), .2)
        self.assertIsNone(result._task)
        self.assertFalse(result.info()['automatic_search_settled'])
        self.assertEqual('not_running', result.info()['maintenance_mode'])


if __name__ == '__main__':
    unittest.main()
