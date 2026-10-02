import unittest
import pandas as pd
import sys
import os

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.logic import calculate_i_factor, calculate_accumulation_strength, compute_canslim_score

class TestInstitutionalLogic(unittest.TestCase):
    def setUp(self):
        # Create a sample chip dataframe
        # Values are in LOTS (1 lot = 1000 shares)
        self.sample_df = pd.DataFrame({
            'date': ['20260401', '20260402', '20260403', '20260404', '20260405'],
            'foreign_net': [100, 200, -50, 300, 150],
            'trust_net': [50, 50, 50, 50, 50],
            'dealer_net': [10, -20, 30, -10, 20]
        })
        # Total net for last 3 days: (-50+50+30) + (300+50-10) + (150+50+20) 
        # = 30 + 340 + 220 = 590 lots
        
        # Total net for last 5 days:
        # (100+50+10) + (200+50-20) + 30 + 340 + 220
        # = 160 + 230 + 590 = 980 lots
        
        self.total_shares = 10000000  # 10M shares

    def test_accumulation_strength_calculation(self):
        # 5 days accumulation: 980 lots * 1000 / 10,000,000 = 980,000 / 10,000,000 = 0.098 (9.8%)
        strength = calculate_accumulation_strength(self.sample_df, self.total_shares, days=5)
        self.assertAlmostEqual(strength, 0.098)

    def test_i_factor_basic(self):
        # Last 3 days sum is 590 > 0
        self.assertTrue(calculate_i_factor(self.sample_df, days=3))

    def test_i_factor_with_shares_and_conviction(self):
        # Strength is 0.098 which is > 0.002
        self.assertTrue(calculate_i_factor(self.sample_df, days=3, total_shares=self.total_shares))
        
        # Test with very large share count where conviction should fail
        large_shares = 1000000000 # 1B shares
        # 980,000 / 1,000,000,000 = 0.00098 (< 0.002)
        self.assertFalse(calculate_i_factor(self.sample_df, days=3, total_shares=large_shares))

    def test_canslim_score_bonus(self):
        # v2 weights: C=25, A=20, N=15, S=10, L=15, I=15 (M is a 1.0x/0.7x multiplier, not additive)
        factors = {'C': True, 'A': True, 'N': True, 'S': True, 'L': True, 'I': True, 'M': True}
        # All factors pass -> full 100, regardless of institutional_strength, since the
        # boolean I factor alone grants full I weight (see compute_canslim_score).
        base_score = compute_canslim_score(factors, institutional_strength=0.0)
        self.assertEqual(base_score, 100)

        # Missing C and A: N(15) + S(10) + L(15) + I(15) = 55, M multiplier is 1.0
        factors_80 = {'C': False, 'A': False, 'N': True, 'S': True, 'L': True, 'I': True, 'M': True}
        score_55 = compute_canslim_score(factors_80, institutional_strength=0.0)
        self.assertEqual(score_55, 55)

        # institutional_strength only matters once it's explicitly passed; here 0.006
        # saturates i_score_abs at the same 100% the boolean fallback already gave,
        # so the score is unchanged.
        score_55_explicit = compute_canslim_score(factors_80, institutional_strength=0.006)
        self.assertEqual(score_55_explicit, 55)

    def test_edge_cases(self):
        # Zero shares
        self.assertEqual(calculate_accumulation_strength(self.sample_df, 0), 0.0)
        # Empty df
        empty_df = pd.DataFrame(columns=['foreign_net', 'trust_net', 'dealer_net'])
        self.assertEqual(calculate_accumulation_strength(empty_df, 1000), 0.0)
        self.assertFalse(calculate_i_factor(empty_df, days=3))

if __name__ == '__main__':
    unittest.main()
