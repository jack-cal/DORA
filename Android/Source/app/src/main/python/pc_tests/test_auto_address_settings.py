"""Automatic listener preferences preserve keys, flags, and schema-1 requests.

Constructor checks mock the node. Every actor fixture binds loopback/port zero;
interface discovery is mocked and no public address is contacted or hosted.
"""
import json
from pathlib import Path
import socket
import tempfile
import unittest
from unittest.mock import patch

from sumuww.app_service import AppService, PUBLIC_CONTACT_NAME
from sumuww.network_settings import (SETTINGS_NAME, OWN_ADDRESS_SETTINGS_NAME,
                                   _atomic_json, load_auto_address, load_settings,
                                   normalize_settings, save_settings)


class AutomaticAddressPreferenceTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='sumuww-auto-address-preferences-')
        self.directory = Path(self.temporary.name)
        self.mode = self.directory / OWN_ADDRESS_SETTINGS_NAME

    def tearDown(self):
        self.temporary.cleanup()

    def explicit_mode(self, automatic):
        _atomic_json(self.mode, {'schema_version': 1, 'automatic': automatic})

    def node_options(self, actor):
        with patch('sumuww.app_service.PeerNode') as constructor:
            actor._make_node(actor._settings)
        self.assertFalse(actor.database.exists())
        return constructor.call_args.kwargs

    def test_missing_or_explicit_boolean_mode(self):
        self.assertIsNone(load_auto_address(self.directory))
        for automatic in (True, False):
            self.explicit_mode(automatic)
            self.assertIs(automatic, load_auto_address(self.directory))

    def test_strict_mode_schema_and_duplicate_fields(self):
        for value in ([], {'schema_version': True, 'automatic': True},
                      {'schema_version': 2, 'automatic': True},
                      {'schema_version': 1, 'automatic': 1},
                      {'schema_version': 1, 'automatic': 'true'},
                      {'schema_version': 1, 'automatic': False, 'address': '8.8.8.8'}):
            self.mode.write_text(json.dumps(value), encoding='utf-8')
            with self.subTest(value=value), self.assertRaises(ValueError):
                load_auto_address(self.directory)
        self.mode.write_text('{"schema_version":1,"automatic":true,"automatic":false}', encoding='utf-8')
        with self.assertRaises(ValueError):
            load_auto_address(self.directory)
        self.mode.write_text('x' * 4097, encoding='utf-8')
        with self.assertRaises(ValueError):
            load_auto_address(self.directory)

    def test_fresh_main_automatic_runtime_binding_keeps_requested_preferences(self):
        actor = AppService(self.directory, network='dora', bootstrap=True)
        options = self.node_options(actor)
        self.assertTrue(actor._auto_address)
        self.assertTrue(options['auto_address'])
        self.assertEqual(('0.0.0.0', 18444), (options['host'], options['port']))
        self.assertIsNone(options['advertised_endpoint'])
        self.assertEqual('127.0.0.1:0', actor.listen)
        self.assertEqual([], list(self.directory.iterdir()))

    def test_existing_default_listener_migrates_only_runtime_mode(self):
        existing = normalize_settings('127.0.0.1:0', ['127.0.0.1:18445'], allow_internet=True)
        save_settings(self.directory, existing)
        original = (self.directory / SETTINGS_NAME).read_bytes()
        actor = AppService(self.directory, network='dora')
        options = self.node_options(actor)
        self.assertTrue(options['auto_address'])
        self.assertEqual([('127.0.0.1', 18445)], options['peers'])
        self.assertEqual(original, (self.directory / SETTINGS_NAME).read_bytes())

    def test_explicit_internet_optout_never_binds_wildcard(self):
        existing = normalize_settings('127.0.0.1:0', [], allow_internet=False)
        save_settings(self.directory, existing)
        self.explicit_mode(True)
        actor = AppService(self.directory, network='dora', bootstrap=True)
        options = self.node_options(actor)
        self.assertTrue(actor._auto_address)
        self.assertFalse(options['auto_address'])
        self.assertFalse(options['allow_internet'])
        self.assertEqual(('127.0.0.1', 0), (options['host'], options['port']))
        self.assertEqual(existing, load_settings(self.directory, bootstrap=True))

    def test_saved_automatic_mode_and_internet_override_discard_inactive_wildcard(self):
        save_settings(self.directory, normalize_settings('0.0.0.0:18444', [], allow_internet=True))
        self.explicit_mode(True)
        actor = AppService(self.directory, network='dora', allow_internet=False)
        options = self.node_options(actor)
        self.assertTrue(actor._auto_address)
        self.assertFalse(options['auto_address'])
        self.assertEqual(('127.0.0.1', 0), (options['host'], options['port']))

    def test_saved_manual_mode_prevents_default_listener_migration(self):
        self.explicit_mode(False)
        actor = AppService(self.directory, network='dora', bootstrap=True)
        options = self.node_options(actor)
        self.assertFalse(actor._auto_address)
        self.assertEqual(('127.0.0.1', 0), (options['host'], options['port']))

    def test_explicit_listener_or_custom_saved_listener_defaults_to_manual(self):
        actor = AppService(self.directory, network='dora', listen='127.0.0.1:0', allow_internet=True)
        self.assertFalse(actor._auto_address)
        save_settings(self.directory, normalize_settings('0.0.0.0:18445', [], allow_internet=True))
        restored = AppService(self.directory, network='dora')
        self.assertFalse(restored._auto_address)
        options = self.node_options(restored)
        self.assertEqual(('0.0.0.0', 18445), (options['host'], options['port']))

    def test_explicit_advanced_listener_overrides_saved_automatic_selection(self):
        self.explicit_mode(True)
        actor = AppService(self.directory, network='dora', listen='127.0.0.1:18445', allow_internet=True)
        options = self.node_options(actor)
        self.assertFalse(actor._auto_address)
        self.assertEqual(('127.0.0.1', 18445), (options['host'], options['port']))
        self.assertEqual('127.0.0.1:18445', actor.listen)

    def test_explicit_contact_overrides_saved_mode_but_explicit_automatic_wins_both(self):
        self.explicit_mode(True)
        advanced = AppService(self.directory, network='dora', listen='0.0.0.0:18445',
                              allow_internet=True, advertise='8.8.8.8:18445')
        self.assertFalse(advanced._auto_address)
        self.assertEqual(('8.8.8.8', 18445), self.node_options(advanced)['advertised_endpoint'])
        automatic = AppService(self.directory, network='dora', listen='127.0.0.1:18445',
                               allow_internet=True, advertise='8.8.8.8:18445', auto_address=True)
        self.assertTrue(automatic._auto_address)
        self.assertIsNone(self.node_options(automatic)['advertised_endpoint'])

    def test_manual_contact_not_applied_in_explicit_automatic_mode(self):
        actor = AppService(self.directory, network='dora', bootstrap=True,
                           advertise='8.8.8.8:18444', auto_address=True)
        options = self.node_options(actor)
        self.assertEqual('8.8.8.8:18444', actor._public_contact)
        self.assertIsNone(options['advertised_endpoint'])

    def test_nonmain_defaults_and_nonboolean_explicit_mode(self):
        actor = AppService(self.directory, network='regtest', allow_internet=True)
        self.assertFalse(actor._auto_address)
        for value in (1, 'true'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                AppService(self.directory, network='dora', auto_address=value)


class AutomaticAddressActorTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='sumuww-auto-address-actor-')
        self.directory = Path(self.temporary.name)
        self.services = []
        original = AppService._make_node

        def loopback_fixture(service, settings, contact=None, auto_address=None):
            node = original(service, settings, contact, auto_address=auto_address)
            node.address = ('127.0.0.1', 0)
            return node

        self.node_patch = patch.object(AppService, '_make_node', loopback_fixture)
        self.interfaces_patch = patch('sumuww.peer.enumerate_ipv4_interfaces', return_value=[])
        self.node_patch.start()
        self.interfaces_patch.start()

    def tearDown(self):
        for service in self.services:
            service.cancel_mining()
            service.stop().result(timeout=15)
        self.interfaces_patch.stop()
        self.node_patch.stop()
        self.temporary.cleanup()

    def service(self, **options):
        actor = AppService(self.directory, network='regtest', **options)
        self.services.append(actor)
        actor.start().result(timeout=15)
        return actor

    def test_mode_persists_separately_and_runtime_addresses_are_not_manual_contacts(self):
        actor = self.service(allow_internet=True, auto_address=True)
        state = actor.status().result(timeout=5)
        self.assertTrue(state['connection']['auto_address'])
        self.assertEqual('127.0.0.1:0', state['connection']['listen'])
        actual = f'127.0.0.1:{state["node"]["listen"]["port"]}'
        self.assertEqual([actual], state['connection']['own_addresses'])
        self.assertEqual('not_verified', state['connection']['self_address']['external_reachability'])
        self.assertEqual({'schema_version': 1, 'automatic': True},
                         json.loads((self.directory / OWN_ADDRESS_SETTINGS_NAME).read_text(encoding='utf-8')))
        self.assertEqual('', state['connection']['public_contact'])
        self.assertFalse((self.directory / PUBLIC_CONTACT_NAME).exists())
        self.assertEqual({'schema_version', 'listen', 'peers', 'allow_internet', 'allow_lan'},
                         set(load_settings(self.directory)))
        actor.stop().result(timeout=15)
        restored = self.service()
        self.assertTrue(restored.status().result(timeout=5)['connection']['auto_address'])

    def test_legacy_explicit_configure_listener_selects_manual_and_keeps_wallet(self):
        actor = self.service(allow_internet=True, auto_address=True)
        wallet = actor.create_wallet('wallet.json', 'isolated test password').result(timeout=15)
        tip = actor.status().result(timeout=5)['node']['tip']
        state = actor.configure_network('127.0.0.1:0', [], allow_internet=True).result(timeout=15)
        self.assertFalse(state['connection']['auto_address'])
        self.assertFalse(actor._node.auto_address)
        self.assertEqual(wallet['address'], state['wallet']['address'])
        self.assertTrue(state['wallet']['unlocked'])
        self.assertEqual(tip, state['node']['tip'])

    def test_inactive_manual_contact_survives_automatic_internet_optout_without_advertising(self):
        actor = self.service(listen='0.0.0.0:0', allow_internet=True,
                             advertise='8.8.8.8:18444', auto_address=False)
        state = actor.configure_network('127.0.0.1:0', [], allow_internet=False,
                                        auto_address=True).result(timeout=15)
        self.assertTrue(state['connection']['auto_address'])
        self.assertFalse(state['connection']['allow_internet'])
        self.assertFalse(actor._node.auto_address)
        self.assertIsNone(actor._node.advertised_endpoint)
        self.assertEqual('8.8.8.8:18444', state['connection']['public_contact'])

    def test_failed_mode_write_rolls_back_all_preferences_node_and_wallet(self):
        actor = self.service(listen='0.0.0.0:0', allow_internet=True,
                             advertise='8.8.8.8:18444', auto_address=False)
        wallet = actor.create_wallet('wallet.json', 'isolated test password').result(timeout=15)
        paths = [self.directory / name for name in (SETTINGS_NAME, PUBLIC_CONTACT_NAME, OWN_ADDRESS_SETTINGS_NAME)]
        originals = {path: path.read_bytes() for path in paths}
        from sumuww.app_service import _atomic_json as actual_write
        writes = []

        def failed_mode_write(path, value):
            actual_write(path, value)
            writes.append(path.name)
            if path.name == OWN_ADDRESS_SETTINGS_NAME:
                raise OSError('Injected mode publication failure')

        with patch('sumuww.app_service._atomic_json', failed_mode_write), self.assertRaises(Exception):
            actor.configure_network('127.0.0.1:0', [], allow_internet=True,
                                    advertise='8.8.4.4:18445', auto_address=True).result(timeout=15)
        self.assertEqual([PUBLIC_CONTACT_NAME, OWN_ADDRESS_SETTINGS_NAME], writes)
        self.assertEqual(originals, {path: path.read_bytes() for path in paths})
        state = actor.status().result(timeout=5)
        self.assertTrue(state['node']['running'])
        self.assertFalse(state['connection']['auto_address'])
        self.assertEqual(wallet['address'], state['wallet']['address'])
        self.assertTrue(state['wallet']['unlocked'])
        self.assertEqual('8.8.8.8:18444', state['connection']['public_contact'])

    def test_wallet_operations_cannot_replace_mode_sidecar(self):
        actor = self.service()
        original = (self.directory / OWN_ADDRESS_SETTINGS_NAME).read_bytes()
        with self.assertRaises(Exception):
            actor.create_wallet(OWN_ADDRESS_SETTINGS_NAME, 'isolated test password').result(timeout=5)
        self.assertEqual(original, (self.directory / OWN_ADDRESS_SETTINGS_NAME).read_bytes())

    def test_automatic_configure_ignores_disabled_listener_with_internet_optout(self):
        actor = self.service(allow_internet=True, auto_address=True)
        for listener in ('', '0.0.0.0:18444', 'stale inactive field'):
            with self.subTest(listener=listener):
                state = actor.configure_network(listener, [], allow_internet=False,
                                                auto_address=True).result(timeout=15)
                self.assertTrue(state['connection']['auto_address'])
                self.assertFalse(actor._node.auto_address)
                self.assertFalse(state['connection']['allow_internet'])
                self.assertEqual('127.0.0.1:0', state['connection']['listen'])
                self.assertEqual('127.0.0.1', state['node']['listen']['host'])
        with self.assertRaises(Exception):
            actor.configure_network('', [], allow_internet=False, auto_address=False).result(timeout=5)
        with self.assertRaises(Exception):
            actor.configure_network('', ['8.8.8.8:18444'], allow_internet=False,
                                    auto_address=True).result(timeout=5)

    def test_adding_manual_peer_preserves_automatic_mode(self):
        actor = self.service(allow_internet=True, auto_address=True)
        with socket.socket() as unavailable:
            unavailable.bind(('127.0.0.1', 0))
            address = f'127.0.0.1:{unavailable.getsockname()[1]}'
            actor.add_peer(address).result(timeout=5)
            self.assertTrue(actor.status().result(timeout=5)['connection']['auto_address'])
            self.assertTrue(actor._node.auto_address)
        self.assertIs(True, load_auto_address(self.directory))


if __name__ == '__main__':
    unittest.main()
