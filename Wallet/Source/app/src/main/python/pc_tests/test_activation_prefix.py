"""Keep the valid legacy prefix when a peer continues across activation.

Normally uses a short independent regtest. Set SUMUWW_ACTIVATION_SEED to an
independently mined legacy height-8999 SQLite fixture for the numeric boundary.
Never point it at a live database: only a read-only backup is used.
"""
import asyncio
from contextlib import closing
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest
from sumuww.chain import Chain
from sumuww.peer import PeerNode
from sumuww.wallet import RegtestKey
from sumuww.errors import ValidationError
from sumuww.wire import (Version, decode_version, encode_version, encode_headers,
                         encode_inventory, Inventory, INV_BLOCK, decode_inventory,
                         read_frame, write_frame)

class ActivationPrefixTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='sumuww-activation-prefix-')
        self.root=Path(self.temp.name);self.nodes=[];self.writers=[]
        self.activation=9000 if os.environ.get('SUMUWW_ACTIVATION_SEED') else 4
        self.pay=RegtestKey.from_int(10001).script_pubkey
        self.seed=self.root/'legacy.sqlite'
        fixture=os.environ.get('SUMUWW_ACTIVATION_SEED')
        if fixture:
            uri=Path(fixture).resolve().as_uri()+'?mode=ro'
            with closing(sqlite3.connect(uri,uri=True)) as src, closing(sqlite3.connect(self.seed)) as dst:src.backup(dst)
        with Chain(self.seed) as old:
            if not fixture:old.mine(self.pay,self.activation-1)
            self.assertEqual(self.activation-1,old._row(old.tip_hash)[2])
            path=old._path(old.tip_hash)
            self.prefix=[b for _,b in path[-2:]]
            self.anchor=path[-3][0][0]
            self.tail=old.mine(self.pay,3)
            # Genuine native PoW, but no post-PoW producer commitment.
            self.blocks=self.prefix+self.tail
            self.parent_utxos=old._state_for(self.anchor)[0]
        self.base=self.root/'base.sqlite'
        with closing(sqlite3.connect(self.seed)) as src, closing(sqlite3.connect(self.base)) as dst:src.backup(dst)
        with Chain(self.base) as c:
            c.connection.execute('BEGIN IMMEDIATE')
            c._replace_utxos(self.parent_utxos)
            c.connection.execute('DELETE FROM blocks WHERE height>=?',(self.activation-2,))
            c.connection.execute("UPDATE metadata SET value=? WHERE name='tip'",(self.anchor,))
            c.connection.execute('COMMIT')

    async def asyncTearDown(self):
        for w in self.writers:w.close()
        for n in reversed(self.nodes):await n.stop()
        for w in self.writers:
            try:await w.wait_closed()
            except (OSError,ConnectionError):pass
        self.temp.cleanup()

    async def node(self):
        db=self.root/f'node-{len(self.nodes)}.sqlite'
        with closing(sqlite3.connect(self.base)) as src, closing(sqlite3.connect(db)) as dst:src.backup(dst)
        n=PeerNode(db,boundary_activation=self.activation,discover_peers=False,dht_enabled=False,
                   auto_address=False,poll_interval=.05,timeout=5)
        await n.start();self.nodes.append(n);return n

    async def until(self,fn):
        async with asyncio.timeout(20):
            while not fn():await asyncio.sleep(.02)

    async def handshake(self,n):
        reader,writer=await asyncio.open_connection(*n.address);self.writers.append(writer)
        own=decode_version((await read_frame(reader,5)).payload)
        await write_frame(writer,'version',encode_version(Version(3,n.genesis,own.nonce^1,n.network.profile_id,self.blocks[-1].block_hash())),5)
        self.assertEqual('verack',(await read_frame(reader,5)).command)
        await write_frame(writer,'verack',b'',5)
        for _ in range(20):
            if (await read_frame(reader,5)).command=='getheaders':break
        else:self.fail('Missing header request')
        return reader,writer

    async def test_mixed_old_batch_keeps_prefix_rejects_suffix_and_resumes_new_chain(self):
        n=await self.node();reader,writer=await self.handshake(n)
        await write_frame(writer,'headers',encode_headers(tuple(b.header for b in self.blocks)),5)
        for _ in range(20):
            frame=await read_frame(reader,5)
            if frame.command=='getdata':break
        else:self.fail('Missing body request')
        requested={i.digest for i in decode_inventory(frame.payload)}
        self.assertTrue(all(b.block_hash() in requested for b in self.blocks))
        # Send one ordered stream containing both sides of the boundary.
        from sumuww.wire import encode_frame
        writer.write(b''.join(encode_frame('block',b.serialize()) for b in self.blocks));await writer.drain()
        await self.until(lambda:n.info()['stats']['invalid_peer_incidents']==1)
        self.assertEqual(self.activation-1,n.chain.summary()['height'])
        self.assertEqual(self.prefix[-1].block_hash(),n.chain.tip_hash)
        self.assertTrue(all(n.chain.has_block(b.block_hash()) for b in self.prefix))
        self.assertFalse(any(n.chain.has_block(b.block_hash()) for b in self.tail))
        before=n.chain.state_commitment()
        # Restart preserves the accepted prefix and its UTXOs.
        with Chain(n.database,boundary_activation=self.activation) as reopened:
            self.assertEqual(before,reopened.state_commitment())
            self.assertEqual(self.activation-1,reopened.summary()['height'])
        # Updated blocks need no witness response and are relayed to a second node.
        new=n.chain.mine(self.pay,3)
        m=await self.node();await m.connect(*n.address)
        await self.until(lambda:m.chain.tip_hash==n.chain.tip_hash)
        self.assertEqual(self.activation+2,m.chain.summary()['height'])
        self.assertEqual(n.chain.state_commitment(),m.chain.state_commitment())
        self.assertTrue(all(m.chain.has_block(b.block_hash()) for b in self.prefix+new))
        self.assertEqual([],m.chain.boundary.all_proofs())

    async def test_each_uncommitted_postactivation_block_is_rejected_without_losing_prefix(self):
        n=await self.node()
        for b in self.prefix:n.chain.accept_block(b)
        before=(n.chain.tip_hash,n.chain.state_commitment())
        for b in self.tail:
            with self.assertRaises(ValidationError):n.chain.accept_block(b)
            self.assertEqual(before,(n.chain.tip_hash,n.chain.state_commitment()))
        # A node can still fetch valid old history from another old connection.
        self.assertEqual(self.activation-1,n.chain.summary()['height'])

if __name__=='__main__':unittest.main()
