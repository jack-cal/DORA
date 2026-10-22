"""Search regression: a full queue must not discard a closer fresh referral.

Owned synthetic KRPC graph, no production endpoints or network sockets.
Physical Android execution is verified separately from these tests.
"""
import asyncio
import ipaddress
import unittest
from unittest.mock import patch, AsyncMock
from sumuww import dht_discovery as dht

class FrontierReplacementTests(unittest.IsolatedAsyncioTestCase):
    async def test_full_search_reaches_new_closer_referral_ipv4_and_ipv6(self):
        for family,host,field in ((dht.socket.AF_INET,'127.0.0.1',b'nodes'),
                                  (dht.socket.AF_INET6,'::1',b'nodes6')):
            with self.subTest(family=family):
                root=(host,2000); closest=(host,2001); peer=(host,34567)
                first=(host,2030); middle=(host,2040); far=(host,2050)
                client=dht.DhtDiscovery('regtest',lambda _:None,scope='loopback',
                                        family=family,routers=[root])
                client.key=bytes(20);client._active=True
                client._ensure_transport=AsyncMock(return_value=True)
                queried=[]
                def nodes(rows):
                    return b''.join(distance.to_bytes(20,'big')+ipaddress.ip_address(target[0]).packed
                                    +target[1].to_bytes(2,'big') for distance,target in rows)
                async def batch(requests,deadline):
                    replies=[]
                    for endpoint,method,args in requests:
                        queried.append(endpoint)
                        body={b'id':b'R'*20}
                        if endpoint==root:body[field]=nodes([(30,first),(40,middle),(50,far)])
                        elif endpoint==first:body[field]=nodes([(1,closest)])
                        elif endpoint==closest:
                            body[b'values']=[ipaddress.ip_address(peer[0]).packed+peer[1].to_bytes(2,'big')]
                        replies.append({b'y':b'r',b'r':body})
                    return replies
                client._batch=batch
                with patch.object(dht,'MAX_NODES',4),patch.object(dht,'MAX_CONCURRENT',1):
                    result=await client._lookup()
                self.assertIn(closest,queried)
                self.assertIn(peer,result)
                self.assertNotIn(far,queried)
                self.assertLessEqual(len(queried),dht.MAX_QUERIES)

    async def test_replacement_keeps_bound_router_fallback_and_visited_exclusions(self):
        client=dht.DhtDiscovery('regtest',lambda _:None,scope='loopback',routers=[('127.0.0.1',1)])
        client.key=bytes(20)
        root=('127.0.0.1',1);fallback=('127.0.0.1',2)
        visited={root}; initial={root,fallback}
        frontier={fallback:(999).to_bytes(20,'big'),('127.0.0.1',3):(30).to_bytes(20,'big'),
                  ('127.0.0.1',4):(40).to_bytes(20,'big')}
        with patch.object(dht,'MAX_NODES',4):
            self.assertTrue(client._retain_referral(frontier,visited,initial,(1).to_bytes(20,'big'),('127.0.0.1',5)))
            self.assertIn(fallback,frontier)
            self.assertNotIn(('127.0.0.1',4),frontier)
            self.assertFalse(client._retain_referral(frontier,visited,initial,bytes(20),root))
            self.assertFalse(client._retain_referral(frontier,visited,initial,(50).to_bytes(20,'big'),('127.0.0.1',6)))
            self.assertLessEqual(len(frontier)+len(visited),4)
            before=dict(frontier)
            self.assertFalse(client._retain_referral(frontier,visited,initial,bytes(20),fallback))
            self.assertEqual(before,frontier)
