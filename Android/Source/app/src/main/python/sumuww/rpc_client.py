"""Authenticated local RPC client; credentials are read from a private file."""

import argparse
import ipaddress
import json
from pathlib import Path
import re
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

MAX_REQUEST_BYTES = 8_100_000
MAX_RESPONSE_BYTES = 16_200_000


class RpcCallError(ValueError):
    """Structured node rejection; retains the original ValueError interface."""
    def __init__(self, code, message):
        self.code = code
        self.message = message
        super().__init__('RPC error %s: %s' % (code, message))


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, response, code, message, headers, new_url):
        return None


def _constant(value):
    raise ValueError('Non-finite JSON numbers are unsupported')


def _object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Duplicate JSON object keys are unsupported')
        result[key] = value
    return result


def _url(value):
    try:
        parsed = urlsplit(value)
        address = ipaddress.IPv4Address(parsed.hostname or '')
        port = parsed.port or 80
    except (ValueError, TypeError):
        raise ValueError('RPC URL must use a numeric loopback IPv4 address') from None
    if (parsed.scheme != 'http' or not address.is_loopback or not 1 <= port <= 65535
            or parsed.username is not None or parsed.password is not None
            or parsed.query or parsed.fragment or parsed.path != '/rpc'):
        raise ValueError('Use http://127.0.0.1:PORT/rpc without credentials or query parameters')
    return value


def call(url, token_file, method, params=None, *, timeout=10):
    from .rpc import read_token
    url = _url(url)
    if not isinstance(method, str) or not re.fullmatch(r'[a-z][a-z0-9]{0,63}', method):
        raise ValueError('Invalid RPC method name')
    if params is None:
        params = {}
    if not isinstance(params, (dict, list)):
        raise ValueError('RPC params must be a JSON object or array')
    token = read_token(token_file)
    payload = json.dumps({'jsonrpc': '2.0', 'id': 1, 'method': method, 'params': params},
                         ensure_ascii=True, allow_nan=False).encode('utf-8')
    if len(payload) > MAX_REQUEST_BYTES:
        raise ValueError('RPC request is too large')
    request = Request(url, data=payload, method='POST', headers={
        'Content-Type': 'application/json', 'Authorization': 'Bearer ' + token,
        'Accept': 'application/json'})
    # Never forward this local credential through environment proxies or redirects.
    opener = build_opener(ProxyHandler({}), _NoRedirect())
    try:
        with opener.open(request, timeout=timeout) as response:
            body = response.read(MAX_RESPONSE_BYTES + 1)
    except HTTPError as error:
        raise ValueError('RPC HTTP request failed (status %d)' % error.code) from None
    except (URLError, TimeoutError, OSError):
        raise ValueError('Unable to reach the local RPC server') from None
    if len(body) > MAX_RESPONSE_BYTES:
        raise ValueError('RPC response is too large')
    try:
        result = json.loads(body.decode('utf-8'), parse_constant=_constant,
                            object_pairs_hook=_object)
    except (ValueError, UnicodeError, RecursionError):
        raise ValueError('Invalid JSON-RPC response') from None
    if not isinstance(result, dict) or result.get('jsonrpc') != '2.0' or result.get('id') != 1:
        raise ValueError('Mismatched JSON-RPC response')
    if 'error' in result:
        error = result['error']
        if not isinstance(error, dict):
            raise ValueError('Invalid JSON-RPC error response')
        raise RpcCallError(error.get('code'), error.get('message'))
    if 'result' not in result:
        raise ValueError('Missing JSON-RPC result')
    return result['result']


def main(argv=None):
    parser = argparse.ArgumentParser(description='SUMUWW local authenticated JSON-RPC client')
    parser.add_argument('--url', default='http://127.0.0.1:18443/rpc')
    parser.add_argument('--token-file', type=Path, required=True,
                        help='Existing private token file created by the RPC server')
    params = parser.add_mutually_exclusive_group()
    params.add_argument('--params', default=None, help='Named JSON object or positional JSON array')
    params.add_argument('--params-file', type=Path, help='UTF-8 JSON parameters file for large transactions/blocks')
    parser.add_argument('method')
    args = parser.parse_args(argv)
    try:
        if args.params_file is not None:
            with args.params_file.open('rb') as stream:
                raw = stream.read(MAX_REQUEST_BYTES + 1)
            if len(raw) > MAX_REQUEST_BYTES:
                raise ValueError('RPC parameters file is too large')
            text = raw.decode('utf-8-sig')
        else:
            text = args.params or '{}'
        parameters = json.loads(text, parse_constant=_constant, object_pairs_hook=_object)
        result = call(args.url, args.token_file, args.method, parameters)
        print(json.dumps(result, ensure_ascii=False, allow_nan=False, indent=2))
        return 0
    except (ValueError, OSError, UnicodeError, RecursionError) as error:
        print(json.dumps({'error': 'RpcClientError', 'message': str(error)}, ensure_ascii=False),
              file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
