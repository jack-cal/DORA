from . import __version__
"""Loopback desktop UI for signed orders and disposable cross-chain checks."""
import argparse, hashlib, json, os, secrets, sys, threading, time
from pathlib import Path
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from .orders import Store
from .network import Relay, decode
from .trades import TradeBook
from .instance import DirectoryLock, AlreadyRunning
from .vault import Vault
from .wallet_link import WalletLinks

class Application:

    def __init__(self, root, data):
        self.data_lock = DirectoryLock(data)
        try:
            self._initialize(root, data)
        except BaseException:
            self.data_lock.close()
            raise

    def _initialize(self, root, data):
        self.root = Path(root)
        self.store = Store(data)
        self.trades = TradeBook(self.store)
        self.trades.mark_interrupted()
        self.relay = Relay(self.store).start()
        self.vault = Vault(self.store.directory / 'wallet-regtest.vault')
        self.wallet_links = WalletLinks(self.store.directory)
        self.peer_swap = None
        swap_config = self.store.directory / 'swap-nodes.json'
        if swap_config.exists():
            self._swap_configure(json.loads(swap_config.read_text()), save=False)
        self.token = secrets.token_hex(32)
        self.job_lock = threading.Lock()
        self.job = {'running': False}
        self.cancel_event = threading.Event()
        self.worker_thread = None
        self.closing = False
        history = self.store.history()
        if history:
            last = history[-1]
            self.job = {'running': False, 'mode': last['evidence'].get('mode'), 'state': last['state'], 'passed': last['evidence'].get('passed', False)}
            if self.job['passed']:
                self.job['result'] = last['evidence']
            else:
                self.job['error'] = 'The previous check was interrupted. Saved test records were retained.'

    def state(self):
        with self.relay.lock:
            peers = list(self.relay.peers)
        with self.job_lock:
            job = dict(self.job)
        return {'version': __version__, 'network': 'regtest-only', 'public_trading': False, 'public_htlc_activation_height': 9100, 'identity': self.store.identity.public, 'relay_port': self.relay.address[1], 'orders': self.store.listing(), 'history': self.store.history(), 'wallet': self.vault.state(), 'wallet_links': self.wallet_links.state(), 'independent_swaps': self.peer_swap.listing() if self.peer_swap else [], 'swap_configured': self.peer_swap is not None, 'relay_host': self.relay.address[0], 'trades': self.trades.listing(), 'peers': [{'host': p[0], 'port': p[1]} for p in peers], 'job': job}

    def _swap_configure(self, config, save=True):
        from .peer_swap import PeerSwap
        candidate = PeerSwap(self.store, self.vault, config)
        if save:
            for node in candidate.nodes.values():
                node.info()
        if self.peer_swap and self.peer_swap.listing():
            raise ValueError('Node settings cannot change after a swap is prepared.')
        if save:
            from .orders import canonical
            from .vault import _write_new
            path = self.store.directory / 'swap-nodes.json'
            temp = path.with_name('swap-nodes.' + secrets.token_hex(8) + '.tmp')
            try:
                _write_new(temp, canonical(config))
                temp.replace(path)
            finally:
                temp.unlink(missing_ok=True)
        self.peer_swap = candidate
        self.relay.swap_handler = candidate.receive
        return {'configured': True, 'network': 'regtest-only'}

    def command(self, name, body):
        if self.closing:
            raise ValueError('The application is closing.')
        if name == 'wallet_link':
            return self.wallet_links.configure(**body)
        if name == 'wallet_refresh':
            return self.wallet_links.refresh(body['coin'])
        if name == 'swap_configure':
            return self._swap_configure(body)
        if name.startswith('peer_'):
            if self.peer_swap is None:
                raise ValueError('Connect the local nodes for the two-party test swap first.')
            session = body['session']
            if name == 'peer_sync':
                terms = self.trades.terms(session)
                other = terms['taker'] if terms['maker'] == self.store.identity.public else terms['maker']
                with self.relay.lock:
                    peer = self.relay.routes.get(other)
                if not peer:
                    raise ValueError('Connect to the peer order node first.')
                self.relay.sync_swap(peer, self.peer_swap.snapshot(session))
                return self.peer_swap.status(session)
            action = {'peer_prepare': 'prepare', 'peer_fund': 'fund', 'peer_claim': 'claim', 'peer_refund': 'refund', 'peer_status': 'status'}.get(name)
            if not action:
                raise ValueError('Unknown swap operation.')
            result = getattr(self.peer_swap, action)(session)
            return self.peer_swap.status(session) if action == 'prepare' else result
        if name == 'listen':
            replacement = Relay(self.store, body['host'], int(body['port'])).start()
            replacement.swap_handler = self.peer_swap.receive if self.peer_swap else None
            old = self.relay
            self.relay = replacement
            old.close()
            return {'host': self.relay.address[0], 'port': self.relay.address[1]}
        if name == 'wallet_create':
            return self.vault.create(body['password'])
        if name == 'wallet_unlock':
            return self.vault.unlock(body['password'])
        if name == 'wallet_lock':
            self.vault.lock()
            return {'locked': True}
        if name == 'wallet_backup':
            return self.vault.backup(body['path'])
        if name == 'wallet_restore':
            return self.vault.restore(body['path'], body['password'])
        if name == 'order':
            p = self.store.create(body['side'], body['smw'], body['btc'])
            return {'order': p, 'delivery': self.relay.publish(p)}
        if name == 'cancel':
            p = self.store.cancel(body['id'])
            return {'delivery': self.relay.publish(p)}
        if name == 'connect':
            return {'orders': self.relay.connect(body.get('host', '127.0.0.1'), int(body['port']))}
        if name == 'sync':
            with self.relay.lock:
                peers = list(self.relay.peers)
            result = []
            for p in peers:
                try:
                    result.append({'port': p[1], 'ok': True, 'orders': self.relay.connect(*p)})
                except (OSError, ValueError):
                    result.append({'port': p[1], 'ok': False})
            return {'peers': result}
        if name == 'reserve':
            row = next((o for o in self.store.listing() if o['id'] == body['id']), None)
            if not row:
                raise ValueError('Order not found.')
            with self.relay.lock:
                endpoint = self.relay.routes.get(row['maker'])
            if not endpoint:
                raise ValueError('Connect to the order maker first.')
            return {'confirmation': self.relay.accept(endpoint, body['id'])}
        if name in ('check', 'execute'):
            mode = body.get('mode')
            if mode not in ('success', 'refund'):
                raise ValueError('Invalid test item.')
            if name == 'execute' and set(body) != {'mode', 'session'}:
                raise ValueError('Only the reservation identifier and test type may be specified.')
            tool = self.root / 'tools/bitcoin-31.1/bin/bitcoind.exe'
            if not tool.exists():
                raise ValueError('Bitcoin Core test tools are missing. Run prepare.py.')
            manifest = json.loads((self.root / 'tools/runtime-manifest.json').read_text())
            if hashlib.sha256(tool.read_bytes()).hexdigest() != manifest['bitcoind.exe']:
                raise ValueError('Bitcoin Core test-tool checksum mismatch.')
            with self.job_lock:
                if self.job.get('running'):
                    raise ValueError('A test is already running.')
                material = self.vault.signing_material() if name == 'execute' and self.vault.state()['exists'] else None
                if name == 'execute' and self.peer_swap and any((t['session'] == body['session'] for t in self.peer_swap.listing())):
                    raise ValueError('This reservation is prepared for a two-party swap and cannot be used for a disposable check.')
                terms = self.trades.start(body['session'], mode) if name == 'execute' else None
                self.job = {'running': True, 'mode': mode, 'state': 'STARTING', 'session': terms['session'] if terms else None}

            def worker():
                from .settlement import run_round
                session = terms['session'] if terms else str(time.time_ns())

                def progress(state):
                    if not terms:
                        self.store.checkpoint(session, state, {'mode': mode})
                    with self.job_lock:
                        self.job['state'] = state

                def detail(state, evidence):
                    if terms:
                        phase = 'FINALIZING' if state in ('COMPLETED', 'REFUNDED') else state
                        self.trades.update(session, phase, evidence)
                        self.store.checkpoint(session, phase, evidence)
                try:
                    self.store.checkpoint(session, 'STARTING', {'mode': mode, **(terms or {})})
                    folder = self.store.directory / ('trades' if terms else 'checks') / session
                    kwargs = {'smw_atoms': terms['smw_atoms'], 'btc_sats': terms['btc_sats'], 'binding': terms, 'detail': detail} if terms else {}
                    if material is not None:
                        kwargs['wallet_material'] = material
                    result = run_round(folder, tool, mode=mode, progress=progress, cancel=self.cancel_event, **kwargs)
                    final = 'COMPLETED' if mode == 'success' else 'REFUNDED'
                    if terms:
                        self.trades.update(session, final, result)
                    self.store.checkpoint(session, final, result)
                    with self.job_lock:
                        self.job = {'running': False, 'mode': mode, 'passed': True, 'result': result, 'session': session}
                except Exception as exc:
                    failure = {'mode': mode, 'error': str(exc), 'passed': False, **(terms or {})}
                    final = 'INTERRUPTED' if self.cancel_event.is_set() else 'FAILED'
                    try:
                        if terms:
                            existing = next((t for t in self.trades.listing() if t['session'] == session))
                            failure = {**existing['evidence'], **failure}
                            if existing['state'] not in ('COMPLETED', 'REFUNDED', 'FAILED', 'INTERRUPTED'):
                                self.trades.update(session, final, failure)
                        self.store.checkpoint(session, final, failure)
                    except Exception as write_error:
                        failure['journal_error'] = str(write_error)
                    with self.job_lock:
                        self.job = {'running': False, 'mode': mode, 'passed': False, 'error': str(exc), 'session': session}
                finally:
                    if 'kwargs' in locals():
                        kwargs.clear()
            self.worker_thread = threading.Thread(target=worker, daemon=True)
            self.worker_thread.start()
            return {'started': True}
        raise ValueError('Unknown request.')

    def close(self):
        if self.closing:
            return
        self.closing = True
        self.cancel_event.set()
        if self.worker_thread and self.worker_thread is not threading.current_thread():
            self.worker_thread.join(45)
        try:
            self.relay.close()
        finally:
            self.vault.lock()
            self.data_lock.close()

def serve(root, data, port=0):
    app = Application(root, data)

    class Handler(BaseHTTPRequestHandler):

        def log_message(self, *_):
            pass

        def reply(self, status, body, content_type='application/json; charset=utf-8'):
            raw = body if isinstance(body, bytes) else json.dumps(body, ensure_ascii=False).encode()
            self.send_response(status)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(raw)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
            self.end_headers()
            self.wfile.write(raw)

        def valid_host(self):
            return self.headers.get('Host') == f'127.0.0.1:{self.server.server_port}'

        def do_GET(self):
            if not self.valid_host():
                return self.reply(403, {'error': 'Local host required'})
            if self.path == '/':
                raw = (app.root / 'web/index.html').read_text(encoding='utf-8').replace('{{TOKEN}}', app.token).encode()
                return self.reply(200, raw, 'text/html; charset=utf-8')
            if self.path in ('/style.css', '/app.js'):
                kind = 'text/css' if self.path.endswith('.css') else 'text/javascript'
                return self.reply(200, (app.root / 'web' / self.path[1:]).read_bytes(), kind + '; charset=utf-8')
            if self.path == '/api/state' and secrets.compare_digest(self.headers.get('X-App-Token', ''), app.token):
                return self.reply(200, app.state())
            return self.reply(404, {'error': 'Not found'})

        def do_POST(self):
            expected = f'http://127.0.0.1:{self.server.server_port}'
            if not self.valid_host() or self.headers.get('Origin') != expected or (not secrets.compare_digest(self.headers.get('X-App-Token', ''), app.token)):
                return self.reply(403, {'error': 'Local authenticated request required'})
            try:
                length = int(self.headers.get('Content-Length', '0'))
                if not 0 < length <= 8192:
                    raise ValueError('Invalid request size')
                self.connection.settimeout(5)
                body = decode(self.rfile.read(length))
                if not isinstance(body, dict):
                    raise ValueError('Expected object')
                if self.path.startswith(('/api/wallet_', '/api/peer_', '/api/swap_', '/api/listen')):
                    return self.reply(403, {'error': 'Wallet and independent swap actions are native UI only'})
                result = app.command(self.path.removeprefix('/api/'), body)
                return self.reply(200, result)
            except (ValueError, KeyError, TypeError, OSError) as exc:
                return self.reply(400, {'error': str(exc)})
    server = ThreadingHTTPServer(('127.0.0.1', port), Handler)
    server.daemon_threads = True
    return (app, server)

def default_data_directory():
    local = os.environ.get('LOCALAPPDATA')
    return (Path(local) if local else Path.home() / '.local/share') / 'SUMUWW/P2P'

def main(root,flavor='full'):
    parser = argparse.ArgumentParser(description='SUMUWW P2P native Windows development application')
    parser.add_argument('--data-dir', type=Path)
    parser.add_argument('--legacy-lab', action='store_true', help='Open the previous disposable BTC test laboratory')
    parser.add_argument('--test-market', action='store_true', help='Use a separate test-only trading board and wallet')
    parser.add_argument('--market-self-check', action='store_true', help='Offline native UI and signed-peer check in a new directory')
    parser.add_argument('--wallet-self-check', action='store_true', help='Disposable regtest check; requires a new --data-dir')
    parser.add_argument('--peer-self-check', action='store_true', help='Two independent regtest participants; requires a new --data-dir')
    args = parser.parse_args()
    if args.market_self_check:
        if args.data_dir is None:parser.error('--market-self-check requires a new --data-dir')
        from .market.self_check import run
        run(root,args.data_dir,flavor=flavor)
        return
    if args.peer_self_check:
        if args.wallet_self_check or args.data_dir is None:
            parser.error('--peer-self-check requires its own new --data-dir')
        from .peer_check import run
        result = run(root, args.data_dir)
        raise SystemExit(0 if result['passed'] else 1)
    if args.wallet_self_check:
        if args.data_dir is None:
            parser.error('--wallet-self-check requires an explicit new --data-dir')
        from .wallet_check import run
        result = run(root, args.data_dir)
        raise SystemExit(0 if result['passed'] else 1)
    if not args.legacy_lab:
        from .market.application import MarketApplication
        from .market.desktop import MarketDesktop
        network='test' if args.test_market else 'mainnet'
        profile=('Market-Light' if flavor=='light' else 'Market')+('-Test' if args.test_market else '')
        directory=args.data_dir or default_data_directory()/profile
        try:app=MarketApplication(root,directory,network,flavor=flavor)
        except AlreadyRunning as exc:
            import tkinter as tk
            from tkinter import messagebox
            window=tk.Tk();window.withdraw()
            messagebox.showinfo('SUMUWW P2P',str(exc),parent=window);window.destroy();return
        MarketDesktop(app).run()
        return
    args.data_dir = args.data_dir or default_data_directory()
    from .desktop import Desktop
    try:
        app = Application(root, args.data_dir)
    except AlreadyRunning as exc:
        import tkinter as tk
        from tkinter import messagebox
        window = tk.Tk()
        window.withdraw()
        messagebox.showinfo('SUMUWW P2P', str(exc), parent=window)
        window.destroy()
        return
    Desktop(app).run()
