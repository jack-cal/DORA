import importlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from sumuww.compatibility import compatibility_fields, public_view
from sumuww.profiles import SUMUWW, get_network
from sumuww.hd import SUMUWW_NAMESPACE
from sumuww.network_settings import default_directory


class PublishedVersionCompatibilityTests(unittest.TestCase):
    def test_existing_wire_chain_and_seed_identities_are_preserved(self):
        self.assertEqual(SUMUWW.genesis.block_hash().hex(),
                         '97af287a70223f8f35a45aa708f329d33d73dac2139b441bc7a843e232000000')
        self.assertEqual(SUMUWW.profile_id, 'dora-independent-v0.12-p2wpkh')
        self.assertEqual(SUMUWW_NAMESPACE, 0x444F5241)
        self.assertIs(get_network('dora'), get_network('sumuww'))

    def test_legacy_imports_share_the_same_types_and_module_state(self):
        old = importlib.import_module('dora.profiles')
        current = importlib.import_module('sumuww.profiles')
        self.assertIs(old, current)
        self.assertIs(old.DORA, SUMUWW)
        self.assertIs(importlib.import_module('dora.hd').DORA_NAMESPACE, SUMUWW_NAMESPACE)
        self.assertIs(importlib.import_module('dora.app_service').AppService,
                      importlib.import_module('sumuww.app_service').AppService)

    def test_new_and_existing_rpc_consumers_receive_identical_money(self):
        result = compatibility_fields({'wallet': {'total_smw': '12.00000000'},
                                       'fee_smw': '0.00100000'})
        self.assertEqual(result['wallet']['total_smw'], result['wallet']['total_dora'])
        self.assertEqual(result['fee_smw'], result['fee_dora'])
        shown = public_view({'node': {'network': 'dora', 'profile': SUMUWW.profile_id,
                                     'last_lookup_result': 'no_dora_contacts'}, **result})
        self.assertNotIn('dora', json.dumps(shown).lower())
        self.assertEqual(shown['wallet']['total_smw'], '12.00000000')

    def test_fresh_install_and_existing_install_select_the_right_data(self):
        with tempfile.TemporaryDirectory() as temp:
            state = Path(temp)
            with patch.dict(os.environ, {'LOCALAPPDATA': str(state), 'SUMUWW_DATA_DIR': '', 'DORA_DATA_DIR': ''}):
                self.assertEqual(default_directory(), (state/'SUMUWW/data').resolve())
                legacy = state/'DORA'
                legacy.mkdir()
                active = state/'existing-data'
                (legacy/'active-node.json').write_text(json.dumps({'directory': str(active)}))
                self.assertEqual(default_directory(), active.resolve())
                self.assertTrue((legacy/'active-node.json').exists())
                with patch.dict(os.environ, {'SUMUWW_DATA_DIR': str(state/'explicit-new')}):
                    self.assertEqual(default_directory(), (state/'explicit-new').resolve())
                with patch.dict(os.environ, {'DORA_DATA_DIR': str(state/'explicit-old')}):
                    self.assertEqual(default_directory(), (state/'explicit-old').resolve())


if __name__ == '__main__':
    unittest.main()
