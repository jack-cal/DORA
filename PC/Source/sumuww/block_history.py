"""Read public active-chain pages on a separate, read-only SQLite snapshot."""
from pathlib import Path
import sqlite3

from .block import Block
from .link_crypto import producer
from .primitives import hash_to_display


def block_history(database, offset=0, limit=50, height=None, own_node_id=None):
    if type(offset) is not int or offset < 0 or type(limit) is not int or not 1 <= limit <= 50:
        raise ValueError('Invalid block page')
    if height is not None and (type(height) is not int or height < 0):
        raise ValueError('Invalid block height')
    connection = sqlite3.connect(Path(database).resolve().as_uri() + '?mode=ro', uri=True, timeout=5)
    try:
        connection.execute('BEGIN')
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
                           'producer_id': identity, 'origin': origin, 'transactions': len(block.transactions)})
        return {'blocks': blocks, 'total': top+1, 'height': top, 'tip_hash': hash_to_display(tip),
                'offset': offset, 'limit': limit}
    finally:
        connection.close()
