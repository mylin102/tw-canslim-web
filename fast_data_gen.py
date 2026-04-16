"""
Fast Dashboard Data Generator - Optimized Batch yfinance
Uses small chunks + robust index mapping for 100% data recovery.
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
from tej_processor import TEJProcessor
from core.logic import (
    calculate_accumulation_strength, compute_canslim_score, 
    compute_canslim_score_etf, calculate_l_factor, 
    calculate_mansfield_rs, calculate_volatility_grid,
    calculate_rs_trend, check_n_factor
)
from excel_processor import ExcelDataProcessor

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

class FastDataGenerator:
    def __init__(self):
        self.ticker_info = get_all_tw_tickers()
        self.root_dir = os.path.dirname(os.path.abspath(__file__))
        self.excel_proc = ExcelDataProcessor(self.root_dir)
        self.excel_ratings = self.excel_proc.load_health_check_data() or {}
        self.fund_holdings = self.excel_proc.load_fund_holdings_data() or {}
        self.industry_data = self.excel_proc.load_industry_data() or {}
        self.tej_processor = TEJProcessor()

    def run(self):
        logger.info(f"Starting Optimized Batch Data Generator for {len(self.ticker_info)} symbols")
        
        # Market Benchmark
        market_prices = None
        for sym in ["^TWII", "0050.TW"]:
            try:
                market_prices = yf.download(sym, period="2y", auto_adjust=True, progress=False)['Close'].squeeze()
                if not market_prices.empty: break
            except: continue
        
        # Institutional Dates
        trading_dates = []
        try:
            r = requests.get("https://www.twse.com.tw/rwd/zh/TAIEX/TAIEXChart", params={"response": "json"}, timeout=15)
            trading_dates = [row[0].replace("-", "") for row in r.json() if row[0]][-20:]
        except: pass
        inst_by_date = {d: fetch_inst_all(d) for d in trading_dates}

        # Chunked Batch Download (Small chunks to avoid rate limit)
        all_symbols = [f"{t}{info['suffix']}" for t, info in self.ticker_info.items()]
        price_data = {}
        
        logger.info(f"Downloading history in chunks of 50...")
        failed_downloads = []
        
        for i in range(0, len(all_symbols), 50):
            chunk = all_symbols[i:i+50]
            chunk_failed = []
            
            try:
                # 使用更穩健的下載方式
                df = yf.download(
                    chunk, 
                    period="2y", 
                    auto_adjust=True, 
                    progress=False, 
                    threads=True,
                    ignore_tz=True,
                    group_by='ticker'
                )
                
                if df is None or df.empty:
                    logger.warning(f"Chunk {i}: df is None or empty")
                    # 嘗試單獨下載每個股票
                    for sym in chunk:
                        try:
                            single_df = yf.download(sym, period="2y", auto_adjust=True, progress=False)
                            if single_df is not None and not single_df.empty and 'Close' in single_df.columns:
                                t = sym.split('.')[0]
                                price_data[t] = single_df['Close'].dropna().squeeze()
                            else:
                                chunk_failed.append(sym)
                        except Exception as e:
                            logger.debug(f"Failed to download {sym} individually: {e}")
                            chunk_failed.append(sym)
                    continue
                
                # 處理下載結果
                if isinstance(df.columns, pd.MultiIndex):
                    # MultiIndex結構: (Price, Ticker) 當 group_by='ticker'
                    # 或者 (Ticker, Price) 當 group_by='column'
                    # 檢查結構
                    if df.columns.names[0] == 'Price' and df.columns.names[1] == 'Ticker':
                        # 結構: (Price, Ticker)
                        tickers = df.columns.get_level_values(1).unique()
                        for ticker in tickers:
                            try:
                                if ('Close', ticker) in df.columns:
                                    close_series = df[('Close', ticker)].dropna().squeeze()
                                    if not close_series.empty:
                                        t = ticker.split('.')[0]
                                        price_data[t] = close_series
                                else:
                                    chunk_failed.append(ticker)
                            except Exception as e:
                                logger.debug(f"Failed to extract {ticker}: {e}")
                                chunk_failed.append(ticker)
                    elif df.columns.names[0] == 'Ticker' and df.columns.names[1] == 'Price':
                        # 結構: (Ticker, Price)
                        tickers = df.columns.get_level_values(0).unique()
                        for ticker in tickers:
                            try:
                                if (ticker, 'Close') in df.columns:
                                    close_series = df[(ticker, 'Close')].dropna().squeeze()
                                    if not close_series.empty:
                                        t = ticker.split('.')[0]
                                        price_data[t] = close_series
                                else:
                                    chunk_failed.append(ticker)
                            except Exception as e:
                                logger.debug(f"Failed to extract {ticker}: {e}")
                                chunk_failed.append(ticker)
                    else:
                        # 未知結構
                        logger.warning(f"Chunk {i}: Unknown MultiIndex structure: {df.columns.names}")
                        # 嘗試通用的方法
                        try:
                            # 尋找包含'Close'的列
                            close_cols = [col for col in df.columns if 'Close' in str(col)]
                            for col in close_cols:
                                try:
                                    close_series = df[col].dropna().squeeze()
                                    if not close_series.empty:
                                        # 嘗試從列名提取股票代號
                                        col_str = str(col)
                                        if '.TW' in col_str or '.TWO' in col_str:
                                            # 從列名提取股票代號
                                            import re
                                            match = re.search(r'([0-9]{4,5}\.[TW]+)', col_str)
                                            if match:
                                                ticker = match.group(1)
                                                t = ticker.split('.')[0]
                                                price_data[t] = close_series
                                except Exception as e:
                                    logger.debug(f"Failed to extract from column {col}: {e}")
                        except Exception as e:
                            logger.warning(f"Failed to extract any data: {e}")
                            chunk_failed.extend(chunk)
                else:
                    # 單一股票或異常結構
                    logger.warning(f"Chunk {i}: Unexpected df structure, shape={df.shape}")
                    # 嘗試提取第一個股票
                    if len(chunk) == 1 and 'Close' in df.columns:
                        t = chunk[0].split('.')[0]
                        price_data[t] = df['Close'].dropna().squeeze()
                    else:
                        # 標記所有失敗
                        chunk_failed.extend(chunk)
                
            except Exception as e:
                logger.error(f"Chunk {i} failed: {e}")
                chunk_failed.extend(chunk)
            
            if chunk_failed:
                failed_downloads.extend(chunk_failed)
                logger.warning(f"Chunk {i}: {len(chunk_failed)} failed downloads")
            
            time.sleep(2) # Polite delay
        
        # 記錄失敗的下載
        if failed_downloads:
            logger.error(f"\n{len(failed_downloads)} Failed downloads:")
            # 分組顯示失敗的股票
            failed_groups = {}
            for sym in failed_downloads:
                base = sym.split('.')[0]
                failed_groups.setdefault(base, []).append(sym)
            
            for base, syms in list(failed_groups.items())[:10]:  # 只顯示前10組
                logger.error(f"  {syms}: Failed to download")

        output = {"last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "stocks": {}}
        
        for t, prices in price_data.items():
            info = self.ticker_info.get(t)
            if not info: continue
            
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
            
            factors = {"C": False, "A": False, "N": n_score, "S": True, "L": l_score, "I": i_score, "M": True}
            if not is_etf and self.excel_ratings and t in self.excel_ratings:
                r = self.excel_ratings[t].get('eps_rating', 0)
                factors["C"] = factors["A"] = r >= 60

            score = compute_canslim_score_etf(factors) if is_etf else compute_canslim_score(factors)
            grid = calculate_volatility_grid(prices, is_etf=is_etf) if (score >= 60 or is_etf) else None

            output["stocks"][t] = {
                "symbol": t, "name": info["name"], "industry": "ETF" if is_etf else self.industry_data.get(t, {}).get('industry', '未知'),
                "is_etf": is_etf,
                "canslim": {
                    "C": bool(factors["C"]), "A": bool(factors["A"]), "N": bool(factors["N"]), 
                    "S": bool(factors["S"]), "L": bool(factors["L"]), "I": bool(factors["I"]), "M": bool(factors["M"]),
                    "score": int(score), "mansfield_rs": float(m_rs), "rs_trend": rs_trend,
                    "grid_strategy": grid, "excel_ratings": self.excel_ratings.get(t), "fund_holdings": self.fund_holdings.get(t)
                },
                "institutional": history[:20]
            }

        # Industry Strength
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
