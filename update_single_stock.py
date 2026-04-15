#!/usr/bin/env python3
"""
Update Single Stock Data script.
Evaluates and updates a specific stock ticker in data_base.json and data.json.
"""

import os
import sys
import json
import logging
import requests
import pandas as pd
import yfinance as yf
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from tej_processor import TEJProcessor
from core.logic import (
    calculate_accumulation_strength, compute_canslim_score, 
    compute_canslim_score_etf, calculate_l_factor, 
    calculate_mansfield_rs, calculate_volatility_grid,
    calculate_rs_trend, check_n_factor
)
from excel_processor import ExcelDataProcessor
from create_medium_data import create_medium_data

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

TWSE_TICKER_URL = "https://mopsfin.twse.com.tw/opendata/t187ap03_L.csv"
TPEx_TICKER_URL = "https://mopsfin.twse.com.tw/opendata/t187ap03_O.csv"
TWSE_INST_URL = "https://www.twse.com.tw/rwd/zh/fund/T86"

def get_all_tw_tickers():
    ticker_map = {}
    for url, suffix in [(TWSE_TICKER_URL, ".TW"), (TPEx_TICKER_URL, ".TWO")]:
        try:
            df = pd.read_csv(url, encoding='utf-8')
            for _, row in df.iterrows():
                tid = str(row['公司代號']).strip()
                if len(tid) == 4:
                    ticker_map[tid] = {"name": str(row['公司簡稱']), "suffix": suffix}
        except: pass
    
    cache_file = "etf_cache.json"
    if os.path.exists(cache_file):
        with open(cache_file, "r", encoding="utf-8") as f:
            etfs = json.load(f).get("etfs", {})
            for tid, info in etfs.items():
                if "<BR>" in tid or "<br>" in tid: continue
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
                for row in data["data"]:
                    t = row[0].strip()
                    def si(s):
                        try: return int(str(s).replace(",", ""))
                        except: return 0
                    result[t] = {"foreign_net": si(row[4]) // 1000, "trust_net": si(row[10]) // 1000, "dealer_net": si(row[11]) // 1000}
    except: pass
    return result

class SingleStockUpdater:
    def __init__(self):
        self.root_dir = os.path.dirname(os.path.abspath(__file__))
        self.ticker_info = get_all_tw_tickers()
        self.excel_proc = ExcelDataProcessor(self.root_dir)
        self.excel_ratings = self.excel_proc.load_health_check_data()
        self.fund_holdings = self.excel_proc.load_fund_holdings_data()
        self.industry_data = self.excel_proc.load_industry_data()
        self.tej_processor = TEJProcessor()
        
        self.data_base_path = os.path.join(self.root_dir, "docs", "data_base.json")

    def update_stock(self, ticker: str):
        # Strict validation: Only allow 4-6 digits
        import re
        if not re.match(r'^\d{4,6}$', ticker):
            logger.error(f"Invalid ticker format: {ticker}. Only 4-6 digits are allowed.")
            return

        logger.info(f"Targeting stock: {ticker}")
        
        info = self.ticker_info.get(ticker)
        if not info:
            logger.error(f"Ticker {ticker} not found in official lists.")
            # Try to guess or use fallback
            info = {"name": ticker, "suffix": ".TW"}
            logger.info(f"Using default fallback: {ticker}.TW")

        # 1. Fetch Market Benchmark
        market_prices = None
        for sym in ["^TWII", "0050.TW"]:
            try:
                market_prices = yf.download(sym, period="2y", auto_adjust=True, progress=False)['Close'].squeeze()
                if not market_prices.empty: break
            except: continue
        
        if market_prices is None or market_prices.empty:
            logger.error("Failed to fetch market benchmark data.")
            return

        # 2. Fetch Institutional Dates & Data
        trading_dates = []
        try:
            r = requests.get("https://www.twse.com.tw/rwd/zh/TAIEX/TAIEXChart", params={"response": "json"}, timeout=15)
            trading_dates = [row[0].replace("-", "") for row in r.json() if row[0]][-20:]
        except: pass
        
        inst_by_date = {d: fetch_inst_all(d) for d in trading_dates}

        # 3. Fetch Stock Price History
        symbol = f"{ticker}{info['suffix']}"
        try:
            prices = yf.download(symbol, period="2y", auto_adjust=True, progress=False)['Close'].dropna().squeeze()
        except Exception as e:
            logger.error(f"Failed to download history for {symbol}: {e}")
            return

        if prices.empty:
            logger.error(f"No price data for {symbol}")
            return

        # 4. Calculate Metrics
        is_etf = self.tej_processor.is_etf(ticker) or ticker.startswith("00")
        history = []
        for d in reversed(trading_dates):
            if d in inst_by_date and ticker in inst_by_date[d]:
                history.append({"date": d, **inst_by_date[d][ticker]})

        m_rs = calculate_mansfield_rs(prices, market_prices)
        rs_trend = calculate_rs_trend(prices, market_prices)
        n_score = check_n_factor(prices)
        l_score = calculate_l_factor(m_rs)
        
        # Institutional score: net buying in last 3 trading days
        i_score = len(history) >= 1 and sum(h["foreign_net"]+h["trust_net"]+h["dealer_net"] for h in history[:3]) > 0
        
        factors = {"C": False, "A": False, "N": n_score, "S": True, "L": l_score, "I": i_score, "M": True}
        if not is_etf and self.excel_ratings and ticker in self.excel_ratings:
            r = self.excel_ratings[ticker].get('eps_rating', 0)
            factors["C"] = factors["A"] = r >= 60

        score = compute_canslim_score_etf(factors) if is_etf else compute_canslim_score(factors)
        grid = calculate_volatility_grid(prices, is_etf=is_etf) if (score >= 60 or is_etf) else None

        stock_entry = {
            "symbol": ticker, "name": info["name"], "industry": "ETF" if is_etf else self.industry_data.get(ticker, {}).get('industry', '未知'),
            "is_etf": is_etf,
            "canslim": {
                "C": bool(factors["C"]), "A": bool(factors["A"]), "N": bool(factors["N"]), 
                "S": bool(factors["S"]), "L": bool(factors["L"]), "I": bool(factors["I"]), "M": bool(factors["M"]),
                "score": int(score), "mansfield_rs": float(m_rs), "rs_trend": rs_trend,
                "grid_strategy": grid, "excel_ratings": self.excel_ratings.get(ticker), "fund_holdings": self.fund_holdings.get(ticker)
            },
            "institutional": history[:20]
        }

        # 5. Update data_base.json
        if not os.path.exists(self.data_base_path):
            logger.error(f"data_base.json not found at {self.data_base_path}")
            return

        with open(self.data_base_path, 'r', encoding='utf-8') as f:
            full_data = json.load(f)

        if "stocks" not in full_data:
            full_data["stocks"] = {}
        
        full_data["stocks"][ticker] = stock_entry
        full_data["last_updated"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Sort out serializability
        def json_serial(obj):
            if isinstance(obj, (datetime, pd.Timestamp)): return obj.strftime('%Y-%m-%d')
            if isinstance(obj, np.bool_): return bool(obj)
            if isinstance(obj, (np.integer, np.floating, np.float64, np.int64)): return obj.item()
            raise TypeError ("Type %s not serializable" % type(obj))

        with open(self.data_base_path, 'w', encoding='utf-8') as f:
            json.dump(full_data, f, ensure_ascii=False, indent=2, default=json_serial)
        
        logger.info(f"✅ Updated {ticker} in data_base.json")

        # 6. Re-sync to medium data (docs/data.json)
        logger.info("Syncing changes to docs/data.json...")
        create_medium_data()
        logger.info("✅ All updates complete.")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python update_single_stock.py <ticker>")
        sys.exit(1)
    
    ticker = sys.argv[1]
    SingleStockUpdater().update_stock(ticker)
