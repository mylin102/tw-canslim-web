import os
import json
import logging
import pandas as pd
import numpy as np
from datetime import datetime
from export_canslim import CanslimEngine

logging.basicConfig(level=logging.INFO)

def verify_local_features():
    engine = CanslimEngine()
    # 增加測試標的：包含大型股與熱門 ETF
    test_tickers = [
        "2330", "2317", "2454", "2603", "2881",  # 個股
        "0050", "00631L", "00981A"               # ETF 範例
    ]
    
    engine.output_data["last_updated"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    market_hist = engine.get_price_history("^TWII".replace("^", ""), period="2y")
    
    print(f"\n🚀 Starting Local Verification for: {test_tickers}")
    
    for t in test_tickers:
        try:
            print(f"--- Analyzing {t} ---")
            info = engine.ticker_info.get(t, {"name": t, "suffix": ".TW"})
            
            # 判斷是否為 ETF (代號 00 開頭 4-6 碼皆視為 ETF)
            is_etf = engine.tej_processor.is_etf(t) or t.startswith("00")
            
            # 1. Institutional Data
            history = engine.fetch_institutional_data_finmind(t, days=60)
            chip_df = pd.DataFrame(history) if history else pd.DataFrame()
            
            # 2. Price History
            stock_hist = engine.get_price_history(t, period="2y")
            
            # 3. Financial Data
            financial_data = engine.fetch_financial_data(t)
            if not financial_data: continue
            
            from core.logic import (
                calculate_accumulation_strength, calculate_mansfield_rs, 
                compute_canslim_score, compute_canslim_score_etf, 
                calculate_l_factor, calculate_volatility_grid
            )
            
            price = financial_data.get("price", 0) or 0
            market_cap = financial_data.get("market_cap", 0) or 0
            total_shares = market_cap / price if price > 0 else 0
            
            m_rs = calculate_mansfield_rs(stock_hist, market_hist) if stock_hist is not None else 0.0
            from core.logic import calculate_rs_trend
            rs_trend = calculate_rs_trend(stock_hist, market_hist) if stock_hist is not None else {"trend": "neutral", "delta": 0}
            
            inst_strength_20d = calculate_accumulation_strength(chip_df, total_shares, days=20) if total_shares > 0 else 0
            
            l_score = calculate_l_factor(m_rs)
            i_score = engine.check_i_institutional(history) if history else False
            
            # TEJ C/A
            tej_ca = engine.tej_processor.calculate_canslim_c_and_a(t) if not is_etf else {}
            
            factors = {
                "C": tej_ca.get("C", False), "A": tej_ca.get("A", False), 
                "N": True, "S": True, "L": l_score, "I": i_score, "M": True
            }
            
            # 網格計算 (Grid)
            grid_data = calculate_volatility_grid(stock_hist, is_etf=is_etf) if stock_hist is not None else None
            
            score = compute_canslim_score_etf(factors, inst_strength_20d) if is_etf else compute_canslim_score(factors, inst_strength_20d)
            
            stock_data = {
                "symbol": t,
                "name": info["name"],
                "industry": "ETF" if is_etf else "驗證標的",
                "is_etf": is_etf,
                "canslim": {
                    "C": factors["C"], "A": factors["A"], "N": True, "S": True, 
                    "L": l_score, "I": i_score, "M": True,
                    "score": score,
                    "mansfield_rs": round(m_rs, 3),
                    "rs_trend": rs_trend,
                    "grid_strategy": grid_data
                },
                "institutional": history[:10] if history else [],
                "financials": financial_data
            }
            engine.output_data["stocks"][t] = stock_data
            type_str = "ETF" if is_etf else "Stock"
            print(f"✅ {t} ({type_str}) Done: Score={score}, GridPivot={grid_data['levels'][2]['price'] if grid_data else 'N/A'}")
            
        except Exception as e:
            print(f"❌ Error on {t}: {e}")

    # Save to docs/data.json
    with open("docs/data.json", "w", encoding="utf-8") as f:
        def json_serial(obj):
            if isinstance(obj, (datetime, pd.Timestamp)):
                return obj.strftime('%Y-%m-%d')
            if isinstance(obj, np.bool_):
                return bool(obj)
            if isinstance(obj, np.integer):
                return int(obj)
            if isinstance(obj, np.floating):
                return float(obj)
            raise TypeError ("Type %s not serializable" % type(obj))

        json.dump(engine.output_data, f, ensure_ascii=False, indent=2, default=json_serial)

    print("\n🎉 Verification data generated successfully at docs/data.json")


if __name__ == "__main__":
    verify_local_features()
