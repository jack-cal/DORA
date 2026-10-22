"""Disposable wallet checks using Windows/Linux crypto wheels, not Android ABI adapters."""
from pathlib import Path
import importlib.util
import json
import sys
import unittest

import coincurve, coincurve.ecdsa
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'app/src/main/python'))
spec = importlib.util.spec_from_file_location('standalone_wallet_flow', ROOT / 'tests/test_wallet_flow.py')
base = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = base
spec.loader.exec_module(base)
sys.path.insert(0, str(ROOT / 'tests'))
from test_additional_wallet import AdditionalWalletChecks
suite = unittest.TestSuite([unittest.defaultTestLoader.loadTestsFromModule(base),
                           unittest.defaultTestLoader.loadTestsFromTestCase(AdditionalWalletChecks)])
result = unittest.TextTestRunner(verbosity=2).run(suite)
if not result.wasSuccessful(): sys.exit(1)
print(json.dumps({'wallet_flow_cases': result.testsRun, 'status': 'passed'}))
