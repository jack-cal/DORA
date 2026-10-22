"""Existing-node wallet observation. Credentials stay on the local computer.

This reader deliberately has no transaction signing, broadcast or wallet-unlock
methods. A successful balance query does not enable public atomic swaps.
"""
import base64
import ipaddress
import json
import secrets
from decimal import Decimal
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, ProxyHandler, HTTPRedirectHandler, build_opener
from sumuww.address import decode_address, _bech32_decode, _convert_bits
from sumuww.profiles import get_network
from .orders import canonical, valid_hex

class NoRedirect(HTTPRedirectHandler):

    def redirect_request(self, *args, **kwargs):
        raise ValueError('RPC redirects are not allowed')

def endpoint(url):
    if not isinstance(url, str) or len(url) > 2048:
        raise ValueError('Invalid local RPC URL')
    p = urlsplit(url)
    try:
        local = ipaddress.ip_address(p.hostname or '')
        port = p.port
    except ValueError:
        raise ValueError('RPC requires a numeric loopback address') from None
    if p.scheme != 'http' or not local.is_loopback or (not port) or p.username or p.password or p.query or p.fragment:
        raise ValueError('RPC must use HTTP on this computer; no embedded credentials')
    return url

class LocalRPC:

    def __init__(self, url, credential_file, coin):
        self.url = endpoint(url)
        self.path = Path(credential_file)
        if coin not in ('smw', 'btc'):
            raise ValueError('Invalid coin')
        self.coin = coin
        self.opener = build_opener(ProxyHandler({}), NoRedirect())

    def call(self, method, *params):
        try:
            if self.path.is_symlink() or not 0 < self.path.stat().st_size <= 4096:
                raise ValueError()
            token = self.path.read_text(encoding='ascii').strip()
            if self.coin == 'smw':
                if not valid_hex(token, 32):
                    raise ValueError()
                authorization = 'Bearer ' + token
            else:
                if ':' not in token or '\n' in token or '\r' in token:
                    raise ValueError()
                authorization = 'Basic ' + base64.b64encode(token.encode()).decode()
        except (OSError, ValueError, UnicodeError):
            raise ValueError('Cannot read the local RPC authentication file.') from None
        identifier = secrets.token_hex(12)
        request = Request(self.url, data=canonical({'jsonrpc': '2.0', 'id': identifier, 'method': method, 'params': list(params)}), headers={'Authorization': authorization, 'Content-Type': 'application/json'})
        try:
            with self.opener.open(request, timeout=60) as response:
                raw = response.read(16 * 1024 * 1024 + 1)
            if len(raw) > 16 * 1024 * 1024:
                raise ValueError('RPC response too large')

            def pairs(items):
                value = {}
                for key, item in items:
                    if key in value:
                        raise ValueError('Duplicate RPC member')
                    value[key] = item
                return value
            body = json.loads(raw, object_pairs_hook=pairs, parse_float=Decimal, parse_constant=lambda _: (_ for _ in ()).throw(ValueError('Nonfinite RPC number')))
            if not isinstance(body, dict) or body.get('id') != identifier:
                raise ValueError('RPC response identifier mismatch')
            if body.get('error'):
                raise ValueError('RPC request rejected. Check node settings and supported features.')
            return body['result']
        except HTTPError as exc:
            raise ValueError('Local RPC authentication or HTTP request rejected.') from None
        except (URLError, OSError, KeyError, json.JSONDecodeError):
            raise ValueError('Cannot connect to the local node or its response is invalid.') from None

def bitcoin_script(address, chain):
    hrp, values = _bech32_decode(address)
    expected = {'main': 'bc', 'test': 'tb', 'testnet4': 'tb', 'signet': 'tb', 'regtest': 'bcrt'}.get(chain)
    if hrp != expected or not values or values[0] != 0:
        raise ValueError('Bitcoin address does not match node network or supported P2WPKH format')
    program = bytes(_convert_bits(values[1:], 5, 8, pad=False))
    if len(program) != 20:
        raise ValueError('Only native P2WPKH receive addresses are supported')
    return b'\x00\x14' + program

class WalletLinks:

    def __init__(self, directory):
        self.path = Path(directory) / 'wallet-links.json'
        self.config = json.loads(self.path.read_text()) if self.path.exists() else {}
        self.results = {}

    def configure(self, coin, url, credential_file, address):
        if coin not in ('smw', 'btc') or not isinstance(address, str) or len(address) > 90:
            raise ValueError('Invalid wallet connection')
        endpoint(url)
        proposed = {'url': url, 'credential_file': str(Path(credential_file).resolve()), 'address': address}
        result = self._query(coin, proposed)
        config = {**self.config, coin: proposed}
        from .vault import _write_new
        temp = self.path.with_name('wallet-links.' + secrets.token_hex(8) + '.tmp')
        try:
            _write_new(temp, canonical(config))
            temp.replace(self.path)
        finally:
            temp.unlink(missing_ok=True)
        self.config = config
        self.results[coin] = result
        return result

    def refresh(self, coin):
        if coin not in self.config:
            raise ValueError('Connect the wallet node first.')
        try:
            result = self._query(coin, self.config[coin])
        except Exception:
            self.results.pop(coin, None)
            raise
        self.results[coin] = result
        return result

    @staticmethod
    def _query(coin, config):
        rpc = LocalRPC(config['url'], config['credential_file'], coin)
        info = rpc.call('getblockchaininfo')
        genesis = rpc.call('getblockhash', 0)
        if not valid_hex(genesis, 32):
            raise ValueError('Invalid genesis identifier')
        addr = config['address']
        activation_height = None
        if coin == 'smw':
            network = get_network(info['network'])
            if genesis != network.genesis.block_hash()[::-1].hex():
                raise ValueError('SUMUWW genesis mismatch')
            decode_address(addr, network=network)
            balance = rpc.call('getaddressbalance', addr)
            confirmed, available, immature = (balance[k + '_units'] for k in ('confirmed', 'available', 'immature'))
            if any((type(n) is not int or n < 0 for n in (confirmed, available, immature))):
                raise ValueError('Invalid SUMUWW balance')
            chain, height = (network.profile_id, balance['height'])
            atomic_swap_supported = False
            try:
                policy = rpc.call('gethtlcinfo')
                if policy.get('genesis') != genesis or type(policy.get('active')) is not bool:
                    raise ValueError('Conditional-spend capability identity mismatch')
                activation_height = policy.get('activation_height')
                if type(activation_height) is int and activation_height > 0:
                    atomic_swap_supported = policy['active'] and policy.get('height', -1) >= activation_height
                else:
                    activation_height = None
            except ValueError:
                pass
        else:
            chain = info['chain']
            script = bitcoin_script(addr, chain)
            scan = rpc.call('scantxoutset', 'start', ['addr(' + addr + ')'])
            if not scan.get('success'):
                raise ValueError('Bitcoin UTXO scan did not complete')
            confirmed = available = immature = 0
            for item in scan['unspents']:
                if item['scriptPubKey'] != script.hex():
                    raise ValueError('Bitcoin script mismatch')
                value = Decimal(str(item['amount'])) * 100000000
                if value != value.to_integral_value() or value < 0:
                    raise ValueError('Invalid Bitcoin amount')
                value = int(value)
                current = rpc.call('gettxout', item['txid'], item['vout'], True)
                if not current:
                    continue
                if current['scriptPubKey']['hex'] != script.hex():
                    raise ValueError('Changed Bitcoin script')
                if Decimal(str(current['value'])) * 100000000 != value:
                    raise ValueError('Changed Bitcoin value')
                confirmed += value
                if current['coinbase'] and current['confirmations'] < 100:
                    immature += value
                else:
                    available += value
            height = scan['height']
            atomic_swap_supported = True
        return {'coin': coin, 'network': chain, 'genesis': genesis, 'address': addr, 'height': height, 'confirmed_units': confirmed, 'available_units': available, 'immature_units': immature, 'read_only': True, 'htlc_activation_height': activation_height, 'htlc_spending_supported': atomic_swap_supported}

    def state(self):
        return {'configured': list(self.config), 'results': dict(self.results), 'public_trading': False}
