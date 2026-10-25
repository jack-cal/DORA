"""Authenticated loopback JSON-RPC 2.0 and HTTP API for the existing node.

All dispatch runs synchronously on the PeerNode asyncio actor. No wallet secrets,
signing or CPU mining are exposed. The token is a local capability, never an API
response field; callers must keep its file private. HTTP connections are bounded
and closed after one request. This is intentionally not a public web server.
"""

import asyncio
import hmac
import ipaddress
import json
import math
import os
from pathlib import Path
import re
import secrets
import socket
from urllib.parse import parse_qs, urlsplit

from .address import AddressError, decode_address, encode_address
from .block import Block, MAX_BLOCK_WEIGHT
from .errors import MempoolFull, UnsupportedFeature, ValidationError
from .rewards import read_reward
from .primitives import (coinbase_is_mature, format_amount, hash_from_display,
                         hash_to_display, valid_target)
from .transaction import Transaction
from .mempool_policy import MempoolPolicyError

MAX_HEADER = 8192
MAX_BODY = 2 * MAX_BLOCK_WEIGHT + 4096
MAX_RESPONSE = 2 * MAX_BODY + 8192
MAX_CONNECTIONS = 16
MAX_BATCH = 16
REQUEST_TIMEOUT = 10
WRITE_TIMEOUT = 3
MAX_LIMIT = 1000
MAX_OFFSET = 1_000_000
_TOKEN = re.compile(r'[0-9a-f]{64}')
_HEADER_NAME = re.compile(r'[!#$%&\'*+.^_`|~0-9A-Za-z-]+')


def validate_rpc_endpoint(host, port):
    """Return a numeric IPv4 loopback endpoint; port 0 permits test binding."""
    if type(host) is not str or type(port) is not int or not 0 <= port <= 65535:
        raise ValueError('RPC requires a loopback IPv4 address and a valid port')
    try:
        address = ipaddress.IPv4Address(host)
    except ipaddress.AddressValueError:
        raise ValueError('RPC requires a loopback IPv4 address') from None
    if not address.is_loopback or str(address) != host:
        raise ValueError('RPC requires a loopback IPv4 address')
    return str(address), port


def read_token(path):
    """Read an existing capability file without creating or replacing it."""
    path = Path(path)
    try:
        if path.is_symlink() or not path.is_file() or path.stat().st_size > 66:
            raise ValueError('Invalid RPC token file')
        with path.open('rb') as source:
            raw = source.read(67)
        token = raw.decode('ascii')
        if token.endswith('\r\n'):
            token = token[:-2]
        elif token.endswith('\n'):
            token = token[:-1]
    except (OSError, UnicodeError):
        raise ValueError('Invalid RPC token file') from None
    if _TOKEN.fullmatch(token) is None:
        raise ValueError('Invalid RPC token file')
    return token


def load_or_create_token(path):
    """Exclusively create a random token, or load a bounded existing token.

    Existing malformed files are never replaced. Creation uses restrictive POSIX
    mode where supported; Windows uses the containing user directory's ACL.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink():
        raise ValueError('Invalid RPC token file')
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        return read_token(path)
    token = secrets.token_hex(32)
    with os.fdopen(descriptor, 'wb') as destination:
        destination.write((token + '\n').encode('ascii'))
        destination.flush()
        os.fsync(destination.fileno())
    return token


class RpcError(Exception):
    def __init__(self, code, message):
        self.code = code
        self.message = message
        super().__init__(message)


class _HttpError(Exception):
    def __init__(self, status, message):
        self.status = status
        self.message = message


def _integer(value, minimum, maximum):
    if type(value) is not int or not minimum <= value <= maximum:
        raise RpcError(-32602, 'Invalid integer parameter')
    return value


def _hash(value):
    try:
        return hash_from_display(value)
    except (TypeError, ValueError):
        raise RpcError(-32602, 'Invalid hash parameter') from None


def _hex(value, maximum=MAX_BLOCK_WEIGHT):
    if (type(value) is not str or not value or len(value) > maximum * 2
            or len(value) % 2 or re.fullmatch(r'[0-9a-fA-F]+', value) is None):
        raise RpcError(-32602, 'Invalid hexadecimal parameter')
    return bytes.fromhex(value)


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Duplicate JSON member')
        result[key] = value
    return result


def _finite_float(text):
    value = float(text)
    if not math.isfinite(value):
        raise ValueError('Nonfinite JSON number')
    return value


def _bad_constant(_):
    raise ValueError('Nonfinite JSON number')


def _decode_json(raw):
    return json.loads(raw.decode('utf-8'), object_pairs_hook=_pairs,
                      parse_float=_finite_float, parse_constant=_bad_constant)


def _encode_json(value):
    return json.dumps(value, separators=(',', ':'), ensure_ascii=True,
                      allow_nan=False).encode('ascii')


METHODS = {
    'getblockchaininfo': (),
    'gethtlcinfo': (),
    'getspendinginfo': (),
    'getdatarecords': ('blockhash', 'offset', 'limit'),
    'decodescript': ('hex',),
    'gettxout': ('txid', 'index', 'include_mempool'),
    'findspendingtransaction': ('txid', 'index', 'start_height'),
    'getnetworkinfo': (),
    'getblockcount': (),
    'getbestblockhash': (),
    'getblockhash': ('height',),
    'getblock': ('hash', 'verbose'),
    'getrawmempool': (),
    'getmempoolinfo': (),
    'getmempoolpolicy': (),
    'estimatefee': ('vsize', 'mode'),
    'testmempoolaccept': ('hex',),
    'getmempoolentry': ('txid',),
    'gettransactionstatus': ('txid',),
    'getrawtransaction': ('txid', 'verbose'),
    'decoderawtransaction': ('hex',),
    'validateaddress': ('address',),
    'listunspent': ('address', 'limit', 'offset'),
    'getaddressbalance': ('address',),
    'sendrawtransaction': ('hex',),
    'submitblock': ('hex',),
    'getblocktemplate': ('address',),
    'help': (),
}
_REQUIRED = {'gettxout': 2, 'findspendingtransaction': 2, 'getblockhash': 1, 'getblock': 1, 'getrawtransaction': 1,
             'listunspent': 1, 'getaddressbalance': 1, 'sendrawtransaction': 1,
             'submitblock': 1, 'getblocktemplate': 1, 'decoderawtransaction': 1,
             'validateaddress': 1, 'testmempoolaccept': 1, 'getmempoolentry': 1, 'gettransactionstatus': 1, 'decodescript': 1, 'getdatarecords': 1}


class RpcServer:
    def __init__(self, node_provider, token, host='127.0.0.1', port=18443):
        self.address = validate_rpc_endpoint(host, port)
        if not callable(node_provider):
            raise ValueError('RPC requires a node provider')
        if type(token) is not str or _TOKEN.fullmatch(token) is None:
            raise ValueError('Invalid RPC token')
        self._node_provider = node_provider
        self._token = token
        self._server = None
        self._tasks = set()
        self._writers = set()
        self._start_lock = asyncio.Lock()
        self._stop_lock = asyncio.Lock()
        self._start_task = None
        self._stopping = False

    async def start(self):
        async with self._start_lock:
            if self._stopping:
                raise RuntimeError('RPC server is stopping')
            if self._server is None:
                self._start_task = asyncio.current_task()
                candidate = None
                try:
                    candidate = await asyncio.start_server(
                        self._accepted, *self.address, family=socket.AF_INET,
                        limit=MAX_HEADER, backlog=MAX_CONNECTIONS, start_serving=False)
                    self._server = candidate
                    bound = candidate.sockets[0].getsockname()
                    self.address = bound[0], bound[1]
                    await candidate.start_serving()
                except BaseException:
                    if candidate is not None:
                        candidate.close()
                        if self._server is candidate:
                            self._server = None
                    # Activation may already have accepted local clients.
                    # Close those too unless an external stop owns cleanup.
                    if not self._stopping:
                        await self.stop()
                    raise
                finally:
                    self._start_task = None
        return self

    async def stop(self):
        async with self._stop_lock:
            self._stopping = True
            try:
                await self._stop()
            finally:
                self._stopping = False

    async def _stop(self):
        current = asyncio.current_task()
        startup = self._start_task
        if startup is not None and startup is not current and not startup.done():
            startup.cancel()
            await asyncio.gather(startup, return_exceptions=True)
        server = self._server
        self._server = None
        if server is not None:
            server.close()
        writers = tuple(self._writers)
        for writer in writers:
            writer.close()
        tasks = tuple(task for task in self._tasks if task is not current)
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        if writers:
            await asyncio.gather(*(self._close_writer(writer) for writer in writers), return_exceptions=True)
        if server is not None:
            await asyncio.wait_for(server.wait_closed(), WRITE_TIMEOUT)

    async def _close_writer(self, writer):
        writer.close()
        try:
            await asyncio.wait_for(writer.wait_closed(), 1)
        except (OSError, TimeoutError, asyncio.CancelledError):
            # A local API client may stop reading a large bounded response.
            # Closing must not leave a flushing transport after its deadline.
            writer.transport.abort()

    def info(self):
        return {'enabled': self._server is not None,
                'listen': {'host': self.address[0], 'port': self.address[1]},
                'authentication': 'Bearer token', 'json_rpc': '2.0',
                'http_api': 'v1', 'scope': 'IPv4 loopback only'}

    async def _accepted(self, reader, writer):
        task = asyncio.current_task()
        if self._server is None or len(self._tasks) >= MAX_CONNECTIONS:
            writer.close()
            return
        self._tasks.add(task)
        self._writers.add(writer)
        try:
            try:
                status, body = await asyncio.wait_for(
                    self._request(reader), REQUEST_TIMEOUT)
            except _HttpError as error:
                status, body = error.status, {'error': {'message': error.message}}
            except (TimeoutError, asyncio.IncompleteReadError,
                    asyncio.LimitOverrunError, ConnectionError):
                status, body = 400, {'error': {'message': 'Incomplete or oversized request'}}
            except Exception:
                status, body = 500, {'error': {'message': 'Internal API error'}}
            payload = b'' if body is None else _encode_json(body)
            if len(payload) > MAX_RESPONSE:
                status, payload = 413, _encode_json({'error': {'message': 'Response exceeds limit'}})
            reason = {200: 'OK', 204: 'No Content', 400: 'Bad Request',
                      401: 'Unauthorized', 403: 'Forbidden', 404: 'Not Found',
                      405: 'Method Not Allowed', 409: 'Conflict',
                      413: 'Content Too Large', 415: 'Unsupported Media Type',
                      500: 'Internal Server Error', 503: 'Service Unavailable'}[status]
            header = (f'HTTP/1.1 {status} {reason}\r\n'
                      f'Content-Length: {len(payload)}\r\n'
                      'Content-Type: application/json\r\n'
                      'Connection: close\r\nCache-Control: no-store\r\n'
                      'X-Content-Type-Options: nosniff\r\n\r\n').encode('ascii')
            writer.write(header + payload)
            await asyncio.wait_for(writer.drain(), WRITE_TIMEOUT)
        except (ConnectionError, OSError, TimeoutError):
            pass
        finally:
            try:
                await self._close_writer(writer)
            finally:
                self._tasks.discard(task)
                self._writers.discard(writer)

    async def _request(self, reader):
        header = await reader.readuntil(b'\r\n\r\n')
        if len(header) > MAX_HEADER:
            raise _HttpError(413, 'Header exceeds limit')
        try:
            lines = header[:-4].decode('ascii').split('\r\n')
            method, target, version = lines[0].split(' ')
        except (UnicodeError, ValueError):
            raise _HttpError(400, 'Invalid HTTP request') from None
        if version != 'HTTP/1.1' or method not in ('GET', 'POST'):
            raise _HttpError(405, 'HTTP/1.1 GET or POST required')
        headers = {}
        for line in lines[1:]:
            if ':' not in line or line[:1] in (' ', '\t'):
                raise _HttpError(400, 'Invalid HTTP header')
            name, value = line.split(':', 1)
            if (_HEADER_NAME.fullmatch(name) is None
                    or any(ord(c) < 32 and c != '\t' for c in value)
                    or any(ord(c) == 127 for c in value)):
                raise _HttpError(400, 'Invalid HTTP header')
            name = name.lower()
            if name in headers:
                raise _HttpError(400, 'Duplicate HTTP header')
            headers[name] = value.strip(' \t')
        if headers.get('host') != f'{self.address[0]}:{self.address[1]}':
            raise _HttpError(403, 'Invalid Host header')
        if ('origin' in headers or 'referer' in headers
                or headers.get('sec-fetch-site', 'none') not in ('none',)):
            raise _HttpError(403, 'Browser-origin requests are not supported')
        expected = 'Bearer ' + self._token
        authorization = headers.get('authorization', '')
        if not hmac.compare_digest(authorization, expected):
            raise _HttpError(401, 'Authentication required')
        if any(name in headers for name in ('transfer-encoding', 'expect', 'trailer', 'upgrade')):
            raise _HttpError(400, 'Unsupported request framing')
        length = headers.get('content-length')
        if length is None:
            if method == 'POST':
                raise _HttpError(400, 'Content-Length required')
            count = 0
        elif not re.fullmatch(r'0|[1-9][0-9]{0,7}', length):
            raise _HttpError(400, 'Invalid Content-Length')
        else:
            count = int(length)
        if count > MAX_BODY:
            raise _HttpError(413, 'Body exceeds limit')
        if method == 'GET' and count:
            raise _HttpError(400, 'GET body is not supported')
        if method == 'POST' and headers.get('content-type', '').lower().split(';', 1)[0].strip() != 'application/json':
            raise _HttpError(415, 'application/json required')
        if not target.startswith('/') or target.startswith('//') or '#' in target or '%' in target:
            raise _HttpError(400, 'Invalid request target')
        parts = urlsplit(target)
        if parts.scheme or parts.netloc:
            raise _HttpError(400, 'Invalid request target')
        raw = await reader.readexactly(count)
        if parts.path == '/rpc':
            if method != 'POST' or parts.query:
                raise _HttpError(405, 'POST /rpc required')
            try:
                value = _decode_json(raw)
            except (ValueError, UnicodeError, RecursionError):
                return 200, self._error(None, -32700, 'Parse error')
            result = self._rpc(value)
            return (204, None) if result is None else (200, result)
        try:
            if method == 'POST':
                try:
                    body = _decode_json(raw)
                except (ValueError, UnicodeError, RecursionError):
                    raise RpcError(-32700, 'Parse error') from None
                if type(body) is not dict:
                    raise RpcError(-32602, 'JSON object required')
            else:
                body = None
            result = self._rest(method, parts.path, parts.query, body)
            return 200, result
        except RpcError as error:
            status = {-32601: 404, -32001: 404, -32002: 409,
                      -32003: 503, -32005: 503, -32006: 409, -32603: 500}.get(error.code, 400)
            return status, {'error': {'code': error.code, 'message': error.message}}

    @staticmethod
    def _error(identifier, code, message):
        return {'jsonrpc': '2.0', 'id': identifier,
                'error': {'code': code, 'message': message}}

    def _rpc(self, value):
        if type(value) is list:
            if not 1 <= len(value) <= MAX_BATCH:
                return self._error(None, -32600, 'Invalid request or batch limit')
            responses = []
            size = 0
            for request in value:
                response = self._rpc_one(request)
                if response is not None:
                    size += len(_encode_json(response))
                    if size > MAX_RESPONSE - 1024:
                        return self._error(None, -32004, 'Batch response exceeds limit')
                    responses.append(response)
            return responses or None
        return self._rpc_one(value)

    def _rpc_one(self, request):
        if type(request) is not dict:
            return self._error(None, -32600, 'Invalid request')
        identifier = request.get('id')
        valid_id = (identifier is None or type(identifier) is int and abs(identifier) < 2 ** 63
                    or type(identifier) is str and len(identifier) <= 128)
        if (request.get('jsonrpc') != '2.0' or type(request.get('method')) is not str
                or not valid_id or set(request) - {'jsonrpc', 'method', 'params', 'id'}
                or type(request.get('params', [])) not in (list, dict)):
            return self._error(None, -32600, 'Invalid request')
        notification = 'id' not in request
        try:
            result = self.call(request['method'], request.get('params', []))
            response = {'jsonrpc': '2.0', 'id': identifier, 'result': result}
        except RpcError as error:
            response = self._error(identifier, error.code, error.message)
        return None if notification else response

    def call(self, method, params=None):
        """Actor-thread dispatcher, also used by the HTTP endpoints."""
        if method not in METHODS:
            raise RpcError(-32601, 'Method not found')
        names = METHODS[method]
        required = _REQUIRED.get(method, 0)
        if params is None:
            params = []
        if type(params) is list:
            if not required <= len(params) <= len(names):
                raise RpcError(-32602, 'Invalid parameters')
            arguments = dict(zip(names, params))
        elif type(params) is dict:
            if set(params) - set(names) or any(name not in params for name in names[:required]):
                raise RpcError(-32602, 'Invalid parameters')
            arguments = params
        else:
            raise RpcError(-32602, 'Invalid parameters')
        if method == 'help':
            return {'methods': {name: {'parameters': list(fields),
                                      'required': _REQUIRED.get(name, 0)}
                                for name, fields in METHODS.items()},
                    'money': 'Integer yugeon amounts and fixed 8-decimal SMW strings; 1 SMW = 100000000 yugeon',
                    'wallet_signing': False}
        try:
            node = self._node_provider()
            if node is None or not node.running:
                raise RpcError(-32003, 'Node is not running')
            from .compatibility import compatibility_fields
            return compatibility_fields(self._dispatch(node, method, arguments))
        except RpcError:
            raise
        except MempoolPolicyError as error:
            raise RpcError(-32006, str(error)) from None
        except MempoolFull:
            raise RpcError(-32005, 'Local mempool is full. Transaction was not queued; retry after capacity becomes available.') from None
        except (ValidationError, UnsupportedFeature):
            raise RpcError(-32002, 'Data rejected by node validation') from None
        except Exception:
            raise RpcError(-32603, 'Internal API error') from None

    @staticmethod
    def _address(chain, address):
        try:
            return decode_address(address, network=chain.network)
        except (AddressError, TypeError):
            raise RpcError(-32602, 'Invalid address parameter') from None

    @staticmethod
    def _transaction_view(transaction, chain, *, block=None, height=None, tip_height=None):
        outputs = []
        for index, output in enumerate(transaction.outputs):
            item = {'index': index, 'value_units': output.value,
                    'value_smw': format_amount(output.value),
                    'script_pubkey': output.script_pubkey.hex()}
            try:
                item['address'] = encode_address(output.script_pubkey, network=chain.network)
            except AddressError:
                pass
            outputs.append(item)
        result = {'txid': hash_to_display(transaction.txid()),
                  'wtxid': hash_to_display(transaction.wtxid()),
                  'hex': transaction.serialize().hex(), 'version': transaction.version,
                  'lock_time': transaction.lock_time, 'coinbase': transaction.is_coinbase(),
                  'weight': transaction.weight(), 'vsize': (transaction.weight()+3)//4, 'amount_unit': 'yugeon', 'outputs': outputs,
                  'inputs': [{'txid': hash_to_display(item.prev_txid),
                              'index': item.prev_index, 'sequence': item.sequence}
                             for item in transaction.inputs],
                  'confirmations': 0 if height is None else tip_height - height + 1,
                  'in_mempool': height is None}
        if height is not None:
            if transaction.is_coinbase():
                from .rewards import read_reward
                result['mining_reward'] = read_reward(chain.connection, block, height)
            result.update({'blockhash': hash_to_display(block.block_hash()), 'height': height})
        return result

    def _dispatch(self, node, method, arguments):
        chain = node.chain
        if method == 'getdatarecords':
            digest = _hash(arguments['blockhash'])
            offset = _integer(arguments.get('offset', 0), 0, MAX_OFFSET)
            limit = _integer(arguments.get('limit', 100), 1, MAX_LIMIT)
            with chain.read_snapshot():
                if not chain.has_block(digest): raise RpcError(-32001, 'Block not found')
                block = chain.get_block(digest)
                height = chain._row(digest)[2]
                path = chain._path(chain.tip_hash)
                active = height < len(path) and path[height][0][0] == digest
                records = [{'txid': hash_to_display(tx.txid()), 'transaction_index': tx_index,
                            'output_index': index, 'script_pubkey': output.script_pubkey.hex(),
                            'value_units': output.value}
                           for tx_index, tx in enumerate(block.transactions)
                           for index, output in enumerate(tx.outputs) if output.script_pubkey.startswith(b'\x6a')]
                return {'blockhash': hash_to_display(digest), 'height': height, 'active': active,
                        'bestblockhash': hash_to_display(chain.tip_hash), 'amount_unit': 'yugeon',
                        'total': len(records), 'offset': offset, 'records': records[offset:offset+limit]}
        if method == 'getspendinginfo':
            return chain.spending_policy.info(chain._row(chain.tip_hash)[2])
        if method == 'decodescript':
            from .spending import SpendingTemplate
            try: template = SpendingTemplate.parse(_hex(arguments['hex'], 600))
            except (ValueError, TypeError, IndexError):
                raise RpcError(-32602, 'Unsupported or noncanonical spending template') from None
            return dict(template.info(), address=encode_address(template.script_pubkey, network=chain.network),
                        activation=chain.spending_policy.info(chain._row(chain.tip_hash)[2]))
        if method == 'getmempoolpolicy':
            return dict(chain.mempool_policy.info(), amount_unit='yugeon', yugeon_per_smw=100_000_000)
        if method == 'estimatefee':
            from .fees import estimate_fee
            size = _integer(arguments.get('vsize', 140), 1, 1_000_000)
            mode = arguments.get('mode', 'normal')
            if mode not in ('slow', 'normal', 'fast'):
                raise RpcError(-32602, 'Invalid fee mode')
            return estimate_fee(chain, size, mode)
        if method == 'testmempoolaccept':
            return chain.test_mempool_accept(Transaction.deserialize(_hex(arguments['hex'])))
        if method == 'getmempoolentry':
            result = chain.mempool_entry(_hash(arguments['txid']))
            if result is None: raise RpcError(-32001, 'Transaction not in local mempool')
            return result
        if method == 'gettransactionstatus':
            return chain.transaction_status(_hash(arguments['txid']))
        if method == 'validateaddress':
            address = arguments['address']
            if not isinstance(address, str):
                raise RpcError(-32602, 'Address must be a string')
            try:
                script = decode_address(address, network=chain.network)
            except AddressError:
                return {'isvalid': False, 'network': chain.network.name}
            return {'isvalid': True, 'network': chain.network.name,
                    'address': encode_address(script, network=chain.network),
                    'script_pubkey': script.hex()}
        if method == 'decoderawtransaction':
            transaction = Transaction.deserialize(_hex(arguments['hex']))
            result = self._transaction_view(transaction, chain)
            # Parsing is independent of acceptance, signature validation and
            # chain membership. Do not fabricate a pending/confirmed state.
            result.pop('confirmations')
            result.pop('in_mempool')
            result['validation'] = 'decoded_only'
            return result
        if method == 'sendrawtransaction':
            raw = _hex(arguments['hex'])
            transaction = Transaction.deserialize(raw)
            digest = chain.submit_transaction(transaction)
            return {'txid': hash_to_display(digest), 'accepted': True}
        if method == 'submitblock':
            raw = _hex(arguments['hex'])
            block = Block.deserialize(raw)
            known = chain.has_block(block.block_hash())
            activated = chain.accept_block(block)
            return {'hash': hash_to_display(block.block_hash()), 'accepted': True,
                    'already_known': known, 'activated': activated}
        with chain.read_snapshot():
            if method == 'gethtlcinfo':
                return chain.htlc_policy.info(chain._row(chain.tip_hash)[2])
            if method == 'gettxout':
                digest = _hash(arguments['txid'])
                index = _integer(arguments['index'], 0, 0xFFFFFFFF)
                include_mempool = arguments.get('include_mempool', True)
                if type(include_mempool) is not bool: raise RpcError(-32602, 'Invalid mempool flag')
                if include_mempool and any(item.prev_txid == digest and item.prev_index == index
                        for tx in chain.mempool_transactions() for item in tx.inputs): return None
                for point, coin in chain.list_utxos():
                    if point == (digest, index):
                        return {'value_units': coin.output.value, 'script_pubkey': coin.output.script_pubkey.hex(),
                                'confirmations': chain._row(chain.tip_hash)[2] - coin.height + 1,
                                'coinbase': coin.coinbase}
                return None
            if method == 'findspendingtransaction':
                digest = _hash(arguments['txid'])
                index = _integer(arguments['index'], 0, 0xFFFFFFFF)
                start = _integer(arguments.get('start_height', 0), 0, 0x7FFFFFFF)
                path = chain._path(chain.tip_hash)
                for height in range(start, len(path)):
                    for tx in path[height][1].transactions:
                        if any(item.prev_txid == digest and item.prev_index == index for item in tx.inputs):
                            return {'txid': hash_to_display(tx.txid()), 'height': height,
                                    'confirmations': len(path) - height, 'hex': tx.serialize().hex()}
                return None
            if method == 'getblockchaininfo':
                result = chain.info()
                result.update(node.synchronization_info())
                return result
            if method == 'getnetworkinfo':
                result = node.info()
                result.pop('last_peer_error', None)
                return result
            if method == 'getblockcount':
                return chain._row(chain.tip_hash)[2]
            if method == 'getbestblockhash':
                return hash_to_display(chain.tip_hash)
            if method == 'getrawmempool':
                return [hash_to_display(tx.txid()) for tx in chain.mempool_transactions()]
            if method == 'getmempoolinfo':
                return chain.mempool_info()
            if method == 'getblocktemplate':
                if chain.network.name == 'dora' and not node.synchronization_info()['mining_ready']:
                    raise RpcError(-32003, 'Mining requires connected synchronized peers')
                script = self._address(chain, arguments['address'])
                template = chain._block_template(script)
                height = chain._row(chain.tip_hash)[2] + 1
                from .rewards import reward_info
                from .primitives import subsidy
                fees = sum(o.value for o in template.transactions[0].outputs) - subsidy(height)
                return {'reward': reward_info(template, height, fees), 'height': height, 'previousblockhash': hash_to_display(chain.tip_hash),
                        'bits': f'{template.header.bits:08x}',
                        'target': f'{valid_target(template.header.bits, chain.network.pow_limit):064x}',
                        'timestamp': template.header.timestamp,
                        'header_hex': template.header.serialize().hex(),
                        'block_hex': template.serialize().hex(),
                        'coinbase_value_units': template.transactions[0].outputs[0].value,
                        'coinbase_value_smw': format_amount(template.transactions[0].outputs[0].value),
                        'transactions': [tx.serialize().hex() for tx in template.transactions[1:]],
                        'pow': 'SHA256d', 'nonce_min': 0, 'nonce_max': 0xFFFFFFFF}
            if method in ('listunspent', 'getaddressbalance'):
                return self._coins(chain, method, arguments)
            path = chain._path(chain.tip_hash)
            tip_height = len(path) - 1
            if method == 'getblockhash':
                height = _integer(arguments['height'], 0, 0x7FFFFFFF)
                if height > tip_height:
                    raise RpcError(-32001, 'Block height not found')
                return hash_to_display(path[height][0][0])
            verbose = arguments.get('verbose', True)
            if type(verbose) is not bool:
                raise RpcError(-32602, 'verbose must be a boolean')
            if method == 'getblock':
                digest = _hash(arguments['hash'])
                if not chain.has_block(digest):
                    raise RpcError(-32001, 'Block not found')
                row = chain._row(digest)
                block = chain.get_block(digest)
                if not verbose:
                    return block.serialize().hex()
                active = row[2] <= tip_height and path[row[2]][0][0] == digest
                return {'hash': hash_to_display(digest), 'height': row[2],
                        'active': active, 'confirmations': tip_height - row[2] + 1 if active else -1,
                        'reward': read_reward(chain.connection, block, row[2]),
                        'previousblockhash': hash_to_display(row[1]),
                        'chainwork': row[3], 'bits': f'{block.header.bits:08x}',
                        'timestamp': block.header.timestamp, 'nonce': block.header.nonce,
                        'weight': block.weight(), 'hex': block.serialize().hex(),
                        'tx': [hash_to_display(tx.txid()) for tx in block.transactions]}
            if method == 'getrawtransaction':
                digest = _hash(arguments['txid'])
                transaction = chain.get_mempool_transaction(digest)
                if transaction is not None:
                    return self._transaction_view(transaction, chain) if verbose else transaction.serialize().hex()
                for height, (_, block) in enumerate(path):
                    for transaction in block.transactions:
                        if transaction.txid() == digest:
                            return (self._transaction_view(transaction, chain, block=block,
                                                           height=height, tip_height=tip_height)
                                    if verbose else transaction.serialize().hex())
                raise RpcError(-32001, 'Transaction not found in active chain or mempool')
        raise RpcError(-32601, 'Method not found')

    def _coins(self, chain, method, arguments):
        script = self._address(chain, arguments['address'])
        tip_height = chain._row(chain.tip_hash)[2]
        pending = {(item.prev_txid, item.prev_index)
                   for transaction in chain.mempool_transactions() for item in transaction.inputs}
        coins = chain.list_utxos(script)
        if method == 'getaddressbalance':
            confirmed = sum(coin.output.value for _, coin in coins)
            mature = sum(coin.output.value for _, coin in coins
                         if not coin.coinbase or coinbase_is_mature(coin.height, tip_height + 1))
            pending_spent = sum(coin.output.value for key, coin in coins if key in pending)
            available = sum(coin.output.value for key, coin in coins if key not in pending
                            and (not coin.coinbase or coinbase_is_mature(coin.height, tip_height + 1)))
            result = {'address': arguments['address'], 'height': tip_height}
            for label, value in [('confirmed', confirmed), ('mature', mature),
                                 ('immature', confirmed - mature),
                                 ('pending_spent', pending_spent), ('available', available)]:
                result[label + '_units'] = value
                result[label + '_smw'] = format_amount(value)
            return result
        limit = _integer(arguments.get('limit', 100), 1, MAX_LIMIT)
        offset = _integer(arguments.get('offset', 0), 0, MAX_OFFSET)
        items = []
        for (digest, index), coin in coins[offset:offset + limit]:
            mature = not coin.coinbase or coinbase_is_mature(coin.height, tip_height + 1)
            spent = (digest, index) in pending
            items.append({'txid': hash_to_display(digest), 'index': index,
                          'value_units': coin.output.value, 'value_smw': format_amount(coin.output.value),
                          'height': coin.height, 'confirmations': tip_height - coin.height + 1,
                          'coinbase': coin.coinbase, 'mature': mature,
                          'pending_spent': spent, 'spendable': mature and not spent,
                          'script_pubkey': script.hex(), 'address': arguments['address']})
        return {'address': arguments['address'], 'height': tip_height, 'total': len(coins),
                'limit': limit, 'offset': offset, 'utxos': items}

    def _rest(self, method, path, query, body):
        reads = {'/api/v1/info': 'getblockchaininfo', '/api/v1/network': 'getnetworkinfo',
                 '/api/v1/mempool': 'getrawmempool',
                 '/api/v1/mempool/info': 'getmempoolinfo'}
        if path in reads and method == 'GET' and not query:
            return self.call(reads[path])
        if method == 'POST' and not query:
            writes = {'/api/v1/transactions': ('sendrawtransaction', 'hex'),
                      '/api/v1/blocks': ('submitblock', 'hex'),
                      '/api/v1/mining/template': ('getblocktemplate', 'address')}
            if path in writes:
                operation, field = writes[path]
                if set(body) != {field}:
                    raise RpcError(-32602, 'Invalid parameters')
                return self.call(operation, body)
        if method == 'GET' and path.startswith('/api/v1/blocks/') and not query:
            identifier = path.removeprefix('/api/v1/blocks/')
            if re.fullmatch(r'0|[1-9][0-9]{0,9}', identifier):
                # A numeric height means the active block at one revision.
                # Keep resolution and the resulting block view in one snapshot
                # even when another CLI/mining connection commits a reorg.
                node = self._node_provider()
                if node is None or not node.running:
                    raise RpcError(-32003, 'Node is not running')
                with node.chain.read_snapshot():
                    identifier = self.call('getblockhash', [int(identifier)])
                    return self.call('getblock', [identifier])
            return self.call('getblock', [identifier])
        if method == 'GET' and path.startswith('/api/v1/transactions/') and not query:
            return self.call('getrawtransaction', [path.removeprefix('/api/v1/transactions/')])
        match = re.fullmatch(r'/api/v1/addresses/([^/]+)/(balance|utxos)', path)
        if method == 'GET' and match:
            address, operation = match.groups()
            if operation == 'balance' and not query:
                return self.call('getaddressbalance', [address])
            if operation == 'utxos':
                try:
                    values = parse_qs(query, keep_blank_values=True, strict_parsing=True,
                                      max_num_fields=2)
                    if set(values) - {'limit', 'offset'} or any(len(v) != 1 for v in values.values()):
                        raise ValueError
                    arguments = {'address': address}
                    for name, value in values.items():
                        if re.fullmatch(r'0|[1-9][0-9]{0,6}', value[0]) is None:
                            raise ValueError
                        arguments[name] = int(value[0])
                except ValueError:
                    raise RpcError(-32602, 'Invalid pagination parameters') from None
                return self.call('listunspent', arguments)
        raise RpcError(-32601, 'API endpoint not found')
