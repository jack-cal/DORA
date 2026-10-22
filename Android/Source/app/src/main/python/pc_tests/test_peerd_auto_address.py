"""CLI opt-in default binding and explicit listener precedence."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from sumuww import peerd


class AutoAddressCliTests(unittest.TestCase):
    def options(self,*flags):
        captured=[]
        async def capture(options):captured.append(options)
        with tempfile.TemporaryDirectory(prefix='sumuww-auto-cli-') as directory,\
             patch.object(peerd,'serve',side_effect=capture):
            code=peerd.main(['--database',str(Path(directory)/'node.sqlite'),*flags])
        self.assertEqual(0,code)
        self.assertEqual(1,len(captured))
        return captured[0]

    def test_internet_automatic_default_is_wildcard_standard_port(self):
        options=self.options('--auto-address','--allow-internet')
        self.assertTrue(options.auto_address)
        self.assertEqual('0.0.0.0:18444',options.listen)

    def test_internet_optout_and_legacy_defaults_stay_loopback_dynamic(self):
        self.assertEqual('127.0.0.1:0',self.options('--auto-address').listen)
        self.assertEqual('127.0.0.1:0',self.options('--allow-internet').listen)
        self.assertEqual('127.0.0.1:0',self.options().listen)

    def test_explicit_listener_precedes_automatic_default(self):
        options=self.options('--auto-address','--allow-internet','--listen','127.0.0.1:23456')
        self.assertEqual('127.0.0.1:23456',options.listen)

    def test_lan_only_automatic_listener_does_not_enable_internet(self):
        options=self.options('--auto-address','--allow-lan')
        self.assertEqual('0.0.0.0:18444',options.listen)
        self.assertTrue(options.allow_lan)
        self.assertFalse(options.allow_internet)


if __name__=='__main__':unittest.main()
