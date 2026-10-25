import unittest
from smw_trade.market.fee_quote import quote,validate_settings


class LiveMarketFeeTests(unittest.TestCase):
    def test_live_congestion_changes_quotes_and_modes(self):
        self.assertEqual(150,quote(150,[],1))
        busy=[[20,2_000_000],[5,2_000_000]]
        self.assertGreater(quote(150,busy,1,'fast'),quote(150,busy,1,'normal'))
        self.assertGreater(quote(150,busy,1,'normal'),quote(150,busy,1,'slow'))

    def test_manual_floor_cap_and_invalid_values(self):
        self.assertEqual(300,quote(150,[],1,manual='2'))
        for value in ('0','-1','NaN','Infinity'):
            with self.assertRaises(ValueError):validate_settings({'fee_rate':value})
        with self.assertRaisesRegex(ValueError,'relay minimum'):quote(150,[],2,manual='1')
        with self.assertRaisesRegex(ValueError,'spending limit'):quote(1000000,[],1,manual='2')
