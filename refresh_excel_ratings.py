"""
Refreshes docs/data.json's canslim.excel_ratings (incl. RS Rating) from a
locally-downloaded 股票健診*.xlsm health-check file, without re-running the
full CANSLIM pipeline.

Why this exists: the health-check Excel file is .gitignore'd (too large,
locally-licensed data) and never available to the GitHub Actions runner, so
export_canslim.py's own excel_ratings merge only ever runs when someone
happens to execute it locally with the file present -- in practice that was
once, months ago, leaving excel_ratings.rs_rating populated for exactly 1 of
2174 stocks in production. This script re-reads a current health-check file
directly from wherever it's downloaded (no need to copy it into the repo)
and refreshes excel_ratings for every stock docs/data.json already knows
about, leaving every other field (score, freshness, mansfield_rs, etc.)
untouched.
"""

import argparse
import json
import logging
import os

from excel_processor import ExcelDataProcessor

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(SCRIPT_DIR, "docs", "data.json")


def refresh(excel_dir: str, data_file: str = DATA_FILE) -> None:
    processor = ExcelDataProcessor(excel_dir)
    if not processor.health_check_file:
        logger.error(f"No 股票健診*.xlsm file found in {excel_dir}")
        return

    excel_ratings = processor.load_health_check_data()
    if not excel_ratings:
        logger.error("Failed to load ratings from the health-check file.")
        return
    logger.info(f"Loaded excel_ratings for {len(excel_ratings)} stocks from {processor.health_check_file}")

    with open(data_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    updated = 0
    for symbol, entry in data.get("stocks", {}).items():
        canslim = entry.get("canslim")
        ratings = excel_ratings.get(symbol)
        if canslim is None or ratings is None:
            continue
        canslim["excel_ratings"] = ratings
        updated += 1

    with open(data_file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")

    logger.info(f"✅ Refreshed excel_ratings for {updated}/{len(data.get('stocks', {}))} stocks in {data_file}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--excel-dir",
        default=os.path.expanduser("~/Downloads"),
        help="Directory to search for a 股票健診*.xlsm file (default: ~/Downloads)",
    )
    parser.add_argument("--data-file", default=DATA_FILE, help="Target data.json to update")
    args = parser.parse_args()
    refresh(args.excel_dir, args.data_file)
