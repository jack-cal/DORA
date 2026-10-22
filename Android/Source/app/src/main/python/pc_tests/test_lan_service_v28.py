"""LAN-only automatic addressing must not require or enable Internet access."""
from pathlib import Path
import tempfile
import unittest

from sumuww.app_service import AppService
from sumuww.profiles import REGTEST


class LanServiceTests(unittest.TestCase):
    def test_lan_only_service_uses_automatic_listener_and_keeps_internet_off(self):
        with tempfile.TemporaryDirectory(prefix='sumuww-lan-service-') as directory:
            service = AppService(Path(directory), network=REGTEST, peers=[],
                                 allow_lan=True, allow_internet=False, auto_address=True)
            try:
                service.start().result(timeout=10)
                status = service.status().result(timeout=10)
                self.assertFalse(status['node']['allow_internet'])
                self.assertTrue(status['node']['allow_lan'])
                self.assertEqual('0.0.0.0', status['node']['listen']['host'])
                self.assertGreater(status['node']['listen']['port'], 0)
                self.assertTrue(status['node']['lan_discovery']['enabled'])
                self.assertFalse(status['node']['bootstrap']['enabled'])
            finally:
                service.stop().result(timeout=15)

    def test_no_network_permission_retains_loopback_and_disabled_lan_discovery(self):
        with tempfile.TemporaryDirectory(prefix='sumuww-no-network-') as directory:
            service = AppService(Path(directory), network=REGTEST, peers=[],
                                 allow_lan=False, allow_internet=False, auto_address=True)
            try:
                service.start().result(timeout=10)
                status = service.status().result(timeout=10)
                self.assertEqual('127.0.0.1', status['node']['listen']['host'])
                self.assertEqual('disabled', status['node']['lan_discovery']['state'])
            finally:
                service.stop().result(timeout=15)


if __name__ == '__main__':
    unittest.main()
