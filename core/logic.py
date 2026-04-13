"""
CANSLIM Core Logic Module.
Pure functions for calculating CANSLIM factors from time-series data.
"""

import pandas as pd
import numpy as np
from typing import List, Optional

def calculate_c_factor(eps_series: pd.Series, threshold: float = 0.25) -> bool:
    """
    C - Current Quarterly Earnings.
    Check if the most recent quarterly EPS growth is >= threshold (同比增長).
    Note: To avoid seasonality, compare with the same quarter of last year.
    """
    if len(eps_series) < 5: # Need at least 4 quarters back for YoY
        return False
    curr = eps_series.iloc[-1]
    last_year = eps_series.iloc[-5]
    if last_year <= 0: return curr > 0
    growth = (curr - last_year) / abs(last_year)
    return growth >= threshold

def calculate_rs_score(stock_returns: pd.Series, market_returns: pd.Series) -> float:
    """
    L - Leader or Laggard (Relative Strength).
    Calculates a simple Relative Strength value. 
    In practice, this should be a percentile rank across the whole market.
    """
    if len(stock_returns) < 250: return 0.0
    return stock_returns.iloc[-1] / market_returns.iloc[-1]

def calculate_a_factor(annual_eps: List[float], threshold: float = 0.25) -> bool:
    """
    A - Annual Earnings Increases.
    Check if 3-year CAGR is >= threshold.
    """
    if len(annual_eps) < 2:
        return False
    try:
        years = len(annual_eps) - 1
        cagr = (annual_eps[-1] / annual_eps[0]) ** (1 / years) - 1
        return cagr >= threshold
    except:
        return False

def calculate_n_factor(current_price: float, high_52w: float, threshold: float = 0.90) -> bool:
    """
    N - New Highs or Near New Highs.
    Check if price is within threshold% of 52-week high.
    """
    if not high_52w: return False
    return current_price >= (high_52w * threshold)

def calculate_s_factor(volume: float, avg_volume: float, threshold: float = 1.5) -> bool:
    """
    S - Supply and Demand.
    Check if current volume is >= threshold * average volume.
    """
    if not avg_volume: return False
    return volume >= (avg_volume * threshold)

def calculate_i_factor(chip_df: pd.DataFrame, days: int = 3) -> bool:
    """
    I - Institutional Sponsorship.
    Check if there is net institutional buying over the last N days.
    """
    if len(chip_df) < days:
        return False
    recent = chip_df.tail(days)
    net_buy = (recent['foreign_net'] + recent['trust_net'] + recent['dealer_net']).sum()
    return net_buy > 0

def compute_canslim_score(factors: dict) -> int:
    """
    Calculates weighted CANSLIM score (0-100).
    C and A are weighted higher.
    """
    weights = {
        'C': 20, 'A': 20, 'N': 10, 'S': 10, 'L': 15, 'I': 15, 'M': 10
    }
    score = 0
    for f, val in factors.items():
        if val:
            score += weights.get(f, 0)
    return score
