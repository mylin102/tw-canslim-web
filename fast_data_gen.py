"""
Fast Dashboard Data Generator - Batch yfinance downloads
Uses TWSE bulk API for institutional data + yfinance batch download.
Generates data.json in ~2 minutes for all ~2000 stocks.
REFACTORED: Now uses core.logic for 100% consistency.
"""

import os
import json
import time
import logging
import requests
import pandas as pd
import yfinance as yf
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from excel_processor import ExcelDataProcessor
from tej_processor import TEJProcessor
from core.logic import (
    calculate_accumulation_strength, compute_canslim_score, 
    compute_canslim_score_etf, calculate_l_factor, 
    calculate_mansfield_rs, calculate_volatility_grid,
    calculate_rs_trend, check_n_factor
)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

TWSE_TICKER_URL = "https://mopsfin.twse.com.tw/opendata/t187ap03_L.csv"
TPEx_TICKER_URL = "https://mopsfin.twse.com.tw/opendata/t187ap03_O.csv"
TWSE_INST_URL = "https://www.twse.com.tw/rwd/zh/fund/T86"
TPEx_INST_URL = "https://www.tpex.org.tw/web/stock/aftertrading/fund_twse/fund_twse_result.php"

def get_all_tw_tickers():
    ticker_map = {}
    for url, suffix in [(TWSE_TICKER_URL, ".TW"), (TPEx_TICKER_URL, ".TWO")]:
        try:
            df = pd.read_csv(url, encoding='utf-8')
            for _, row in df.iterrows():
                tid = str(row['公司代號']).strip()
                if len(tid) == 4:
                    ticker_map[tid] = {"name": str(row['公司簡稱']), "suffix": suffix}
        except Exception as e:
            logger.error(f"Ticker fetch error: {e}")
    
    # Add ETFs from cache
    cache_file = "etf_cache.json"
    if os.path.exists(cache_file):
        with open(cache_file, "r", encoding="utf-8") as f:
            etfs = json.load(f).get("etfs", {})
            for tid, info in etfs.items():
                if "<BR>" in tid or "(" in tid: continue # Filter garbage
                suffix = ".TW" if info.get("market") == "TWSE" else ".TWO"
                ticker_map[tid] = {"name": info["name"], "suffix": suffix}
                
    return ticker_map

def fetch_inst_all(date_str: str) -> Dict:
    result = {}
    try:
        r = requests.get(TWSE_INST_URL, params={"response": "json", "date": date_str, "selectType": "ALL"}, timeout=15)
        if r.status_code == 200:
            data = r.json()
            if data.get("stat") == "OK":
                fields = data.get("fields", [])
                idx_f = next((i for i, f in enumerate(fields) if "外資" in f and "買賣超" in f), 4)
                idx_t = next((i for i, f in enumerate(fields) if "投信" in f and "買賣超" in f), 10)
                idx_d = next((i for i, f in enumerate(fields) if "自營商" in f and "買賣超" in f), 11)
                for row in data["data"]:
                    t = row[0].strip()
                    def si(s):
                        try: return int(str(s).replace(",", ""))
                        except: return 0
                    result[t] = {
                        "foreign_net": si(row[idx_f]) // 1000,
                        "trust_net": si(row[idx_t]) // 1000,
                        "dealer_net": si(row[idx_d]) // 1000
                    }
    except: pass
    return result

class FastDataGenerator:
    def __init__(self):
        self.ticker_info = get_all_tw_tickers()
        ep = os.path.dirname(os.path.abspath(__file__))
        self.excel_proc = ExcelDataProcessor(ep)
        self.excel_ratings = self.excel_proc.load_health_check_data()
        self.fund_holdings = self.excel_proc.load_fund_holdings_data()
        self.industry_data = self.excel_proc.load_industry_data()
        self.tej_processor = TEJProcessor()

    def run(self):
        logger.info("Starting Refactored Fast Data Generator")
        
        # 1. Fetch Market Benchmark (^TWII)
        market_prices = None
        try:
            market_prices = yf.download("^TWII", period="2y", auto_adjust=True)['Close'].squeeze()
        except: pass

        # 2. Institutional Dates (last 20)
        trading_dates = []
        try:
            twii_url = "https://www.twse.com.tw/rwd/zh/TAIEX/TAIEXChart"
            r = requests.get(twii_url, params={"response": "json"}, timeout=15)
            if r.status_code == 200:
                data = r.json()
                trading_dates = [row[0].replace("-", "") for row in data if row[0]][-20:]
        except: pass
        
        inst_by_date = {d: fetch_inst_all(d) for d in trading_dates}

        # 3. Batch Price Download
        ticker_symbols = [f"{t}{info['suffix']}" for t, info in self.ticker_info.items()]
        # Fetch 2 years for Mansfield RS
        full_df = yf.download(ticker_symbols, start=(datetime.now()-timedelta(days=730)).strftime("%Y-%m-%d"), 
                             group_by='ticker', progress=False, threads=True, auto_adjust=True)

        # 4. Processing Loop
        output = {"last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "stocks": {}}
        
        for t, info in self.ticker_info.items():
            sym = f"{t}{info['suffix']}"
            if sym not in full_df.columns.levels[0]: continue
            
            # Use .squeeze() to ensure 1D Series even if yfinance returns 2D
            prices = full_df[sym]['Close'].dropna().squeeze()
            if prices.empty: continue
            
            # Use logic functions
            is_etf = self.tej_processor.is_etf(t) or t.startswith("00")
            
            # Institutional
            history = []
            for d in reversed(trading_dates):
                if d in inst_by_date and t in inst_by_date[d]:
                    inst = inst_by_date[d][t]
                    history.append({"date": d, **inst})

            # RS and N
            m_rs = calculate_mansfield_rs(prices, market_prices)
            rs_trend = calculate_rs_trend(prices, market_prices)
            n_score = check_n_factor(prices)
            l_score = calculate_l_factor(m_rs)

            # rs_ratio (Relative Strength Ratio)
            rs_ratio = 1.0
            if market_prices is not None and len(prices) >= 120 and len(market_prices) >= 120:
                stock_ret = (prices.iloc[-1] - prices.iloc[-120]) / prices.iloc[-120]
                market_ret = (market_prices.iloc[-1] - market_prices.iloc[-120]) / market_prices.iloc[-120]
                rs_ratio = round(stock_ret / market_ret, 2) if abs(market_ret) > 0.01 else 1.0

            i_score = len(history) >= 3 and sum(h["foreign_net"]+h["trust_net"]+h["dealer_net"] for h in history[:3]) > 0
            
            factors = {
                "C": False, "A": False, "N": n_score, "S": True, "L": l_score, "I": i_score, "M": True
            }
            
            # C/A Backup from Excel
            if not is_etf and self.excel_ratings and t in self.excel_ratings:
                eps_rating = self.excel_ratings[t].get('eps_rating', 0)
                factors["C"] = eps_rating >= 60
                factors["A"] = eps_rating >= 60

            if is_etf:
                score = compute_canslim_score_etf(factors)
            else:
                score = compute_canslim_score(factors)

            grid_data = calculate_volatility_grid(prices, is_etf=is_etf) if (score >= 60 or is_etf) else None

            output["stocks"][t] = {
                "symbol": t, "name": info["name"], "industry": "ETF" if is_etf else self.industry_data.get(t, {}).get('industry', '未知'),
                "is_etf": is_etf,
                "canslim": {
                    "C": bool(factors["C"]), "A": bool(factors["A"]), "N": bool(factors["N"]), 
                    "S": bool(factors["S"]), "L": bool(factors["L"]), "I": bool(factors["I"]), "M": bool(factors["M"]),
                    "score": int(score), "mansfield_rs": float(m_rs), "rs_trend": rs_trend, "rs_ratio": rs_ratio,
                    "grid_strategy": grid_data, 
                    "excel_ratings": self.excel_ratings.get(t),
                    "fund_holdings": self.fund_holdings.get(t)
                },
                "institutional": history[:20]
            }

        # Save with JSON Serializer
        def json_serial(obj):
            if isinstance(obj, (datetime, pd.Timestamp)): return obj.strftime('%Y-%m-%d')
            if isinstance(obj, np.bool_): return bool(obj)
            if isinstance(obj, (np.integer, np.floating)): return obj.item()
            raise TypeError ("Type %s not serializable" % type(obj))

        # Get project root directory
        root_dir = os.path.dirname(os.path.abspath(__file__))
        out_path = os.path.join(root_dir, "docs", "data.json")
        with open(out_path, 'w', encoding='utf-8') as f:
            json.dump(output, f, ensure_ascii=False, indent=2, default=json_serial)
        
        logger.info(f"✅ Fast Data Gen Completed! Stocks: {len(output['stocks'])}")

if __name__ == "__main__":
    FastDataGenerator().run()
