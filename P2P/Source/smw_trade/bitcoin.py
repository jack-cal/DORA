"""Owned Bitcoin Core regtest process, cookie RPC, no public-chain mode."""
from pathlib import Path
import base64, json, os, socket, subprocess, time
from urllib.request import Request, urlopen, ProxyHandler, build_opener
from urllib.error import HTTPError

class Bitcoin:

    def __init__(self, executable, directory, cancel=None):
        self.executable = Path(executable).resolve()
        self.directory = Path(directory).resolve()
        self.directory.mkdir(parents=True, exist_ok=True)
        with socket.socket() as s:
            s.bind(('127.0.0.1', 0))
            self.port = s.getsockname()[1]
        self.cookie = self.directory / 'regtest/.cookie'
        self.opener = build_opener(ProxyHandler({}))
        self.log = (self.directory / 'process.log').open('wb')
        self.process = None
        self.cancel = cancel

    def start(self):
        self.process = subprocess.Popen([str(self.executable), '-regtest', '-server=1', '-listen=0', '-discover=0', '-dnsseed=0', '-connect=0', '-txindex=1', f'-datadir={self.directory}', f'-rpcport={self.port}', '-rpcbind=127.0.0.1', '-rpcallowip=127.0.0.1', '-fallbackfee=0.0002'], stdout=self.log, stderr=subprocess.STDOUT, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            if self.cancel is not None and self.cancel.is_set():
                self.close()
                raise RuntimeError('The test was interrupted by a shutdown request.')
            if self.process.poll() is not None:
                raise RuntimeError('Owned Bitcoin regtest node failed; inspect process.log')
            try:
                info = self.rpc('getblockchaininfo')
                if info['chain'] != 'regtest':
                    raise RuntimeError('Unexpected Bitcoin chain')
                wallets = self.rpc('listwallets')
                if 'exchange-test' not in wallets:
                    existing = self.rpc('listwalletdir')['wallets']
                    if any((w['name'] == 'exchange-test' for w in existing)):
                        self.rpc('loadwallet', 'exchange-test')
                    else:
                        self.rpc('createwallet', 'exchange-test')
                return self
            except (OSError, ValueError, RuntimeError):
                time.sleep(0.1)
        self.close()
        raise RuntimeError('Bitcoin regtest startup deadline')

    def rpc(self, method, *args):
        token = self.cookie.read_text().strip()
        req = Request(f'http://127.0.0.1:{self.port}/', data=json.dumps({'jsonrpc': '2.0', 'id': 1, 'method': method, 'params': args}).encode(), headers={'Authorization': 'Basic ' + base64.b64encode(token.encode()).decode(), 'Content-Type': 'application/json'})
        try:
            with self.opener.open(req, timeout=30) as r:
                body = json.load(r)
        except HTTPError as exc:
            body = json.load(exc)
        if body.get('error'):
            raise ValueError(str(body['error']))
        return body['result']

    def mine(self, count=1):
        return self.rpc('generatetoaddress', count, self.rpc('getnewaddress', '', 'bech32'))

    def restart(self):
        executable, directory, cancel = (self.executable, self.directory, self.cancel)
        self.close()
        self.__init__(executable, directory, cancel=cancel)
        self.start()

    def close(self):
        if self.process and self.process.poll() is None:
            try:
                self.rpc('stop')
                self.process.wait(timeout=15)
            except Exception:
                self.process.terminate()
                try:
                    self.process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self.process.kill()
                    self.process.wait(timeout=5)
        self.log.close()

    def __enter__(self):
        return self.start()

    def __exit__(self, *_):
        self.close()
