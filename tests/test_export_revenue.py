import json
import os
from pathlib import Path
from unittest.mock import MagicMock
import pytest
from export_canslim import CanslimEngine

@pytest.fixture
def engine(tmp_path):
    # Set up a mock engine and its environment
    with MagicMock() as mock_engine:
        # We'll use a real CanslimEngine but mock some methods
        real_engine = CanslimEngine()
        # Mock get_all_tw_tickers as it hits network
        real_engine.ticker_info = {"2330": {"name": "TSMC", "suffix": ".TW"}}
        # Mock Excel processor to avoid file I/O
        real_engine.excel_processor = MagicMock()
        real_engine.excel_ratings = {}
        real_engine.fund_holdings = {}
        real_engine.industry_data = {}
        real_engine.industry_strength = []
        
        # Override output_data for the test
        real_engine.output_data = {
            "stocks": {
                "2330": {
                    "symbol": "2330",
                    "name": "TSMC",
                    "industry": "Semiconductors",
                    "canslim": {
                        "score": 80,
                        "revenue_score": 6.0,
                        "rev_accelerating": True,
                        "rev_strong": True,
                        "N": True,
                        "mansfield_rs": 1.5
                    }
                }
            },
            "industry_strength": [{"industry": "Semiconductors", "avg_score": 80}]
        }
        return real_engine

def test_export_leaders_json_blends_revenue(engine, tmp_path):
    # Mock selection
    selection = MagicMock()
    selection.core_symbols = ["2330"]
    
    # Mock SCRIPT_DIR to tmp_path so it writes leaders.json there
    import export_canslim
    original_script_dir = export_canslim.SCRIPT_DIR
    export_canslim.SCRIPT_DIR = str(tmp_path)
    
    try:
        engine._export_leaders_json(selection)
        
        leaders_file = tmp_path / "data" / "leaders.json"
        assert leaders_file.exists()
        
        with open(leaders_file, "r", encoding="utf-8") as f:
            payload = json.load(f)
            
        universe = payload["universe"]
        assert len(universe) == 1
        tsmc = universe[0]
        assert tsmc["symbol"] == "2330"
        
        # New three-factor formula:
        # blended = 0.4 * (80/100) + 0.3 * rs_weight + 0.3 * (6/6)
        # rs_rating = min(99, max(1, 50 + int(1.5 * 5))) = min(99, 57) = 57
        # rs_weight = 57/100 = 0.57
        # blended = 0.4*0.80 + 0.3*0.57 + 0.3*1.0 = 0.32 + 0.171 + 0.30 = 0.791
        assert tsmc["composite_score"] == 0.791
        
        # Tags
        assert "rev_acc" in tsmc["tags"]
        assert "rev_strong" in tsmc["tags"]
        assert "breakout_candidate" in tsmc["tags"] # Because N is True
        
    finally:
        export_canslim.SCRIPT_DIR = original_script_dir

def test_export_leaders_json_missing_revenue(engine, tmp_path):
    # Mock stock without revenue data
    engine.output_data["stocks"]["2330"]["canslim"] = {
        "score": 80,
        "N": False,
        "mansfield_rs": 1.5
    }
    
    selection = MagicMock()
    selection.core_symbols = ["2330"]
    
    import export_canslim
    original_script_dir = export_canslim.SCRIPT_DIR
    export_canslim.SCRIPT_DIR = str(tmp_path)
    
    try:
        engine._export_leaders_json(selection)
        
        leaders_file = tmp_path / "data" / "leaders.json"
        with open(leaders_file, "r", encoding="utf-8") as f:
            payload = json.load(f)
            
        tsmc = payload["universe"][0]
        # New three-factor formula with missing revenue:
        # rs_rating = min(99, max(1, 50 + int(1.5 * 5))) = min(99, 57) = 57
        # blended = 0.4 * (80/100) + 0.3 * (57/100) + 0.3 * (0/6)
        #         = 0.32 + 0.171 + 0.0 = 0.491
        assert tsmc["composite_score"] == 0.491
        assert "rev_acc" not in tsmc["tags"]
        assert "rev_strong" not in tsmc["tags"]
        
    finally:
        export_canslim.SCRIPT_DIR = original_script_dir
