
import pytest
import pandas as pd
import numpy as np
from core.logic import (
    calculate_c_factor, 
    calculate_a_factor, 
    calculate_accumulation_strength,
    calculate_mansfield_rs,
    calculate_volatility_grid,
    compute_canslim_score,
    compute_canslim_score_etf
)

def test_calculate_c_factor():
    # Case 1: Normal growth >= 25%
    eps = pd.Series([1.0, 1.1, 1.2, 1.3, 2.0]) # iloc[-1]=2.0, iloc[-5]=1.0
    assert calculate_c_factor(eps) == True
    
    # Case 2: Growth < 25%
    eps = pd.Series([1.0, 1.1, 1.2, 1.3, 1.1])
    assert calculate_c_factor(eps) == False
    
    # Case 3: Turnaround (Negative to Positive)
    eps = pd.Series([-0.5, 0.1, 0.2, 0.3, 0.5]) # iloc[-5]=-0.5, iloc[-1]=0.5
    assert calculate_c_factor(eps) == True

def test_calculate_a_factor():
    # Case 1: Growth >= 25% and ROE >= 17%
    annual_eps = pd.Series([10.0, 13.0])
    assert calculate_a_factor(annual_eps, roe=0.18) == True
    
    # Case 2: Growth >= 25% but ROE too low
    assert calculate_a_factor(annual_eps, roe=0.10) == False
    
    # Case 3: No ROE provided (default to growth check only)
    assert calculate_a_factor(annual_eps) == True

def test_calculate_accumulation_strength():
    data = {
        'foreign_net': [100, 200, -50],
        'trust_net': [50, 50, 50],
        'dealer_net': [10, -10, 0]
    }
    df = pd.DataFrame(data)
    # Total net = 100+200-50 + 50+50+50 + 10-10+0 = 400
    # Shares = 1,000,000. Strength = (400 * 1000) / 1,000,000 = 0.4 (decimal: 0.4)
    # Wait, 400,000 / 1,000,000 is 0.4.
    strength = calculate_accumulation_strength(df, total_shares=1000000, days=3)
    assert strength == 0.4

def test_calculate_mansfield_rs():
    stock = pd.Series([100, 110], index=pd.to_datetime(['2023-01-01', '2023-01-02']))
    market = pd.Series([20000, 21000], index=pd.to_datetime(['2023-01-01', '2023-01-02']))
    # Need at least 'window' (default 250) rows. Let's mock a simpler version or provide data
    stock_long = pd.Series([100]*300)
    market_long = pd.Series([20000]*300)
    rs = calculate_mansfield_rs(stock_long, market_long)
    assert rs == 0.0 # No change relative to average

def test_calculate_volatility_grid():
    prices = pd.Series([100, 102, 98, 101, 105, 103, 100] * 10) # 70 points
    grid = calculate_volatility_grid(prices, is_etf=True)
    assert grid is not None
    assert grid['is_etf'] == True
    assert len(grid['levels']) == 5
    assert grid['levels'][2]['label'] == "Pivot (平衡位)"

def test_compute_canslim_score_etf():
    # Current Weights: C:25, A:20, N:15, S:10, L:15, I:15
    # If L is True, C and A are forced to True for ETFs.
    factors = {'N': True, 'S': True, 'L': True, 'I': True, 'M': True}
    score = compute_canslim_score_etf(factors)
    assert score == 100
    
    factors_weak = {'N': False, 'S': False, 'L': True, 'I': False, 'M': True}
    # C(25) + A(20) + L(15) = 60
    score = compute_canslim_score_etf(factors_weak)
    assert score == 60
