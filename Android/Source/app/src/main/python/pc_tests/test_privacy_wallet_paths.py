import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from sumuww.app_service import AppService,AppServiceError
from sumuww.__main__ import _guard_paths
from sumuww.managed_privacy import ManagedRouter


class PrivacyWalletPaths(unittest.TestCase):
    def test_legacy_wallet_in_router_config_is_preserved(self):
        for mode,kind,name in [('tor','arti','arti.toml'),('tor','tor','torrc'),('i2p','i2pd','i2pd.conf')]:
            with self.subTest(mode=mode,kind=kind),tempfile.TemporaryDirectory() as directory:
                router=ManagedRouter(mode,directory)
                router.directory.mkdir(parents=True)
                path=router.directory/name
                sentinel=json.dumps({'format':'sumuww-hd-wallet','owned_fixture':'not a real wallet'}).encode()
                path.write_bytes(sentinel)
                with self.assertRaises(ValueError):router._command('not-executed',kind)
                self.assertEqual(sentinel,path.read_bytes())

    def test_service_refuses_wallet_and_backup_destinations_in_router_state(self):
        with tempfile.TemporaryDirectory() as directory:
            service=AppService(directory,network='regtest',peers=[],bootstrap=False)
            for suffix in ('tor/arti.toml','tor/state/my-wallet.json','i2p/certificates/reseed/my-wallet.json'):
                with self.subTest(suffix=suffix):
                    target=Path(directory)/'privacy'/suffix
                    with self.assertRaises(AppServiceError):service._guard_paths(target,destination=target)
                    self.assertFalse(target.exists())

    def test_cli_reserves_router_state_with_explicit_database(self):
        with tempfile.TemporaryDirectory() as directory:
            args=SimpleNamespace(database=Path(directory)/'node.sqlite',wallet=Path(directory)/'privacy/tor/state/wallet.json',
                backup=None,password_file=None,hex_file=None,phrase_file=None,phrase_output=None)
            with self.assertRaises(ValueError):_guard_paths(args)
            self.assertFalse(args.wallet.exists())
