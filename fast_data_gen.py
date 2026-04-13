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
        # TWSE - exact field indices from API
        r = requests.get(TWSE_INST_URL, params={"response": "json", "date": date_str, "selectType": "ALL"}, timeout=15)
        if r.status_code == 200:
            data = r.json()
            if data.get("stat") == "OK":
                fields = data.get("fields", [])
                # Exact indices from TWSE T86 API:
                # [4] 外陸資買賣超股數(不含外資自營商)
                # [10] 投信買賣超股數
                # [11] 自營商買賣超股數
                idx_f = next((i for i, f in enumerate(fields) if f == "外陸資買賣超股數(不含外資自營商)"), 4)
                idx_t = next((i for i, f in enumerate(fields) if f == "投信買賣超股數"), 10)
                idx_d = next((i for i, f in enumerate(fields) if f == "自營商買賣超股數"), 11)
                for row in data["data"]:
                    t = row[0].strip()
                    def si(s):
                        try: return int(str(s).replace(",", ""))
                        except: return 0
                    result[t] = {
                        "foreign_net": round(si(row[idx_f]) / 1000),
                        "trust_net": round(si(row[idx_t]) / 1000),
                        "dealer_net": round(si(row[idx_d]) / 1000)
                    }
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
                    try: return int(str(s).replace(",", ""))
                    except: return 0
                result[t] = {
                    "foreign_net": round(si(row[7]) / 1000),
                    "trust_net": round(si(row[8]) / 1000),
                    "dealer_net": round(si(row[9]) / 1000)
                }
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
        
        # Market return - use TWSE TAIEX data instead of yfinance
        market_ret = None
        try:
            # Fetch TAIEX from TWSE (free API)
            twii_url = "https://www.twse.com.tw/rwd/zh/TAIEXChart/BasicIndex"
            end_dt = datetime.now()
            start_dt = end_dt - timedelta(days=180)
            params = {"response": "json", "dateRange": "1", "frequency": "D", 
                     "startDate": start_dt.strftime("%Y/%m/%d"), "endDate": end_dt.strftime("%Y/%m/%d")}
            r = requests.get(twii_url, params=params, timeout=15)
            if r.status_code == 200:
                data = r.json()
                if data:
                    close_prices = [float(row[8]) for row in data if row[8]]
                    if len(close_prices) >= 2:
                        market_ret = (close_prices[-1] - close_prices[0]) / close_prices[0]
                        logger.info(f"Market return (6mo): {market_ret*100:.2f}% ({close_prices[0]:.0f} → {close_prices[-1]:.0f})")
        except Exception as e:
            logger.warning(f"Failed to fetch TAIEX: {e}")
        
        if market_ret is None:
            logger.warning("Using default market return of 0.3 (30%)")
            market_ret = 0.3
        
        # Institutional data (bulk, 20 dates) - get recent trading dates
        trading_dates = []
        try:
            # Fetch TAIEX from TWSE to get actual trading dates
            twii_url = "https://www.twse.com.tw/rwd/zh/TAIEX/TAIEXChart"
            end_dt = datetime.now()
            start_dt = end_dt - timedelta(days=60)
            params = {"response": "json", "startDate": start_dt.strftime("%Y%m%d"), "endDate": end_dt.strftime("%Y%m%d")}
            r = requests.get(twii_url, params=params, timeout=15)
            if r.status_code == 200:
                data = r.json()
                if data:
                    trading_dates = [row[0].replace("-", "") for row in data if row[0]][-20:]
        except: pass
        
        # Fallback: generate recent weekdays (skip weekends)
        if not trading_dates:
            trading_dates = []
            d = datetime.now() - timedelta(days=1)  # Start from yesterday
            while len(trading_dates) < 10:  # Reduced to 10 for speed
                if d.weekday() < 5:  # Mon-Fri
                    trading_dates.append(d.strftime("%Y%m%d"))
                d -= timedelta(days=1)
            trading_dates = list(reversed(trading_dates))
        
        logger.info(f"Fetching {len(trading_dates)} institutional dates...")
        inst_by_date = {}
        valid_dates = []
        for i, d in enumerate(trading_dates):
            if i % 5 == 0: logger.info(f"Inst: {i}/{len(trading_dates)}")
            data = fetch_inst_all(d)
            if data:  # Only keep dates with actual data
                inst_by_date[d] = data
                valid_dates.append(d)
            time.sleep(0.5)  # Reduced delay
        
        trading_dates = valid_dates
        logger.info(f"Got institutional data for {len(trading_dates)} valid trading dates")
        
        # Fetch price data via yfinance (batch download with rate limit handling)
        logger.info(f"Fetching price data for {len(self.ticker_info)} stocks...")
        price_data = {}  # ticker -> {'price': float, 'high_52w': float, 'low_52w': float}
        
        ticker_symbols = {t: f"{t}{info['suffix']}" for t, info in self.ticker_info.items()}
        symbols_list = list(ticker_symbols.items())
        
        # Download in chunks of 100
        for i in range(0, len(symbols_list), 100):
            chunk = symbols_list[i:i+100]
            tickers_str = ' '.join([s[1] for s in chunk])
            try:
                df = yf.download(tickers_str, start=(datetime.now()-timedelta(days=365)).strftime("%Y-%m-%d"), 
                                end=datetime.now().strftime("%Y-%m-%d"), group_by='ticker', progress=False, threads=True)
                if df is not None and not df.empty:
                    for ticker, sym in chunk:
                        close_col = (sym, 'Close')
                        if close_col in df.columns:
                            prices = df[close_col].dropna()
                            if not prices.empty:
                                price_data[ticker] = {
                                    "price": prices.iloc[-1],
                                    "high_52w": prices.max(),
                                    "low_52w": prices.min()
                                }
            except Exception as e:
                if "Rate limit" in str(e) or "404" in str(e):
                    logger.warning(f"yfinance rate limited at chunk {i}, skipping remaining")
                    break
                logger.warning(f"Download chunk {i} failed: {e}")
            if i % 500 == 0: logger.info(f"Price: {min(i+100, len(symbols_list))}/{len(symbols_list)}")
            time.sleep(1)  # Rate limit delay
        
        logger.info(f"Got price data for {len(price_data)} stocks")
        
        # Build output
        output = {"last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "stocks": {}}
        
        for t, pd_info in price_data.items():
            info = self.ticker_info.get(t)
            if not info: continue
            
            price = pd_info['price']
            high_52w = pd_info['high_52w']
            low_52w = pd_info['low_52w']
            
            # Volume (if available)
            vol = None
            avg_vol = None
            
            # S score: volume spike (need volume data from yfinance)
            s_score = False  # Default - volume data not always reliable from batch download

            # N score: near 52-week high
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

            # RS ratio and L score
            rs_ratio = None
            l_score = False
            if high_52w > low_52w and market_ret is not None and abs(market_ret) > 0.01:
                pos = (price - low_52w) / (high_52w - low_52w)
                ret_approx = pos * 0.8 - 0.2
                rs_ratio = round(ret_approx / market_ret, 2)
                l_score = (ret_approx / market_ret) >= 1.2

            # C score: use Excel EPS rating if available, else False
            c_score = False
            if self.excel_ratings and t in self.excel_ratings:
                eps_rating = self.excel_ratings[t].get('eps_rating')
                if eps_rating:
                    c_score = eps_rating >= 60  # Top 40% EPS

            # A score: use RS position as proxy (stocks near 52w high likely have good earnings)
            a_score = False
            if high_52w > low_52w:
                pos = (price - low_52w) / (high_52w - low_52w)
                a_score = pos >= 0.5  # Above midpoint of 52w range

            # M score: market trend (positive market return = bullish)
            m_score = market_ret is not None and market_ret > 0

            # Score: weighted CANSLIM
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
        
        # Calculate Industry Strength
        industry_map = {} # industry -> [scores, inst_3d_nets, high_score_count, stock_count]
        for s in output["stocks"].values():
            ind = s["industry"] or "未知"
            if ind not in industry_map:
                industry_map[ind] = {"scores": [], "inst_3d_net": 0, "high_score_count": 0, "stock_count": 0}
            
            # Scores
            score = s["canslim"]["score"]
            industry_map[ind]["scores"].append(score)
            industry_map[ind]["stock_count"] += 1
            if score >= 80:
                industry_map[ind]["high_score_count"] += 1
            
            # Institutional 3d net
            if s["institutional"] and len(s["institutional"]) >= 1:
                n = min(3, len(s["institutional"]))
                net_3d = sum((d.get("foreign_net", 0) + d.get("trust_net", 0) + d.get("dealer_net", 0)) 
                            for d in s["institutional"][:n])
                industry_map[ind]["inst_3d_net"] += net_3d

        industry_strength = []
        for ind, data in industry_map.items():
            if ind == "未知": continue
            avg_score = round(sum(data["scores"]) / len(data["scores"]), 1) if data["scores"] else 0
            industry_strength.append({
                "industry": ind,
                "avg_score": avg_score,
                "total_inst_net_3d": int(data["inst_3d_net"]),
                "high_score_count": data["high_score_count"],
                "stock_count": data["stock_count"]
            })
        
        # Sort by avg_score
        output["industry_strength"] = sorted(industry_strength, key=lambda x: x["avg_score"], reverse=True)
        
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
