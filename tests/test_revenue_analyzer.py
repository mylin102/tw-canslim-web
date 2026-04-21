import pytest
import pandas as pd
import numpy as np
from revenue_analyzer import calculate_revenue_features, calculate_revenue_score

def create_mock_revenue_data(revenues):
    """Helper to create mock revenue DataFrame."""
    dates = pd.date_range(end='2024-01-01', periods=len(revenues), freq='ME')
    df = pd.DataFrame({
        'mdate': dates,
        'r16': revenues
    })
    return df

def test_calculate_revenue_features_valid():
    # Create 15 months of increasing revenue
    # Month 1-12: 100
    # Month 13: 110 (YoY prev2: (110-100)/100 = 0.1)
    # Month 14: 130 (YoY prev: (130-100)/100 = 0.3)
    # Month 15: 160 (YoY now: (160-100)/100 = 0.6)
    
    # rev_yoy_now = 0.6
    # rev_yoy_prev = 0.3
    # rev_yoy_prev2 = 0.1
    # rev_mom = (160-130)/130 = 0.2307...
    # rev_acc_1 = 0.6 - 0.3 = 0.3
    # rev_acc_2 = 0.3 - 0.1 = 0.2
    
    revenues = [100] * 12 + [110, 130, 160]
    df = create_mock_revenue_data(revenues)
    
    features = calculate_revenue_features(df)
    
    assert features is not None
    assert pytest.approx(features['rev_yoy'], 0.001) == 0.6
    assert pytest.approx(features['rev_mom'], 0.001) == 0.2307
    assert pytest.approx(features['rev_acc_1'], 0.001) == 0.3
    assert pytest.approx(features['rev_acc_2'], 0.001) == 0.2
    assert features['rev_accelerating'] == True
    assert features['rev_strong'] == True
    assert features['revenue_score'] == 6

def test_calculate_revenue_features_insufficient_data():
    df = create_mock_revenue_data([100] * 14)
    features = calculate_revenue_features(df)
    assert features is None

def test_calculate_revenue_features_flat():
    revenues = [100] * 15
    df = create_mock_revenue_data(revenues)
    features = calculate_revenue_features(df)
    
    assert features['rev_yoy'] == 0.0
    assert features['rev_mom'] == 0.0
    assert features['rev_acc_1'] == 0.0
    assert features['rev_acc_2'] == 0.0
    assert features['rev_accelerating'] == False
    assert features['rev_strong'] == False
    assert features['revenue_score'] == 0

def test_calculate_revenue_score():
    features = {
        'rev_yoy': 0.6,
        'rev_mom': 0.15,
        'rev_acc_1': 0.1,
        'rev_acc_2': 0.05
    }
    # yoy > 0.25 (+1), yoy > 0.5 (+1) -> 2
    # mom > 0 (+1), mom > 0.1 (+1) -> 4
    # acc_1 > 0 (+1) -> 5
    # acc_2 > 0 (+1) -> 6
    assert calculate_revenue_score(features) == 6
    
    features['rev_yoy'] = 0.3
    # yoy > 0.25 (+1) -> 1
    # mom > 0 (+1), mom > 0.1 (+1) -> 3
    # acc_1 > 0 (+1) -> 4
    # acc_2 > 0 (+1) -> 5
    assert calculate_revenue_score(features) == 5

def test_handle_zero_division():
    # Year ago revenue is 0
    revenues = [0] * 12 + [110, 130, 160]
    df = create_mock_revenue_data(revenues)
    features = calculate_revenue_features(df)
    # Should handle gracefully, maybe return 0 or None for YoY
    # In pandas, x/0 is inf.
    assert features is not None
    # If we handle it by returning 0 or a very large number, we should be consistent.
    # Usually we cap it or skip it.
