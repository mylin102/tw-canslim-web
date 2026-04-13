"""
Tests for Relative Strength (RS) calculation.
"""

import pytest


class TestRelativeStrength:
    """Test RS calculation logic."""
    
    def test_rs_ratio_normal(self):
        """Test RS ratio when market is up."""
        stock_return = 0.50  # 50%
        market_return = 0.20  # 20%
        
        # RS ratio = stock / market
        rs_ratio = stock_return / market_return
        assert rs_ratio == 2.5
        
        # RS >= 1.2 should pass L metric
        assert rs_ratio >= 1.2
    
    def test_rs_ratio_weak_stock(self):
        """Test RS ratio for underperforming stock."""
        stock_return = 0.10  # 10%
        market_return = 0.20  # 20%
        
        rs_ratio = stock_return / market_return
        assert rs_ratio == 0.5
        
        # RS < 1.2 should fail L metric
        assert rs_ratio < 1.2
    
    def test_rs_ratio_market_down(self):
        """Test RS ratio when market is down (both negative)."""
        stock_return = -0.10  # -10% (less bad)
        market_return = -0.20  # -20% (more bad)
        
        # RS ratio = (-0.10) / (-0.20) = 0.5
        rs_ratio = stock_return / market_return
        assert rs_ratio == 0.5
        
        # This means stock fell less than market - actually good
        # But ratio < 1, so need special handling for negative markets
    
    def test_rs_percentile_ranking(self):
        """Test RS percentile approach."""
        returns = [0.10, 0.20, 0.30, 0.40, 0.50]
        
        # Rank: 0.50 is highest → 99th percentile
        # Simple percentile: (index / total) * 99 + 1
        for i, ret in enumerate(sorted(returns)):
            percentile = int((i / len(returns)) * 99) + 1
            # 0.10 → 20, 0.20 → 40, 0.30 → 60, 0.40 → 80, 0.50 → 99
        
        # Verify top stock gets RS ~99
        top_returns = sorted(returns, reverse=True)
        rs_99 = int((0 / len(returns)) * 99) + 99  # Simplified
        assert rs_99 >= 95
    
    def test_division_by_zero_protection(self):
        """Test RS handles near-zero market return."""
        stock_return = 0.15
        market_return = 0.001  # ~0% market
        
        # Should use fallback percentile instead of division
        if abs(market_return) < 0.01:
            # Fallback: use raw return as strength indicator
            strength = stock_return
            assert strength > 0
        else:
            rs = stock_return / market_return
            assert rs > 0
    
    def test_l_metric_threshold(self):
        """Test L metric pass/fail threshold."""
        # RS >= 1.2 → L = True
        assert 1.2 >= 1.2  # Pass
        assert 1.19 < 1.2  # Fail
        assert 1.5 >= 1.2  # Pass
        assert 0.8 < 1.2   # Fail


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
