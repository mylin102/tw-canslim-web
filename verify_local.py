"""
Advanced Data Verifier & Rebuilder.
"""

from __future__ import annotations

import copy
import json
import logging
import time
from datetime import UTC, datetime
from typing import Any

import numpy as np
import pandas as pd
import yfinance as yf

from core.logic import (
    calculate_l_factor,
    calculate_mansfield_rs,
    calculate_rs_trend,
    calculate_volatility_grid,
    check_n_factor,
    compute_canslim_score,
    compute_canslim_score_etf,
)
from export_canslim import CanslimEngine
from publish_safety import PublishTransactionError, PublishValidationError, publish_artifact_bundle

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def get_market_benchmark(symbols: tuple[str, ...] = ("^TWII", "0050.TW")):
    """Fetch the benchmark series with an explicit fallback path."""
    for symbol in symbols:
        try:
            market_hist = yf.download(symbol, period="2y", auto_adjust=True, progress=False)["Close"].squeeze()
            if not market_hist.empty:
                return market_hist
        except Exception as exc:  # noqa: BLE001 - intentional fallback logging
            logger.warning("Benchmark download failed for %s: %s", symbol, exc)
    raise RuntimeError("Unable to fetch market benchmark data")


def build_light_payload(output: dict[str, Any]) -> dict[str, Any]:
    """Build a validated light payload for publish safety."""
    light_payload = copy.deepcopy(output)
    light_payload["artifact_kind"] = "data_light"
    return light_payload


def publish_rebuild_bundle(output: dict[str, Any], target_tickers: list[str]) -> dict[str, Any]:
    """Publish rebuilt verification artifacts through the shared bundle helper."""
    summary = {
        "schema_version": "1.0",
        "artifact_kind": "update_summary",
        "timestamp": output["last_updated"],
        "update_type": "verification rebuild",
        "description": f"Verification rebuild for {', '.join(target_tickers)}",
        "run_id": output["run_id"],
        "data_stats": {
            "total_stocks": len(output.get("stocks", {})),
            "updated_stocks": len(target_tickers),
        },
        "refreshed_symbols": list(target_tickers),
        "failed_symbols": [],
        "next_rotation": {
            "batch_index": 0,
            "symbols": [],
        },
        "freshness_counts": {
            "today": 0,
            "warning": 0,
            "stale": 0,
        },
        "published_targets": [
            "docs/data.json",
            "docs/data_light.json",
            "docs/update_summary.json",
        ],
        "next_action": "Review verification output before promoting additional operational changes.",
    }
    publish_artifact_bundle(
        {
            "docs/data.json": {"artifact_kind": "data", "payload": output},
            "docs/data_light.json": {"artifact_kind": "data_light", "payload": build_light_payload(output)},
            "docs/update_summary.json": {"artifact_kind": "update_summary", "payload": summary},
        },
        lock_path="docs/.publish.lock",
        backup_dir="backups/last_good",
        logger=logger,
        json_default=json_default,
    )
    return {"run_id": output["run_id"]}


def json_default(obj):
    """Serialize pandas and numpy values for JSON output."""
    if isinstance(obj, (datetime, pd.Timestamp)):
        return obj.strftime("%Y-%m-%d")
    if isinstance(obj, np.bool_):
        return bool(obj)
    if isinstance(obj, (np.integer, np.floating)):
        return obj.item()
    return obj


def rebuild(target_tickers: list[str] | None = None, sleep_seconds: float = 0.5) -> bool:
    """Rebuild and publish high-fidelity data for key symbols."""
    engine = CanslimEngine()
    target_tickers = target_tickers or [
        "2330",
        "2317",
        "2454",
        "2603",
        "2881",
        "2308",
        "2382",
        "3711",
        "0050",
        "0052",
        "0056",
        "00878",
        "00631L",
        "00981A",
        "00881",
    ]

    market_hist = get_market_benchmark()
    run_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    output = {
        "schema_version": "1.0",
        "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "run_id": run_id,
        "stocks": {},
    }

    for ticker in target_tickers:
        try:
            info = engine.ticker_info.get(ticker, {"name": ticker, "suffix": ".TW"})
            is_etf = ticker.startswith("00")
            stock_hist = yf.download(
                f"{ticker}{info['suffix']}",
                period="2y",
                auto_adjust=True,
                progress=False,
            )["Close"].squeeze()
            if stock_hist.empty:
                logger.warning("Skipping %s because no price history was available", ticker)
                continue

            history = engine.fetch_institutional_data_finmind(ticker, days=60)
            m_rs = calculate_mansfield_rs(stock_hist, market_hist)
            rs_trend = calculate_rs_trend(stock_hist, market_hist)
            n_score = check_n_factor(stock_hist)
            l_score = calculate_l_factor(m_rs)

            c_pass = a_pass = False
            if is_etf:
                c_pass = a_pass = bool(l_score)
            else:
                tej_ca = engine.tej_processor.calculate_canslim_c_and_a(ticker)
                c_pass = tej_ca.get("C", False)
                a_pass = tej_ca.get("A", False)
                if not c_pass and engine.excel_ratings and ticker in engine.excel_ratings:
                    if engine.excel_ratings[ticker].get("eps_rating", 0) >= 60:
                        c_pass = a_pass = True

            i_pass = engine.check_i_institutional(history) if history else False
            if not i_pass and engine.fund_holdings and ticker in engine.fund_holdings:
                i_pass = True

            factors = {"C": c_pass, "A": a_pass, "N": n_score, "S": True, "L": l_score, "I": i_pass, "M": True}
            score = compute_canslim_score_etf(factors) if is_etf else compute_canslim_score(factors)
            grid = calculate_volatility_grid(stock_hist, is_etf=is_etf) if (score >= 60 or is_etf) else None

            output["stocks"][ticker] = {
                "schema_version": "1.0",
                "symbol": ticker,
                "name": info["name"],
                "is_etf": is_etf,
                "industry": "ETF" if is_etf else "核心權值",
                "canslim": {
                    "C": bool(factors["C"]),
                    "A": bool(factors["A"]),
                    "N": bool(factors["N"]),
                    "S": bool(factors["S"]),
                    "L": bool(factors["L"]),
                    "I": bool(factors["I"]),
                    "M": bool(factors["M"]),
                    "score": int(score),
                    "mansfield_rs": float(m_rs),
                    "rs_trend": rs_trend,
                    "rs_ratio": 1.0,
                    "grid_strategy": grid,
                    "excel_ratings": engine.excel_ratings.get(ticker) if engine.excel_ratings else None,
                    "fund_holdings": engine.fund_holdings.get(ticker) if engine.fund_holdings else None,
                },
                "institutional": history[:10] if history else [],
            }
            time.sleep(sleep_seconds)
        except Exception as exc:  # noqa: BLE001 - verification errors must be explicit
            logger.exception("Verification rebuild failed for %s: %s", ticker, exc)

    try:
        publish_rebuild_bundle(output, target_tickers)
    except (PublishValidationError, PublishTransactionError) as exc:
        logger.error("Verification publish failed: %s", exc)
        return False

    logger.info("🎉 Verification Rebuild Complete.")
    return True


if __name__ == "__main__":
    rebuild()
