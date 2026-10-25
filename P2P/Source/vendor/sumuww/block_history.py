"""Read public active-chain pages on a separate, read-only SQLite snapshot."""
from pathlib import Path
import sqlite3

from .block import Block
from .link_crypto import producer
from .primitives import hash_to_display
from .rewards import read_reward


def block_history(database, offset=0, limit=50, height=None, own_node_id=None):
    if type(offset) is not int or offset < 0 or type(limit) is not int or not 1 <= limit <= 50:
        raise ValueError('Invalid block page')
    if height is not None and (type(height) is not int or height < 0):
        raise ValueError('Invalid block height')
    connection = sqlite3.connect(Path(database).resolve().as_uri() + '?mode=ro', uri=True, timeout=5)
    try:
        connection.execute('BEGIN')
        has_proofs = connection.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='link_proofs'").fetchone() is not None
        tip = connection.execute("SELECT value FROM metadata WHERE name='tip'").fetchone()[0]
        top = connection.execute('SELECT height FROM blocks WHERE hash=?', (tip,)).fetchone()[0]
        if height is not None:
            if height > top:
                raise ValueError(f'Block height: 0–{top}')
            offset = top - height
        offset = min(offset, top)
        # Follow parent hashes, never an unfiltered height index which could
        # include side branches. Only the requested page loads block bodies.
        rows = connection.execute('''
            WITH RECURSIVE ancestry(hash,parent,height) AS (
                SELECT hash,parent,height FROM blocks WHERE hash=?
                UNION ALL
                SELECT b.hash,b.parent,b.height FROM blocks b JOIN ancestry c
                  ON b.hash=c.parent AND b.height=c.height-1
                  WHERE c.height>0 AND c.height>?
            ), page AS (
                SELECT hash,parent,height FROM ancestry WHERE height<=?
                ORDER BY height DESC LIMIT ?
            )
            SELECT p.hash,p.parent,p.height,b.raw FROM page p JOIN blocks b ON b.hash=p.hash
            ORDER BY p.height DESC
        ''', (tip, max(0, top-offset-limit+1), top-offset, limit)).fetchall()
        blocks = []
        for digest, parent, block_height, raw in rows:
            block = Block.deserialize(raw)
            if block.block_hash() != digest:
                raise ValueError('Block bytes/index mismatch')
            try:
                identity = producer(block)
            except ValueError:
                identity = None
            origin = ('unknown' if identity is None or own_node_id is None else
                      'local' if identity == own_node_id else 'other')
            blocks.append({'height': block_height, 'hash': hash_to_display(digest),
                           'parent_hash': hash_to_display(parent), 'timestamp': block.header.timestamp,
                           'reward': read_reward(connection, block, block_height),
                           'producer_id': identity, 'origin': origin, 'transactions': len(block.transactions),
                           'proofs': connection.execute('SELECT COUNT(*) FROM link_proofs WHERE source=? OR target=?', (digest, digest)).fetchone()[0] if has_proofs else 0})
        return {'blocks': blocks, 'total': top+1, 'height': top, 'tip_hash': hash_to_display(tip),
                'offset': offset, 'limit': limit,
                'stored_proofs': connection.execute('SELECT COUNT(*) FROM link_proofs').fetchone()[0] if has_proofs else 0}
    finally:
        connection.close()


def block_transactions(database, block_hash, offset=0, limit=50, network='dora'):
    """Page every transaction of an active block, without a wallet filter.

    The same snapshot supplies membership and confirmations. A block removed by
    a reorganization is rejected instead of presenting stale confirmations.
    Only the selected block body is deserialized; historical inputs remain
    public outpoint references rather than an unbounded ancestry scan.
    """
    from .address import encode_address
    if (type(block_hash) is not str or len(block_hash) != 64 or
            type(offset) is not int or offset < 0 or
            type(limit) is not int or not 1 <= limit <= 50):
        raise ValueError('Invalid block transaction page')
    digest = bytes.fromhex(block_hash)[::-1]
    connection = sqlite3.connect(Path(database).resolve().as_uri() + '?mode=ro', uri=True, timeout=5)
    try:
        connection.execute('BEGIN')
        tip = connection.execute("SELECT value FROM metadata WHERE name='tip'").fetchone()[0]
        top = connection.execute('SELECT height FROM blocks WHERE hash=?', (tip,)).fetchone()[0]
        row = connection.execute('''WITH RECURSIVE ancestry(hash,parent,height) AS (
            SELECT hash,parent,height FROM blocks WHERE hash=? UNION ALL
            SELECT b.hash,b.parent,b.height FROM blocks b JOIN ancestry c
            ON b.hash=c.parent AND b.height=c.height-1 WHERE c.height>0)
            SELECT b.height,b.raw FROM ancestry a JOIN blocks b ON a.hash=b.hash
            WHERE a.hash=?''', (tip, digest)).fetchone()
        if row is None:
            raise ValueError('Block is no longer in the active chain. Refresh the list.')
        height, raw = row
        block = Block.deserialize(raw)
        if block.block_hash() != digest:
            raise ValueError('Block bytes/index mismatch')
        total = len(block.transactions)
        offset = min(offset, max(0, total-1))
        transactions = []
        for tx in block.transactions[offset:offset+limit]:
            outputs = []
            for index, output in enumerate(tx.outputs):
                try: address = encode_address(output.script_pubkey, network=network)
                except ValueError: address = None
                outputs.append({'index': index, 'value': output.value, 'address': address,
                                'script': output.script_pubkey.hex()})
            transactions.append({'mining_reward': read_reward(connection, block, height) if tx.is_coinbase() else None,
                                 'txid': hash_to_display(tx.txid()), 'coinbase': tx.is_coinbase(),
                                 'output_total': sum(o.value for o in tx.outputs), 'outputs': outputs,
                                 'inputs': [{'txid': hash_to_display(i.prev_txid),
                                             'index': i.prev_index} for i in tx.inputs]})
        return {'block_hash': block_hash, 'height': height, 'reward': read_reward(connection, block, height), 'confirmations': top-height+1,
                'tip_hash': hash_to_display(tip), 'transactions': transactions,
                'offset': offset, 'total': total, 'limit': limit}
    finally:
        connection.close()
