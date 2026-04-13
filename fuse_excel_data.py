"""
Fuses specialized Excel ratings into the master CANSLIM Parquet signals.
Adds 'rs_rating', 'composite_rating', and 'fund_change' as high-value features.
"""

import pandas as pd
import os
import logging
from excel_processor import ExcelDataProcessor

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

MASTER_SIGNAL_PATH = "master_canslim_signals.parquet"
EXCEL_FILE = "股票健診60409.xlsm"

def fuse_data():
    if not os.path.exists(MASTER_SIGNAL_PATH):
        logger.error("Master signal file not found. Run historical_generator first.")
        return

    logger.info(f"🚀 Loading Excel ratings from {EXCEL_FILE}...")
    processor = ExcelDataProcessor(os.getcwd())
    excel_ratings = processor.load_health_check_data()
    fund_holdings = processor.load_fund_holdings_data()

    if not excel_ratings:
        logger.error("Failed to load Excel ratings.")
        return

    # Convert to DataFrame
    df_excel = pd.DataFrame.from_dict(excel_ratings, orient='index').reset_index()
    df_excel.rename(columns={'index': 'stock_id'}, inplace=True)
    
    # Merge fund data if available
    if fund_holdings:
        df_funds = pd.DataFrame.from_dict(fund_holdings, orient='index').reset_index()
        df_funds.rename(columns={'index': 'stock_id', 'change': 'fund_change'}, inplace=True)
        df_excel = pd.merge(df_excel, df_funds[['stock_id', 'fund_change']], on='stock_id', how='left')

    logger.info(f"🚀 Fusing features into {MASTER_SIGNAL_PATH}...")
    df_master = pd.read_parquet(MASTER_SIGNAL_PATH)
    
    # Merge logic: We apply the latest Excel rating to all recent dates in the backtest 
    # (or you can use it as a point-in-time snapshot if you have historical excels)
    # For Phase 1, we treat the latest Excel rating as the 'current quality profile'.
    df_fused = pd.merge(
        df_master, 
        df_excel[['stock_id', 'rs_rating', 'composite_rating', 'smr_rating', 'fund_change']], 
        on='stock_id', 
        how='left'
    )

    # Save the Super-Master file
    output_path = "master_canslim_signals_fused.parquet"
    df_fused.to_parquet(output_path)
    
    logger.info(f"✅ Success! Super Alpha Database saved to {output_path}")
    print(df_fused.tail())

if __name__ == "__main__":
    fuse_data()
