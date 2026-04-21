import json
from pathlib import Path
import pandas as pd
import pytest
from core_selection import (
    load_selector_inputs, 
    RankedCandidate, 
    _ranked_candidate_sort_key,
    build_core_universe
)

@pytest.fixture
def mock_artifacts(tmp_path):
    config_path = tmp_path / "core_selection_config.json"
    config_path.write_text(json.dumps({
        "base_symbols": ["2330"],
        "etf_symbols": ["0050"],
        "watchlist_symbols": [],
        "target_size": 10
    }))
    
    fused_path = tmp_path / "fused.parquet"
    fused_df = pd.DataFrame([
        {"stock_id": "2330", "date": "2024-01-02", "score": 80, "rs_rating": 85, "latest_volume": 1000, "volume_rank": 1},
        {"stock_id": "2454", "date": "2024-01-02", "score": 90, "rs_rating": 90, "latest_volume": 500, "volume_rank": 2},
        {"stock_id": "2317", "date": "2024-01-02", "score": 70, "rs_rating": 75, "latest_volume": 800, "volume_rank": 3},
    ])
    fused_df.to_parquet(fused_path)
    
    master_path = tmp_path / "master.parquet"
    master_df = pd.DataFrame([
        {"stock_id": "2330", "date": "2024-01-02", "score": 80, "latest_volume": 1000, "volume_rank": 1},
        {"stock_id": "2454", "date": "2024-01-02", "score": 90, "latest_volume": 500, "volume_rank": 2},
        {"stock_id": "2317", "date": "2024-01-02", "score": 70, "latest_volume": 800, "volume_rank": 3},
    ])
    master_df.to_parquet(master_path)
    
    baseline_path = tmp_path / "baseline.json"
    baseline_path.write_text(json.dumps({
        "stocks": {
            "2330": {"canslim": {"mansfield_rs": 1.5}},
            "2454": {"canslim": {"mansfield_rs": 2.0}},
            "2317": {"canslim": {"mansfield_rs": 0.5}}
        }
    }))
    
    revenue_path = tmp_path / "stock_features.json"
    revenue_path.write_text(json.dumps({
        "2317": {"revenue_score": 6, "rev_accelerating": True},
        "2454": {"revenue_score": 4, "rev_accelerating": True},
        "2330": {"revenue_score": 5, "rev_accelerating": False}
    }))
    
    return {
        "config_path": config_path,
        "fused_path": fused_path,
        "master_path": master_path,
        "baseline_path": baseline_path,
        "revenue_path": revenue_path
    }

def test_load_selector_inputs_with_revenue(mock_artifacts):
    inputs = load_selector_inputs(
        config_path=mock_artifacts["config_path"],
        fused_path=mock_artifacts["fused_path"],
        master_path=mock_artifacts["master_path"],
        baseline_path=mock_artifacts["baseline_path"],
        revenue_path=mock_artifacts["revenue_path"]
    )
    
    # Check new bucket
    assert "revenue_alpha_leaders" in inputs
    # 2317 has score 6 and accelerating True -> should be in
    # 2454 has score 4 (too low) -> out
    # 2330 has accelerating False -> out
    assert inputs["revenue_alpha_leaders"] == ["2317"]
    
    # Check RankedCandidate revenue_score
    candidates = {c.symbol: c for c in inputs["ranked_candidates"]}
    assert candidates["2317"].revenue_score == 6.0
    assert candidates["2454"].revenue_score == 4.0
    assert candidates["2330"].revenue_score == 5.0

def test_ranked_candidate_sorting_prioritizes_revenue():
    c1 = RankedCandidate(symbol="1111", mansfield_rs=10.0, revenue_score=5.0)
    c2 = RankedCandidate(symbol="2222", mansfield_rs=20.0, revenue_score=4.0)
    c3 = RankedCandidate(symbol="3333", mansfield_rs=5.0, revenue_score=6.0)
    
    # Sorted list: highest revenue score first
    sorted_candidates = sorted([c1, c2, c3], key=_ranked_candidate_sort_key)
    assert sorted_candidates[0].symbol == "3333" # rev 6.0
    assert sorted_candidates[1].symbol == "1111" # rev 5.0
    assert sorted_candidates[2].symbol == "2222" # rev 4.0

def test_build_core_universe_includes_revenue_bucket(mock_artifacts):
    result = build_core_universe(
        all_symbols=["2330", "2454", "2317", "0050"],
        config_path=mock_artifacts["config_path"],
        fused_path=mock_artifacts["fused_path"],
        master_path=mock_artifacts["master_path"],
        baseline_path=mock_artifacts["baseline_path"],
        revenue_path=mock_artifacts["revenue_path"],
        target_size=10
    )
    
    assert "revenue_alpha_leaders" in result.bucket_symbols
    assert result.bucket_symbols["revenue_alpha_leaders"] == ["2317"]
    # Check BUCKET_ORDER (today_signals is after revenue_alpha_leaders in my plan, 
    # but plan says "after 'today_signals'")
    # Plan says: build_core_universe includes 'revenue_alpha_leaders' in BUCKET_ORDER after 'today_signals'.
    
    # Check if 2317 is in core_symbols
    assert "2317" in result.core_symbols
