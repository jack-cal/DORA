"""Retry verified contacts after outages without depending on fresh discovery."""
import asyncio
import json
from pathlib import Path
import tempfile
import unittest
from sumuww.peer import PeerNode
from sumuww.peer_discovery import PeerAddressBook,CACHE_MAX_AGE
from sumuww.wallet import RegtestKey

class VerifiedRetryTests(unittest.TestCase):
    def test_transient_failure_keeps_verified_contact_on_disk_and_retries(self):
        with tempfile.TemporaryDirectory() as root:
            now=[10000.];path=Path(root)/'peers.json';target=('127.0.0.1',12345)
            book=PeerAddressBook(path,'fixture',bytes(32),scope='loopback',clock=lambda:now[0],retry_clock=lambda:now[0])
            book.verified(target);book.attempted(target)
            self.assertIn(target,book.known())
            self.assertIsNone(book.candidate())
            self.assertEqual(12345,json.loads(path.read_text())['peers'][0]['port'])
            now[0]+=11;self.assertEqual(target,book.candidate())
            reloaded=PeerAddressBook(path,'fixture',bytes(32),scope='loopback',clock=lambda:now[0])
            self.assertIn(target,reloaded.known())
            book.verified(target);self.assertEqual(0,book._entries[target].failures)
    def test_unverified_failure_removed_and_stale_verified_contact_expires(self):
        with tempfile.TemporaryDirectory() as root:
            now=[10000.];book=PeerAddressBook(Path(root)/'peers.json','fixture',bytes(32),scope='loopback',clock=lambda:now[0],retry_clock=lambda:now[0])
            unknown=('127.0.0.1',12345);verified=('127.0.0.1',12346)
            book.add_hint(unknown);book.attempted(unknown)
            self.assertNotIn(unknown,book._entries);self.assertFalse(book.add_hint(unknown))
            book.verified(verified);book.attempted(verified)
            now[0]+=CACHE_MAX_AGE+1;book.prune()
            self.assertNotIn(verified,book.known())

class RetrySocketTests(unittest.IsolatedAsyncioTestCase):
    async def test_three_nodes_reconnect_after_failed_dial_without_new_hint(self):
        with tempfile.TemporaryDirectory() as root:
            nodes=[];clock=[1000.]
            def node(name,**kw):
                value=PeerNode(Path(root)/f'{name}.sqlite',poll_interval=.03,timeout=2,discovery_scope='loopback',
                    dht_enabled=False,**kw)
                value._addresses.retry_clock=lambda:clock[0]
                nodes.append(value);return value
            async def wait(check):
                for _ in range(200):
                    if check():return
                    await asyncio.sleep(.03)
                self.fail('Retry recovery deadline: '+repr([(n.address,n._last_error,n.info()['peers'],n._addresses._entries) for n in nodes if n.running]))
            try:
                a=node('a',discover_peers=False);c=node('c',discover_peers=False)
                await a.start();await c.start()
                b=node('b',discover_peers=True);await b.start()
                b._addresses.add_hint(a.address);b._addresses.add_hint(c.address)
                await wait(lambda:b.info()['peers']==2)
                await wait(lambda:a.address in b._addresses.known() and c.address in b._addresses.known())
                endpoint=a.address;await a.stop()
                await wait(lambda:b.info()['peers']==1)
                clock[0]+=400
                await wait(lambda:b._addresses._entries.get(endpoint) is None or b._addresses._entries[endpoint].failures>0)
                self.assertIn(endpoint,b._addresses.known())
                self.assertTrue(b.synchronization_info()['mining_ready'])
                c.chain.mine(RegtestKey.from_int(222).script_pubkey)
                await wait(lambda:b.chain.tip_hash==c.chain.tip_hash)
                replacement=node('a',host=endpoint[0],port=endpoint[1],discover_peers=False)
                await replacement.start();clock[0]+=400
                await wait(lambda:b.info()['peers']==2 and replacement.chain.tip_hash==b.chain.tip_hash)
                self.assertTrue(b.synchronization_info()['mining_ready'])
            finally:
                for n in reversed(nodes):await n.stop()
