"""Node status contacts can be pasted into connection input unchanged.

Addresses below are display fixtures. No public socket, user profile, wallet,
router or firewall operation is performed.
"""
from pathlib import Path
import tempfile
import unittest

from sumuww.app_service import AppService
from sumuww.peer import PeerNode
from sumuww.peerd import endpoint
from sumuww.self_address import SelfAddressState


class StatusAddressRoundTripTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='sumuww-status-address-')
        self.directory = Path(self.temporary.name)
        self.nodes = []

    async def asyncTearDown(self):
        for node in self.nodes:
            await node.stop()
        self.temporary.cleanup()

    def public_contact(self, host):
        node = PeerNode(self.directory / 'node.sqlite', network='regtest')
        self.nodes.append(node)
        node._self_state = SelfAddressState(((host, 18444),), (host, 18444), 'direct_public_interface')
        return node.info()['self_address']['public_contact']

    async def test_ipv6_public_contact_status_roundtrips_through_peer_input(self):
        text = self.public_contact('2606:4700::1111')
        self.assertEqual('[2606:4700::1111]:18444', text)
        self.assertEqual(('2606:4700::1111', 18444), endpoint(text, allow_internet=True))

    async def test_ipv4_public_contact_status_remains_accepted(self):
        text = self.public_contact('8.8.8.8')
        self.assertEqual('8.8.8.8:18444', text)
        self.assertEqual(('8.8.8.8', 18444), endpoint(text, allow_internet=True))

    def effective_listener(self, host):
        service = AppService(self.directory / 'service', network='regtest')
        return service._connection({'listen': {'host': host, 'port': 18444}})['effective_listen']

    async def test_ipv6_effective_listen_status_roundtrips_through_listener_input(self):
        text = self.effective_listener('::1')
        self.assertEqual('[::1]:18444', text)
        self.assertEqual(('::1', 18444), endpoint(text, for_listen=True))

    async def test_ipv4_effective_listen_status_remains_accepted(self):
        text = self.effective_listener('127.0.0.1')
        self.assertEqual('127.0.0.1:18444', text)
        self.assertEqual(('127.0.0.1', 18444), endpoint(text, for_listen=True))


if __name__ == '__main__':
    unittest.main()
