"""App-owned optional privacy routers. Direct mode never starts a router.

Only pinned, packaged binaries are used; no runtime download or system service
is installed. Routers bind their application proxies to loopback only.
"""
import asyncio
import ctypes
import hashlib
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import tempfile
from .wallet_paths import reject_wallet_overwrite

_android_paths = None


def install_android_paths(provider):
    global _android_paths
    _android_paths = provider


def _asset_root():
    return Path(__file__).resolve().parents[1] / 'assets' / 'privacy'


def _free_port():
    with socket.socket() as owned:
        owned.bind(('127.0.0.1', 0))
        return owned.getsockname()[1]


class _AndroidChild:
    def __init__(self, command):
        self.lib = ctypes.CDLL('libsumuww_platform.so', use_errno=True)
        spawn = self.lib.sumuww_router_spawn
        spawn.argtypes = [ctypes.c_char_p, ctypes.POINTER(ctypes.c_char_p)]
        spawn.restype = ctypes.c_int
        args = (ctypes.c_char_p * (len(command)+1))(*[os.fsencode(x) for x in command], None)
        self.pid = spawn(os.fsencode(command[0]), args)
        if self.pid <= 0:
            raise OSError('Could not start the packaged privacy router')
        self.returncode = None

    def poll(self):
        if self.returncode is None:
            pid, status = os.waitpid(self.pid, os.WNOHANG)
            if pid:
                self.returncode = os.waitstatus_to_exitcode(status)
        return self.returncode

    def terminate(self):
        if self.poll() is None:
            os.kill(self.pid, signal.SIGTERM)

    def kill(self):
        if self.poll() is None:
            os.kill(self.pid, signal.SIGKILL)


class _WindowsJob:
    """Close only the owned router if its parent process exits unexpectedly."""
    def __init__(self, child):
        from ctypes import wintypes as W
        class Limits(ctypes.Structure):
            _fields_ = [('process_time', ctypes.c_longlong), ('job_time', ctypes.c_longlong),
                        ('flags', W.DWORD), ('minimum', ctypes.c_size_t), ('maximum', ctypes.c_size_t),
                        ('active', W.DWORD), ('affinity', ctypes.c_size_t), ('priority', W.DWORD), ('scheduling', W.DWORD)]
        class Extended(ctypes.Structure):
            _fields_ = [('basic', Limits), ('io', ctypes.c_ulonglong*6),
                        ('process_memory', ctypes.c_size_t), ('job_memory', ctypes.c_size_t),
                        ('peak_process', ctypes.c_size_t), ('peak_job', ctypes.c_size_t)]
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel.CreateJobObjectW.argtypes = [ctypes.c_void_p, W.LPCWSTR]
        kernel.CreateJobObjectW.restype = W.HANDLE
        kernel.SetInformationJobObject.argtypes = [W.HANDLE, ctypes.c_int, ctypes.c_void_p, W.DWORD]
        kernel.AssignProcessToJobObject.argtypes = [W.HANDLE, W.HANDLE]
        kernel.CloseHandle.argtypes = [W.HANDLE]
        self.kernel, self.handle = kernel, kernel.CreateJobObjectW(None, None)
        limits = Extended(); limits.basic.flags = 0x2000
        if (not self.handle or not kernel.SetInformationJobObject(self.handle, 9, ctypes.byref(limits), ctypes.sizeof(limits))
                or not kernel.AssignProcessToJobObject(self.handle, int(child._handle))):
            self.close()
            raise OSError('Could not own the privacy router process')

    def close(self):
        if self.handle:
            self.kernel.CloseHandle(self.handle)
            self.handle = None


class ManagedRouter:
    def __init__(self, mode, directory):
        if mode not in ('tor', 'i2p'):
            raise ValueError('A managed router requires Tor or I2P')
        self.mode = mode
        self.root = Path(directory).resolve()
        self.directory = self.root / 'privacy' / mode
        self.process = self.job = None
        self.port = None
        self.version = None
        self._lock = asyncio.Lock()

    def info(self):
        return {'embedded': True, 'running': self.process is not None and self.process.poll() is None,
                'version': self.version}

    def _binary(self):
        root = _asset_root()
        android = _android_paths() if _android_paths is not None else None
        platform = 'android' if android else 'windows' if sys.platform == 'win32' else None
        if platform is None:
            raise OSError('No packaged privacy router for this platform')
        manifest = json.loads((root / platform / 'manifest.json').read_text(encoding='utf-8'))
        item = manifest[self.mode]
        if android:
            item = {**item, **item['architectures'][android['abi']]}
            binary = Path(android['library_directory']) / item['file']
        else:
            binary = root / platform / item['file']
            if not binary.resolve().is_relative_to((root / platform).resolve()):
                raise OSError('Invalid packaged router path')
        if not binary.is_file():
            raise OSError('Packaged privacy router is missing')
        with binary.open('rb') as stream:
            if hashlib.file_digest(stream, 'sha256').hexdigest() != item['sha256']:
                raise OSError('Packaged privacy router checksum mismatch')
        self.version = item['version']
        return str(binary), item['kind']

    def _ensure_directory(self, directory):
        self.root.mkdir(parents=True, exist_ok=True)
        current = self.root
        for part in Path(directory).relative_to(self.root).parts:
            current = current / part
            if current.is_symlink() or getattr(current, 'is_junction', lambda: False)():
                raise OSError('Privacy runtime directories must not redirect to other paths')
            current.mkdir(exist_ok=True)

    def _write(self, path, data):
        """Publish only owned settings/certificates, preserving existing wallets."""
        self._ensure_directory(path.parent)
        temporary = None
        try:
            if path.is_symlink():
                raise OSError('Privacy runtime files must not be symbolic links')
            reject_wallet_overwrite(path)
            with tempfile.NamedTemporaryFile('wb', dir=path.parent, prefix='.'+path.name+'.', delete=False) as stream:
                temporary = Path(stream.name)
                stream.write(data); stream.flush(); os.fsync(stream.fileno())
            if path.is_symlink():
                raise OSError('Privacy runtime files must not be symbolic links')
            reject_wallet_overwrite(path)
            os.replace(temporary, path)
        finally:
            if temporary is not None and temporary.exists():
                temporary.unlink()

    def _command(self, binary, kind):
        self._ensure_directory(self.directory)
        self.port = _free_port()
        if self.mode == 'tor' and kind == 'arti':
            # Native TLS on Windows uses the OS trust store; no public listener.
            config = self.directory / 'arti.toml'
            path = lambda p: json.dumps(str(p).replace('\\', '/'))
            self._ensure_directory(self.directory/'cache')
            self._ensure_directory(self.directory/'state')
            self._write(config, ('[storage]\ncache_dir = '+path(self.directory/'cache')+
                '\nstate_dir = '+path(self.directory/'state')+'\n').encode('utf-8'))
            return [binary, '-c', str(config), 'proxy', '-p', str(self.port)]
        if self.mode == 'tor':
            config = self.directory / 'torrc'
            self._ensure_directory(self.directory/'data')
            self._write(config, ('SocksPort 127.0.0.1:'+str(self.port)+'\nDataDirectory '+
                json.dumps(str(self.directory/'data').replace('\\', '/'))+
                '\nClientOnly 1\nAvoidDiskWrites 1\nLog err stdout\n').encode('utf-8'))
            return [binary, '-f', str(config)]
        # An endpoint client does not volunteer as an unrestricted transit router.
        # Signed reseed certificates are packaged for initial I2P discovery.
        certificates = _asset_root() / 'i2p-certificates'
        for certificate in certificates.rglob('*'):
            if certificate.is_file():
                self._write(self.directory/'certificates'/certificate.relative_to(certificates), certificate.read_bytes())
        config = self.directory / 'i2pd.conf'
        self._write(config, ('daemon = false\nloglevel = error\nnotransit = true\n'
            '[http]\nenabled = false\n[httpproxy]\nenabled = false\n'
            '[socksproxy]\nenabled = false\n[sam]\nenabled = true\naddress = 127.0.0.1\nport = '+str(self.port)+
            '\n[bob]\nenabled = false\n[i2cp]\nenabled = false\n[upnp]\nenabled = false\n').encode('utf-8'))
        return [binary, '--datadir='+str(self.directory), '--conf='+str(config)]

    async def ensure_running(self):
        async with self._lock:
            if self.process is not None and self.process.poll() is None:
                return self.port
            await self._stop()
            binary, kind = self._binary()
            command = self._command(binary, kind)
            try:
                if _android_paths is not None:
                    self.process = _AndroidChild(command)
                else:
                    self.process = subprocess.Popen(command, stdin=subprocess.DEVNULL,
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                        creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0)
                    if sys.platform == 'win32':
                        self.job = _WindowsJob(self.process)
                deadline = asyncio.get_running_loop().time()+15
                while self.process.poll() is None:
                    try:
                        reader, writer = await asyncio.wait_for(asyncio.open_connection('127.0.0.1', self.port), .5)
                        writer.close(); await writer.wait_closed()
                        return self.port
                    except (OSError, TimeoutError):
                        if asyncio.get_running_loop().time() >= deadline:
                            break
                        await asyncio.sleep(.1)
                raise OSError('Embedded privacy router did not start; no direct fallback')
            except BaseException:
                await self._stop()
                raise

    async def _stop(self):
        process, self.process = self.process, None
        try:
            if process is not None and process.poll() is None:
                process.terminate()
                deadline = asyncio.get_running_loop().time()+5
                while process.poll() is None and asyncio.get_running_loop().time() < deadline:
                    await asyncio.sleep(.05)
                if process.poll() is None:
                    process.kill()
                    for _ in range(40):
                        if process.poll() is not None:
                            break
                        await asyncio.sleep(.05)
        finally:
            if self.job is not None:
                self.job.close(); self.job = None

    async def stop(self):
        async with self._lock:
            await self._stop()
