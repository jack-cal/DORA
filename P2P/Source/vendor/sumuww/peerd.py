"""Manual IP peer daemon with explicit LAN/internet transport opt-ins."""

import argparse
import asyncio
import json
import ipaddress
import os
from pathlib import Path
import re
import sys
import tempfile
import time

from . import __version__
from .peer import PeerNode, _endpoint
from .profiles import NETWORK_NAMES, get_network
from .bootstrap import load_bootstrap
from .self_address import DEFAULT_PORT
from .wallet_paths import reject_wallet_overwrite


def endpoint(text, *, allow_zero=True, allow_lan=False, allow_internet=False, for_listen=False):
    if not isinstance(text, str):
        raise ValueError('Use a permitted IPv4 or enabled outbound DNS HOST:PORT endpoint')
    if text.startswith('['):
        match = re.fullmatch(r'\[([^\]]+)\]:([0-9]{1,5})', text)
        if match is None:
            raise ValueError('Use [IPv6]:PORT')
        fields = match.groups()
    else:
        fields = text.split(':')
        if len(fields) != 2 or not re.fullmatch(r'[0-9]{1,5}', fields[1]):
            raise ValueError('Use HOST:PORT or [IPv6]:PORT')
    return _endpoint(fields[0], int(fields[1]), allow_zero=allow_zero, allow_lan=allow_lan,
                     allow_internet=allow_internet, for_listen=for_listen)


def public_contact(text, listen, *, allow_internet=False, allow_lan=False):
    """Validate an explicitly supplied reachable address; never discover an IP.

    A NAT operator may listen on a private interface and publish a separately
    mapped public endpoint. A loopback-only listener cannot accept that traffic.
    The contact remains a hint: only a real connection verifies reachability.
    """
    if text is None or text == '':
        return None
    if not isinstance(text, str):
        raise ValueError('Public contact must be a numeric public IPv4:port')
    if not allow_internet:
        raise ValueError('A public contact requires internet connection permission')
    host, port = endpoint(text, allow_zero=False, allow_internet=True)
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        raise ValueError('Public contact must be a numeric public IPv4:port') from None
    if not address.is_global or address.is_multicast:
        raise ValueError('Public contact must be a numeric public IPv4:port')
    listening_host, _ = endpoint(listen, allow_lan=allow_lan,
                                 allow_internet=allow_internet, for_listen=True)
    if ipaddress.ip_address(listening_host).is_loopback:
        raise ValueError('A public contact requires a non-loopback listening address')
    return str(address), port


def atomic_json(path, value):
    path = Path(path)
    reject_wallet_overwrite(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent, prefix=path.name + '.', suffix='.tmp', delete=False) as output:
            temporary = Path(output.name)
            json.dump(value, output, ensure_ascii=False, indent=2)
            output.write('\n')
        for attempt in range(5):
            try:
                reject_wallet_overwrite(path)
                os.replace(temporary, path)
                break
            except PermissionError:
                if attempt == 4:
                    raise
                time.sleep(0.01)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


async def serve(options):
    allow_lan = getattr(options, 'allow_lan', False)
    allow_internet = getattr(options, 'allow_internet', False)
    network = get_network(getattr(options, 'network', None) or ('dora' if allow_internet else 'regtest'))
    host, port = endpoint(options.listen, allow_lan=allow_lan, allow_internet=allow_internet, for_listen=True)
    advertised = public_contact(getattr(options, 'advertise', None), options.listen,
                                allow_lan=allow_lan, allow_internet=allow_internet)
    peers = tuple(endpoint(item, allow_zero=False, allow_lan=allow_lan, allow_internet=allow_internet) for item in options.peer)
    manifest = getattr(options, 'bootstrap_manifest', None)
    scope = getattr(options, 'bootstrap_scope', 'public')
    bootstrap_options = {}
    if allow_internet and (network.name == 'dora' or manifest is not None):
        config = load_bootstrap(network, path=manifest, scope=scope)
        bootstrap_options = {'bootstrap_seeds': config.dns_seeds,
                             'bootstrap_peers': config.fallback_peers,
                             'bootstrap_scope': scope,
                             'discovery_scope': scope}
    from .privacy import load as load_privacy
    privacy_options = load_privacy(options.database.resolve().parent)
    if privacy_options['mode'] == 'i2p':
        peers = [peer for peer in peers if peer[0].endswith('.b32.i2p')]
    from .managed_privacy import ManagedRouter
    connection_limit = options.max_peers
    node = PeerNode(options.database, host=host, port=port, peers=peers, poll_interval=options.poll_interval, timeout=options.timeout, max_peers=connection_limit, outgoing_target=None, allow_lan=allow_lan, allow_internet=allow_internet, network=network, advertised_endpoint=advertised, auto_address=getattr(options, 'auto_address', False), privacy=privacy_options, privacy_router_factory=ManagedRouter, **bootstrap_options)
    current = None
    rpc = None
    try:
        await node.start()
        if getattr(options, 'rpc', False):
            from .rpc import RpcServer, load_or_create_token
            token_path = getattr(options, 'rpc_token_file', None) or options.database.resolve().parent / 'rpc-token'
            rpc = RpcServer(lambda: node, load_or_create_token(token_path),
                            port=getattr(options, 'rpc_port', 18443))
            await rpc.start()
        def status(running):
            value = {**node.info(), 'application_version': __version__, 'pid': os.getpid(), 'running': running, 'listen': {'host': node.address[0], 'port': node.address[1]}, 'database': str(options.database.resolve())}
            value['rpc'] = rpc.info() if rpc is not None else {'enabled': False}
            return value
        current = status(True)
        if options.ready_file:
            atomic_json(options.ready_file, current)
        print(json.dumps(current, ensure_ascii=False), flush=True)
        while options.stop_file is None or not options.stop_file.exists():
            await asyncio.sleep(options.poll_interval)
            if options.ready_file:
                current = status(True)
                atomic_json(options.ready_file, current)
    finally:
        try:
            if options.ready_file and current is not None:
                atomic_json(options.ready_file, {**current, 'running': False})
        except OSError as error:
            print(f'Status publication failed during shutdown: {error}', file=sys.stderr)
        finally:
            try:
                if rpc is not None:
                    await rpc.stop()
            finally:
                await node.stop()


def validate_state_paths(database, ready_file=None, stop_file=None, rpc_token_file=None, bootstrap_manifest=None):
    database = database.resolve()
    reserved = {os.path.normcase(str(database))}
    reserved.add(os.path.normcase(str(database.parent / 'privacy-settings.json')))
    reserved.update(os.path.normcase(str(database) + suffix) for suffix in ('-wal', '-shm', '-journal', '.peers.json', '.peers.json.tmp'))
    if bootstrap_manifest is not None:
        manifest = os.path.normcase(str(bootstrap_manifest.resolve()))
        if manifest in reserved:
            raise ValueError('Bootstrap configuration must differ from the database and its state sidecars')
        reserved.add(manifest)
    auxiliary = [os.path.normcase(str(item.resolve())) for item in (ready_file, stop_file, rpc_token_file) if item is not None]
    if len(set(auxiliary)) != len(auxiliary) or any(item in reserved for item in auxiliary):
        raise ValueError('Ready/stop/token files must differ from the database, its state sidecars and each other')


def main(argv=None):
    parser = argparse.ArgumentParser(description=f'SUMUWW {__version__} manual IPv4 TCP node; internet transport requires opt-in')
    parser.add_argument('--database', type=Path, required=True)
    parser.add_argument('--network', choices=NETWORK_NAMES, default=None, help='DB/profile identity must match; default sumuww with --allow-internet, otherwise regtest')
    parser.add_argument('--listen', default=None, help='Explicit numeric IP listener overrides the automatic binding; port 0 is OS-assigned; default 127.0.0.1:0')
    parser.add_argument('--auto-address', action='store_true', help='Use local OS IP interfaces and the actual listener port; with --allow-internet or --allow-lan default to 0.0.0.0:18444, otherwise 127.0.0.1:0; no NAT/firewall changes or external reachability guarantee')
    parser.add_argument('--advertise', default=None, help='Public IP:port to advertise; requires --allow-internet and a non-loopback listener; configure inbound access separately')
    parser.add_argument('--peer', action='append', default=[], help='Manual IP peer HOST:PORT, or DNS name with --allow-internet; repeatable')
    parser.add_argument('--bootstrap-manifest', type=Path, help='Optional network/genesis-bound DNS seed and fallback address configuration; otherwise use the shipped main-network configuration')
    parser.add_argument('--bootstrap-scope', choices=('public','loopback'), default='public', help='Public by default; loopback is limited to explicit non-main test profiles')
    parser.add_argument('--allow-lan', action='store_true', help='Opt in to RFC1918 TCP and bounded local multicast discovery; permits wildcard listen but no public/DNS outbound, link-local or IPv6 endpoints')
    parser.add_argument('--allow-internet', action='store_true', help='Enable global IPv4/IPv6/DNS peers, configured initial discovery and wildcard listen; includes RFC1918; IPv6 uses [HOST]:PORT')
    parser.add_argument('--ready-file', type=Path, help='Atomically replaced JSON containing PID, port and current node status')
    parser.add_argument('--stop-file', type=Path, help='Stop gracefully when this file appears; must not exist at startup')
    parser.add_argument('--poll-interval', type=float, default=0.5)
    parser.add_argument('--timeout', type=float, default=5)
    parser.add_argument('--max-peers', type=int, default=None, help='Optional explicit peer limit; default: no count limit')
    parser.add_argument('--rpc', action='store_true', help='Enable authenticated local JSON-RPC and HTTP API on 127.0.0.1')
    parser.add_argument('--rpc-port', type=int, default=18443, help='Local API port; 0 selects an available port')
    parser.add_argument('--rpc-token-file', type=Path, help='Private Bearer token file; default is rpc-token beside the database; created only with --rpc')
    args = parser.parse_args(argv)
    if args.network == 'sumuww':
        args.network = 'dora'
    try:
        if args.listen is None:
            args.listen = f'0.0.0.0:{DEFAULT_PORT}' if args.auto_address and (args.allow_internet or args.allow_lan) else '127.0.0.1:0'
        if args.network is None:
            args.network = 'dora' if args.allow_internet else 'regtest'
        get_network(args.network)
        if args.network == 'dora' and args.bootstrap_scope != 'public':
            raise ValueError('The main network requires public bootstrap scope')
        if not args.allow_internet and args.bootstrap_manifest is not None:
            raise ValueError('Initial DNS discovery requires internet connection permission')
        endpoint(args.listen, allow_lan=args.allow_lan, allow_internet=args.allow_internet, for_listen=True)
        public_contact(args.advertise, args.listen, allow_lan=args.allow_lan,
                       allow_internet=args.allow_internet)
        for item in args.peer:
            endpoint(item, allow_zero=False, allow_lan=args.allow_lan, allow_internet=args.allow_internet)
        if not 0.1 <= args.poll_interval <= 5 or not 0.5 <= args.timeout <= 30:
            raise ValueError('Use poll interval 0.1..5 and timeout 0.5..30 seconds')
        if args.stop_file is not None and args.stop_file.exists():
            raise ValueError('Stop file already exists; choose a new stop-file path')
        if args.rpc:
            from .rpc import validate_rpc_endpoint
            validate_rpc_endpoint('127.0.0.1', args.rpc_port)
            if args.rpc_token_file is None:
                args.rpc_token_file = args.database.resolve().parent / 'rpc-token'
        elif args.rpc_token_file is not None or args.rpc_port != 18443:
            raise ValueError('RPC port/token options require --rpc')
        validate_state_paths(args.database, args.ready_file, args.stop_file,
                             args.rpc_token_file if args.rpc else None,
                             args.bootstrap_manifest)
        asyncio.run(serve(args))
        return 0
    except KeyboardInterrupt:
        return 0
    except (ValueError, OSError, RuntimeError) as exc:
        print(json.dumps({'error': type(exc).__name__, 'message': str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
