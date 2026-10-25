"""Run disposable node-feature examples and regression scenarios."""
import sys
from pathlib import Path
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
if __name__ == "__main__":
    suite=unittest.defaultTestLoader.loadTestsFromNames(["tests.test_fee_policy_v43","tests.test_spending_v43","tests.test_node_contract"])
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    raise SystemExit(not result.wasSuccessful())
