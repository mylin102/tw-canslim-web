"""
Fast Dashboard Data Generator - Parallel yfinance downloads
Uses ThreadPoolExecutor for stable, parallel data fetching.
Generates data.json with 100% consistency with core.logic.
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
from concurrent.futures import ThreadPoolExecutor, as_completed
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
                if "<BR>" in tid: continue
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

class FastDataGenerator:
    def __init__(self):
        self.ticker_info = get_all_tw_tickers()
        self.root_dir = os.path.dirname(os.path.abspath(__file__))
        self.excel_proc = ExcelDataProcessor(self.root_dir)
        self.excel_ratings = self.excel_proc.load_health_check_data()
        self.fund_holdings = self.excel_proc.load_fund_holdings_data()
        self.industry_data = self.excel_proc.load_industry_data()
        self.tej_processor = TEJProcessor()

    def fetch_single(self, t, info, market_prices, trading_dates, inst_by_date):
        try:
            sym = f"{t}{info['suffix']}"
            prices = yf.Ticker(sym).history(period="2y", auto_adjust=True)['Close'].squeeze()
            if prices.empty: return None
            
            is_etf = self.tej_processor.is_etf(t) or t.startswith("00")
            history = []
            for d in reversed(trading_dates):
                if d in inst_by_date and t in inst_by_date[d]:
                    history.append({"date": d, **inst_by_date[d][t]})

            m_rs = calculate_mansfield_rs(prices, market_prices)
            rs_trend = calculate_rs_trend(prices, market_prices)
            n_score = check_n_factor(prices)
            l_score = calculate_l_factor(m_rs)
            i_score = len(history) >= 1 and sum(h["foreign_net"]+h["trust_net"]+h["dealer_net"] for h in history[:3]) > 0
            
            # rs_ratio (approximate)
            rs_ratio = 1.0
            if market_prices is not None and len(prices) >= 60:
                stock_ret = (prices.iloc[-1] - prices.iloc[-60]) / prices.iloc[-60]
                m_ret = (market_prices.iloc[-1] - market_prices.iloc[-60]) / market_prices.iloc[-60]
                rs_ratio = round(stock_ret / m_ret, 2) if abs(m_ret) > 0.01 else 1.0

            factors = {"C": False, "A": False, "N": n_score, "S": True, "L": l_score, "I": i_score, "M": True}
            if not is_etf and self.excel_ratings and t in self.excel_ratings:
                r = self.excel_ratings[t].get('eps_rating', 0)
                factors["C"] = factors["A"] = r >= 60

            score = compute_canslim_score_etf(factors) if is_etf else compute_canslim_score(factors)
            grid = calculate_volatility_grid(prices, is_etf=is_etf) if (score >= 60 or is_etf) else None

            return t, {
                "symbol": t, "name": info["name"], "industry": "ETF" if is_etf else self.industry_data.get(t, {}).get('industry', '未知'),
                "is_etf": is_etf,
                "canslim": {
                    "C": bool(factors["C"]), "A": bool(factors["A"]), "N": bool(factors["N"]), 
                    "S": bool(factors["S"]), "L": bool(factors["L"]), "I": bool(factors["I"]), "M": bool(factors["M"]),
                    "score": int(score), "mansfield_rs": float(m_rs), "rs_trend": rs_trend, "rs_ratio": rs_ratio,
                    "grid_strategy": grid, "excel_ratings": self.excel_ratings.get(t), "fund_holdings": self.fund_holdings.get(t)
                },
                "institutional": history[:20]
            }
        except: return None

    def run(self):
        logger.info(f"Starting Parallel Data Generator for {len(self.ticker_info)} symbols")
        market_prices = yf.download("^TWII", period="2y", auto_adjust=True)['Close'].squeeze()
        
        # Institutional Dates
        trading_dates = []
        try:
            r = requests.get("https://www.twse.com.tw/rwd/zh/TAIEX/TAIEXChart", params={"response": "json"}, timeout=15)
            trading_dates = [row[0].replace("-", "") for row in r.json() if row[0]][-20:]
        except: pass
        inst_by_date = {d: fetch_inst_all(d) for d in trading_dates}

        output = {"last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "stocks": {}}
        
        # Limit to top 500 for fast dashboard, or all if you prefer
        tickers = list(self.ticker_info.items())
        
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(self.fetch_single, t, info, market_prices, trading_dates, inst_by_date) for t, info in tickers]
            for i, future in enumerate(as_completed(futures)):
                res = future.result()
                if res:
                    output["stocks"][res[0]] = res[1]
                if i % 100 == 0: logger.info(f"Progress: {i}/{len(tickers)}")

        # Recalculate Industry Strength
        ind_map = {}
        for s in output["stocks"].values():
            ind = s["industry"]
            if ind not in ind_map: ind_map[ind] = {"scores": [], "inst_3d_net": 0, "high_score_count": 0, "stock_count": 0}
            sc = s["canslim"]["score"]
            ind_map[ind]["scores"].append(sc)
            ind_map[ind]["stock_count"] += 1
            if sc >= 80: ind_map[ind]["high_score_count"] += 1
            if s["institutional"]:
                ind_map[ind]["inst_3d_net"] += sum((d.get("foreign_net", 0) + d.get("trust_net", 0) + d.get("dealer_net", 0)) for d in s["institutional"][:3])

        output["industry_strength"] = sorted([
            {"industry": i, "avg_score": round(sum(d["scores"])/len(d["scores"]), 1), "total_inst_net_3d": int(d["inst_3d_net"]), "high_score_count": d["high_score_count"], "stock_count": d["stock_count"]}
            for i, d in ind_map.items() if i != "未知"
        ], key=lambda x: x["avg_score"], reverse=True)

        def json_serial(obj):
            if isinstance(obj, (datetime, pd.Timestamp)): return obj.strftime('%Y-%m-%d')
            if isinstance(obj, np.bool_): return bool(obj)
            if isinstance(obj, (np.integer, np.floating, np.float64, np.int64)): return obj.item()
            raise TypeError ("Type %s not serializable" % type(obj))

        out_path = os.path.join(self.root_dir, "docs", "data.json")
        with open(out_path, 'w', encoding='utf-8') as f:
            json.dump(output, f, ensure_ascii=False, indent=2, default=json_serial)
        logger.info(f"✅ Exported {len(output['stocks'])} stocks.")

if __name__ == "__main__":
    FastDataGenerator().run()
