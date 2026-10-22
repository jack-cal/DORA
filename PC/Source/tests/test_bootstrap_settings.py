"""Bootstrap migration preserves schema-1 manual peers and permission choices."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from sumuww import network_settings


class BootstrapSettingsMigrationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='sumuww-bootstrap-settings-')
        self.directory = Path(self.temporary.name)
        self.path = self.directory / network_settings.SETTINGS_NAME

    def tearDown(self):
        self.temporary.cleanup()

    def write(self, *, peers=None, allow_internet=False, allow_lan=False,
              listen='127.0.0.1:0'):
        value = {'schema_version': 1, 'listen': listen,
                 'peers': [] if peers is None else peers,
                 'allow_internet': allow_internet, 'allow_lan': allow_lan}
        self.path.write_text(json.dumps(value, indent=4) + '\n', encoding='utf-8')
        return value

    def test_fresh_main_bootstrap_enables_internet_without_saved_peers(self):
        value = network_settings.load_settings(self.directory, bootstrap=True)
        self.assertTrue(value['allow_internet'])
        self.assertFalse(value['allow_lan'])
        self.assertEqual([], value['peers'])
        self.assertEqual('127.0.0.1:0', value['listen'])
        self.assertEqual([], list(self.directory.iterdir()))

    def test_fresh_nonbootstrap_remains_local_only(self):
        value = network_settings.load_settings(self.directory)
        self.assertFalse(value['allow_internet'])
        self.assertFalse(value['allow_lan'])
        self.assertEqual([], value['peers'])

    def test_legacy_bootstrap_constant_is_not_injected_into_manual_peers(self):
        with patch.object(network_settings, 'BOOTSTRAP_PEERS', ['bootstrap.example:18444']):
            value = network_settings.load_settings(self.directory, bootstrap=True)
        self.assertEqual([], value['peers'])
        self.assertFalse(self.path.exists())

    def test_existing_empty_internet_enabled_preferences_remain_unchanged(self):
        expected = self.write(allow_internet=True)
        original = self.path.read_bytes()
        value = network_settings.load_settings(self.directory, bootstrap=True)
        self.assertEqual(expected, value)
        self.assertEqual(original, self.path.read_bytes())
        self.assertEqual([], value['peers'])

    def test_explicit_saved_internet_optout_is_never_overridden(self):
        expected = self.write(allow_internet=False)
        original = self.path.read_bytes()
        self.assertEqual(expected, network_settings.load_settings(self.directory, bootstrap=True))
        self.assertFalse(network_settings.load_settings(self.directory, bootstrap=True)['allow_internet'])
        self.assertEqual(original, self.path.read_bytes())

    def test_saved_lan_only_permission_and_contacts_remain_unchanged(self):
        expected = self.write(peers=['192.168.1.12:18444'], allow_lan=True)
        self.assertEqual(expected, network_settings.load_settings(self.directory, bootstrap=True))

    def test_saved_manual_public_and_dns_contacts_are_preserved(self):
        expected = self.write(peers=['8.8.8.8:18444', 'peer.example:18444'],
                              allow_internet=True, listen='0.0.0.0:18444')
        original = self.path.read_bytes()
        self.assertEqual(expected, network_settings.load_settings(self.directory, bootstrap=True))
        self.assertEqual(original, self.path.read_bytes())

    def test_saved_schema_has_no_bootstrap_or_manifest_fields(self):
        expected = self.write(allow_internet=True)
        network_settings.save_settings(self.directory, expected)
        self.assertEqual({'schema_version', 'listen', 'peers', 'allow_internet', 'allow_lan'},
                         set(json.loads(self.path.read_text(encoding='utf-8'))))
        self.assertEqual(expected, network_settings.load_settings(self.directory, bootstrap=True))

    def test_bootstrap_setting_does_not_write_or_read_wallet_data(self):
        wallet = self.directory / 'wallet.json'
        wallet.write_bytes(b'not a wallet; test sentinel')
        original = wallet.read_bytes()
        original_read = Path.read_text
        reads = []

        def audited_read(path, *args, **kwargs):
            reads.append(path.name)
            return original_read(path, *args, **kwargs)

        with patch.object(Path, 'read_text', audited_read):
            network_settings.load_settings(self.directory, bootstrap=True)
        self.assertEqual([], reads)
        self.assertEqual(original, wallet.read_bytes())
        self.assertEqual([wallet], list(self.directory.iterdir()))

    def test_fresh_peer_lists_are_not_shared_between_calls(self):
        first = network_settings.load_settings(self.directory, bootstrap=True)
        first['peers'].append('127.0.0.1:18444')
        self.assertEqual([], network_settings.load_settings(self.directory, bootstrap=True)['peers'])

    def test_invalid_saved_schema_is_not_replaced_with_bootstrap_defaults(self):
        for document in ([], {'schema_version': 1},
                         {'schema_version': True, 'listen': '127.0.0.1:0', 'peers': [],
                          'allow_internet': False, 'allow_lan': False},
                         {'schema_version': 1, 'listen': '127.0.0.1:0', 'peers': [],
                          'allow_internet': False, 'allow_lan': False, 'bootstrap': True}):
            self.path.write_text(json.dumps(document), encoding='utf-8')
            original = self.path.read_bytes()
            with self.subTest(document=document), self.assertRaises(ValueError):
                network_settings.load_settings(self.directory, bootstrap=True)
            self.assertEqual(original, self.path.read_bytes())

    def test_invalid_saved_permission_type_cannot_enable_bootstrap(self):
        for permission in (1, 'true', None):
            self.write(allow_internet=permission)
            with self.subTest(permission=permission), self.assertRaises(ValueError):
                network_settings.load_settings(self.directory, bootstrap=True)

    def test_saved_invalid_scope_does_not_gain_internet_permission(self):
        self.write(peers=['8.8.8.8:18444'], allow_internet=False)
        with self.assertRaises(ValueError):
            network_settings.load_settings(self.directory, bootstrap=True)

    def test_oversized_preferences_fail_without_replacing_file(self):
        self.path.write_bytes(b'x' * 16385)
        with self.assertRaises(ValueError):
            network_settings.load_settings(self.directory, bootstrap=True)
        self.assertEqual(b'x' * 16385, self.path.read_bytes())


class BootstrapAppIntegrationTests(unittest.TestCase):
    """Inspect node-constructor inputs without making any network connections."""
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='sumuww-bootstrap-app-options-')
        self.directory = Path(self.temporary.name)
        self.manifest = self.directory / 'fixture-bootstrap.json'
        from sumuww.profiles import SUMUWW
        self.manifest.write_text(json.dumps({
            'schema_version': 2, 'network': 'dora', 'genesis': SUMUWW.genesis.block_hash().hex(),
            'dns_seeds': [{'host': 'seed.example', 'port': 18444}],
            'fallback_peers': [{'host': '8.8.8.8', 'port': 18444}],
        }), encoding='utf-8')

    def tearDown(self):
        self.temporary.cleanup()

    def inspect_node(self, actor):
        with patch('sumuww.app_service.PeerNode') as constructor:
            actor._make_node(actor._settings)
        self.assertFalse((self.directory / 'node.sqlite').exists())
        return constructor.call_args.kwargs

    def test_fresh_main_sources_are_separate_from_empty_manual_peers(self):
        from sumuww.app_service import AppService
        actor = AppService(self.directory, network='dora', bootstrap=True,
                           bootstrap_manifest=self.manifest)
        options = self.inspect_node(actor)
        self.assertEqual([], options['peers'])
        self.assertEqual((('seed.example', 18444),), options['bootstrap_seeds'])
        self.assertEqual((('8.8.8.8', 18444),), options['bootstrap_peers'])
        self.assertTrue(options['allow_internet'])
        self.assertFalse((self.directory / network_settings.SETTINGS_NAME).exists())

    def test_existing_empty_enabled_preferences_receive_sources_without_mutation(self):
        from sumuww.app_service import AppService
        preference = network_settings.normalize_settings('127.0.0.1:0', [], allow_internet=True)
        network_settings.save_settings(self.directory, preference)
        path = self.directory / network_settings.SETTINGS_NAME
        original = path.read_bytes()
        # Even an old data folder and bootstrap=False must receive independent
        # sources if its existing internet permission is explicitly enabled.
        actor = AppService(self.directory, network='dora', bootstrap=False,
                           bootstrap_manifest=self.manifest)
        options = self.inspect_node(actor)
        self.assertEqual([], options['peers'])
        self.assertEqual((('seed.example', 18444),), options['bootstrap_seeds'])
        self.assertEqual(original, path.read_bytes())

    def test_saved_optout_skips_manifest_loader_and_all_automatic_sources(self):
        from sumuww.app_service import AppService
        preference = network_settings.normalize_settings('127.0.0.1:0', [], allow_internet=False)
        network_settings.save_settings(self.directory, preference)
        actor = AppService(self.directory, network='dora', bootstrap=True,
                           bootstrap_manifest=self.manifest)
        with patch('sumuww.app_service.load_bootstrap', side_effect=AssertionError('Opt-out must skip sources')):
            options = self.inspect_node(actor)
        self.assertFalse(options['allow_internet'])
        self.assertFalse(options.get('bootstrap_seeds'))
        self.assertFalse(options.get('bootstrap_peers'))
        self.assertEqual(preference, network_settings.load_settings(self.directory, bootstrap=True))

    def test_manual_peers_stay_separate_and_survive_invalid_optional_manifest(self):
        from sumuww.app_service import AppService
        self.manifest.write_text('invalid optional source', encoding='utf-8')
        actor = AppService(self.directory, network='dora', allow_internet=True,
                           peers=['127.0.0.1:18444'], bootstrap_manifest=self.manifest)
        options = self.inspect_node(actor)
        self.assertEqual([('127.0.0.1', 18444)], options['peers'])
        self.assertFalse(options.get('bootstrap_seeds'))
        self.assertFalse(options.get('bootstrap_peers'))
        self.assertEqual('Invalid initial discovery configuration', actor._bootstrap_error)

    def test_main_profile_refuses_test_scope_before_constructing_database(self):
        from sumuww.app_service import AppService
        with self.assertRaises(ValueError):
            AppService(self.directory, network='dora', allow_internet=True,
                       bootstrap_manifest=self.manifest, bootstrap_scope='loopback')
        self.assertFalse((self.directory / 'node.sqlite').exists())


if __name__ == '__main__':
    unittest.main()
