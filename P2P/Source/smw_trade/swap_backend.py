"""Node adapters for independently signing parties. Funding is regtest-only.

The SMW adapter speaks to an explicitly configured research node, never the
running public miner. Bitcoin uses an existing Bitcoin Core regtest RPC node.
No adapter mines, creates wallets, or obtains another party's signing key.
"""
from decimal import Decimal
from sumuww.transaction import Transaction, TxOutput
from .wallet_link import LocalRPC
from .settlement import address, display


class BitcoinBackend:
    def __init__(self, url, cookie): self.client = LocalRPC(url, cookie, 'btc')

    def info(self):
        info = self.client.call('getblockchaininfo')
        if info['chain'] != 'regtest': raise ValueError('Public Bitcoin funding is disabled in this development version')
        return {'network': 'regtest', 'genesis': self.client.call('getblockhash', 0),
                'height': info['blocks'], 'htlc': 'exact-p2wsh-htlc-v1'}

    def coins(self, script):
        self.info()
        scan = self.client.call('scantxoutset', 'start', ['addr(' + address(script) + ')'])
        if not scan['success']: raise ValueError('Bitcoin scan incomplete')
        result = []
        for coin in scan['unspents']:
            current = self.output(coin['txid'], coin['vout'])
            if current and current['confirmations'] >= 1 and (not current['coinbase'] or current['confirmations'] >= 100):
                if current['script'] != script.hex(): raise ValueError('Changed input script')
                result.append({'txid': coin['txid'], 'vout': coin['vout'], 'value': current['value'], 'script': current['script']})
        return result

    def output(self, txid, index):
        output = self.client.call('gettxout', txid, index, True)
        if output is None: return None
        value = Decimal(str(output['value'])) * 100000000
        if value != value.to_integral_value(): raise ValueError('Invalid Bitcoin amount')
        return {'value': int(value), 'script': output['scriptPubKey']['hex'],
                'confirmations': output['confirmations'], 'coinbase': output['coinbase']}

    def transaction(self, txid):
        value = self.client.call('getrawtransaction', txid, True)
        tx = Transaction.deserialize(bytes.fromhex(value['hex']))
        if display(tx) != txid: raise ValueError('Bitcoin transaction ID mismatch')
        return tx, value.get('confirmations', 0)

    def broadcast(self, tx):
        self.info()
        try: result = self.client.call('sendrawtransaction', tx.serialize().hex())
        except ValueError:
            known, _ = self.transaction(display(tx))
            if known.serialize() != tx.serialize(): raise ValueError('Unexpected known transaction')
            return display(tx)
        if result != display(tx): raise ValueError('Broadcast transaction ID mismatch')
        return result

    def find_spend(self, funding, index, start):
        tip = self.info()['height']
        # Scan actual block transactions, including when the peer withholds its
        # claim notice. No claim/complete message is treated as chain evidence.
        for height in range(start, tip + 1):
            block = self.client.call('getblock', self.client.call('getblockhash', height), 2)
            for value in block['tx']:
                for item in value['vin']:
                    if item.get('txid') == funding and item.get('vout') == index:
                        return value['txid']
        return None


class SMWBackend:
    def __init__(self, url, token): self.client = LocalRPC(url, token, 'smw');self.standard=False;self.detected=False

    def info(self):
        try:
            value = self.client.call('swapinfo')
            self.standard=False
        except ValueError:
            value=self.client.call('gethtlcinfo')
            if not value.get('active'):raise ValueError('SUMUWW conditional-spend activation has not arrived')
            value={**value,'htlc':value.get('template')};self.standard=True
        if value.get('network') != 'regtest' or value.get('htlc') != 'exact-p2wsh-htlc-v1':
            raise ValueError('This exchange build accepts only the isolated HTLC network; public funding is disabled')
        self.detected=True
        return value

    def coins(self, script):
        if not self.detected:self.info()
        if not self.standard:return self.client.call('swapcoins', script.hex())
        from sumuww.address import encode_address
        addr=encode_address(script,network='regtest');offset=0;result=[]
        while True:
            page=self.client.call('listunspent',addr,1000,offset)
            for item in page['utxos']:
                if item['spendable']:
                    result.append({'txid':item['txid'],'vout':item['index'],'value':item['value_units'],'script':item['script_pubkey']})
            offset+=len(page['utxos'])
            if offset>=page['total']:return result
            if not page['utxos']:raise ValueError('Non-advancing SUMUWW UTXO cursor')

    def output(self, txid, index):
        if not self.detected:self.info()
        if not self.standard:return self.client.call('swapoutput', txid, index)
        value=self.client.call('gettxout',txid,index,True)
        return None if value is None else {'value':value['value_units'],'script':value['script_pubkey'],
                                           'confirmations':value['confirmations'],'coinbase':value['coinbase']}
    def transaction(self, txid):
        if not self.detected:self.info()
        value = self.client.call('getrawtransaction',txid,True) if self.standard else self.client.call('swaptransaction', txid)
        tx = Transaction.deserialize(bytes.fromhex(value['hex']))
        if display(tx) != txid: raise ValueError('SUMUWW transaction ID mismatch')
        return tx, value['confirmations']
    def broadcast(self, tx):
        self.info()
        if self.standard:
            try:result=self.client.call('sendrawtransaction',tx.serialize().hex())['txid']
            except ValueError:
                known,_=self.transaction(display(tx))
                if known.serialize()!=tx.serialize():raise ValueError('Known SUMUWW witness mismatch')
                result=display(tx)
        else:result = self.client.call('swapbroadcast', tx.serialize().hex())
        if result != display(tx): raise ValueError('SUMUWW broadcast ID mismatch')
        return result
    def find_spend(self, funding, index, start):
        if not self.detected:self.info()
        if not self.standard:return self.client.call('swapfindspend', funding, index, start)
        result=self.client.call('findspendingtransaction',funding,index,start)
        return result['txid'] if result else None


def backends(config):
    if set(config) != {'smw_url', 'smw_token', 'btc_url', 'btc_cookie'}:
        raise ValueError('Both local chain endpoints and credential files are required')
    return {'smw': SMWBackend(config['smw_url'], config['smw_token']),
            'btc': BitcoinBackend(config['btc_url'], config['btc_cookie'])}
