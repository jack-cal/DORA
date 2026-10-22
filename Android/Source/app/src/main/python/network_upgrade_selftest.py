"""Disposable Android runtime checks; never uses the application's wallet DB."""
import io
import json
import unittest

def run(vectors):
    stream = io.StringIO()
    names = ['pc_tests.test_asert_upgrade.AsertTests.test_extreme_delta_is_bounded',
             'pc_tests.test_dgw_upgrade',
             'pc_tests.test_asert_upgrade.AsertTests.test_actual_branch_ancestry_and_activation',
             'pc_tests.test_asert_upgrade.AsertTests.test_chain_replay_template_summary_and_wrong_bits',
             'pc_tests.test_privacy_transport',
             'pc_tests.test_peer_exploration']
    result = unittest.TextTestRunner(stream=stream).run(unittest.defaultTestLoader.loadTestsFromNames(names))
    from sumuww.profiles import SUMUWW
    from sumuww.asert import next_bits
    from sumuww.primitives import valid_target
    limit = valid_target(0x1d00ffff, (1 << 256)-1)
    cases = json.loads(vectors)
    vector_ok = all(next_bits(a,t,h,limit) == expected for a,t,h,expected in cases)
    return json.dumps({'passed': result.wasSuccessful() and vector_ok, 'tests': result.testsRun,
                       'official_asert_vectors': len(cases), 'vectors_passed': vector_ok,
                       'activation_height': SUMUWW.dgw_activation_height,
                       'algorithm': 'DGW v3',
                       'output': stream.getvalue()})
