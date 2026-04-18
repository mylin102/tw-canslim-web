"""
Export consolidated Alpha data for Dashboard 2.0.
Combines fused Parquet signals with ticker metadata (names, industries).
"""

from datetime import UTC, datetime
import logging
import os

import pandas as pd

from export_canslim import get_all_tw_tickers  # Reuse ticker fetcher
from publish_safety import (
    PublishTransactionError,
    PublishValidationError,
    publish_artifact_bundle,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

FUSED_DATA_PATH = "master_canslim_signals_fused.parquet"
OUTPUT_JSON_PATH = "docs/data.json"
SCHEMA_VERSION = "1.0"


def _build_run_id() -> str:
    """Create a bundle run identifier for dashboard exports."""
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")


def _generated_at() -> str:
    """Return an ISO-like UTC timestamp."""
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _json_default(obj):
    """Serialize datetime-like objects for bundle publishing."""
    if isinstance(obj, (datetime, pd.Timestamp)):
        return obj.strftime("%Y-%m-%d")
    raise TypeError(f"Type {type(obj)} not serializable")


def export_data():
    """Export the latest dashboard snapshot through the shared publish helper."""
    if not os.path.exists(FUSED_DATA_PATH):
        message = f"Source file {FUSED_DATA_PATH} not found."
        logger.exception(message)
        raise FileNotFoundError(message)

    try:
        logger.info("Loading latest Alpha signals...")
        df = pd.read_parquet(FUSED_DATA_PATH)
        latest_date = df.date.max()
        df_latest = df[df.date == latest_date].copy()

        logger.info("Fetching ticker metadata...")
        ticker_info = get_all_tw_tickers()

        output = {
            "schema_version": SCHEMA_VERSION,
            "artifact_kind": "data",
            "run_id": _build_run_id(),
            "generated_at": _generated_at(),
            "last_updated": latest_date.strftime("%Y-%m-%d %H:%M:%S"),
            "stocks": {},
        }

        logger.info(f"Processing {len(df_latest)} stocks for snapshot {latest_date}...")

        for _, row in df_latest.iterrows():
            sid = str(row["stock_id"])
            meta = ticker_info.get(sid, {"name": sid, "suffix": ".TW"})
            mansfield_rs = float(row["rs_rating"]) if pd.notna(row["rs_rating"]) else 0.0

            output["stocks"][sid] = {
                "schema_version": SCHEMA_VERSION,
                "symbol": sid,
                "name": meta["name"],
                "canslim": {
                    "C": bool(row["C"]),
                    "I": bool(row["I"]),
                    "N": bool(row["N"]),
                    "S": bool(row["S"]),
                    "score": int(row["score"]),
                    "rs_rating": mansfield_rs,
                    "mansfield_rs": mansfield_rs,
                    "fund_change": float(row["fund_change"]) if pd.notna(row["fund_change"]) else None,
                    "smr_rating": str(row["smr_rating"]) if pd.notna(row["smr_rating"]) else None,
                    "grid_strategy": {
                        "mode": "dashboard_snapshot",
                        "position": "n/a",
                    },
                },
                "institutional": [],
            }

        os.makedirs(os.path.dirname(OUTPUT_JSON_PATH), exist_ok=True)
        publish_artifact_bundle(
            {
                OUTPUT_JSON_PATH: {
                    "artifact_kind": "data",
                    "payload": output,
                }
            },
            logger=logger,
            json_default=_json_default,
        )
    except (FileNotFoundError, PublishValidationError, PublishTransactionError):
        logger.exception("Dashboard export failed")
        raise
    except Exception:
        logger.exception("Dashboard export failed unexpectedly")
        raise

    logger.info(f"✅ Dashboard data exported to {OUTPUT_JSON_PATH}")


if __name__ == "__main__":
    export_data()
