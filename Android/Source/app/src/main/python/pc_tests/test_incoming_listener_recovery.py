"""An inbound-only peer must not leave its neighbors dependent on a hub."""
import asyncio
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from sumuww.peer import PeerNode
from sumuww.wallet import RegtestKey


class IncomingListenerRecoveryTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.folder=tempfile.TemporaryDirectory();self.nodes=[]

    async def asyncTearDown(self):
        await asyncio.gather(*(n.stop() for n in self.nodes),return_exceptions=True)
        self.folder.cleanup()

    async def node(self,name,**options):
        options.setdefault('allow_internet',True)
        value=PeerNode(Path(self.folder.name)/(name+'.sqlite'),poll_interval=.03,timeout=2,
                       discovery_interval=1,discovery_scope='loopback',dht_enabled=False,**options)
        self.nodes.append(value);await value.start();return value

    async def wait(self,predicate):
        async with asyncio.timeout(15):
            while not predicate():await asyncio.sleep(.03)

    async def test_empty_address_reply_recovers_listener_then_phone_survives_hub_exit(self):
        hub=await self.node('hub')
        # This node accepts connections but advertises no listener or contacts.
        # Internet-enabled peers can observe its actual incoming source IP.
        remote=await self.node('remote')
        remote._own_listener=lambda:None
        remote._addresses.known=lambda maximum=32:()
        remote._request_addresses=lambda *args:asyncio.sleep(0)
        with patch('sumuww.peer.DEFAULT_PORT',remote.address[1]):
            await remote.connect(*hub.address)
            await self.wait(lambda:remote.address in hub._addresses.known())
            self.assertEqual(1,sum(s.nonce==remote.nonce for s in hub._healthy_sessions()))
            phone=await self.node('phone',peers=(hub.address,))
            await self.wait(lambda:remote.address in phone._addresses.known())
            await self.wait(lambda:any(s.nonce==remote.nonce for s in phone._healthy_sessions()))
            await hub.stop()
            await self.wait(lambda:len(phone._healthy_sessions())==1 and
                            phone._healthy_sessions()[0].nonce==remote.nonce)
            remote.chain.mine(RegtestKey.from_int(43).script_pubkey,1)
            await self.wait(lambda:phone.chain.tip_hash==remote.chain.tip_hash)
            self.assertEqual(1,phone.chain.info()['height'])
            self.assertTrue(phone.synchronization_info()['mining_ready'])

    async def test_probe_is_only_an_unverified_hint_and_uses_no_ephemeral_source_port(self):
        node=await self.node('guard')
        session=SimpleNamespace(ready=True,synchronized=True,outgoing=None,remote_ip='127.0.0.2',
            remote_listener=None,address_response_count=1,observed_listener_probe_round=0)
        node._hint_observed_listener(session)
        target=('127.0.0.2',18444)
        self.assertIn(target,node._addresses._entries)
        self.assertNotIn(target,node._addresses.known())
        self.assertFalse(node._addresses.path.exists())
        node._addresses._entries.clear()
        node._hint_observed_listener(session)
        self.assertEqual(0,len(node._addresses._entries))
        # A fresh reply can revive an unsuccessful probe, but only after the
        # ordinary failed-hint cooldown. It still never verifies the address.
        clock=[100.0];node._addresses.retry_clock=lambda:clock[0]
        node._addresses.add_hint(target)
        node._addresses.attempted(target,success=False)
        session.address_response_count+=1
        node._hint_observed_listener(session)
        self.assertEqual(0,len(node._addresses._entries))
        clock[0]+=61;session.address_response_count+=1
        node._hint_observed_listener(session)
        self.assertIn(target,node._addresses._entries)
        self.assertNotIn(target,node._addresses.known())

    async def test_no_probe_for_unverified_outgoing_advertised_or_privacy_sessions(self):
        node=await self.node('guard-filters')
        defaults=dict(ready=True,synchronized=True,outgoing=None,remote_ip='127.0.0.2',
                      remote_listener=None,address_response_count=1,observed_listener_probe_round=0)
        for changes in [dict(ready=False),dict(synchronized=False),dict(outgoing=('127.0.0.2',12345)),
                        dict(remote_listener=('127.0.0.2',12345)),dict(address_response_count=0),
                        dict(remote_ip='0.0.0.0'),dict(remote_ip='224.0.0.1')]:
            with self.subTest(changes=changes):
                node._hint_observed_listener(SimpleNamespace(**(defaults|changes)))
                self.assertEqual(0,len(node._addresses._entries))
        with patch.object(node,'_privacy',SimpleNamespace(mode='tor')):
            node._hint_observed_listener(SimpleNamespace(**defaults))
        self.assertEqual(0,len(node._addresses._entries))
        node.allow_internet=False
        node._hint_observed_listener(SimpleNamespace(**defaults))
        self.assertEqual(0,len(node._addresses._entries))
