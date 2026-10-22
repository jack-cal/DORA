"""Offline fixtures only: strict contact manifests and bounded OS DNS jobs."""
import asyncio
import json
from pathlib import Path
import socket
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from sumuww.bootstrap import (MAX_DNS_WORKERS, BootstrapConfig, load_bootstrap,
                            lookup_seed, normalize_fallbacks, normalize_seeds)
from sumuww.profiles import get_network


def dns_records(hosts,port=18444):
    return [(socket.AF_INET,socket.SOCK_STREAM,socket.IPPROTO_TCP,'',(host,port)) for host in hosts]


class BootstrapManifestTests(unittest.TestCase):
    def setUp(self):
        self.temporary=tempfile.TemporaryDirectory(prefix='sumuww-bootstrap-manifest-')
        self.path=Path(self.temporary.name)/'contacts.json'
        self.profile=get_network('dora')

    def tearDown(self):self.temporary.cleanup()

    def value(self,**changes):
        result={'schema_version':2,'network':'dora','genesis':self.profile.genesis.block_hash().hex(),
                'dns_seeds':[],'fallback_peers':[]}
        result.update(changes);return result

    def write(self,value):self.path.write_text(json.dumps(value),encoding='utf-8')

    def test_absent_manifest_has_no_fabricated_contact(self):
        with patch('sumuww.bootstrap.manifest_path',return_value=self.path):
            self.assertEqual(load_bootstrap(),BootstrapConfig())
        with self.assertRaises(ValueError):load_bootstrap(path=self.path)
        self.assertFalse(self.path.exists())

    def test_shipped_manifest_is_empty_and_bound_to_exact_main_genesis(self):
        config=load_bootstrap(self.profile)
        self.assertEqual(config,BootstrapConfig())

    def test_valid_config_accepts_normalized_public_dns_and_numeric_contacts(self):
        self.write(self.value(dns_seeds=[{'host':'Seed.Fixture.Invalid.','port':18444}],
                              fallback_peers=[{'host':'8.8.8.8','port':18444}]))
        loaded=load_bootstrap(self.profile,path=self.path)
        self.assertEqual(loaded.dns_seeds,(('seed.fixture.invalid',18444),))
        self.assertEqual(loaded.fallback_peers,(('8.8.8.8',18444),))

    def test_foreign_network_or_genesis_never_supplies_contacts(self):
        for change in ({'network':'regtest'},{'genesis':'ff'*32},{'genesis':self.profile.genesis.block_hash().hex().upper()}):
            self.write(self.value(**change))
            with self.subTest(change=change),self.assertRaises(ValueError):load_bootstrap(path=self.path)

    def test_duplicate_json_keys_unknown_fields_or_boolean_version_are_rejected(self):
        for value in (self.value(extra=1),self.value(schema_version=True),self.value(schema_version=3),
                      self.value(dns_seeds=[{'host':'seed.fixture.invalid','port':True}])):
            self.write(value)
            with self.assertRaises(ValueError):load_bootstrap(path=self.path)
        raw=json.dumps(self.value()).replace('"schema_version": 2','"schema_version": 2, "schema_version": 2')
        self.path.write_text(raw,encoding='utf-8')
        with self.assertRaises(ValueError):load_bootstrap(path=self.path)
        raw=json.dumps(self.value(dns_seeds=[{'host':'seed.fixture.invalid','port':18444}]))
        raw=raw.replace('"port": 18444','"port": 18444, "port": 18444')
        self.path.write_text(raw,encoding='utf-8')
        with self.assertRaises(ValueError):load_bootstrap(path=self.path)

    def test_invalid_encoding_size_depth_and_nonfinite_numbers_are_rejected(self):
        for raw in (b'\xff',b'x'*(64*1024+1),b'{',b'['*1500+b']'*1500,
                    json.dumps(self.value()).replace('"schema_version": 2','"schema_version": NaN').encode()):
            self.path.write_bytes(raw)
            with self.assertRaises(ValueError):load_bootstrap(path=self.path)

    def test_provider_and_fixed_contact_bounds_and_duplicates(self):
        seeds=[(f'seed{index}.fixture.invalid',18444) for index in range(8)]
        contacts=[('8.8.8.8',10000+index) for index in range(128)]
        self.assertEqual(len(normalize_seeds(seeds)),8)
        self.assertEqual(len(normalize_fallbacks(contacts)),128)
        for values in (seeds+[('seed8.fixture.invalid',18444)],seeds+[seeds[0]],
                       [('SEED.fixture.invalid',18444),('seed.fixture.invalid.',18444)]):
            with self.assertRaises(ValueError):normalize_seeds(values)
        for values in (contacts+[('8.8.8.8',11000)],[contacts[0],contacts[0]]):
            with self.assertRaises(ValueError):normalize_fallbacks(values)

    def test_numeric_local_private_or_single_label_seed_names_are_rejected(self):
        for host in ('8.8.8.8','127.0.0.1','localhost','seed.localhost','seed.local','seed.internal',
                     'seed.lan','seed.home.arpa','seed.onion','seed','seed..example','a'*64+'.example'):
            with self.subTest(host=host),self.assertRaises(ValueError):normalize_seeds([(host,18444)])

    def test_fixed_contacts_cannot_supply_private_reserved_dns_or_zero_ports(self):
        for target in (('127.0.0.1',18444),('192.168.1.2',18444),('100.64.0.1',18444),
                       ('198.51.100.1',18444),('seed.fixture.invalid',18444),('8.8.8.8',0)):
            with self.subTest(target=target),self.assertRaises(ValueError):normalize_fallbacks([target])
        self.assertEqual(normalize_fallbacks([('127.0.0.1',18444)],scope='loopback'),(('127.0.0.1',18444),))

    def test_legacy_schema_only_accepts_network_matching_scoped_numeric_contacts(self):
        self.write({'schema_version':1,'network':'dora','peers':['8.8.8.8:18444']})
        self.assertEqual(load_bootstrap(path=self.path).fallback_peers,(('8.8.8.8',18444),))
        for peers in (['127.0.0.1:18444'],['seed.fixture.invalid:18444'],['8.8.8.8:0']):
            self.write({'schema_version':1,'network':'dora','peers':peers})
            with self.assertRaises(ValueError):load_bootstrap(path=self.path)
        self.write({'schema_version':1,'network':'regtest','peers':['8.8.8.8:18444']})
        with self.assertRaises(ValueError):load_bootstrap(path=self.path)


class BootstrapResolverTests(unittest.IsolatedAsyncioTestCase):
    async def test_public_dns_answer_filters_private_reserved_and_non_ipv4_records(self):
        values=dns_records(['127.0.0.1','192.168.1.2','198.51.100.1','8.8.8.8','8.8.8.8','1.1.1.1'])
        values.extend([(socket.AF_INET6,socket.SOCK_STREAM,6,'',('::1',18444)),('malformed',)])
        with patch('sumuww.bootstrap.socket.getaddrinfo',return_value=values) as resolver:
            result=await lookup_seed(('seed.fixture.invalid',18444),timeout=.2)
        self.assertIsNone(result.error)
        self.assertEqual(result.endpoints,(('8.8.8.8',18444),('1.1.1.1',18444)))
        self.assertEqual(resolver.call_count,1)

    async def test_dns_answer_budget_is_at_most_32_unique_addresses(self):
        with patch('sumuww.bootstrap.socket.getaddrinfo',return_value=dns_records([f'8.8.8.{index}' for index in range(1,100)])):
            result=await lookup_seed(('seed.fixture.invalid',18444),timeout=.2)
        self.assertEqual(len(result.endpoints),32)

    async def test_provider_resolution_error_and_no_permitted_results_are_independent_failures(self):
        with patch('sumuww.bootstrap.socket.getaddrinfo',side_effect=socket.gaierror('fixture')):
            result=await lookup_seed(('seed.fixture.invalid',18444),timeout=.2)
        self.assertEqual(result.error,'resolution_failed')
        with patch('sumuww.bootstrap.socket.getaddrinfo',return_value=dns_records(['127.0.0.1'])):
            result=await lookup_seed(('seed.fixture.invalid',18444),timeout=.2)
        self.assertEqual(result.error,'no_permitted_addresses')

    async def test_query_times_out_without_joining_one_second_os_dns(self):
        finished=threading.Event()
        def slow(*arguments,**options):
            try:time.sleep(1);return dns_records(['8.8.8.8'])
            finally:finished.set()
        try:
            with patch('sumuww.bootstrap.socket.getaddrinfo',side_effect=slow):
                started=time.monotonic()
                result=await lookup_seed(('seed.fixture.invalid',18444),timeout=.05)
            self.assertEqual(result.error,'timeout')
            self.assertLess(time.monotonic()-started,.4)
            self.assertFalse(finished.is_set())
        finally:
            deadline=time.monotonic()+2
            while not finished.is_set():
                if time.monotonic()>deadline:self.fail('Owned DNS fixture did not finish')
                await asyncio.sleep(.02)

    async def test_cancelled_or_repeated_queries_never_exceed_eight_daemon_workers(self):
        release=threading.Event();calls=[];lock=threading.Lock()
        def stuck(*arguments,**options):
            with lock:calls.append(threading.current_thread().daemon)
            release.wait(3);return dns_records(['8.8.8.8'])
        try:
            with patch('sumuww.bootstrap.socket.getaddrinfo',side_effect=stuck):
                seeds=[(f'seed{index}.fixture.invalid',18444) for index in range(MAX_DNS_WORKERS)]
                first=await asyncio.gather(*(lookup_seed(seed,timeout=.1) for seed in seeds))
                self.assertTrue(all(result.error=='timeout' for result in first))
                self.assertEqual(len(calls),8)
                for _ in range(3):
                    result=await lookup_seed(seeds[0],timeout=.1)
                    self.assertEqual(result.error,'resolver_capacity')
                self.assertEqual(len(calls),8)
                self.assertTrue(all(calls))
        finally:
            release.set();deadline=time.monotonic()+1
            while any(thread.name=='sumuww-bootstrap-dns' for thread in threading.enumerate()):
                if time.monotonic()>deadline:self.fail('Owned DNS workers did not finish')
                await asyncio.sleep(.01)


if __name__=='__main__':unittest.main()
