"""
CANSLIM Historical Signal Generator v3.0
Uses FREE TWSE/TPEx APIs + yfinance instead of FinMind/TEJ.

Architecture:
1. Fetch all TWSE/TPEx tickers (free)
2. Fetch institutional data by date (TWSE T86 + TPEx - free)
3. Fetch price/EPS data via yfinance (free)
4. Compute CANSLIM factors (C, A, N, S, L, I, M)
5. Export master_canslim_signals.parquet
"""

import os
import logging
import time
import requests
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from core.logic import calculate_c_factor, calculate_a_factor, compute_canslim_score

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Free TWSE/TPEx API endpoints
TWSE_TICKER_URL = "https://mopsfin.twse.com.tw/opendata/t187ap03_L.csv"
TPEX_TICKER_URL = "https://mopsfin.twse.com.tw/opendata/t187ap03_O.csv"
TWSE_INST_URL = "https://www.twse.com.tw/rwd/zh/fund/T86"
TPEX_INST_URL = "https://www.tpex.org.tw/web/stock/aftertrading/fund_twse/fund_twse_result.php"

def get_all_tw_tickers() -> Dict[str, str]:
    """Fetch full TWSE and TPEx ticker lists."""
    ticker_map = {}
    for url in [TWSE_TICKER_URL, TPEX_TICKER_URL]:
        try:
            df = pd.read_csv(url, encoding='utf-8')
            suffix = ".TW" if "t187ap03_L" in url else ".TWO"
            for _, row in df.iterrows():
                tid = str(row['公司代號']).strip()
                if len(tid) == 4:
                    ticker_map[tid] = suffix
        except Exception as e:
            logger.error(f"Failed to fetch tickers from {url}: {e}")
    logger.info(f"Total tickers: {len(ticker_map)}")
    return ticker_map

def fetch_twse_inst_by_date(date_str: str) -> Dict:
    """Fetch TWSE institutional data for a specific date."""
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
                    result[t] = {
                        "foreign_net": safe_int(row[idx_f]) // 1000,
                        "trust_net": safe_int(row[idx_t]) // 1000,
                        "dealer_net": safe_int(row[idx_d]) // 1000
                    }
                return result
    except Exception as e:
        logger.warning(f"TWSE inst fetch failed for {date_str}: {e}")
    return {}

def fetch_tpex_inst_by_date(date_str: str) -> Dict:
    """Fetch TPEx institutional data for a specific date."""
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
                    result[t] = {
                        "foreign_net": safe_int(row[7]) // 1000,
                        "trust_net": safe_int(row[8]) // 1000,
                        "dealer_net": safe_int(row[9]) // 1000
                    }
                return result
    except Exception as e:
        logger.warning(f"TPEx inst fetch failed for {date_str}: {e}")
    return {}

def get_trading_dates(end_date: str, days: int = 500) -> List[str]:
    """Get list of trading dates using TAIEX data."""
    try:
        twii = yf.Ticker("^TWII")
        start = (datetime.strptime(end_date, "%Y-%m-%d") - timedelta(days=days+30)).strftime("%Y-%m-%d")
        hist = twii.history(start=start, end=end_date)
        if not hist.empty:
            dates = [d.strftime("%Y%m%d") for d in hist.index]
            # Also return YYYY-MM-DD format
            return dates, [d.strftime("%Y-%m-%d") for d in hist.index]
    except Exception as e:
        logger.error(f"Failed to get trading dates: {e}")
    return [], []

class HistoricalGeneratorV2:
    def __init__(self):
        self.tickers = get_all_tw_tickers()
        self.inst_cache = {}
    
    def fetch_price_data(self, ticker: str, suffix: str, start_date: str, end_date: str) -> Optional[pd.DataFrame]:
        """Fetch price data via yfinance."""
        try:
            full_ticker = f"{ticker}{suffix}"
            stock = yf.Ticker(full_ticker)
            hist = stock.history(start=start_date, end=end_date)
            if not hist.empty:
                hist = hist.reset_index()
                hist['stock_id'] = ticker
                hist['date'] = pd.to_datetime(hist['Date'])
                hist['close'] = hist['Close']
                hist['high'] = hist['High']
                hist['volume'] = hist['Volume']
                return hist[['stock_id', 'date', 'close', 'high', 'volume']]
        except Exception as e:
            logger.debug(f"Price fetch failed for {ticker}: {e}")
        return None
    
    def fetch_eps_data(self, ticker: str, suffix: str) -> Optional[pd.DataFrame]:
        """Fetch quarterly EPS via TWSE MOPS API."""
        try:
            url = "https://mops.twse.com.tw/mops/web/ajax_t163sb04"
            params = {
                "encodeURIComponent": 1, "step": 1, "firstin": 1, "off": 1,
                "companyid": ticker,
            }
            resp = requests.post(url, data=params, timeout=10)
            if resp.status_code == 200:
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(resp.text, 'html.parser')
                eps_data = []
                table = soup.find('table')
                if table:
                    for row in table.find_all('tr')[1:]:
                        cols = row.find_all('td')
                        if len(cols) >= 4:
                            try:
                                year = cols[0].get_text(strip=True)
                                quarter = cols[1].get_text(strip=True)
                                eps_val = float(cols[3].get_text(strip=True).replace(',', ''))
                                eps_data.append({
                                    'stock_id': ticker,
                                    'year': int(year),
                                    'quarter': int(quarter),
                                    'eps': eps_val
                                })
                            except:
                                pass
                if eps_data:
                    return pd.DataFrame(eps_data)
        except Exception as e:
            logger.debug(f"EPS fetch failed for {ticker}: {e}")
        return None
    
    def process_all_stocks(self, end_date: str):
        """Process all stocks using free APIs."""
        logger.info(f"🚀 Starting full market scan for {len(self.tickers)} stocks (Free APIs)...")
        
        end_dt = datetime.strptime(end_date, "%Y-%m-%d")
        start_dt = end_dt - timedelta(days=600)
        start_str = start_dt.strftime("%Y-%m-%d")
        
        trading_dates_tw, trading_dates_iso = get_trading_dates(end_date, days=500)
        if not trading_dates_iso:
            logger.error("No trading dates found, aborting")
            return
        
        logger.info(f"Trading dates: {len(trading_dates_iso)} from {trading_dates_iso[0]} to {trading_dates_iso[-1]}")
        
        # Fetch institutional data for recent dates (last 20 trading days)
        recent_dates_iso = trading_dates_iso[-20:]
        logger.info(f"Fetching institutional data for {len(recent_dates_iso)} recent dates...")
        
        inst_data_by_date = {}
        for i, date_iso in enumerate(recent_dates_iso):
            if i % 5 == 0:
                logger.info(f"Fetching inst data: {i}/{len(recent_dates_iso)}")
            date_num = date_iso.replace("-", "")
            twse_inst = fetch_twse_inst_by_date(date_num)
            tpex_inst = fetch_tpex_inst_by_date(date_num)
            combined = {**twse_inst, **tpex_inst}
            inst_data_by_date[date_iso] = combined
            time.sleep(1)  # Rate limit
        
        # Process each stock
        all_results = []
        ticker_list = sorted(self.tickers.keys())
        
        for i, ticker in enumerate(ticker_list):
            if i % 100 == 0:
                logger.info(f"Processing stocks: {i}/{len(ticker_list)}")
            
            suffix = self.tickers[ticker]
            
            # Fetch price data
            df_price = self.fetch_price_data(ticker, suffix, start_str, end_date)
            if df_price is None or df_price.empty:
                continue
            
            df_price = df_price.sort_values('date')
            
            # Calculate N factor (near 52-week high)
            df_price['high_250d'] = df_price['high'].rolling(window=250, min_periods=1).max()
            df_price['N'] = df_price['close'] >= (df_price['high_250d'] * 0.90)
            
            # Calculate S factor (volume spike)
            df_price['vol_avg_50d'] = df_price['volume'].rolling(window=50, min_periods=1).mean()
            df_price['S'] = df_price['volume'] >= (df_price['vol_avg_50d'] * 1.5)
            
            # Calculate 1-year return for RS ranking
            df_price['one_year_return'] = (df_price['close'] - df_price['close'].shift(250)) / df_price['close'].shift(250)
            
            # Fetch EPS data
            df_eps = self.fetch_eps_data(ticker, suffix)
            
            # Map EPS to dates
            if df_eps is not None and not df_eps.empty:
                eps_announce_dates = pd.to_datetime(df_eps['year'].astype(str) + '-' + 
                    ((df_eps['quarter'] * 3).astype(str)).str.zfill(2) + '-01')
                for _, eps_row in df_eps.iterrows():
                    announce_date = pd.Timestamp(f"{eps_row['year']}-{(eps_row['quarter']*3):02d}-01")
                    mask = df_price['date'] >= announce_date
                    if mask.any():
                        first_idx = mask.idxmax()
                        df_price.loc[first_idx:, 'eps'] = eps_row['eps']
            
            df_price['eps'] = df_price.get('eps', pd.Series(dtype=float)).fillna(0)
            
            # Calculate C factor (quarterly EPS growth) - simplified
            # Use recent EPS values to determine growth
            if df_eps is not None and len(df_eps) >= 4:
                eps_sorted = df_eps.sort_values(['year', 'quarter'], ascending=False)
                eps_values = eps_sorted['eps'].values
                if len(eps_values) >= 4 and eps_values[3] > 0:
                    c_growth = (eps_values[0] - eps_values[3]) / eps_values[3]
                    c_pass = c_growth >= 0.25
                else:
                    c_pass = False
                a_pass = False  # Simplified for now
            else:
                c_pass = False
                a_pass = False
            
            # Map institutional data
            df_price['foreign_net'] = 0
            df_price['trust_net'] = 0
            
            for date_iso in recent_dates_iso:
                if date_iso in inst_data_by_date and ticker in inst_data_by_date[date_iso]:
                    inst = inst_data_by_date[date_iso][ticker]
                    mask = df_price['date'] == pd.Timestamp(date_iso)
                    if mask.any():
                        df_price.loc[mask, 'foreign_net'] = inst['foreign_net']
                        df_price.loc[mask, 'trust_net'] = inst['trust_net']
            
            # Calculate I factor (3-day institutional net buying)
            df_price['inst_net'] = df_price['foreign_net'] + df_price['trust_net']
            df_price['I'] = df_price['inst_net'].rolling(window=3, min_periods=1).sum() > 0
            
            # Store results
            df_result = df_price[['stock_id', 'date', 'close', 'one_year_return', 'C', 'I', 'N', 'S']].copy()
            df_result['C'] = c_pass
            df_result['A'] = True  # Default to True (simplified)
            df_result['M'] = True  # Default to True (market trend)
            
            all_results.append(df_result)
            
            time.sleep(0.1)  # Rate limit
        
        if not all_results:
            logger.error("No results generated!")
            return
        
        # Combine all results
        master_df = pd.concat(all_results, ignore_index=True)
        logger.info(f"Combined {len(master_df)} rows")
        
        # Calculate RS ranking (L factor)
        master_df = master_df.dropna(subset=['one_year_return'])
        master_df['L_rank'] = master_df.groupby('date')['one_year_return'].rank(pct=True) * 100
        master_df['L'] = master_df['L_rank'] >= 80
        
        # Calculate score
        master_df['score'] = master_df.apply(lambda x: compute_canslim_score({
            'C': x['C'], 'A': x['A'], 'N': x['N'], 'S': x['S'], 
            'L': x['L'], 'I': x['I'], 'M': x['M']
        }), axis=1)
        
        # Save
        output_path = "master_canslim_signals.parquet"
        master_df.to_parquet(output_path)
        logger.info(f"✅ Master signals saved to {output_path}")
        
        # Summary
        latest_date = master_df['date'].max()
        latest_stocks = master_df[master_df['date'] == latest_date]
        logger.info(f"Latest date: {latest_date}")
        logger.info(f"Stocks on latest date: {len(latest_stocks)}")

if __name__ == "__main__":
    end_date = datetime.now().strftime("%Y-%m-%d")
    gen = HistoricalGeneratorV2()
    gen.process_all_stocks(end_date)
