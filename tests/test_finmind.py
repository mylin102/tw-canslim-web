"""
Unit tests for FinMind data processor.
Tests FinMind API integration BEFORE implementation (TDD approach).
"""

import pytest
from unittest.mock import Mock, patch
from datetime import datetime, timedelta


class TestFinMindProcessor:
    """Test suite for FinMind data processor."""
    
    @pytest.fixture
    def mock_institutional_data(self):
        """Mock institutional investors data response."""
        import pandas as pd
        return pd.DataFrame({
            'date': ['2026-04-07', '2026-04-07', '2026-04-07',
                     '2026-04-08', '2026-04-08', '2026-04-08'],
            'stock_id': ['2330'] * 6,
            'buy': [0, 59000, 13401937, 0, 1252000, 34485923],
            'name': ['Foreign_Dealer_Self', 'Dealer_self', 'Foreign_Investor',
                     'Foreign_Dealer_Self', 'Dealer_self', 'Foreign_Investor'],
            'sell': [0, 95136, 7521487, 0, 158000, 16092438]
        })
    
    def test_finmind_processor_initialization(self):
        """Test FinMindProcessor can be initialized."""
        from finmind_processor import FinMindProcessor
        processor = FinMindProcessor()
        assert processor is not None
        assert hasattr(processor, 'dl')
        assert hasattr(processor, 'investor_name_map')
    
    def test_fetch_institutional_investors(self, mock_institutional_data):
        """Test fetching institutional investors data."""
        try:
            from finmind_processor import FinMindProcessor
            
            with patch('finmind_processor.DataLoader') as mock_loader:
                mock_loader.return_value.taiwan_stock_institutional_investors.return_value = mock_institutional_data
                
                processor = FinMindProcessor()
                result = processor.fetch_institutional_investors(
                    stock_id="2330",
                    start_date="2026-04-07",
                    end_date="2026-04-08"
                )
                
                assert result is not None
                assert len(result) > 0
                assert 'date' in result.columns
                assert 'stock_id' in result.columns
        except ImportError:
            pytest.skip("FinMindProcessor not implemented yet")
    
    def test_parse_institutional_data(self, mock_institutional_data):
        """Test parsing and aggregating institutional data."""
        try:
            from finmind_processor import FinMindProcessor
            
            processor = FinMindProcessor()
            result = processor.parse_institutional_data(mock_institutional_data)
            
            # Should have aggregated by date
            assert result is not None
            assert isinstance(result, dict)
            
            # Check structure
            for date, data in result.items():
                assert 'foreign_net' in data
                assert 'trust_net' in data
                assert 'dealer_net' in data
                assert isinstance(data['foreign_net'], int)
                assert isinstance(data['trust_net'], int)
                assert isinstance(data['dealer_net'], int)
        except ImportError:
            pytest.skip("FinMindProcessor not implemented yet")
    
    def test_calculate_net_buy_sell(self):
        """Test net buy/sell calculation."""
        try:
            from finmind_processor import FinMindProcessor
            
            processor = FinMindProcessor()
            
            # Test basic calculation
            buy = 1000
            sell = 600
            net = processor.calculate_net(buy, sell)
            assert net == 400
            
            # Test negative net
            buy = 500
            sell = 800
            net = processor.calculate_net(buy, sell)
            assert net == -300
        except ImportError:
            pytest.skip("FinMindProcessor not implemented yet")
    
    def test_map_investor_names(self):
        """Test mapping English names to Chinese."""
        try:
            from finmind_processor import FinMindProcessor
            
            processor = FinMindProcessor()
            
            # Test mappings
            assert processor.map_investor_name('Foreign_Investor') == '外資'
            assert processor.map_investor_name('Investment_Trust') == '投信'
            assert processor.map_investor_name('Dealer_self') == '自營商'
            assert processor.map_investor_name('Dealer_Hedging') == '自營商避險'
            assert processor.map_investor_name('Unknown') == 'Unknown'
        except ImportError:
            pytest.skip("FinMindProcessor not implemented yet")
    
    def test_fetch_recent_trading_days(self, mock_institutional_data):
        """Test fetching last N trading days."""
        try:
            from finmind_processor import FinMindProcessor
            
            with patch('finmind_processor.DataLoader') as mock_loader:
                mock_loader.return_value.taiwan_stock_institutional_investors.return_value = mock_institutional_data
                
                processor = FinMindProcessor()
                result = processor.fetch_recent_trading_days(
                    stock_id="2330",
                    days=5
                )
                
                assert result is not None
                # Should return parsed data structure
                assert isinstance(result, dict)
        except ImportError:
            pytest.skip("FinMindProcessor not implemented yet")
    
    def test_handle_api_failure(self):
        """Test graceful handling of API failures."""
        try:
            from finmind_processor import FinMindProcessor
            
            with patch('finmind_processor.DataLoader') as mock_loader:
                mock_loader.side_effect = Exception("API Error")
                
                processor = FinMindProcessor()
                
                # Should not raise exception
                result = processor.fetch_institutional_investors(
                    stock_id="2330",
                    start_date="2026-04-07",
                    end_date="2026-04-08"
                )
                
                # Should return empty or None gracefully
                assert result is None or len(result) == 0
        except ImportError:
            pytest.skip("FinMindProcessor not implemented yet")
    
    def test_handle_missing_stock_data(self):
        """Test handling data for non-existent stock."""
        try:
            from finmind_processor import FinMindProcessor
            
            with patch('finmind_processor.DataLoader') as mock_loader:
                # Return empty DataFrame
                import pandas as pd
                mock_loader.return_value.taiwan_stock_institutional_investors.return_value = pd.DataFrame()
                
                processor = FinMindProcessor()
                result = processor.fetch_institutional_investors(
                    stock_id="9999",  # Invalid stock
                    start_date="2026-04-07",
                    end_date="2026-04-08"
                )
                
                # Should handle gracefully
                assert result is None or len(result) == 0
        except ImportError:
            pytest.skip("FinMindProcessor not implemented yet")


class TestFinMindIntegration:
    """Integration tests for FinMind with CANSLIM engine."""
    
    def test_finmind_data_in_canslim_score(self):
        """Test that FinMind data affects CANSLIM I score."""
        try:
            from finmind_processor import FinMindProcessor
            from export_canslim import CanslimEngine
            
            # Create processor with mock data
            processor = FinMindProcessor()
            
            # Mock: 3 consecutive days of net buying by institutions
            mock_data = {
                '2026-04-07': {'foreign_net': 1000, 'trust_net': 500, 'dealer_net': 200},
                '2026-04-08': {'foreign_net': 800, 'trust_net': 300, 'dealer_net': 100},
                '2026-04-09': {'foreign_net': 1200, 'trust_net': 400, 'dealer_net': 150}
            }
            
            # I metric should be True (consecutive buying)
            engine = CanslimEngine()
            i_score = engine.check_i_institutional(
                [
                    {'foreign_net': 1000, 'trust_net': 500, 'dealer_net': 200, 'date': '20260407'},
                    {'foreign_net': 800, 'trust_net': 300, 'dealer_net': 100, 'date': '20260408'},
                    {'foreign_net': 1200, 'trust_net': 400, 'dealer_net': 150, 'date': '20260409'}
                ]
            )
            
            assert i_score == True
            
            # Test selling scenario
            selling_data = [
                {'foreign_net': -1000, 'trust_net': -500, 'dealer_net': -200, 'date': '20260407'},
                {'foreign_net': -800, 'trust_net': -300, 'dealer_net': -100, 'date': '20260408'},
                {'foreign_net': -1200, 'trust_net': -400, 'dealer_net': -150, 'date': '20260409'}
            ]
            
            i_score_selling = engine.check_i_institutional(selling_data)
            assert i_score_selling == False
            
        except ImportError:
            pytest.skip("FinMindProcessor not implemented yet")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
