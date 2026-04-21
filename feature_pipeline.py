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
OUTPUT_DIR = "api"

class FeaturePipeline:
    def __init__(self, api_key: Optional[str] = None):
        self.processor = TEJProcessor(api_key=api_key)
        if not os.path.exists(OUTPUT_DIR):
            os.makedirs(OUTPUT_DIR)

    def process_stocks(self, symbols: List[str]) -> Dict[str, List]:
        """Process a list of symbols and return aggregated features and rankings."""
        stock_features = []
        rankings = []
        
        updated_at = datetime.now().strftime("%Y-%m-%d")
        
        for symbol in symbols:
            logger.info(f"Processing features for {symbol}...")
            try:
                # Fetch monthly revenue
                rev_df = self.processor.get_monthly_revenue(symbol)
                if rev_df is None or len(rev_df) < 15:
                    logger.warning(f"Insufficient revenue data for {symbol}")
                    continue
                
                # Calculate features
                features = calculate_revenue_features(rev_df)
                if features:
                    # Prepare stock_features.json entry
                    feature_entry = {
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
                    stock_features.append(feature_entry)
                    
                    # Prepare ranking.json entry
                    ranking_entry = {
                        "symbol": symbol,
                        "total_score": features['revenue_score'], # Currently only revenue score
                        "revenue_score": features['revenue_score'],
                        "updated_at": updated_at
                    }
                    rankings.append(ranking_entry)
                else:
                    logger.warning(f"Could not calculate features for {symbol}")
            except Exception as e:
                logger.error(f"Error processing {symbol}: {e}")
                
        return {
            "stock_features": stock_features,
            "rankings": rankings
        }

    def export_results(self, data: Dict[str, List]):
        """Export results to JSON files."""
        features_path = os.path.join(OUTPUT_DIR, "stock_features.json")
        ranking_path = os.path.join(OUTPUT_DIR, "ranking.json")
        
        with open(features_path, 'w', encoding='utf-8') as f:
            json.dump(data["stock_features"], f, indent=2, ensure_ascii=False)
            
        with open(ranking_path, 'w', encoding='utf-8') as f:
            json.dump(data["rankings"], f, indent=2, ensure_ascii=False)
            
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
