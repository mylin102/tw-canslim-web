"""
Export consolidated Alpha data for Dashboard 2.0.
Combines fused Parquet signals with ticker metadata (names, industries).
"""

import pandas as pd
import json
import os
import logging
from export_canslim import get_all_tw_tickers # Reuse ticker fetcher

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

FUSED_DATA_PATH = "master_canslim_signals_fused.parquet"
OUTPUT_JSON_PATH = "docs/data.json"

def export_data():
    if not os.path.exists(FUSED_DATA_PATH):
        logger.error(f"Source file {FUSED_DATA_PATH} not found.")
        return

    # 1. Load latest fused signals
    logger.info("Loading latest Alpha signals...")
    df = pd.read_parquet(FUSED_DATA_PATH)
    latest_date = df.date.max()
    df_latest = df[df.date == latest_date].copy()

    # 2. Load Ticker Metadata (Names)
    logger.info("Fetching ticker metadata...")
    ticker_info = get_all_tw_tickers()
    
    # 3. Construct JSON structure
    output = {
        "last_updated": latest_date.strftime("%Y-%m-%d %H:%M:%S"),
        "stocks": {}
    }

    logger.info(f"Processing {len(df_latest)} stocks for snapshot {latest_date}...")
    
    for _, row in df_latest.iterrows():
        sid = str(row['stock_id'])
        meta = ticker_info.get(sid, {"name": sid, "suffix": ".TW"})
        
        output["stocks"][sid] = {
            "symbol": sid,
            "name": meta["name"],
            "canslim": {
                "C": bool(row['C']),
                "I": bool(row['I']),
                "N": bool(row['N']),
                "S": bool(row['S']),
                "score": int(row['score']),
                "rs_rating": float(row['rs_rating']) if pd.notna(row['rs_rating']) else None,
                "fund_change": float(row['fund_change']) if pd.notna(row['fund_change']) else None,
                "smr_rating": str(row['smr_rating']) if pd.notna(row['smr_rating']) else None
            },
            "institutional": [] # Placeholder for future history integration
        }

    # 4. Save to docs/
    os.makedirs(os.path.dirname(OUTPUT_JSON_PATH), exist_ok=True)
    with open(OUTPUT_JSON_PATH, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    
    logger.info(f"✅ Dashboard data exported to {OUTPUT_JSON_PATH}")

if __name__ == "__main__":
    export_data()
