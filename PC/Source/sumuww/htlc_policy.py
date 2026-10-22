"""Height-gated conditional-spend policy, separate from the height-9000 BLS rule."""
import json
from .errors import StorageError

PUBLIC_HTLC_ACTIVATION_HEIGHT=9100
TEMPLATE='exact-p2wsh-htlc-v1'


def activation_for(network,requested):
    if network.name=='dora':
        if requested is not None and (type(requested) is not int or requested!=PUBLIC_HTLC_ACTIVATION_HEIGHT):
            raise StorageError('Public HTLC activation is fixed at 9100')
        return PUBLIC_HTLC_ACTIVATION_HEIGHT
    if requested is not None and (type(requested) is not int or not 1<=requested<500_000_000):
        raise StorageError('Invalid isolated HTLC activation')
    return requested


class HtlcPolicy:
    def __init__(self,chain,activation):
        self.chain=chain;self.activation=activation
        self.config={'domain':'sumuww-htlc-activation-v1','network':chain.network.genesis.block_hash().hex(),
                     'activationHeight':activation,'template':TEMPLATE}
        encoded=json.dumps(self.config,sort_keys=True,separators=(',',':')).encode('ascii')
        c=chain.connection
        exists=c.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='htlc_config'").fetchone()
        if activation is None and not exists:return
        c.execute('BEGIN IMMEDIATE')
        try:
            c.execute('CREATE TABLE IF NOT EXISTS htlc_config (one INTEGER PRIMARY KEY CHECK(one=1), config BLOB NOT NULL)')
            old=c.execute('SELECT config FROM htlc_config WHERE one=1').fetchone()
            if old is None:
                if activation is None:raise StorageError('Missing configured HTLC activation')
                c.execute('INSERT INTO htlc_config VALUES (1,?)',(encoded,))
            elif old[0]!=encoded:raise StorageError('HTLC activation configuration mismatch')
            c.execute('COMMIT')
        except BaseException:
            c.execute('ROLLBACK');raise

    def active(self,height):return self.activation is not None and height>=self.activation

    def info(self,height):
        return {'template':TEMPLATE,'activation_height':self.activation,'active':self.active(height),
                'next_block_active':self.active(height+1),'height':height,
                'genesis':self.chain.network.genesis.block_hash()[::-1].hex(),
                'network':self.chain.network.name,'existing_p2wpkh_transfers':True,
                'coin_creation_height_restricted':False}
