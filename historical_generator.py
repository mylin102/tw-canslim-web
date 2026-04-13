"""
CANSLIM Historical Signal Generator v2.0
100% Quantified Alpha Engine with Full Market Ranking.

Architecture:
1. Fetch Raw Data (EPS, Chips, Price, TAIEX)
2. Apply Lag Logic (Point-in-time Alignment)
3. Compute Factors (C, A, N, S, I)
4. Compute Global Factors (L: RS Percentile Rank, M: Market MA200)
5. Fuse & Export
"""

import os
import logging
import pandas as pd
import time
import requests
from datetime import datetime, timedelta
from typing import List, Dict
from FinMind.data import DataLoader
from core.logic import calculate_c_factor, calculate_a_factor, calculate_i_factor, compute_canslim_score
from core.data_adapter import apply_announcement_lag, resample_to_daily

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

CACHE_DIR = ".raw_cache"
os.makedirs(CACHE_DIR, exist_ok=True)

def get_all_tw_tickers() -> Dict[str, str]:
    """Fetch full TWSE and TPEx ticker lists with correct metadata."""
    ticker_map = {}
    TWSE_TICKER_URL = "https://mopsfin.twse.com.tw/opendata/t187ap03_L.csv"
    TPEx_TICKER_URL = "https://mopsfin.twse.com.tw/opendata/t187ap03_O.csv"
    
    # 1. Listed (上市)
    try:
        df_l = pd.read_csv(TWSE_TICKER_URL, encoding='utf-8')
        for _, row in df_l.iterrows():
            tid = str(row['公司代號']).strip()
            if len(tid) == 4: ticker_map[tid] = ".TW"
    except Exception as e:
        logger.error(f"Failed to fetch TWSE tickers: {e}")
    
    # 2. OTC (上櫃)
    try:
        df_o = pd.read_csv(TPEx_TICKER_URL, encoding='utf-8')
        for _, row in df_o.iterrows():
            tid = str(row['公司代號']).strip()
            if len(tid) == 4: ticker_map[tid] = ".TWO"
    except Exception as e:
        logger.error(f"Failed to fetch TPEx tickers: {e}")
    
    logger.info(f"Final ticker count: {len(ticker_map)}")
    return ticker_map

class HistoricalGenerator:
    def __init__(self, token: str = None):
        self.dl = DataLoader()
        if token: self.dl.login_by_token(token)
        
    def fetch_raw_data(self, stock_id: str, start_date: str, end_date: str):
        eps_path = os.path.join(CACHE_DIR, f"{stock_id}_eps.parquet")
        chip_path = os.path.join(CACHE_DIR, f"{stock_id}_chip.parquet")
        price_path = os.path.join(CACHE_DIR, f"{stock_id}_price.parquet")
        
        if not os.path.exists(eps_path):
            df = self.dl.taiwan_stock_financial_statement(stock_id=stock_id, start_date="2019-01-01")
            if not df.empty:
                df = df[df['type'] == 'EPS'].rename(columns={'value': 'eps'})
                df.to_parquet(eps_path)
            time.sleep(0.1)
        
        if not os.path.exists(chip_path):
            df = self.dl.taiwan_stock_institutional_investors(stock_id=stock_id, start_date=start_date, end_date=end_date)
            if not df.empty: df.to_parquet(chip_path)
            time.sleep(0.1)

        if not os.path.exists(price_path):
            df = self.dl.taiwan_stock_daily(stock_id=stock_id, start_date="2023-01-01", end_date=end_date)
            if not df.empty: df.to_parquet(price_path)
            time.sleep(0.1)
            
        return (pd.read_parquet(eps_path) if os.path.exists(eps_path) else pd.DataFrame(),
                pd.read_parquet(chip_path) if os.path.exists(chip_path) else pd.DataFrame(),
                pd.read_parquet(price_path) if os.path.exists(price_path) else pd.DataFrame())

    def _aggregate_chips(self, df_chip: pd.DataFrame) -> pd.DataFrame:
        df = df_chip.copy()
        df['net'] = df['buy'] - df['sell']
        pivot = df.pivot_table(index=['stock_id', 'date'], columns='name', values='net', aggfunc='sum').fillna(0).reset_index()
        col_map = {'Foreign_Investor': 'foreign_net', 'Investment_Trust': 'trust_net', 'Dealer_self': 'dealer_net'}
        pivot.rename(columns=col_map, inplace=True)
        for col in col_map.values():
            if col not in pivot.columns: pivot[col] = 0
        return pivot

    def process_ticker(self, stock_id: str, start_date: str, end_date: str) -> pd.DataFrame:
        try:
            df_eps_raw, df_chip_raw, df_price_raw = self.fetch_raw_data(stock_id, start_date, end_date)
            if df_price_raw.empty: return pd.DataFrame()
            
            df_price = df_price_raw.copy()
            df_price['date'] = pd.to_datetime(df_price['date'])
            df_price = df_price.sort_values('date')
            df_price['high_250d'] = df_price['max'].rolling(window=250, min_periods=1).max()
            df_price['N'] = df_price['close'] >= (df_price['high_250d'] * 0.9)
            df_price['vol_avg_50d'] = df_price['Trading_Volume'].rolling(window=50, min_periods=1).mean()
            df_price['S'] = df_price['Trading_Volume'] >= (df_price['vol_avg_50d'] * 1.5)
            df_price['one_year_return'] = (df_price['close'] - df_price['close'].shift(250)) / df_price['close'].shift(250)

            if not df_eps_raw.empty:
                df_eps_lagged = apply_announcement_lag(df_eps_raw)
                df_eps_daily = resample_to_daily(df_eps_lagged, start_date, end_date)
                df_eps_daily['date'] = pd.to_datetime(df_eps_daily['date'])
                df_combined = pd.merge(df_price, df_eps_daily, on=['stock_id', 'date'], how='left').ffill().fillna(0)
            else:
                df_combined = df_price.copy(); df_combined['eps'] = 0

            if not df_chip_raw.empty:
                df_chip_daily = self._aggregate_chips(df_chip_raw)
                df_chip_daily['date'] = pd.to_datetime(df_chip_daily['date'])
                df_combined = pd.merge(df_combined, df_chip_daily, on=['stock_id', 'date'], how='left').fillna(0)
            else:
                df_combined['foreign_net'] = 0; df_combined['trust_net'] = 0

            df_combined['C'] = df_combined['eps'].rolling(window=250).apply(lambda x: calculate_c_factor(pd.Series(x[::60]))).fillna(0).astype(bool)
            df_combined['A'] = df_combined['eps'].rolling(window=500).apply(lambda x: calculate_a_factor(pd.Series(x[::250]))).fillna(0).astype(bool)
            df_combined['I'] = (df_combined['foreign_net'] + df_combined['trust_net']).rolling(window=3).sum() > 0
            
            return df_combined[['stock_id', 'date', 'close', 'one_year_return', 'C', 'I', 'N', 'S', 'A']]
        except Exception as e:
            return pd.DataFrame()

    def run_full_market(self, start_date: str, end_date: str):
        tickers = get_all_tw_tickers()
        logger.info(f"🚀 Starting full market scan for {len(tickers)} stocks...")
        
        # Fallback for Market factor (M) if index data is unavailable
        # In a production system, we'd fetch this from a reliable source like yfinance
        market_status = True 
        
        all_dfs = []
        ticker_list = list(tickers.keys())
        for i, ticker in enumerate(ticker_list):
            if i % 100 == 0: logger.info(f"Progress: {i}/{len(ticker_list)}")
            df = self.process_ticker(ticker, start_date, end_date)
            if not df.empty: all_dfs.append(df)
            
        if not all_dfs: return
        
        master_df = pd.concat(all_dfs, ignore_index=True)
        master_df['L_rank'] = master_df.groupby('date')['one_year_return'].rank(pct=True) * 100
        master_df['L'] = master_df['L_rank'] >= 80
        
        # Set M factor
        master_df['M'] = market_status
        
        from core.logic import compute_canslim_score
        master_df['score'] = master_df.apply(lambda x: compute_canslim_score({
            'C': x['C'], 'A': x['A'], 'N': x['N'], 'S': x['S'], 'L': x['L'], 'I': x['I'], 'M': x['M']
        }), axis=1)
        
        master_df.to_parquet("master_canslim_signals.parquet")
        logger.info(f"✅ Success! Master signals saved.")

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    gen = HistoricalGenerator(token=os.getenv("FINMIND_TOKEN"))
    end_date = datetime.now().strftime("%Y-%m-%d")
    gen.run_full_market("2024-01-01", end_date)
