"""Exercise the explorer's real difficulty prediction across 9000/9010."""
import unittest
from test_explorer import ExplorerTests


class DgwTenBlockReaderTests(unittest.TestCase):
    setUp = ExplorerTests.setUp
    tearDown = ExplorerTests.tearDown
    make = ExplorerTests.make
    add = ExplorerTests.add

    def test_post_activation_holds_until_tenth_block(self):
        parent = self.two
        for height in range(3, 9001):
            parent = self.make(parent, height)
            self.add(parent, height)
        self.c.commit()
        self.explorer.refresh(force=True)
        data = self.explorer.run('mining_analysis', 24)
        self.assertEqual(data['next_height'], 9001)
        self.assertEqual(data['current_bits'], data['next_bits'])
        self.assertEqual(data['next_change_percent'], 0)
        for height in range(9001, 9010):
            parent = self.make(parent, height)
            self.add(parent, height)
        self.c.commit()
        self.explorer.refresh(force=True)
        data = self.explorer.run('mining_analysis', 24)
        self.assertEqual(data['next_height'], 9010)
        # DGW uses 23 timestamp gaps in a 24-block observation window.
        self.assertNotEqual(data['current_bits'], data['next_bits'])
