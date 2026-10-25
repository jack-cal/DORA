"""Explicit activation boundary for new consensus spending templates."""
import json
from .errors import StorageError


class SpendingPolicy:
    def __init__(self, chain, activation=None):
        # A local installation cannot pick a public consensus activation height.
        if chain.network.name == 'dora' and activation is not None:
            raise StorageError('Public multisig and lock activation is not scheduled')
        if activation is not None and (type(activation) is not int or not 1 <= activation < 500_000_000):
            raise StorageError('Invalid isolated spending activation')
        self.activation = activation
        config = json.dumps({'template': 'sumuww-witness-v1', 'activation': activation,
                             'genesis': chain.network.genesis.block_hash().hex()}, sort_keys=True).encode()
        connection = chain.connection
        exists = connection.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='spending_config'").fetchone()
        if activation is None and not exists: return
        connection.execute('BEGIN IMMEDIATE')
        try:
            connection.execute('CREATE TABLE IF NOT EXISTS spending_config (one INTEGER PRIMARY KEY CHECK(one=1), config BLOB NOT NULL)')
            old = connection.execute('SELECT config FROM spending_config WHERE one=1').fetchone()
            if old is None:
                if activation is None: raise StorageError('Missing spending activation')
                connection.execute('INSERT INTO spending_config VALUES (1,?)', (config,))
            elif old[0] != config:
                raise StorageError('Spending activation configuration mismatch')
            connection.execute('COMMIT')
        except BaseException:
            connection.execute('ROLLBACK')
            raise

    def active(self, height):
        return self.activation is not None and height >= self.activation

    def info(self, height):
        return {'template': 'sumuww-witness-v1', 'activation_height': self.activation,
                'active': self.active(height), 'next_block_active': self.active(height+1),
                'multisig_max_keys': 16, 'sighash': 'ALL', 'witness_version': 0,
                'locks': ['height', 'time', 'relative_height', 'relative_time'],
                'public_activation_scheduled': False}
