import pandas as pd
import numpy as np
from typing import Dict, Any

class SkewAnalyzer:
    """
    Analyzes option data to extract Skew and Volatility Regime signals.
    """
    def __init__(self):
        pass

    def calculate_skew_metrics(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Derives perception signals from TXO market snapshot.
        """
        if df is None or df.empty:
            return {"status": "no_data"}

        try:
            # 1. 取得近月合約 (通常成交量最大)
            # 在 FinMind 資料中，Option_id 包含日期，例如 TXO202605
            df['Expiry'] = df['Option_id'].str.extract(r'(\d{6})')
            main_expiry = df.groupby('Expiry')['Volume'].sum().idxmax()
            near_month = df[df['Expiry'] == main_expiry]
            
            # 2. 找出平值 (At-the-money) 價格
            # 簡單做法：成交量最大的履約價
            atm_strike = near_month.groupby('StrikePrice')['Volume'].sum().idxmax()
            
            # 3. 分類價外 Call/Put
            otm_calls = near_month[(near_month['CallPut'] == 'Call') & (near_month['StrikePrice'] > atm_strike)]
            otm_puts = near_month[(near_month['CallPut'] == 'Put') & (near_month['StrikePrice'] < atm_strike)]
            
            # 4. 計算偏斜 (Skew) - 這裡以 Iv 差值為例
            # 注意：若 FinMind 沒有直接給 Iv，我們目前先用成交量/未平倉量比例作為替代 Perception
            otm_put_oi = otm_puts['OpenInterest'].sum()
            otm_call_oi = otm_calls['OpenInterest'].sum()
            
            skew_ratio = otm_put_oi / otm_call_oi if otm_call_oi > 0 else 1.0
            
            # 判定狀態
            direction = "NEUTRAL"
            if skew_ratio > 1.5:
                direction = "PROTECTIVE" # 市場正在買入大量價外 Put 避險
            elif skew_ratio < 0.7:
                direction = "SPECULATIVE" # 市場正在追逐價外 Call
                
            return {
                "expiry": main_expiry,
                "atm_strike": float(atm_strike),
                "skew_ratio": round(float(skew_ratio), 2),
                "perception": direction,
                "vol_regime": "NORMAL", # 暫定，需歷史比較
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}

from datetime import datetime
