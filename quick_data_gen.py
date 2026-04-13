"""
Quick Dashboard Data Generator - No FinMind/TEJ Required
Uses FREE TWSE/TPEx bulk APIs + yfinance for all ~2000 stocks.
Generates data.json directly (bypasses stale parquet pipeline).
"""

import os
import json
import time
import logging
import requests
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta
from typing import Dict, Optional
from excel_processor import ExcelDataProcessor

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Free APIs
TWSE_TICKER_URL = "https://mopsfin.twse.com.tw/opendata/t187ap03_L.csv"
TPEX_TICKER_URL = "https://mopsfin.twse.com.tw/opendata/t187ap03_O.csv"
TWSE_INST_URL = "https://www.twse.com.tw/rwd/zh/fund/T86"
TPEX_INST_URL = "https://www.tpex.org.tw/web/stock/aftertrading/fund_twse/fund_twse_result.php"

KNOWN_STOCK_NAMES = {
    "3565": "山太士",
    "6770": "力智",
}

def get_all_tw_tickers():
    """Fetch full TWSE and TPEx ticker lists."""
    ticker_map = {}
    for url, suffix in [(TWSE_TICKER_URL, ".TW"), (TPEX_TICKER_URL, ".TWO")]:
        try:
            df = pd.read_csv(url, encoding='utf-8')
            for _, row in df.iterrows():
                tid = str(row['公司代號']).strip()
                if len(tid) == 4:
                    ticker_map[tid] = {"name": str(row['公司簡稱']), "suffix": suffix}
        except Exception as e:
            logger.error(f"Failed to fetch tickers from {url}: {e}")
    
    for code, name in KNOWN_STOCK_NAMES.items():
        if code not in ticker_map:
            ticker_map[code] = {"name": name, "suffix": ".TWO"}
    
    logger.info(f"Total tickers: {len(ticker_map)}")
    return ticker_map

def fetch_twse_inst(date_str: str) -> Dict:
    """Fetch TWSE institutional data for a date (bulk)."""
    try:
        params = {"response": "json", "date": date_str, "selectType": "ALL"}
        resp = requests.get(TWSE_INST_URL, params=params, timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            if data.get("stat") == "OK":
                fields = data.get("fields", [])
                idx_f = next((i for i, f in enumerate(fields) if "外資" in f and "買賣超" in f), 4)
                idx_t = next((i for i, f in enumerate(fields) if "投信" in f and "買賣超" in f), 10)
                idx_d = next((i for i, f in enumerate(fields) if "自營商" in f and "買賣超" in f), 11)
                result = {}
                for row in data["data"]:
                    t = row[0].strip()
                    def safe_int(s):
                        try: return int(str(s).replace(",", "").replace("-", "0") or "0")
                        except: return 0
                    result[t] = {"foreign_net": safe_int(row[idx_f]) // 1000, "trust_net": safe_int(row[idx_t]) // 1000, "dealer_net": safe_int(row[idx_d]) // 1000}
                return result
    except Exception as e:
        logger.warning(f"TWSE inst fetch failed: {e}")
    return {}

def fetch_tpex_inst(date_str: str) -> Dict:
    """Fetch TPEx institutional data for a date (bulk)."""
    try:
        y, m, d = date_str[:4], date_str[4:6], date_str[6:]
        roc_date = f"{int(y)-1911}/{m}/{d}"
        params = {"l": "zh-tw", "o": "json", "d": roc_date}
        resp = requests.get(TPEX_INST_URL, params=params, timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            rows = data.get("aaData", [])
            if rows:
                result = {}
                for row in rows:
                    t = row[0].strip()
                    def safe_int(s):
                        try: return int(str(s).replace(",", "").replace("-", "0") or "0")
                        except: return 0
                    result[t] = {"foreign_net": safe_int(row[7]) // 1000, "trust_net": safe_int(row[8]) // 1000, "dealer_net": safe_int(row[9]) // 1000}
                return result
    except Exception as e:
        logger.warning(f"TPEx inst fetch failed: {e}")
    return {}

def get_recent_trading_dates(count: int = 20) -> list:
    """Get recent trading dates from TAIEX."""
    try:
        twii = yf.Ticker("^TWII")
        end = datetime.now()
        start = end - timedelta(days=60)
        hist = twii.history(start=start.strftime("%Y-%m-%d"), end=end.strftime("%Y-%m-%d"))
        if not hist.empty:
            dates = [d.strftime("%Y%m%d") for d in hist.index]
            return dates[-count:]
    except:
        pass
    # Fallback: generate recent weekdays
    dates = []
    d = datetime.now()
    while len(dates) < count:
        if d.weekday() < 5:
            dates.append(d.strftime("%Y%m%d"))
        d -= timedelta(days=1)
    return list(reversed(dates))

class QuickDataGenerator:
    def __init__(self):
        self.ticker_info = get_all_tw_tickers()
        self.excel_processor = ExcelDataProcessor(os.path.dirname(os.path.abspath(__file__)))
        self.excel_ratings = None
        self.fund_holdings = None
        self.industry_data = None
        self._load_excel_data()
    
    def _load_excel_data(self):
        try:
            self.excel_ratings = self.excel_processor.load_health_check_data()
            if self.excel_ratings: logger.info(f"Loaded Excel ratings for {len(self.excel_ratings)} stocks")
            self.fund_holdings = self.excel_processor.load_fund_holdings_data()
            if self.fund_holdings: logger.info(f"Loaded fund holdings for {len(self.fund_holdings)} stocks")
            self.industry_data = self.excel_processor.load_industry_data()
            if self.industry_data: logger.info(f"Loaded industry data for {len(self.industry_data)} stocks")
        except Exception as e:
            logger.warning(f"Excel data load failed: {e}")
    
    def run(self):
        logger.info("="*80)
        logger.info("Quick Dashboard Data Generator (Free APIs Only)")
        logger.info("="*80)
        
        # Get market return
        try:
            twii = yf.Ticker("^TWII")
            end = datetime.now()
            start = end - timedelta(days=180)
            hist = twii.history(start=start.strftime("%Y-%m-%d"), end=end.strftime("%Y-%m-%d"))
            if not hist.empty:
                market_return = (hist['Close'].iloc[-1] - hist['Close'].iloc[0]) / hist['Close'].iloc[0]
                logger.info(f"Market return (6mo): {market_return*100:.2f}%")
            else:
                market_return = None
        except:
            market_return = None
        
        # Fetch institutional data for recent dates (bulk, by date)
        trading_dates = get_recent_trading_dates(20)
        logger.info(f"Fetching institutional data for {len(trading_dates)} dates...")
        
        inst_by_date = {}
        for i, date_num in enumerate(trading_dates):
            if i % 5 == 0:
                logger.info(f"Inst dates: {i}/{len(trading_dates)}")
            twse = fetch_twse_inst(date_num)
            tpex = fetch_tpex_inst(date_num)
            inst_by_date[date_num] = {**twse, **tpex}
            time.sleep(1)
        
        # Process all stocks
        output = {
            "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "stocks": {}
        }
        
        ticker_list = sorted(self.ticker_info.keys())
        logger.info(f"Processing {len(ticker_list)} stocks...")
        
        for i, t in enumerate(ticker_list):
            if i % 100 == 0:
                logger.info(f"Processing: {i}/{len(ticker_list)}")
            
            info = self.ticker_info[t]
            suffix = info["suffix"]
            
            # Build institutional history
            history = []
            for date_num in reversed(trading_dates):
                if date_num in inst_by_date and t in inst_by_date[date_num]:
                    inst = inst_by_date[date_num][t]
                    history.append({
                        "date": date_num,
                        "foreign_net": inst["foreign_net"],
                        "trust_net": inst["trust_net"],
                        "dealer_net": inst["dealer_net"]
                    })
            
            # Fetch price data via yfinance
            try:
                full_ticker = f"{t}{suffix}"
                stock = yf.Ticker(full_ticker)
                info_yf = stock.info
                price = info_yf.get("currentPrice") or info_yf.get("regularMarketPrice")
                high_52w = info_yf.get("fiftyTwoWeekHigh")
                low_52w = info_yf.get("fiftyTwoWeekLow")
                volume = info_yf.get("volume") or info_yf.get("regularMarketVolume")
                avg_volume = info_yf.get("averageVolume") or info_yf.get("averageDailyVolume10Day")
            except:
                price = high_52w = low_52w = volume = avg_volume = None
            
            if price is None:
                continue  # Skip if no price data
            
            # CANSLIM metrics
            n_score = bool(price and high_52w and price >= high_52w * 0.90)
            s_score = bool(volume and avg_volume and avg_volume > 0 and volume >= avg_volume * 1.5)
            
            # I score: check recent institutional buying
            i_score = False
            if len(history) >= 3:
                net_3d = sum(h["foreign_net"] + h["trust_net"] + h["dealer_net"] for h in history[:3])
                i_score = net_3d > 0
            elif history:
                net = history[0]["foreign_net"] + history[0]["trust_net"] + history[0]["dealer_net"]
                i_score = net > 0
            
            # RS ratio
            rs_ratio = None
            l_score = True
            if price and high_52w and low_52w and high_52w > low_52w and market_return is not None:
                pos = (price - low_52w) / (high_52w - low_52w)
                ret_approx = pos * 0.8 - 0.2
                rs_ratio = round(ret_approx / market_return, 2) if abs(market_return) > 0.01 else 1.0
                l_score = (ret_approx / market_return) >= 1.2 if abs(market_return) > 0.01 else ret_approx >= 0.05
            
            # Score
            c_score = True  # Default
            a_score = True
            m_score = True
            score = sum([1 for x in [c_score, a_score, n_score, s_score, l_score, i_score, m_score] if x]) * 14
            if c_score and a_score: score += 2
            score = min(score, 100)
            
            # Excel ratings
            excel_ratings = None
            if self.excel_ratings and t in self.excel_ratings:
                excel_ratings = self.excel_ratings[t]
            
            fund_data = None
            if self.fund_holdings and t in self.fund_holdings:
                fund_data = self.fund_holdings[t]
            
            industry = None
            if self.industry_data and t in self.industry_data:
                industry = self.industry_data[t].get('industry')
            
            output["stocks"][t] = {
                "symbol": t,
                "name": info["name"],
                "industry": industry,
                "canslim": {
                    "C": c_score,
                    "A": a_score,
                    "N": n_score,
                    "S": s_score,
                    "L": l_score,
                    "I": i_score,
                    "M": m_score,
                    "score": score,
                    "rs_rating": rs_ratio,
                    "excel_ratings": excel_ratings,
                    "fund_holdings": fund_data
                },
                "institutional": history[:20]
            }
            
            time.sleep(0.05)  # Small delay for yfinance
        
        # Save to docs/data.json
        output_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "docs", "data.json")
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(output, f, ensure_ascii=False, indent=2)
        
        logger.info(f"✅ Dashboard data exported to {output_path}")
        logger.info(f"Total stocks: {len(output['stocks'])}")
        
        # Check 2330
        if "2330" in output["stocks"]:
            s = output["stocks"]["2330"]
            logger.info(f"2330: {s['name']}, Score: {s['canslim']['score']}, RS: {s['canslim'].get('rs_rating')}")
        else:
            logger.warning("2330 NOT FOUND!")

if __name__ == "__main__":
    gen = QuickDataGenerator()
    gen.run()
