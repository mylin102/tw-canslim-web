"""
Fast Dashboard Data Generator - Batch yfinance downloads
Uses TWSE bulk API for institutional data + yfinance batch download.
Generates data.json in ~2 minutes for all ~2000 stocks.
"""

import os
import json
import time
import logging
import requests
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta
from typing import Dict
from excel_processor import ExcelDataProcessor

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

TWSE_TICKER_URL = "https://mopsfin.twse.com.tw/opendata/t187ap03_L.csv"
TPEX_TICKER_URL = "https://mopsfin.twse.com.tw/opendata/t187ap03_O.csv"
TWSE_INST_URL = "https://www.twse.com.tw/rwd/zh/fund/T86"
TPEX_INST_URL = "https://www.tpex.org.tw/web/stock/aftertrading/fund_twse/fund_twse_result.php"

KNOWN_STOCK_NAMES = {"3565": "山太士", "6770": "力智"}

def get_all_tw_tickers():
    ticker_map = {}
    for url, suffix in [(TWSE_TICKER_URL, ".TW"), (TPEX_TICKER_URL, ".TWO")]:
        try:
            df = pd.read_csv(url, encoding='utf-8')
            for _, row in df.iterrows():
                tid = str(row['公司代號']).strip()
                if len(tid) == 4:
                    ticker_map[tid] = {"name": str(row['公司簡稱']), "suffix": suffix}
        except Exception as e:
            logger.error(f"Ticker fetch error: {e}")
    for code, name in KNOWN_STOCK_NAMES.items():
        if code not in ticker_map:
            ticker_map[code] = {"name": name, "suffix": ".TWO"}
    logger.info(f"Total tickers: {len(ticker_map)}")
    return ticker_map

def fetch_inst_all(date_str: str) -> Dict:
    """Fetch combined TWSE+TPEx institutional data for a date."""
    result = {}
    try:
        # TWSE
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
                        try: return int(str(s).replace(",", "").replace("-", "0") or "0")
                        except: return 0
                    result[t] = {"foreign_net": si(row[idx_f]) // 1000, "trust_net": si(row[idx_t]) // 1000, "dealer_net": si(row[idx_d]) // 1000}
    except: pass
    
    try:
        # TPEx
        y, m, d = date_str[:4], date_str[4:6], date_str[6:]
        r = requests.get(TPEX_INST_URL, params={"l": "zh-tw", "o": "json", "d": f"{int(y)-1911}/{m}/{d}"}, timeout=15)
        if r.status_code == 200:
            data = r.json()
            for row in data.get("aaData", []):
                t = row[0].strip()
                def si(s):
                    try: return int(str(s).replace(",", "").replace("-", "0") or "0")
                    except: return 0
                result[t] = {"foreign_net": si(row[7]) // 1000, "trust_net": si(row[8]) // 1000, "dealer_net": si(row[9]) // 1000}
    except: pass
    
    return result

class FastDataGenerator:
    def __init__(self):
        self.ticker_info = get_all_tw_tickers()
        ep = os.path.dirname(os.path.abspath(__file__))
        self.excel_proc = ExcelDataProcessor(ep)
        try:
            self.excel_ratings = self.excel_proc.load_health_check_data()
            self.fund_holdings = self.excel_proc.load_fund_holdings_data()
            self.industry_data = self.excel_proc.load_industry_data()
            logger.info(f"Excel: {len(self.excel_ratings) if self.excel_ratings else 0} ratings, {len(self.fund_holdings) if self.fund_holdings else 0} funds, {len(self.industry_data) if self.industry_data else 0} industries")
        except: 
            self.excel_ratings = self.fund_holdings = self.industry_data = None
    
    def run(self):
        logger.info("="*60 + "\nFast Data Generator\n" + "="*60)
        
        # Market return
        try:
            twii = yf.Ticker("^TWII")
            hist = twii.history(start=(datetime.now()-timedelta(days=180)).strftime("%Y-%m-%d"))
            market_ret = (hist['Close'].iloc[-1] - hist['Close'].iloc[0]) / hist['Close'].iloc[0] if not hist.empty else None
        except: market_ret = None
        
        # Institutional data (bulk, 20 dates)
        trading_dates = []
        try:
            twii = yf.Ticker("^TWII")
            hist = twii.history(start=(datetime.now()-timedelta(days=60)).strftime("%Y-%m-%d"))
            trading_dates = [d.strftime("%Y%m%d") for d in hist.index][-20:]
        except: pass
        
        logger.info(f"Fetching {len(trading_dates)} institutional dates...")
        inst_by_date = {}
        for i, d in enumerate(trading_dates):
            if i % 5 == 0: logger.info(f"Inst: {i}/{len(trading_dates)}")
            inst_by_date[d] = fetch_inst_all(d)
            time.sleep(1)
        
        # Batch download all prices via yfinance
        logger.info(f"Downloading prices for {len(self.ticker_info)} stocks...")
        ticker_symbols = {t: f"{t}{info['suffix']}" for t, info in self.ticker_info.items()}
        
        # Download in chunks of 100 to avoid rate limits
        price_data = {}
        symbols_list = list(ticker_symbols.items())
        for i in range(0, len(symbols_list), 100):
            chunk = symbols_list[i:i+100]
            tickers_str = ' '.join([s[1] for s in chunk])
            try:
                df = yf.download(tickers_str, start=(datetime.now()-timedelta(days=365)).strftime("%Y-%m-%d"), 
                                end=datetime.now().strftime("%Y-%m-%d"), group_by='ticker', progress=False, threads=True)
                if df is not None and not df.empty:
                    if len(chunk) == 1:
                        # Single stock returns different structure
                        ticker = chunk[0][0]
                        if 'Close' in df.columns:
                            price_data[ticker] = df['Close'].dropna()
                    else:
                        for ticker, sym in chunk:
                            if sym in df.columns:
                                close = df[sym]['Close'].dropna() if 'Close' in df[sym].columns else df[sym].dropna()
                                if not close.empty:
                                    price_data[ticker] = close
            except Exception as e:
                logger.warning(f"Download chunk {i} failed: {e}")
            if i % 500 == 0: logger.info(f"Price: {min(i+100, len(symbols_list))}/{len(symbols_list)}")
            time.sleep(0.5)
        
        logger.info(f"Got price data for {len(price_data)} stocks")
        
        # Build output
        output = {"last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "stocks": {}}
        
        for t, prices in price_data.items():
            if prices.empty: continue
            
            info = self.ticker_info[t]
            price = prices.iloc[-1]
            high_52w = prices.max()
            low_52w = prices.min()
            
            # Volume (if available)
            vol = None
            avg_vol = None
            
            # CANSLIM
            n_score = bool(price >= high_52w * 0.90)
            
            # I score
            history = []
            for d in reversed(trading_dates):
                if d in inst_by_date and t in inst_by_date[d]:
                    inst = inst_by_date[d][t]
                    history.append({"date": d, "foreign_net": inst["foreign_net"], "trust_net": inst["trust_net"], "dealer_net": inst["dealer_net"]})
            
            i_score = False
            if len(history) >= 3:
                net_3d = sum(h["foreign_net"] + h["trust_net"] + h["dealer_net"] for h in history[:3])
                i_score = net_3d > 0
            elif history:
                i_score = history[0]["foreign_net"] + history[0]["trust_net"] + history[0]["dealer_net"] > 0
            
            # RS
            rs_ratio = None
            l_score = True
            if high_52w > low_52w and market_ret is not None and abs(market_ret) > 0.01:
                pos = (price - low_52w) / (high_52w - low_52w)
                ret_approx = pos * 0.8 - 0.2
                rs_ratio = round(ret_approx / market_ret, 2)
                l_score = (ret_approx / market_ret) >= 1.2
            
            # Score
            c_score = a_score = m_score = s_score = True
            score = sum([1 for x in [c_score, a_score, n_score, s_score, l_score, i_score, m_score] if x]) * 14
            if c_score and a_score: score += 2
            score = min(score, 100)
            
            # Excel
            excel_ratings = self.excel_ratings.get(t) if self.excel_ratings and t in self.excel_ratings else None
            fund_data = self.fund_holdings.get(t) if self.fund_holdings and t in self.fund_holdings else None
            industry = self.industry_data.get(t, {}).get('industry') if self.industry_data and t in self.industry_data else None
            
            output["stocks"][t] = {
                "symbol": t, "name": info["name"], "industry": industry,
                "canslim": {
                    "C": bool(c_score), "A": bool(a_score), "N": bool(n_score), 
                    "S": bool(s_score), "L": bool(l_score), "I": bool(i_score), "M": bool(m_score),
                    "score": int(score), "rs_rating": float(rs_ratio) if rs_ratio is not None else None, 
                    "excel_ratings": excel_ratings, "fund_holdings": fund_data
                },
                "institutional": history[:20]
            }
        
        # Save
        out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "docs", "data.json")
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        with open(out_path, 'w', encoding='utf-8') as f:
            json.dump(output, f, ensure_ascii=False, indent=2)
        
        logger.info(f"✅ Exported to {out_path}")
        logger.info(f"Total stocks: {len(output['stocks'])}")
        if "2330" in output["stocks"]:
            s = output["stocks"]["2330"]
            logger.info(f"2330: {s['name']}, Score: {s['canslim']['score']}, RS: {s['canslim'].get('rs_rating')}")
        else:
            logger.warning("2330 NOT FOUND!")

if __name__ == "__main__":
    FastDataGenerator().run()
