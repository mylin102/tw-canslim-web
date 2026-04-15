import os, json, logging, pandas as pd, numpy as np, yfinance as yf, requests, time
from datetime import datetime, timedelta
from core.logic import *
from export_canslim import CanslimEngine

logging.basicConfig(level=logging.INFO)
def rebuild():
    engine = CanslimEngine()
    # 抓取所有 00 開頭的 ETF + 權值股
    all_tickers = list(engine.ticker_info.keys())
    target_tickers = [t for t in all_tickers if t.startswith("00") or t in ["2330", "2317", "2454", "2603", "2881", "2308"]]
    target_tickers = target_tickers[:150] # 限制在 150 隻以防封鎖
    
    market_hist = yf.download("^TWII", period="2y", auto_adjust=True, progress=False)['Close'].squeeze()
    
    output = {"last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "stocks": {}}
    print(f"🚀 Rebuilding for {len(target_tickers)} symbols...")
    
    for t in target_tickers:
        try:
            info = engine.ticker_info.get(t, {"name": t, "suffix": ".TW"})
            is_etf = t.startswith("00")
            stock_hist = yf.download(f"{t}{info['suffix']}", period="2y", auto_adjust=True, progress=False)['Close'].squeeze()
            if stock_hist.empty: continue
            
            m_rs = calculate_mansfield_rs(stock_hist, market_hist)
            n_score = check_n_factor(stock_hist)
            factors = {"C": False, "A": False, "N": n_score, "S": True, "L": calculate_l_factor(m_rs), "I": False, "M": True}
            
            score = compute_canslim_score_etf(factors) if is_etf else compute_canslim_score(factors)
            grid = calculate_volatility_grid(stock_hist, is_etf=is_etf) if (score >= 60 or is_etf) else None
            
            output["stocks"][t] = {
                "symbol": t, "name": info["name"], "is_etf": is_etf, "industry": "ETF" if is_etf else "核心股",
                "canslim": {
                    "C": factors["C"], "A": factors["A"], "N": factors["N"], "S": factors["S"], 
                    "L": factors["L"], "I": factors["I"], "M": factors["M"],
                    "score": int(score), "mansfield_rs": float(m_rs), "rs_ratio": 1.0,
                    "grid_strategy": grid
                },
                "institutional": []
            }
            print(f"✅ {t} processed.")
            time.sleep(0.5)
        except: pass

    with open("docs/data.json", "w") as f:
        def js(obj):
            if isinstance(obj, (datetime, pd.Timestamp)): return str(obj)
            if isinstance(obj, np.bool_): return bool(obj)
            return obj
        json.dump(output, f, ensure_ascii=False, indent=2, default=js)
    print("🎉 Rebuild Success.")

if __name__ == "__main__": rebuild()
