"""
CANSLIM Core Logic Module.
Pure functions for calculating CANSLIM factors from time-series data.
"""

import pandas as pd
import numpy as np
from typing import List, Optional, Dict, Any

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

def calculate_i_factor(
    chip_df: pd.DataFrame,
    days: int = 3,
    total_shares: Optional[float] = None,
    conviction_threshold: float = 0.002,
) -> bool:
    """
    I - Institutional Sponsorship.
    Backwards-compatible helper for tests and older callers.
    """
    if chip_df.empty:
        return False

    recent = chip_df.head(days).copy()
    cols = ['foreign_net', 'trust_net', 'dealer_net']
    for c in cols:
        if c not in recent.columns:
            recent[c] = 0

    if total_shares is not None:
        return calculate_accumulation_strength(recent, total_shares, days=days) >= conviction_threshold

    total_net_buy = (recent['foreign_net'] + recent['trust_net'] + recent['dealer_net']).sum()
    return total_net_buy > 0

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

def calculate_l_factor(rs_value: float, threshold: float = 0) -> bool:
    """
    L - Leader or Laggard.
    For Mansfield RS, any value > 0 is outperforming.
    """
    return rs_value > threshold

def check_n_factor(prices: pd.Series) -> bool:
    """
    N - New Highs or New Momentum.
    Pass if price is near 52-week high OR 60-day high.
    This handles stocks with historical split anomalies.
    """
    if prices is None or len(prices) < 20: return False
    
    current = prices.iloc[-1]
    high_52w = prices.tail(250).max()
    high_60d = prices.tail(60).max()
    
    # Pass if within 10% of 52-week high OR at 60-day high (New Momentum)
    return (current >= high_52w * 0.9) or (current >= high_60d * 0.98)

def calculate_mansfield_rs(stock_prices: Optional[pd.Series], market_prices: Optional[pd.Series], window: int = 250) -> float:
    """
    Calculates Mansfield Relative Strength (MRIS).
    Uses an adaptive window if 250-day data shows extreme anomalies.
    """
    if stock_prices is None or market_prices is None: return 0.0
    df = pd.DataFrame({'stock': stock_prices, 'market': market_prices}).dropna()
    if len(df) < 60: return 0.0
    
    df['rs'] = df['stock'] / df['market']
    
    # Try 250-day average first
    actual_window = min(window, len(df))
    avg_rs = df['rs'].tail(actual_window).mean()
    current_rs = df['rs'].iloc[-1]
    
    mris = ((current_rs / avg_rs) - 1) * 10 if avg_rs != 0 else 0
    
    # Self-Correction: If MRIS is extremely negative but price is at short-term high,
    # it's likely a data split anomaly. Fallback to 60-day relative strength.
    if mris < -5 and current_rs >= df['rs'].tail(60).max() * 0.95:
        avg_rs_short = df['rs'].tail(60).mean()
        mris = ((current_rs / avg_rs_short) - 1) * 10 if avg_rs_short != 0 else 0
        
    return round(mris, 3)

def calculate_rs_trend(stock_prices: Optional[pd.Series], market_prices: Optional[pd.Series], window: int = 250) -> dict:
    """
    Analyzes the trend of Mansfield RS over the last 5 trading days.
    Returns: {trend: 'up'|'down'|'flat', delta: float}
    """
    if stock_prices is None or market_prices is None or len(stock_prices) < window + 5:
        return {'trend': 'neutral', 'delta': 0}
    
    df = pd.DataFrame({'stock': stock_prices, 'market': market_prices}).dropna()
    if len(df) < window + 5: return {'trend': 'neutral', 'delta': 0}
    
    df['rs'] = df['stock'] / df['market']
    
    def get_mris_at(idx):
        subset = df['rs'].iloc[:idx]
        curr = subset.iloc[-1]
        avg = subset.tail(window).mean()
        return ((curr / avg) - 1) * 10 if avg != 0 else 0

    mris_now = get_mris_at(len(df))
    mris_prev = get_mris_at(len(df) - 5) # 5 days ago
    
    delta = round(mris_now - mris_prev, 3)
    if delta > 0.05: trend = 'up'
    elif delta < -0.05: trend = 'down'
    else: trend = 'flat'
    
    return {'trend': trend, 'delta': delta, 'current': round(mris_now, 3)}

def calculate_i_score_v2(
    chip_df: pd.DataFrame,
    total_shares: float,
    days: int = 20
) -> Dict[str, Any]:
    """
    I - Institutional Sponsorship (v2).
    Calculates a weighted institutional score using:
    1. Exponentially weighted net buy volume (recent days have more weight).
    2. Buy volume ratio (net buy as % of total shares).
    3. Buy streak bonus.

    Returns:
        Dict with absolute_score (0-100) and details.
    """
    if chip_df.empty or total_shares <= 0:
        return {"score": 0.0, "details": {}}

    # Ensure column names
    cols = ['foreign_net', 'trust_net', 'dealer_net']
    for c in cols:
        if c not in chip_df.columns: chip_df[c] = 0

    df = chip_df.head(days).copy()
    df['total_net'] = df['foreign_net'] + df['trust_net'] + df['dealer_net']

    # 1. Weighted Net Buy (Exponential decay)
    weights = np.exp(np.linspace(-1, 0, len(df))) # Most recent is index 0 or N? 
    # Usually chip_df is sorted by date descending (newest first)
    # If newest is first:
    w_sum = (df['total_net'] * weights).sum()

    # 2. Buy volume ratio (lots * 1000 / total_shares)
    ratio_20d = (df['total_net'].sum() * 1000) / total_shares

    # 3. Streak bonus
    streak = 0
    for val in df['total_net']:
        if val > 0: streak += 1
        else: break

    # Scoring logic
    # Base score from ratio: 0.1% accumulation in 20 days is good, 0.5% is great
    ratio_score = min(ratio_20d / 0.005 * 60, 60) if ratio_20d > 0 else (ratio_20d * 10)
    streak_score = min(streak * 8, 40)

    total_score = max(0, min(ratio_score + streak_score, 100))

    return {
        "score": round(total_score, 2),
        "details": {
            "streak": streak,
            "ratio_20d": round(ratio_20d * 100, 4),
            "weighted_net": round(w_sum, 2)
        }
    }

def calculate_percentile_ranks(scores: pd.Series) -> pd.Series:
    """Convert absolute scores to 0-100 percentile ranks."""
    if scores.empty:
        return scores
    return scores.rank(pct=True) * 100

def compute_canslim_score(factors: dict, institutional_strength: float = 0) -> int:
    """Legacy wrapper for compute_canslim_score_v2."""
    # Convert institutional_strength (percentage) to approximate abs score for v2 logic
    i_score_abs = min(institutional_strength / 0.005 * 100, 100)
    return compute_canslim_score_v2(factors, i_score_abs=i_score_abs)

def compute_canslim_score_etf(factors: dict, institutional_strength: float = 0) -> int:
    """Legacy wrapper for ETF scoring."""
    # ETF scoring (L=PASS means quality components)
    f = factors.copy()
    if f.get('L'):
        f['C'] = True
        f['A'] = True
    # Boost I for ETFs in this wrapper to hit 100 if all pass
    return compute_canslim_score_v2(f, i_score_abs=100 if f.get('I') else 0)

def compute_canslim_score_v2(
    factors: dict, 
    i_score_abs: float = 0,
    momentum_bonus: float = 0
) -> int:
    """
    Calculates weighted CANSLIM score (0-100) with non-linear weighting.
    """
    # Base weights
    weights = {
        'C': 25, 'A': 20, 'N': 15, 'S': 10, 'L': 15, 'I': 15
    }

    base_score = 0
    for f, w in weights.items():
        if f == 'I':
            # Use the refined I score (normalized)
            base_score += (i_score_abs / 100) * w
        elif factors.get(f):
            base_score += w

    # M (Market) is a multiplier/gate
    m_multiplier = 1.0 if factors.get('M') else 0.7

    final_score = base_score * m_multiplier + momentum_bonus

    return int(max(0, min(final_score, 100)))

def calculate_score_delta(today_score: int, yesterday_score: int) -> int:
    """Calculate the change in score."""
    return today_score - yesterday_score

def get_market_sentiment(stock_scores: List[int]) -> str:
    """Determine market sentiment based on top score density."""
    if not stock_scores:
        return "Unknown"

    high_scores = [s for s in stock_scores if s >= 80]
    ratio = len(high_scores) / len(stock_scores)

    if ratio > 0.05: return "Bullish (強勢多頭)"
    if ratio > 0.02: return "Neutral (中性震盪)"
    return "Bearish (盤整空頭)"

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
