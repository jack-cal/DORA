import asyncio,unittest
from sumuww import dht_discovery as dht

# Deliberately unordered but unique KRPC keys, like an observed router reply.
def response(tx=b'owned123'):
    body=b'd6:nodes60:2:id20:'+b'I'*20+b'5:token3:toke'
    return b'd1:t'+str(len(tx)).encode()+b':'+tx+b'1:y1:r1:r'+body+b'e'

class ResponseOrderTests(unittest.IsolatedAsyncioTestCase):
    async def test_default_decoder_remains_canonical(self):
        with self.assertRaises(ValueError):dht.decode_bencode(response())
    async def test_inbound_decoder_accepts_unique_unordered_keys(self):
        obj=dht.decode_bencode(response(),require_sorted_keys=False)
        self.assertEqual(b'owned123',obj[b't']);self.assertEqual(b'I'*20,obj[b'r'][b'id'])
    async def test_nonadjacent_duplicate_keys_remain_rejected(self):
        for raw in (b'd1:b1:x1:a1:y1:b1:ze',b'd1:ad1:b1:x1:a1:y1:b1:ze1:t1:xe'):
            with self.assertRaises(ValueError):dht.decode_bencode(raw,require_sorted_keys=False)
    async def test_correlated_router_response_completes_query(self):
        client=dht.DhtDiscovery('regtest',lambda _:None,scope='loopback');client._active=True
        future=asyncio.get_running_loop().create_future();client._pending[b'owned123']=(('::1',1234),future)
        client._received(response(),('::1',1234,0,0))
        self.assertTrue(future.done());self.assertEqual(1,client.info()['stats']['responses'])
    async def test_wrong_transaction_or_source_cannot_complete_query(self):
        client=dht.DhtDiscovery('regtest',lambda _:None,scope='loopback');client._active=True
        future=asyncio.get_running_loop().create_future();client._pending[b'owned123']=(('::1',1234),future)
        client._received(response(b'wrong123'),('::1',1234,0,0));client._received(response(),('::1',1235,0,0))
        self.assertFalse(future.done());self.assertEqual(0,client.info()['stats']['responses'])
    async def test_oversize_and_truncated_responses_remain_rejected(self):
        for raw in (response()[:-1],response()+b'junk',b'x'*(dht.MAX_PACKET_BYTES+1)):
            with self.assertRaises(ValueError):dht.decode_bencode(raw,require_sorted_keys=False)
