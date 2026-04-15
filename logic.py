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

def calculate_rs_score(stock_returns: pd.Series, market_returns: pd.Series) -> float:
    """
    L - Leader or Laggard (Relative Strength).
    Calculates a simple Relative Strength value. 
    In practice, this should be a percentile rank across the whole market.
    """
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
        # Standard CANSLIM: Annual growth >= 25% AND ROE >= 17%
        return is_growing and roe >= 0.17
        
    return is_growing

def calculate_mansfield_rs(stock_prices: Optional[pd.Series], market_prices: Optional[pd.Series], window: int = 250) -> float:
    """
    Calculates Mansfield Relative Strength (MRIS).
    Formula: ((Current RS / Avg RS over Window) - 1) * 10
    MRIS > 0 indicates stock is outperforming its historical trend relative to market.
    """
    if stock_prices is None or market_prices is None:
        return 0.0
        
    if len(stock_prices) < window or len(market_prices) < window:
        return 0.0
    
    # 1. Base RS (Price Ratio)
    # Ensure indices align if they are different
    combined = pd.DataFrame({'stock': stock_prices, 'market': market_prices}).dropna()
    if len(combined) < window:
        return 0.0
        
    rs_base = combined['stock'] / combined['market']
    
    # 2. RS Moving Average (Window usually 52 weeks / 250 trading days)
    rs_ma = rs_base.rolling(window=window).mean()
    
    # 3. Mansfield RS
    curr_rs = rs_base.iloc[-1]
    curr_ma = rs_ma.iloc[-1]
    
    if not curr_ma or curr_ma == 0:
        return 0.0
        
    mris = ((curr_rs / curr_ma) - 1) * 10
    return float(mris)

def calculate_l_factor(mansfield_rs: float, rs_rank: float = 0, threshold: float = 0) -> bool:
    """
    L - Leader or Laggard.
    Check if the stock's Mansfield RS is positive (> 0).
    Or fallback to RS Rank if provided.
    """
    if mansfield_rs != 0:
        return mansfield_rs > threshold
    return rs_rank >= 80

def calculate_m_factor(market_price: float, market_ma200: float) -> bool:
    """
    M - Market Direction.
    Only trade when the market (TAIEX) is above its 200-day moving average.
    """
    return market_price > market_ma200

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

def calculate_i_factor(chip_df: pd.DataFrame, days: int = 3, total_shares: Optional[int] = None) -> bool:
    """
    I - Institutional Sponsorship.
    Check if there is net institutional buying over the last N days.
    If total_shares is provided, also considers accumulation strength.
    """
    if len(chip_df) < days:
        return False
    
    recent = chip_df.tail(days)
    net_buy = (recent['foreign_net'] + recent['trust_net'] + recent['dealer_net']).sum()
    
    # Basic binary check
    is_buying = net_buy > 0
    
    # Enhanced conviction check if total_shares available
    if is_buying and total_shares and total_shares > 0:
        # 20-day conviction check (standard threshold 0.2%)
        strength_20d = calculate_accumulation_strength(chip_df, total_shares, days=20)
        return strength_20d >= 0.002
        
    return is_buying

def calculate_accumulation_strength(chip_df: pd.DataFrame, total_shares: int, days: int = 20) -> float:
    """
    Calculates the institutional accumulation strength as a percentage of total shares.
    Formula: (Net Buy Lots * 1000) / total_shares
    """
    if total_shares <= 0 or len(chip_df) == 0:
        return 0.0
    
    actual_days = min(len(chip_df), days)
    recent = chip_df.tail(actual_days)
    
    # Net buy in shares (lots * 1000)
    net_buy_shares = (recent['foreign_net'] + recent['trust_net'] + recent['dealer_net']).sum() * 1000
    
    return net_buy_shares / total_shares

def compute_canslim_score(factors: dict, institutional_strength: float = 0.0) -> int:
    """
    Calculates weighted CANSLIM score (0-100).
    C and A are weighted higher.
    Includes bonus points for strong institutional conviction.
    """
    weights = {
        'C': 20, 'A': 20, 'N': 10, 'S': 10, 'L': 15, 'I': 15, 'M': 10
    }
    score = 0
    for f, val in factors.items():
        if val:
            score += weights.get(f, 0)
            
    # Bonus for high institutional conviction (>= 0.5% of shares in 20 days)
    if institutional_strength >= 0.005:
        score = min(score + 5, 100)
        
    return score

def compute_canslim_score_etf(factors: dict, institutional_strength: float = 0.0) -> int:
    """
    Calculates weighted score for ETFs (0-100).
    Excludes C and A, redistributing weight to L and I.
    """
    # ETF Weights: L(40), I(30), N(20), M(10). S is combined or ignored.
    weights = {
        'N': 20, 'L': 40, 'I': 30, 'M': 10
    }
    score = 0
    for f, val in factors.items():
        if val:
            score += weights.get(f, 0)
            
    # Bonus for high institutional conviction in ETFs
    if institutional_strength >= 0.002: # Lower threshold for ETFs due to large capital
        score = min(score + 5, 100)
        
    return score

def calculate_volatility_grid(prices: pd.Series, is_etf: bool = False) -> Optional[dict]:
    """
    Calculates dynamic grid levels based on historical volatility (Standard Deviation).
    Returns a dict with volatility % and price levels.
    For ETFs, uses specialized labels and potentially tighter spacing.
    """
    if prices is None or len(prices) < 20:
        return None
    
    recent = prices.tail(60) # Use longer window for stability
    current_price = prices.iloc[-1]
    
    # Calculate daily volatility (Std Dev of percentage changes)
    returns = recent.pct_change().dropna()
    volatility = returns.std()
    
    if volatility == 0 or pd.isna(volatility):
        spacing_pct = 0.02
    else:
        # Standard spacing: 1.5-2.0 * volatility
        # ETFs usually have lower volatility, so grid levels are more meaningful
        multiplier = 1.2 if is_etf else 1.5
        spacing_pct = volatility * multiplier
    
    # Grid Design (Inspired by grid-design patterns)
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
