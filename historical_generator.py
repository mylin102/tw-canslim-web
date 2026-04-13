"""
CANSLIM Historical Signal Generator.
Fetches historical data, applies lag logic, computes daily scores, and saves to Parquet.

Architecture:
[FinMind API] -> [Raw Cache (.raw_cache/)] -> [Adapter (Lag)] -> [Engine] -> [canslim_signals.parquet]
"""

import os
import logging
import pandas as pd
import time
from datetime import datetime, timedelta
from typing import List
from FinMind.data import DataLoader
from core.logic import calculate_c_factor, calculate_i_factor, compute_canslim_score
from core.data_adapter import apply_announcement_lag, resample_to_daily

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

CACHE_DIR = ".raw_cache"
os.makedirs(CACHE_DIR, exist_ok=True)

class HistoricalGenerator:
    def __init__(self, token: str = None):
        self.dl = DataLoader()
        if token: self.dl.login_by_token(token)
        
    def fetch_raw_data(self, stock_id: str, start_date: str, end_date: str):
        """Fetch EPS and Institutional Trades, utilizing local cache."""
        eps_path = os.path.join(CACHE_DIR, f"{stock_id}_eps.parquet")
        chip_path = os.path.join(CACHE_DIR, f"{stock_id}_chip.parquet")
        
        # 1. Fetch EPS (Quarterly)
        if not os.path.exists(eps_path):
            logger.info(f"Downloading EPS for {stock_id}...")
            df_eps = self.dl.taiwan_stock_financial_statement(
                stock_id=stock_id, start_date="2020-01-01"
            )
            df_eps = df_eps[df_eps['type'] == 'EPS']
            df_eps = df_eps.rename(columns={'value': 'eps'})
            df_eps.to_parquet(eps_path)
            time.sleep(1) # Rate limit protection
        
        # 2. Fetch Institutional Trades (Daily)
        if not os.path.exists(chip_path):
            logger.info(f"Downloading Chip Flow for {stock_id}...")
            df_chip = self.dl.taiwan_stock_institutional_investors(
                stock_id=stock_id, start_date=start_date, end_date=end_date
            )
            df_chip.to_parquet(chip_path)
            time.sleep(1)
            
        return pd.read_parquet(eps_path), pd.read_parquet(chip_path)

    def process_ticker(self, stock_id: str, start_date: str, end_date: str) -> pd.DataFrame:
        """Computes daily CANSLIM scores for a single ticker."""
        try:
            df_eps_raw, df_chip_raw = self.fetch_raw_data(stock_id, start_date, end_date)
            
            # Apply Lag to EPS
            df_eps_lagged = apply_announcement_lag(df_eps_raw)
            
            # Resample both to daily timeline
            df_eps_daily = resample_to_daily(df_eps_lagged, start_date, end_date)
            
            # Aggregate Chips (Pivot FinMind structure)
            df_chip_daily = self._aggregate_chips(df_chip_raw)
            
            # Ensure date types match for merge
            df_eps_daily['date'] = pd.to_datetime(df_eps_daily['date'])
            df_chip_daily['date'] = pd.to_datetime(df_chip_daily['date'])
            
            # Merge
            df_combined = pd.merge(df_eps_daily, df_chip_daily, on=['stock_id', 'date'], how='left').fillna(0)
            
            # Rolling Score Calculation (Optimized for speed)
            df_combined['C'] = df_combined['eps'].rolling(window=2).apply(
                lambda x: calculate_c_factor(pd.Series(x))
            ).fillna(0).astype(bool)
            
            # Simplified I factor (3-day institutional buying)
            df_combined['I'] = (df_combined['foreign_net'] + df_combined['trust_net']).rolling(window=3).sum() > 0
            
            # Compute Final Score (Assuming other factors True for now as placeholders)
            df_combined['score'] = df_combined.apply(
                lambda x: compute_canslim_score({'C': x['C'], 'I': x['I'], 'A': True, 'N': True, 'S': True, 'L': True, 'M': True}),
                axis=1
            )
            
            return df_combined[['stock_id', 'date', 'score', 'C', 'I']]
            
        except Exception as e:
            logger.error(f"Failed to process {stock_id}: {e}")
            return pd.DataFrame()

    def _aggregate_chips(self, df_chip: pd.DataFrame) -> pd.DataFrame:
        """Pivots FinMind raw chip data into a wide format."""
        if df_chip.empty: return pd.DataFrame(columns=['stock_id', 'date', 'foreign_net', 'trust_net', 'dealer_net'])
        
        # Map names to categories
        df = df_chip.copy()
        df['net'] = df['buy'] - df['sell']
        
        pivot = df.pivot_table(
            index=['stock_id', 'date'], 
            columns='name', 
            values='net', 
            aggfunc='sum'
        ).fillna(0).reset_index()
        
        # Standardize columns
        col_map = {
            'Foreign_Investor': 'foreign_net',
            'Investment_Trust': 'trust_net',
            'Dealer_self': 'dealer_net'
        }
        pivot.rename(columns=col_map, inplace=True)
        return pivot

if __name__ == "__main__":
    gen = HistoricalGenerator()
    # Test with 2330 for 2024
    results = gen.process_ticker("2330", "2024-01-01", "2024-12-31")
    if not results.empty:
        output_file = "canslim_signals_2330.parquet"
        results.to_parquet(output_file)
        logger.info(f"✅ Success! Saved signals to {output_file}")
        print(results.tail())
