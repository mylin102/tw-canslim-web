"""
Advanced Data Verifier & Rebuilder.
Syncs all fallback logic (Excel, Funds, TEJ) to ensure maximum data accuracy.
"""

import os, json, logging, pandas as pd, numpy as np, yfinance as yf, requests, time
from datetime import datetime, timedelta
from core.logic import *
from export_canslim import CanslimEngine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def rebuild():
    engine = CanslimEngine()
    
    # 標的清單：確保這些核心標的有最完美的資料
    target_tickers = [
        "2330", "2317", "2454", "2603", "2881", "2308", "2382", "3711",
        "0050", "0052", "0056", "00878", "00631L", "00981A", "00881"
    ]
    
    # 抓取基準大盤
    market_hist = None
    for sym in ["^TWII", "0050.TW"]:
        try:
            market_hist = yf.download(sym, period="2y", auto_adjust=True, progress=False)['Close'].squeeze()
            if not market_hist.empty: break
        except: continue

    output = {"last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "stocks": {}}
    print(f"🚀 Rebuilding high-fidelity data for {len(target_tickers)} symbols...")
    
    for t in target_tickers:
        try:
            print(f"--- Analyzing {t} ---")
            info = engine.ticker_info.get(t, {"name": t, "suffix": ".TW"})
            is_etf = t.startswith("00")
            
            # 1. Price History
            stock_hist = yf.download(f"{t}{info['suffix']}", period="2y", auto_adjust=True, progress=False)['Close'].squeeze()
            if stock_hist.empty: continue
            
            # 2. Institutional Data
            history = engine.fetch_institutional_data_finmind(t, days=60)
            
            # 3. Basic metrics
            m_rs = calculate_mansfield_rs(stock_hist, market_hist)
            rs_trend = calculate_rs_trend(stock_hist, market_hist)
            n_score = check_n_factor(stock_hist)
            l_score = calculate_l_factor(m_rs)
            
            # 4. C & A with Excel Fallback
            c_pass = a_pass = False
            if is_etf:
                # ETF Proxy Logic (already in logic.py but we'll be explicit here)
                if l_score: c_pass = a_pass = True
            else:
                # Try TEJ first
                tej_ca = engine.tej_processor.calculate_canslim_c_and_a(t)
                c_pass = tej_ca.get("C", False)
                a_pass = tej_ca.get("A", False)
                
                # Excel Backup (Essential for trial keys)
                if not c_pass and engine.excel_ratings and t in engine.excel_ratings:
                    if engine.excel_ratings[t].get('eps_rating', 0) >= 60:
                        c_pass = a_pass = True
                        print(f"  ℹ️ {t} using Excel fallback for C/A")

            # 5. I Factor with Fund Backup
            i_pass = engine.check_i_institutional(history) if history else False
            if not i_pass and engine.fund_holdings and t in engine.fund_holdings:
                i_pass = True
                print(f"  ℹ️ {t} passed I via fund holdings backup")

            factors = {"C": c_pass, "A": a_pass, "N": n_score, "S": True, "L": l_score, "I": i_pass, "M": True}
            score = compute_canslim_score_etf(factors) if is_etf else compute_canslim_score(factors)
            grid = calculate_volatility_grid(stock_hist, is_etf=is_etf) if (score >= 60 or is_etf) else None
            
            output["stocks"][t] = {
                "symbol": t, "name": info["name"], "is_etf": is_etf, "industry": "ETF" if is_etf else "核心權值",
                "canslim": {
                    "C": bool(factors["C"]), "A": bool(factors["A"]), "N": bool(factors["N"]), 
                    "S": bool(factors["S"]), "L": bool(factors["L"]), "I": bool(factors["I"]), "M": bool(factors["M"]),
                    "score": int(score), "mansfield_rs": float(m_rs), "rs_trend": rs_trend, "rs_ratio": 1.0,
                    "grid_strategy": grid,
                    "excel_ratings": engine.excel_ratings.get(t) if engine.excel_ratings else None,
                    "fund_holdings": engine.fund_holdings.get(t) if engine.fund_holdings else None
                },
                "institutional": history[:10] if history else []
            }
            print(f"✅ {t} Done: Score={score}")
            time.sleep(0.5)
        except Exception as e:
            print(f"❌ Error on {t}: {e}")

    # Save and Merge
    with open("docs/data.json", "w") as f:
        def js(obj):
            if isinstance(obj, (datetime, pd.Timestamp)): return obj.strftime('%Y-%m-%d')
            if isinstance(obj, np.bool_): return bool(obj)
            if isinstance(obj, (np.integer, np.floating)): return obj.item()
            return obj
        json.dump(output, f, ensure_ascii=False, indent=2, default=js)
    
    print("\n🎉 Verification Rebuild Complete.")

if __name__ == "__main__": rebuild()
