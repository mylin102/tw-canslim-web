"""
CANSLIM Alpha Integration Module for squeeze-backtest.
Provides high-performance filtering for backtesting engines.
"""

import pandas as pd
import logging

class AlphaFilter:
    def __init__(self, signal_path: str = "master_canslim_signals_fused.parquet"):
        """
        Initializes the filter by loading fused CANSLIM + Professional signals.
        """
        logging.info(f"🚀 Loading Super Alpha signals from {signal_path}...")
        self.df_signals = pd.read_parquet(signal_path)
        self.df_signals['date'] = pd.to_datetime(self.df_signals['date'])
        
    def filter_backtest_data(self, df_price: pd.DataFrame, 
                             min_score: int = 75, 
                             min_rs: int = 0,
                             require_fund_increase: bool = False) -> pd.DataFrame:
        """
        Integrates multi-dimensional Alpha signals into price data.
        
        Args:
            df_price: OHLCV DF.
            min_score: Threshold for our quantitative score.
            min_rs: Threshold for professional RS Rating (0-100).
            require_fund_increase: If True, only picks stocks with positive fund count change.
        """
        df_price['date'] = pd.to_datetime(df_price['date'])
        
        # Merge all available features
        df_merged = pd.merge(
            df_price, 
            self.df_signals[['stock_id', 'date', 'score', 'C', 'I', 'rs_rating', 'fund_change']], 
            on=['stock_id', 'date'], 
            how='left'
        )
        
        # 1. Base CANSLIM Logic
        df_merged['is_canslim_approved'] = df_merged['score'].fillna(0) >= min_score
        
        # 2. Professional RS Logic (Handle NaNs for stocks not in professional list)
        if min_rs > 0:
            df_merged['is_rs_approved'] = df_merged['rs_rating'].fillna(0) >= min_rs
        else:
            df_merged['is_rs_approved'] = True
            
        # 3. Fund Concentration Logic
        if require_fund_increase:
            df_merged['is_fund_growing'] = df_merged['fund_change'].fillna(0) > 0
        else:
            df_merged['is_fund_growing'] = True
            
        # Final Decision
        df_merged['is_alpha_confirmed'] = (
            df_merged['is_canslim_approved'] & 
            df_merged['is_rs_approved'] & 
            df_merged['is_fund_growing']
        )
        
        return df_merged

    def get_quality_stats(self, df_merged: pd.DataFrame):
        """Prints impact analysis of the CANSLIM filter."""
        total_setups = len(df_merged[df_merged.get('squeeze_fired', False) == True])
        quality_setups = len(df_merged[(df_merged.get('squeeze_fired', False) == True) & (df_merged['is_canslim_approved'] == True)])
        
        print("\n=== Alpha Filter Impact Analysis ===")
        print(f"Total Technical Squeeze Setups: {total_setups}")
        print(f"High Quality (CANSLIM) Setups: {quality_setups}")
        if total_setups > 0:
            print(f"Noise Reduction Rate: {(1 - quality_setups/total_setups)*100:.1f}%")
        print("====================================\n")

if __name__ == "__main__":
    # Usage Example for squeeze-backtest:
    # filter = AlphaFilter("master_canslim_signals.parquet")
    # df = filter.filter_backtest_data(your_price_df, min_score=75)
    # df['entry'] = df['squeeze_fired'] & df['is_canslim_approved']
    print("Alpha Integration Module Ready.")
