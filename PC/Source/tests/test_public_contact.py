"""Explicit public contact preferences; all live test sockets stay loopback."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from sumuww.app_service import AppService, PUBLIC_CONTACT_NAME, _load_public_contact
from sumuww.network_settings import SETTINGS_NAME, load_settings, save_settings
from sumuww.peerd import public_contact


CONTACT = '8.8.8.8:18444'  # Validation input only; never connected to.


class PublicContactValidationTests(unittest.TestCase):
    def test_empty_is_disabled_without_permission_or_public_listener(self):
        self.assertIsNone(public_contact('', '127.0.0.1:0'))
        self.assertIsNone(public_contact(None, '127.0.0.1:0'))

    def test_public_contact_accepts_wildcard_and_nat_private_listeners(self):
        for listener in ('0.0.0.0:18444', '192.168.1.10:18444', '8.8.4.4:18444'):
            with self.subTest(listener=listener):
                self.assertEqual(('8.8.8.8', 18444), public_contact(CONTACT, listener, allow_internet=True))

    def test_contact_rejects_hostname_special_addresses_and_zero_port(self):
        for address in ('localhost:18444', 'example.org:18444', '127.0.0.1:18444',
                        '192.168.1.1:18444', '10.0.0.1:18444', '0.0.0.0:18444',
                        '100.64.0.1:18444', '169.254.1.1:18444', '224.0.0.1:18444',
                        '192.0.2.1:18444', '8.8.8.8:0', '8.8.8.8:65536', '::1:18444', True):
            with self.subTest(address=address), self.assertRaises(ValueError):
                public_contact(address, '0.0.0.0:18444', allow_internet=True)

    def test_contact_requires_internet_permission_and_inbound_listener(self):
        with self.assertRaises(ValueError):
            public_contact(CONTACT, '192.168.1.10:18444', allow_lan=True)
        with self.assertRaises(ValueError):
            public_contact(CONTACT, '127.0.0.1:18444', allow_internet=True)

    def test_contact_validation_never_performs_external_lookup(self):
        with patch('socket.getaddrinfo', side_effect=AssertionError('DNS must not be used')):
            self.assertEqual(('8.8.8.8', 18444), public_contact(CONTACT, '0.0.0.0:18444', allow_internet=True))

    def test_missing_and_strict_saved_contact_schema(self):
        with tempfile.TemporaryDirectory(prefix='sumuww-public-contact-schema-') as temporary:
            directory = Path(temporary)
            self.assertEqual('', _load_public_contact(directory))
            path = directory / PUBLIC_CONTACT_NAME
            for value in ({'schema_version': True, 'endpoint': CONTACT},
                          {'schema_version': 1, 'endpoint': CONTACT, 'extra': 1},
                          {'schema_version': 1, 'endpoint': 42}, []):
                path.write_text(json.dumps(value), encoding='utf-8')
                with self.subTest(value=value), self.assertRaises(ValueError):
                    _load_public_contact(directory)
            path.write_text('x' * 4097, encoding='utf-8')
            with self.assertRaises(ValueError):
                _load_public_contact(directory)
            path.write_text('{"schema_version":1,"endpoint":"","endpoint":"8.8.8.8:18444"}', encoding='utf-8')
            with self.assertRaises(ValueError):
                _load_public_contact(directory)


class PublicContactActorTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='sumuww-public-contact-actor-')
        self.directory = Path(self.temporary.name)
        self.services = []
        original = AppService._make_node

        def loopback_test_node(service, settings, contact=None, auto_address=None):
            node = original(service, settings, contact, auto_address=auto_address)
            # Validate actual constructor behavior but never expose a public
            # fixture listener. Advertisements are metadata only in this test.
            node.address = ('127.0.0.1', node.address[1])
            return node

        self.node_patch = patch.object(AppService, '_make_node', loopback_test_node)
        self.node_patch.start()

    def tearDown(self):
        for service in self.services:
            service.cancel_mining()
            service.stop().result(timeout=15)
        self.node_patch.stop()
        self.temporary.cleanup()

    def service(self, **options):
        actor = AppService(self.directory, network='regtest', **options)
        self.services.append(actor)
        actor.start().result(timeout=15)
        return actor

    def test_legacy_preferences_preserved_and_no_contact_generated(self):
        actor = self.service(bootstrap=True)
        state = actor.status().result(timeout=5)
        self.assertEqual('', state['connection']['public_contact'])
        self.assertFalse((self.directory / PUBLIC_CONTACT_NAME).exists())
        self.assertEqual({'schema_version', 'listen', 'peers', 'allow_internet', 'allow_lan'},
                         set(load_settings(self.directory)))
        self.assertIsNone(actor._node.advertised_endpoint)

    def test_contact_persists_on_same_chain_and_none_reuses_saved_value(self):
        actor = self.service()
        initial_tip = actor.status().result(timeout=5)['node']['tip']
        actor.configure_network('0.0.0.0:0', [], allow_internet=True, advertise=CONTACT).result(timeout=15)
        self.assertEqual(('8.8.8.8', 18444), actor._node.advertised_endpoint)
        self.assertEqual({'schema_version': 1, 'endpoint': CONTACT},
                         json.loads((self.directory / PUBLIC_CONTACT_NAME).read_text(encoding='utf-8')))
        actor.stop().result(timeout=15)
        restored = self.service()
        state = restored.status().result(timeout=5)
        self.assertEqual(CONTACT, state['connection']['public_contact'])
        self.assertEqual(initial_tip, state['node']['tip'])
        self.assertEqual(('8.8.8.8', 18444), restored._node.advertised_endpoint)
        restored.configure_network('0.0.0.0:0', [], allow_internet=True).result(timeout=15)
        self.assertEqual(CONTACT, restored.status().result(timeout=5)['connection']['public_contact'])

    def test_clear_contact_allows_return_to_loopback_and_keeps_selected_wallet(self):
        actor = self.service(listen='0.0.0.0:0', allow_internet=True, advertise=CONTACT)
        wallet = actor.create_wallet('wallet.json', 'temporary test password').result(timeout=15)
        tip = actor.status().result(timeout=5)['node']['tip']
        state = actor.configure_network('127.0.0.1:0', [], advertise='').result(timeout=15)
        self.assertEqual('', state['connection']['public_contact'])
        self.assertEqual(wallet['address'], state['wallet']['address'])
        self.assertTrue(state['wallet']['unlocked'])
        self.assertEqual(tip, state['node']['tip'])
        self.assertIsNone(actor._node.advertised_endpoint)

    def test_invalid_change_keeps_existing_node_and_preferences(self):
        actor = self.service()
        node = actor._node
        prior = (self.directory / SETTINGS_NAME).read_bytes()
        with self.assertRaises(Exception):
            actor.configure_network('127.0.0.1:0', [], allow_internet=True, advertise=CONTACT).result(timeout=5)
        self.assertIs(node, actor._node)
        self.assertTrue(actor.status().result(timeout=5)['node']['running'])
        self.assertEqual(prior, (self.directory / SETTINGS_NAME).read_bytes())
        self.assertFalse((self.directory / PUBLIC_CONTACT_NAME).exists())

    def test_failed_contact_publication_restores_both_documents_and_old_node(self):
        actor = self.service(listen='0.0.0.0:0', allow_internet=True, advertise=CONTACT)
        paths = (self.directory / SETTINGS_NAME, self.directory / PUBLIC_CONTACT_NAME)
        original = {path: path.read_bytes() for path in paths}
        from sumuww.app_service import _atomic_json
        published = []

        def publish_then_fail(path, value):
            _atomic_json(path, value)
            published.append(value)
            raise OSError('Injected contact publication failure')

        with patch('sumuww.app_service._atomic_json', publish_then_fail), self.assertRaises(Exception):
            actor.configure_network('0.0.0.0:0', [], allow_internet=True, allow_lan=True,
                                    advertise='8.8.4.4:18445').result(timeout=15)
        self.assertEqual([{'schema_version': 1, 'endpoint': '8.8.4.4:18445'}], published)
        self.assertEqual(original, {path: path.read_bytes() for path in paths})
        state = actor.status().result(timeout=5)
        self.assertTrue(state['node']['running'])
        self.assertEqual(CONTACT, state['connection']['public_contact'])
        self.assertEqual('0.0.0.0:0', state['connection']['listen'])
        self.assertEqual(('8.8.8.8', 18444), actor._node.advertised_endpoint)

    def test_failed_base_settings_publication_leaves_contact_and_old_node(self):
        actor = self.service()
        original = (self.directory / SETTINGS_NAME).read_bytes()
        with patch('sumuww.network_settings._atomic_json', side_effect=OSError('Injected base publication failure')), self.assertRaises(Exception):
            actor.configure_network('0.0.0.0:0', [], allow_internet=True, advertise=CONTACT).result(timeout=15)
        self.assertEqual(original, (self.directory / SETTINGS_NAME).read_bytes())
        self.assertFalse((self.directory / PUBLIC_CONTACT_NAME).exists())
        self.assertTrue(actor.status().result(timeout=5)['node']['running'])

    def test_contact_preference_cannot_be_overwritten_with_wallet(self):
        actor = self.service()
        with self.assertRaises(Exception):
            actor.create_wallet(PUBLIC_CONTACT_NAME, 'temporary test password').result(timeout=5)
        self.assertFalse((self.directory / PUBLIC_CONTACT_NAME).exists())


if __name__ == '__main__':
    unittest.main()
