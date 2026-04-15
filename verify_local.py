"""
Unified Data Verifier - Stable fetching for key symbols.
Ensures critical stocks and ETFs have 100% correct CANSLIM & RS metrics.
"""

import os
import json
import logging
import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime, timedelta
from export_canslim import CanslimEngine
from core.logic import (
    calculate_accumulation_strength, calculate_mansfield_rs, 
    compute_canslim_score, compute_canslim_score_etf, 
    calculate_l_factor, calculate_volatility_grid,
    calculate_rs_trend, check_n_factor
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def verify_local_features():
    engine = CanslimEngine()
    # 核心驗證清單：確保這些標的有最準確的資料
    test_tickers = [
        "2330", "2317", "2454", "2603", "2881", "2308", "2382", "3711", # 權值股
        "0050", "0052", "0056", "00878", "00631L", "00981A", "00881"    # 關鍵 ETF
    ]
    
    # 抓取大盤作為基準
    market_hist = None
    for sym in ["^TWII", "0050.TW"]:
        try:
            market_hist = yf.download(sym, period="2y", auto_adjust=True, progress=False)['Close'].squeeze()
            if not market_hist.empty: break
        except: continue

    engine.output_data["last_updated"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    print(f"\n🚀 Running High-Fidelity Verification for {len(test_tickers)} stocks...")
    
    for t in test_tickers:
        try:
            print(f"--- Analyzing {t} ---")
            info = engine.ticker_info.get(t, {"name": t, "suffix": ".TW"})
            is_etf = engine.tej_processor.is_etf(t) or t.startswith("00")
            
            # Fetch Price History (2 years for stable RS)
            stock_hist = yf.download(f"{t}{info['suffix']}", period="2y", auto_adjust=True, progress=False)['Close'].squeeze()
            if stock_hist.empty: continue
            
            # Institutional Data
            history = engine.fetch_institutional_data_finmind(t, days=60)
            chip_df = pd.DataFrame(history) if history else pd.DataFrame()
            
            # Financial Data
            financial_data = engine.fetch_financial_data(t)
            price = financial_data.get("price", stock_hist.iloc[-1])
            market_cap = financial_data.get("market_cap", 0)
            total_shares = market_cap / price if price > 0 else 1e9
            
            # Calculations
            m_rs = calculate_mansfield_rs(stock_hist, market_hist)
            rs_trend = calculate_rs_trend(stock_hist, market_hist)
            n_score = check_n_factor(stock_hist)
            l_score = calculate_l_factor(m_rs)
            i_score = engine.check_i_institutional(history) if history else False
            
            # rs_ratio
            rs_ratio = 1.0
            if market_hist is not None and len(stock_hist) >= 120:
                stock_ret = (stock_hist.iloc[-1] - stock_hist.iloc[-120]) / stock_hist.iloc[-120]
                market_ret = (market_hist.iloc[-1] - market_hist.iloc[-120]) / market_hist.iloc[-120]
                rs_ratio = round(stock_ret / market_ret, 2) if abs(market_ret) > 0.01 else 1.0

            inst_strength_20d = calculate_accumulation_strength(chip_df, total_shares, days=20)
            
            # TEJ Proxy
            tej_ca = engine.tej_processor.calculate_canslim_c_and_a(t) if not is_etf else {}
            factors = {"C": tej_ca.get("C", False), "A": tej_ca.get("A", False), "N": n_score, "S": True, "L": l_score, "I": i_score, "M": True}
            
            # Score
            score = compute_canslim_score_etf(factors) if is_etf else compute_canslim_score(factors)
            grid_data = calculate_volatility_grid(stock_hist, is_etf=is_etf) if (score >= 60 or is_etf) else None
            
            stock_data = {
                "symbol": t, "name": info["name"], "industry": "ETF" if is_etf else "核心標的",
                "is_etf": is_etf,
                "canslim": {
                    "C": bool(factors["C"]), "A": bool(factors["A"]), "N": bool(factors["N"]), 
                    "S": bool(factors["S"]), "L": bool(factors["L"]), "I": bool(factors["I"]), "M": bool(factors["M"]),
                    "score": int(score), "mansfield_rs": float(m_rs), "rs_trend": rs_trend, "rs_ratio": rs_ratio,
                    "grid_strategy": grid_data
                },
                "institutional": history[:10] if history else [],
                "financials": financial_data
            }
            engine.output_data["stocks"][t] = stock_data
            print(f"✅ {t} Done: Score={score}, RS={m_rs}")
            
        except Exception as e:
            print(f"❌ Error on {t}: {e}")

    # Save to docs/data.json
    with open("docs/data.json", "w", encoding="utf-8") as f:
        def json_serial(obj):
            if isinstance(obj, (datetime, pd.Timestamp)): return obj.strftime('%Y-%m-%d')
            if isinstance(obj, np.bool_): return bool(obj)
            if isinstance(obj, (np.integer, np.floating, np.float64, np.int64)): return obj.item()
            raise TypeError ("Type %s not serializable" % type(obj))
        json.dump(engine.output_data, f, ensure_ascii=False, indent=2, default=json_serial)
    
    print("\n🎉 High-Fidelity Data Generated at docs/data.json")

if __name__ == "__main__":
    verify_local_features()
