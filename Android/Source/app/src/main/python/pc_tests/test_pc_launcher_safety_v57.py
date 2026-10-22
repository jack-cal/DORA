"""Windows launcher and optional firewall-record safety using owned fixtures.

Only the helper's parsed record-writing function is executed. The helper's
firewall commands and elevation code are never invoked by these tests.
"""

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

from sumuww.keystore import create_hd_wallet, create_wallet, load_wallet
from sumuww.profiles import REGTEST


SOURCE = Path(__file__).resolve().parents[1]
PASSWORD = 'owned-firewall-record-fixture-password'
POWERSHELL = shutil.which('powershell.exe') if os.name == 'nt' else None
NO_WINDOW = getattr(subprocess, 'CREATE_NO_WINDOW', 0)


@unittest.skipUnless(POWERSHELL, 'Windows PowerShell is required')
class PublicFirewallRecordTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='sumuww-firewall-record-')
        self.addCleanup(self.temporary.cleanup)
        self.folder = Path(self.temporary.name)
        self.record = self.folder / 'profile' / 'SUMUWW' / 'public-firewall.json'
        self.record.parent.mkdir(parents=True)

    def save_record(self, *, after_absence_check=None):
        # Extract just this function from the real script with the PowerShell
        # parser. Never dot-source or invoke the full administrative helper.
        command = r'''
$ErrorActionPreference = 'Stop'
$tokens = $null
$parseErrors = $null
$ast = [Management.Automation.Language.Parser]::ParseFile($env:SUMUWW_HELPER_FIXTURE, [ref]$tokens, [ref]$parseErrors)
if ($parseErrors.Count -ne 0) { throw 'Firewall helper has parse errors' }
$functions = @($ast.FindAll({ param($item) $item -is [Management.Automation.Language.FunctionDefinitionAst] -and $item.Name -eq 'Save-SumuwwFirewallRecord' }, $false))
if ($functions.Count -ne 1) { throw 'Expected one record-writing function' }
Invoke-Expression $functions[0].Extent.Text
$record = Join-Path $env:LOCALAPPDATA 'SUMUWW\public-firewall.json'
if ($env:SUMUWW_APPEARING_WALLET_FIXTURE) {
    if ([IO.File]::Exists($record)) { throw 'Race fixture should start absent' }
    [IO.File]::Copy($env:SUMUWW_APPEARING_WALLET_FIXTURE, $record, $false)
}
Save-SumuwwFirewallRecord -Path $record -RuleName 'SUMUWW-P2P-TCP-18444'
'''
        environment = dict(os.environ, LOCALAPPDATA=str(self.record.parent.parent),
                           SUMUWW_HELPER_FIXTURE=str(SOURCE / 'tools' / 'allow-public-connections.ps1'),
                           SUMUWW_APPEARING_WALLET_FIXTURE=str(after_absence_check or ''))
        result = subprocess.run([POWERSHELL, '-NoProfile', '-NonInteractive', '-Command', command],
                                env=environment, capture_output=True, text=True,
                                timeout=15, creationflags=NO_WINDOW)
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)

    def test_record_is_created_once_and_repeated_execution_preserves_it(self):
        self.save_record()
        original = self.record.read_bytes()
        record = json.loads(original)
        self.assertEqual('SUMUWW-P2P-TCP-18444', record['rule'])
        self.assertEqual(18444, record['tcp_port'])
        self.assertTrue(record['enabled_at'])
        self.save_record()
        self.assertEqual(original, self.record.read_bytes())

    def test_legacy_single_key_and_hd_wallets_remain_encrypted_and_loadable(self):
        for create in (create_wallet, create_hd_wallet):
            with self.subTest(format=create.__name__):
                self.record.unlink(missing_ok=True)
                key = create(self.record, PASSWORD, network=REGTEST)
                original = self.record.read_bytes()
                self.save_record()
                self.assertEqual(original, self.record.read_bytes())
                self.assertEqual(key.address, load_wallet(self.record, PASSWORD, network=REGTEST).address)

    def test_hardlinked_wallet_and_its_record_alias_are_preserved(self):
        wallet = self.folder / 'owned-wallet.json'
        key = create_wallet(wallet, PASSWORD, network=REGTEST)
        original = wallet.read_bytes()
        os.link(wallet, self.record)
        self.save_record()
        self.assertEqual(original, self.record.read_bytes())
        self.assertEqual(original, wallet.read_bytes())
        self.assertTrue(os.path.samefile(wallet, self.record))
        self.assertEqual(key.address, load_wallet(wallet, PASSWORD, network=REGTEST).address)

    def symlink_record(self, target):
        try:
            self.record.symlink_to(target)
        except OSError as error:
            if os.name == 'nt' and error.winerror == 1314:
                self.skipTest('Windows symbolic-link privilege is unavailable')
            raise

    def test_symbolic_wallet_link_is_not_followed_or_replaced(self):
        wallet = self.folder / 'owned-wallet.json'
        create_hd_wallet(wallet, PASSWORD, network=REGTEST)
        original = wallet.read_bytes()
        self.symlink_record(wallet)
        self.save_record()
        self.assertTrue(self.record.is_symlink())
        self.assertEqual(original, wallet.read_bytes())
        self.assertEqual(original, self.record.read_bytes())

    def test_dangling_symbolic_link_is_preserved_without_creating_its_target(self):
        wallet = self.folder / 'not-yet-created-wallet.json'
        self.symlink_record(wallet)
        self.save_record()
        self.assertTrue(self.record.is_symlink())
        self.assertFalse(wallet.exists())

    def test_unrecognized_or_empty_existing_files_are_preserved_without_truncation(self):
        for original in (b'', b'{malformed', b'{}', b'opaque-owned-file' * 400):
            with self.subTest(length=len(original)):
                self.record.write_bytes(original)
                self.save_record()
                self.assertEqual(original, self.record.read_bytes())

    def test_wallet_appearing_after_an_absence_check_is_preserved(self):
        wallet = self.folder / 'owned-wallet.json'
        key = create_wallet(wallet, PASSWORD, network=REGTEST)
        original = wallet.read_bytes()
        self.assertFalse(self.record.exists())
        self.save_record(after_absence_check=wallet)
        self.assertEqual(original, self.record.read_bytes())
        self.assertEqual(key.address, load_wallet(self.record, PASSWORD, network=REGTEST).address)


@unittest.skipUnless(POWERSHELL, 'Windows PowerShell is required')
class WindowsRpcLauncherTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory(prefix='sumuww-rpc-launcher-')
        cls.addClassCleanup(cls.temporary.cleanup)
        cls.folder = Path(cls.temporary.name)
        cls.executable = cls.folder / 'owned-node-stub.exe'
        # A real executable fixture records its arguments and exit status.
        # It cannot access node profiles or open network listeners.
        command = r'''
$ErrorActionPreference = 'Stop'
Add-Type -TypeDefinition @'
public static class OwnedNodeFixture {
    public static int Main(string[] args) {
        foreach (string argument in args) System.Console.WriteLine(argument);
        return 37;
    }
}
'@ -OutputAssembly $env:SUMUWW_STUB_FIXTURE -OutputType ConsoleApplication
'''
        result = subprocess.run([POWERSHELL, '-NoProfile', '-NonInteractive', '-Command', command],
                                env=dict(os.environ, SUMUWW_STUB_FIXTURE=str(cls.executable)),
                                capture_output=True, text=True, timeout=30, creationflags=NO_WINDOW)
        if result.returncode:
            raise AssertionError(result.stdout + result.stderr)

    def run_wrapper(self, wrapper, *arguments, python=None):
        environment = dict(os.environ, SUMUWW_PYTHON=str(python or self.folder / 'unavailable-python.exe'),
                           LOCALAPPDATA=str(self.folder / 'isolated-profile'),
                           PYTHONDONTWRITEBYTECODE='1')
        return subprocess.run([str(wrapper), *arguments], shell=True, cwd=self.folder,
                              env=environment, capture_output=True, text=True,
                              encoding='utf-8', timeout=20, creationflags=NO_WINDOW)

    def check_layout(self, nested):
        package = self.folder / ('nested 패키지' if nested else 'portable 패키지')
        package.mkdir()
        wrapper = package / 'run.cmd'
        shutil.copyfile(SOURCE / 'run.cmd', wrapper)
        binary = package / 'bin' / 'SUMUWW' / 'SUMUWW-node.exe' if nested else package / 'SUMUWW-node.exe'
        binary.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(self.executable, binary)
        result = self.run_wrapper(wrapper, 'rpc', '--params-file', 'parameters with spaces.json', 'getblockhash')
        self.assertEqual(37, result.returncode, result.stdout + result.stderr)
        self.assertEqual(['rpc', '--params-file', 'parameters with spaces.json', 'getblockhash'],
                         result.stdout.splitlines())

    def test_portable_rpc_dispatch_preserves_arguments_and_exit_code_without_python(self):
        self.check_layout(False)

    def test_nested_rpc_dispatch_preserves_arguments_and_exit_code_without_python(self):
        self.check_layout(True)

    def test_source_only_rpc_falls_back_to_configured_python(self):
        package = self.folder / 'source only'
        package.mkdir()
        wrapper = package / 'run.cmd'
        shutil.copyfile(SOURCE / 'run.cmd', wrapper)
        (package / 'run.py').write_text('import json, sys\nprint(json.dumps(sys.argv[1:]))\nsys.exit(17)\n',
                                      encoding='utf-8')
        result = self.run_wrapper(wrapper, 'rpc', '--params-file', 'parameters with spaces.json',
                                  python=sys.executable)
        self.assertEqual(17, result.returncode, result.stderr)
        self.assertEqual(['rpc', '--params-file', 'parameters with spaces.json'], json.loads(result.stdout))

    def test_packaged_node_rpc_help_runs_through_wrapper_without_python(self):
        binary = SOURCE / 'bin' / 'SUMUWW' / 'SUMUWW-node.exe'
        if not binary.is_file():
            self.skipTest('Packaged Windows node executable is unavailable')
        result = self.run_wrapper(SOURCE / 'run.cmd', 'rpc', '--help')
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertIn('--token-file', result.stdout)
        self.assertIn('--url', result.stdout)


if __name__ == '__main__':
    unittest.main()
