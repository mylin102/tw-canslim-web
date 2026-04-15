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
    Supports Turnaround detection.
    """
    if len(eps_series) < 5: # Need at least 4 quarters back for YoY
        return False
    curr = eps_series.iloc[-1]
    last_year = eps_series.iloc[-5]
    
    if pd.isna(curr) or pd.isna(last_year):
        return False
        
    # Turnaround: Negative/Zero to Positive
    if last_year <= 0:
        return curr > 0
        
    growth = (curr - last_year) / abs(last_year)
    return growth >= threshold

def calculate_accumulation_strength(chip_df: pd.DataFrame, total_shares: float, days: int = 20) -> float:
    """
    Calculates institutional accumulation strength as a percentage of total shares.
    """
    if chip_df.empty or total_shares <= 0:
        return 0.0
    
    # Ensure column names match
    cols = ['foreign_net', 'trust_net', 'dealer_net']
    for c in cols:
        if c not in chip_df.columns: chip_df[c] = 0
        
    recent = chip_df.head(days)
    total_net_buy = (recent['foreign_net'] + recent['trust_net'] + recent['dealer_net']).sum()
    
    # Taiwan stock chips are in 'shares' (1000 per lot)
    strength = (total_net_buy * 1000) / total_shares
    # Return as decimal (e.g., 0.004 for 0.4%)
    return round(strength, 6)

def calculate_rs_score(stock_returns: pd.Series, market_returns: pd.Series) -> float:
    """Simple RS ratio."""
    if len(stock_returns) < 250: return 0.0
    return stock_returns.iloc[-1] / market_returns.iloc[-1]

def calculate_a_factor(eps_years: pd.Series, threshold: float = 0.25, roe: Optional[float] = None) -> bool:
    """
    A - Annual Earnings Increases.
    Check if the latest annual EPS shows consistent growth.
    Optionally check ROE (Standard CANSLIM >= 17%).
    """
    if len(eps_years) < 2: return False
    latest = eps_years.iloc[-1]
    prev = eps_years.iloc[-2]
    
    if pd.isna(latest) or pd.isna(prev):
        return False
        
    if prev <= 0:
        is_growing = latest > 0
    else:
        is_growing = (latest - prev) / abs(prev) >= threshold
        
    if roe is not None:
        return is_growing and roe >= 0.17
        
    return is_growing

def calculate_l_factor(rs_rank: float, threshold: float = 80) -> bool:
    """L - Leader or Laggard."""
    return rs_rank >= threshold

def calculate_mansfield_rs(stock_prices: Optional[pd.Series], market_prices: Optional[pd.Series], window: int = 250) -> float:
    """
    Calculates Mansfield Relative Strength (MRIS).
    Formula: ((Current RS / Avg RS over Window) - 1) * 10
    """
    if stock_prices is None or market_prices is None: return 0.0
    if len(stock_prices) < window or len(market_prices) < window: return 0.0
    
    # Align dates
    df = pd.DataFrame({'stock': stock_prices, 'market': market_prices}).dropna()
    if len(df) < window: return 0.0
    
    df['rs'] = df['stock'] / df['market']
    current_rs = df['rs'].iloc[-1]
    avg_rs = df['rs'].tail(window).mean()
    
    if avg_rs == 0: return 0.0
    mris = ((current_rs / avg_rs) - 1) * 10
    return round(mris, 3)

def compute_canslim_score(factors: dict, institutional_strength: float = 0) -> int:
    """Calculates composite CANSLIM score (0-100)."""
    score = 0
    weights = {'C': 20, 'A': 20, 'N': 10, 'S': 10, 'L': 20, 'I': 10, 'M': 10}
    for f, w in weights.items():
        if factors.get(f): score += w
    
    # Extra points for strong institutional accumulation
    if institutional_strength >= 0.005: score += 5
    elif institutional_strength >= 0.002: score += 2
    
    return min(score, 100)

def compute_canslim_score_etf(factors: dict, institutional_strength: float = 0) -> int:
    """ETF specialized scoring (ignores C/A)."""
    score = 0
    weights = {'N': 20, 'S': 20, 'L': 30, 'I': 10, 'M': 20}
    for f, w in weights.items():
        if factors.get(f): score += w
    
    if institutional_strength >= 0.002: score += 5
    return min(score, 100)

def calculate_volatility_grid(prices: pd.Series, is_etf: bool = False) -> Optional[dict]:
    """Calculates dynamic grid levels based on historical volatility."""
    if prices is None or len(prices) < 20: return None
    
    recent = prices.tail(60)
    current_price = prices.iloc[-1]
    returns = recent.pct_change().dropna()
    volatility = returns.std()
    
    if volatility == 0 or pd.isna(volatility):
        spacing_pct = 0.02
    else:
        multiplier = 1.2 if is_etf else 1.5
        spacing_pct = volatility * multiplier
    
    if is_etf:
        levels = [
            {"label": "Sell 2 (超漲出清)", "price": round(current_price * (1 + 2 * spacing_pct), 2), "type": "sell-strong"},
            {"label": "Sell 1 (壓力減碼)", "price": round(current_price * (1 + 1 * spacing_pct), 2), "type": "sell"},
            {"label": "Pivot (平衡位)", "price": round(current_price, 2), "type": "neutral"},
            {"label": "Buy 1 (支撐分批)", "price": round(current_price * (1 - 1 * spacing_pct), 2), "type": "buy"},
            {"label": "Buy 2 (超跌佈局)", "price": round(current_price * (1 - 2 * spacing_pct), 2), "type": "buy-strong"}
        ]
    else:
        levels = [
            {"label": "Sell 2 (強勢減碼)", "price": round(current_price * (1 + 2 * spacing_pct), 2), "type": "sell-strong"},
            {"label": "Sell 1 (分批獲利)", "price": round(current_price * (1 + 1 * spacing_pct), 2), "type": "sell"},
            {"label": "Pivot (基準位)", "price": round(current_price, 2), "type": "neutral"},
            {"label": "Buy 1 (支撐加碼)", "price": round(current_price * (1 - 1 * spacing_pct), 2), "type": "buy"},
            {"label": "Buy 2 (強力支撐)", "price": round(current_price * (1 - 2 * spacing_pct), 2), "type": "buy-strong"}
        ]
    
    return {
        "volatility_daily": round(volatility * 100, 2),
        "volatility_annual": round(volatility * np.sqrt(252) * 100, 2),
        "spacing_pct": round(spacing_pct * 100, 2),
        "levels": levels,
        "is_etf": is_etf
    }
