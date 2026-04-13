"""
CANSLIM Historical Signal Generator.
Fetches historical data, applies lag logic, computes daily scores, and saves to Parquet.

Architecture:
[FinMind API] -> [Raw Cache (.raw_cache/)] -> [Adapter (Lag)] -> [Engine] -> [master_canslim_signals.parquet]
"""

import os
import logging
import pandas as pd
import time
from datetime import datetime, timedelta
from typing import List, Dict
from FinMind.data import DataLoader
from core.logic import calculate_c_factor, calculate_i_factor, compute_canslim_score
from core.data_adapter import apply_announcement_lag, resample_to_daily

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

CACHE_DIR = ".raw_cache"
os.makedirs(CACHE_DIR, exist_ok=True)

def get_all_tw_tickers() -> Dict[str, str]:
    """Fetch full TWSE and TPEx ticker lists."""
    ticker_map = {}
    TWSE_TICKER_URL = "https://mopsfin.twse.com.tw/opendata/t187ap03_L.csv"
    TPEx_TICKER_URL = "https://mopsfin.twse.com.tw/opendata/t187ap03_O.csv"
    
    try:
        df_l = pd.read_csv(TWSE_TICKER_URL)
        for tid in df_l['公司代號']:
            if len(str(tid).strip()) == 4: ticker_map[str(tid).strip()] = ".TW"
        df_o = pd.read_csv(TPEx_TICKER_URL)
        for tid in df_o['公司代號']:
            if len(str(tid).strip()) == 4: ticker_map[str(tid).strip()] = ".TWO"
    except:
        logger.warning("Failed to fetch online tickers, using fallback priority list.")
        return {"2330": ".TW", "2303": ".TW", "2454": ".TW", "8069": ".TWO"}
    return ticker_map

class HistoricalGenerator:
    def __init__(self, token: str = None):
        self.dl = DataLoader()
        if token: self.dl.login_by_token(token)
        
    def fetch_raw_data(self, stock_id: str, start_date: str, end_date: str):
        """Fetch EPS, Institutional Trades, and OHLCV data."""
        eps_path = os.path.join(CACHE_DIR, f"{stock_id}_eps.parquet")
        chip_path = os.path.join(CACHE_DIR, f"{stock_id}_chip.parquet")
        price_path = os.path.join(CACHE_DIR, f"{stock_id}_price.parquet")
        
        # 1. Fetch EPS
        if not os.path.exists(eps_path):
            try:
                df_eps = self.dl.taiwan_stock_financial_statement(stock_id=stock_id, start_date="2019-01-01")
                if not df_eps.empty:
                    df_eps = df_eps[df_eps['type'] == 'EPS'].rename(columns={'value': 'eps'})
                    df_eps.to_parquet(eps_path)
                time.sleep(0.2)
            except Exception as e: logger.debug(f"EPS Error {stock_id}: {e}")
        
        # 2. Fetch Institutional Trades
        if not os.path.exists(chip_path):
            try:
                df_chip = self.dl.taiwan_stock_institutional_investors(stock_id=stock_id, start_date=start_date, end_date=end_date)
                if not df_chip.empty: df_chip.to_parquet(chip_path)
                time.sleep(0.2)
            except Exception as e: logger.debug(f"Chip Error {stock_id}: {e}")

        # 3. Fetch OHLCV (Price)
        if not os.path.exists(price_path):
            try:
                df_price = self.dl.taiwan_stock_daily(stock_id=stock_id, start_date="2023-01-01", end_date=end_date)
                if not df_price.empty: df_price.to_parquet(price_path)
                time.sleep(0.2)
            except Exception as e: logger.debug(f"Price Error {stock_id}: {e}")
            
        # Final load
        return (
            pd.read_parquet(eps_path) if os.path.exists(eps_path) else pd.DataFrame(),
            pd.read_parquet(chip_path) if os.path.exists(chip_path) else pd.DataFrame(),
            pd.read_parquet(price_path) if os.path.exists(price_path) else pd.DataFrame()
        )

    def process_ticker(self, stock_id: str, start_date: str, end_date: str) -> pd.DataFrame:
        """Computes daily CANSLIM scores."""
        try:
            df_eps_raw, df_chip_raw, df_price_raw = self.fetch_raw_data(stock_id, start_date, end_date)
            if df_price_raw.empty: return pd.DataFrame()
            
            # 1. Pre-process Price Data
            df_price = df_price_raw.copy()
            df_price['date'] = pd.to_datetime(df_price['date'])
            df_price = df_price.sort_values('date')
            df_price['high_250d'] = df_price['max'].rolling(window=250, min_periods=1).max()
            df_price['N'] = df_price['close'] >= (df_price['high_250d'] * 0.9)
            df_price['vol_avg_50d'] = df_price['Trading_Volume'].rolling(window=50, min_periods=1).mean()
            df_price['S'] = df_price['Trading_Volume'] >= (df_price['vol_avg_50d'] * 1.5)

            # 2. Financials with Lag
            if not df_eps_raw.empty:
                df_eps_lagged = apply_announcement_lag(df_eps_raw)
                df_eps_daily = resample_to_daily(df_eps_lagged, start_date, end_date)
                df_eps_daily['date'] = pd.to_datetime(df_eps_daily['date'])
                df_combined = pd.merge(df_price, df_eps_daily, on=['stock_id', 'date'], how='left').fillna(method='ffill').fillna(0)
            else:
                df_combined = df_price.copy(); df_combined['eps'] = 0

            # 3. Chips
            if not df_chip_raw.empty:
                df_chip_daily = self._aggregate_chips(df_chip_raw)
                df_chip_daily['date'] = pd.to_datetime(df_chip_daily['date'])
                df_combined = pd.merge(df_combined, df_chip_daily, on=['stock_id', 'date'], how='left').fillna(0)
            else:
                df_combined['foreign_net'] = 0; df_combined['trust_net'] = 0

            # Factors
            df_combined['C'] = df_combined['eps'].rolling(window=250).apply(lambda x: calculate_c_factor(pd.Series(x[::60]))).fillna(0).astype(bool)
            df_combined['I'] = (df_combined['foreign_net'] + df_combined['trust_net']).rolling(window=3).sum() > 0
            
            df_combined['score'] = df_combined.apply(lambda x: compute_canslim_score({'C': x['C'], 'I': x['I'], 'N': x['N'], 'S': x['S'], 'A': True, 'L': True, 'M': True}), axis=1)
            
            return df_combined[['stock_id', 'date', 'score', 'C', 'I', 'N', 'S']]
        except Exception as e:
            logger.debug(f"Process Error {stock_id}: {e}")
            return pd.DataFrame()

    def _aggregate_chips(self, df_chip: pd.DataFrame) -> pd.DataFrame:
        df = df_chip.copy()
        df['net'] = df['buy'] - df['sell']
        pivot = df.pivot_table(index=['stock_id', 'date'], columns='name', values='net', aggfunc='sum').fillna(0).reset_index()
        col_map = {'Foreign_Investor': 'foreign_net', 'Investment_Trust': 'trust_net', 'Dealer_self': 'dealer_net'}
        pivot.rename(columns=col_map, inplace=True)
        # Ensure columns exist even if some investor types are missing
        for col in col_map.values():
            if col not in pivot.columns: pivot[col] = 0
        return pivot

    def run_full_market(self, start_date: str, end_date: str):
        """Processes all tickers and saves a master signal file."""
        tickers = get_all_tw_tickers()
        logger.info(f"🚀 Starting full market scan for {len(tickers)} stocks...")
        all_results = []
        for i, ticker in enumerate(tickers):
            if i % 50 == 0: logger.info(f"Progress: {i}/{len(tickers)}")
            df_signal = self.process_ticker(ticker, start_date, end_date)
            if not df_signal.empty: all_results.append(df_signal)
            time.sleep(0.1)

        if all_results:
            master_df = pd.concat(all_results, ignore_index=True)
            master_df.to_parquet("master_canslim_signals.parquet")
            logger.info(f"✅ Success! Total signals: {len(master_df)} rows.")
        else: logger.error("❌ No data processed.")

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    gen = HistoricalGenerator(token=os.getenv("FINMIND_TOKEN"))
    gen.run_full_market("2024-01-01", "2025-04-10")
