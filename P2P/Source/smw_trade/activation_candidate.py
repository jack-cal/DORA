"""Unpublished node upgrade candidate. NOT loaded by the exchange/native miner.

An explicitly agreed activation height is required for public rollout. Genesis,
PoW, subsidies, existing P2WPKH ownership and boundary rules are inherited intact.
Old nodes cannot validate the newly supported conditional spends after activation.
This module alone does not activate a public network or authorize funds transfer.
"""
import sqlite3
from contextlib import closing
from pathlib import Path
from sumuww.chain import Chain
from .research_chain import SwapChain

PUBLIC_HTLC_ACTIVATION_HEIGHT=9100


class ConditionalSpendCandidate(Chain):
    def __init__(self,database,*,activation_height,network='regtest',**kwargs):
        if type(activation_height) is not int or not 1<=activation_height<500_000_000:
            raise ValueError('An explicit future rollout height is required')
        self.htlc_activation_height=activation_height
        from sumuww.profiles import get_network
        if get_network(network).name=='dora' and activation_height!=PUBLIC_HTLC_ACTIVATION_HEIGHT:
            raise ValueError('Public HTLC activation is fixed at 9100')
        database=Path(database)
        if database.exists():
            with closing(sqlite3.connect(database.as_uri()+'?mode=ro',uri=True)) as conn:
                tables={r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
                if 'exchange_research_policy' in tables:raise ValueError('Do not convert an always-active research chain')
                if 'conditional_spend_policy' in tables:
                    row=conn.execute('SELECT height FROM conditional_spend_policy').fetchall()
                    if row!=[(activation_height,)]:raise ValueError('Cannot change an existing activation policy')
        super().__init__(database,network=network,**kwargs)
        self.connection.execute('CREATE TABLE IF NOT EXISTS conditional_spend_policy (height INTEGER NOT NULL UNIQUE)')
        if not self.connection.execute('SELECT 1 FROM conditional_spend_policy').fetchone():
            self.connection.execute('INSERT INTO conditional_spend_policy VALUES (?)',(activation_height,))

    def _apply_transaction(self,transaction,state,height,path):
        if height<self.htlc_activation_height:
            return super()._apply_transaction(transaction,state,height,path)
        return SwapChain._apply_transaction(self,transaction,state,height,path)

    def info(self):
        result=super().info()
        active=result['height']>=self.htlc_activation_height
        result['conditional_spend']={'template':'exact-p2wsh-htlc-v1','activation_height':self.htlc_activation_height,
                                     'active':active,'rollout_status':'unpublished-upgrade-candidate'}
        if active:result['spending_support']='native P2WPKH / SIGHASH_ALL plus exact P2WSH HTLC v1'
        return result

    @classmethod
    def public_upgrade(cls,database,**kwargs):
        return cls(database,activation_height=PUBLIC_HTLC_ACTIVATION_HEIGHT,network='sumuww',**kwargs)
