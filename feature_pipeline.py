"""
Feature Pipeline Orchestrator for tw-canslim-web.
Processes stocks to compute revenue features and rankings, then exports to JSON.
"""

import os
import json
import logging
import pandas as pd
from datetime import datetime
from typing import List, Dict, Optional

from revenue_analyzer import calculate_revenue_features
from tej_processor import TEJProcessor

logger = logging.getLogger(__name__)

FEATURE_VERSION = "v1.0"
# 2026-05-31 Hermes Agent: fix OUTPUT_DIR to docs/api/ so it matches
# the path that export_canslim.py reads from (docs/api/stock_features.json).
# Previously was "api" (repo root ./api/), causing writes to wrong directory.
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "docs", "api")

class FeaturePipeline:
    def __init__(self, api_key: Optional[str] = None):
        self.processor = TEJProcessor(api_key=api_key)
        if not os.path.exists(OUTPUT_DIR):
            os.makedirs(OUTPUT_DIR)

    def process_stocks(self, symbols: List[str]) -> Dict[str, Dict]:
        """Process a list of symbols and return aggregated features and rankings."""
        stock_features = {}
        rankings = {}
        
        updated_at = datetime.now().strftime("%Y-%m-%d")
        
        for symbol in symbols:
            logger.info(f"Processing features for {symbol}...")
            try:
                # Fetch monthly revenue
                rev_df = self.processor.get_monthly_revenue(symbol)
                # 2026-05-31 Hermes Agent: reduce threshold from 15 to 4 months.
                # TEJ TAIM1AQ now returns quarterly rows (4/year) so 15 is unreachable.
                # 4 months is enough for current-vs-prior-vs-year-ago comparisons.
                if rev_df is None or len(rev_df) < 4:
                    logger.warning(f"Insufficient revenue data for {symbol}")
                    continue
                
                # Calculate features
                features = calculate_revenue_features(rev_df)
                if features:
                    # Prepare stock_features.json entry
                    stock_features[symbol] = {
                        "symbol": symbol,
                        "rev_yoy": round(features['rev_yoy'], 4),
                        "rev_mom": round(features['rev_mom'], 4),
                        "rev_acc_1": round(features['rev_acc_1'], 4),
                        "rev_acc_2": round(features['rev_acc_2'], 4),
                        "revenue_score": features['revenue_score'],
                        "rev_accelerating": bool(features['rev_accelerating']),
                        "rev_strong": bool(features['rev_strong']),
                        "updated_at": updated_at,
                        "feature_version": FEATURE_VERSION
                    }
                    
                    # Prepare ranking.json entry
                    rankings[symbol] = {
                        "symbol": symbol,
                        "total_score": features['revenue_score'], # Currently only revenue score
                        "revenue_score": features['revenue_score'],
                        "updated_at": updated_at
                    }
                else:
                    logger.warning(f"Could not calculate features for {symbol}")
            except Exception as e:
                logger.error(f"Error processing {symbol}: {e}")
                
        return {
            "stock_features": stock_features,
            "rankings": rankings
        }

    def export_results(self, data: Dict[str, List]):
        """Export results without allowing a provider outage to erase live data."""
        features_path = os.path.join(OUTPUT_DIR, "stock_features.json")
        ranking_path = os.path.join(OUTPUT_DIR, "ranking.json")

        def preserve_existing_if_incomplete(path: str, records: Dict, label: str) -> Dict:
            """Keep the last usable export when an upstream provider returns too little."""
            try:
                with open(path, "r", encoding="utf-8") as handle:
                    existing = json.load(handle)
            except (OSError, json.JSONDecodeError):
                existing = {}

            if not isinstance(existing, dict):
                existing = {}

            minimum_acceptable = max(1, (len(existing) + 4) // 5)
            if existing and len(records) < minimum_acceptable:
                logger.error(
                    "Refusing to replace %s with %d records; keeping prior %d records.",
                    label,
                    len(records),
                    len(existing),
                )
                return existing
            return records

        features = preserve_existing_if_incomplete(
            features_path, data["stock_features"], "stock features"
        )
        rankings = preserve_existing_if_incomplete(
            ranking_path, data["rankings"], "rankings"
        )

        with open(features_path, 'w', encoding='utf-8') as f:
            json.dump(features, f, indent=2, ensure_ascii=False)

        with open(ranking_path, 'w', encoding='utf-8') as f:
            json.dump(rankings, f, indent=2, ensure_ascii=False)
            
        logger.info(f"Exported features to {features_path}")
        logger.info(f"Exported rankings to {ranking_path}")

    def run(self, symbols: Optional[List[str]] = None):
        """Main entry point for the pipeline."""
        if not symbols:
            # Try to load from docs/data.json
            try:
                with open('docs/data.json', 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    symbols = list(data.get("stocks", {}).keys())
            except Exception as e:
                logger.error(f"Could not load symbols from docs/data.json: {e}")
                return
        
        if not symbols:
            logger.warning("No symbols to process.")
            return

        logger.info(f"Starting feature pipeline for {len(symbols)} symbols...")
        results = self.process_stocks(symbols)
        self.export_results(results)
        logger.info("Feature pipeline completed.")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbols", nargs="+", help="Symbols to process")
    parser.add_argument("--test-mode", action="store_true", help="Run in test mode with 2 symbols")
    args = parser.parse_args()
    
    pipeline = FeaturePipeline()
    target_symbols = args.symbols
    if args.test_mode:
        target_symbols = ["2330", "2317"]
        
    pipeline.run(symbols=target_symbols)
