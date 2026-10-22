"""Selected network must bind wallets, addresses and the local chain."""

import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from sumuww.__main__ import main
from sumuww.chain import Chain
from sumuww.keystore import create_wallet
from sumuww.profiles import REGTEST, RETARGET_LAB

PASSWORD = 'network-cli-test-password'


class NetworkCliTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='network-cli-')
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.database = self.directory / 'chain.sqlite'
        self.wallet = self.directory / 'wallet.json'
        self.password = self.directory / 'password.txt'
        self.password.write_text(PASSWORD + '\n')

    def invoke(self, *arguments):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = main(list(arguments))
        self.assertNotIn(PASSWORD, out.getvalue() + err.getvalue())
        return code, json.loads(out.getvalue() or err.getvalue())

    def test_genesis_cli_selects_explicit_profile_without_database(self):
        for network in (REGTEST, RETARGET_LAB):
            code, result = self.invoke('--network', network.name, 'genesis')
            self.assertEqual(code, 0)
            self.assertEqual(result['profile'], network.profile_id)
            self.assertEqual(result['hash'], network.genesis.block_hash()[::-1].hex())
            self.assertEqual(result['no_retarget'], network.no_retarget)
        self.assertFalse(self.database.exists())

    def test_wallet_create_cli_sets_laboratory_address_and_no_database(self):
        code, result = self.invoke('--network', 'retarget-lab', '--database', str(self.database), 'wallet-create', '--wallet', str(self.wallet), '--password-file', str(self.password))
        self.assertEqual(code, 0)
        self.assertEqual(result['network'], 'retarget-lab')
        self.assertTrue(result['address'].startswith('dtl1'))
        self.assertFalse(self.database.exists())

    def test_wrong_network_wallet_rejected_before_chain_creation(self):
        key = create_wallet(self.wallet, PASSWORD, network=RETARGET_LAB)
        before = self.wallet.read_bytes()
        code, error = self.invoke('--database', str(self.database), 'wallet-send', '--wallet', str(self.wallet), '--password-file', str(self.password), '--to-address', key.address, '--amount', '1')
        self.assertEqual(code, 2)
        self.assertEqual(error['error'], 'WalletFormatError')
        self.assertFalse(self.database.exists())
        self.assertEqual(self.wallet.read_bytes(), before)

    def test_wrong_network_address_rejected_before_database_creation(self):
        from sumuww.address import encode_address
        address = encode_address(b'\x00\x14' + b'\x01' * 20, network=RETARGET_LAB)
        code, _ = self.invoke('--database', str(self.database), 'mine', '--address', address)
        self.assertEqual(code, 2)
        self.assertFalse(self.database.exists())

    def test_wrong_database_profile_cli_preserves_history(self):
        with Chain(self.database) as chain:
            before = chain.info()
        code, error = self.invoke('--network', 'retarget-lab', '--database', str(self.database), 'info')
        self.assertEqual(code, 2)
        self.assertEqual(error['error'], 'StorageError')
        with Chain(self.database) as chain:
            self.assertEqual(chain.info()['tip'], before['tip'])
            self.assertEqual(chain.info()['utxo_commitment'], before['utxo_commitment'])


if __name__ == '__main__':
    unittest.main()
