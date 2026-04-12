import pytest
import os
import sys
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from export_canslim import CanslimEngine, C_QUARTERLY_GROWTH_THRESHOLD


class TestCanslimEngine:
    """Test suite for CANSLIM engine."""
    
    @pytest.fixture
    def engine(self):
        """Create a CanslimEngine instance."""
        return CanslimEngine()
    
    def test_safe_int_with_normal_input(self, engine):
        """Test _safe_int with normal integer input."""
        assert engine._safe_int("1000") == 1000
        assert engine._safe_int("1,234") == 1234
    
    def test_safe_int_with_edge_cases(self, engine):
        """Test _safe_int with edge cases."""
        assert engine._safe_int("") == 0
        assert engine._safe_int(None) == 0
        assert engine._safe_int("-") == 0
    
    def test_check_c_quarterly_growth_pass(self, engine):
        """Test C metric: 25% growth should pass."""
        current_eps = 5.0
        previous_eps = 4.0  # 25% growth
        assert engine.check_c_quarterly_growth(current_eps, previous_eps) == True
    
    def test_check_c_quarterly_growth_fail(self, engine):
        """Test C metric: less than 25% growth should fail."""
        current_eps = 4.5
        previous_eps = 4.0  # 12.5% growth
        assert engine.check_c_quarterly_growth(current_eps, previous_eps) == False
    
    def test_check_c_quarterly_growth_zero_eps(self, engine):
        """Test C metric: zero or negative EPS should fail."""
        assert engine.check_c_quarterly_growth(0, 4.0) == False
        assert engine.check_c_quarterly_growth(5.0, 0) == False
        assert engine.check_c_quarterly_growth(-1.0, 4.0) == False
    
    def test_check_a_annual_growth_pass(self, engine):
        """Test A metric: 3-year CAGR >= 25% should pass."""
        eps_history = [4.0, 5.0, 6.0, 8.0]  # 100% growth over 3 years
        assert engine.check_a_annual_growth(eps_history) == True
    
    def test_check_a_annual_growth_fail(self, engine):
        """Test A metric: low CAGR should fail."""
        eps_history = [4.0, 4.1, 4.2, 4.3]  # Minimal growth
        assert engine.check_a_annual_growth(eps_history) == False
    
    def test_check_n_new_high_pass(self, engine):
        """Test N metric: price near 52-week high should pass."""
        assert engine.check_n_new_high(180, 200) == True  # 90% of high
    
    def test_check_n_new_high_fail(self, engine):
        """Test N metric: price far from 52-week high should fail."""
        assert engine.check_n_new_high(150, 200) == False  # 75% of high
    
    def test_check_s_volume_pass(self, engine):
        """Test S metric: volume >= 150% of average should pass."""
        assert engine.check_s_volume(15000, 10000) == True
    
    def test_check_s_volume_fail(self, engine):
        """Test S metric: volume < 150% of average should fail."""
        assert engine.check_s_volume(12000, 10000) == False
    
    def test_check_i_institutional_pass(self, engine):
        """Test I metric: consecutive net buying should pass."""
        inst_history = [
            {"foreign_net": 100, "trust_net": 50, "dealer_net": 20},
            {"foreign_net": 80, "trust_net": 30, "dealer_net": 10},
            {"foreign_net": 120, "trust_net": 40, "dealer_net": 15}
        ]
        assert engine.check_i_institutional(inst_history) == True
    
    def test_check_i_institutional_fail(self, engine):
        """Test I metric: net selling should fail."""
        inst_history = [
            {"foreign_net": -100, "trust_net": -50, "dealer_net": -20},
            {"foreign_net": -80, "trust_net": -30, "dealer_net": -10},
            {"foreign_net": -120, "trust_net": -40, "dealer_net": -15}
        ]
        assert engine.check_i_institutional(inst_history) == False
    
    def test_calculate_canslim_score_all_pass(self, engine):
        """Test score calculation: all metrics pass should give ~100."""
        score = engine.calculate_canslim_score(True, True, True, True, True, True, True)
        assert score == 100
    
    def test_calculate_canslim_score_partial(self, engine):
        """Test score calculation: partial metrics pass."""
        score = engine.calculate_canslim_score(True, False, True, False, True, True, True)
        # 5 metrics pass = 5 * 14 = 70, no C&A bonus
        assert score == 70
    
    def test_calculate_canslim_score_c_a_bonus(self, engine):
        """Test score calculation: C and A both pass gives bonus."""
        score = engine.calculate_canslim_score(True, True, False, False, False, False, False)
        # 2 metrics pass = 2 * 14 = 28, C&A bonus = 2, total = 30
        assert score == 30
    
    def test_validate_stock_data_valid(self, engine):
        """Test validation: valid stock data should pass."""
        data = {
            "symbol": "2330",
            "name": "台積電",
            "canslim": {
                "C": True, "A": True, "N": True, "S": True,
                "L": True, "I": True, "M": True, "score": 100
            },
            "institutional": []
        }
        assert engine.validate_stock_data(data) == True
    
    def test_validate_stock_data_missing_keys(self, engine):
        """Test validation: missing keys should fail."""
        data = {
            "symbol": "2330",
            "name": "台積電"
        }
        assert engine.validate_stock_data(data) == False
    
    def test_validate_stock_data_missing_canslim_keys(self, engine):
        """Test validation: missing CANSLIM keys should fail."""
        data = {
            "symbol": "2330",
            "name": "台積電",
            "canslim": {"C": True},
            "institutional": []
        }
        assert engine.validate_stock_data(data) == False


class TestCANSLIMThresholds:
    """Test CANSLIM threshold constants."""
    
    def test_c_threshold_value(self):
        """Verify C threshold is 25%."""
        from export_canslim import C_QUARTERLY_GROWTH_THRESHOLD
        assert C_QUARTERLY_GROWTH_THRESHOLD == 0.25
    
    def test_n_threshold_value(self):
        """Verify N threshold is 90% of 52-week high."""
        from export_canslim import N_NEW_HIGH_THRESHOLD
        assert N_NEW_HIGH_THRESHOLD == 0.90
    
    def test_s_threshold_value(self):
        """Verify S threshold is 150% of average volume."""
        from export_canslim import S_VOLUME_THRESHOLD
        assert S_VOLUME_THRESHOLD == 1.5


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
