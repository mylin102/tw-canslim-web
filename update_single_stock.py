#!/usr/bin/env python3
"""
Update Single Stock Data script.
"""

from __future__ import annotations

import copy
import json
import logging
import os
import re
import sys
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any

import numpy as np
import pandas as pd
import requests
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
from excel_processor import ExcelDataProcessor
from publish_safety import (
    PublishTransactionError,
    PublishValidationError,
    load_artifact_json,
    publish_artifact_bundle,
)
from orchestration_state import DEFAULT_STATE_PATH, load_rotation_state, save_rotation_state
from publish_projection import build_publish_projection_bundle
from tej_processor import TEJProcessor

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

TWSE_TICKER_URL = "https://mopsfin.twse.com.tw/opendata/t187ap03_L.csv"
TPEx_TICKER_URL = "https://mopsfin.twse.com.tw/opendata/t187ap03_O.csv"
TWSE_INST_URL = "https://www.twse.com.tw/rwd/zh/fund/T86"


def get_all_tw_tickers() -> dict[str, dict[str, str]]:
    """Fetch ticker metadata from official lists and ETF cache."""
    ticker_map = {}
    for url, suffix in ((TWSE_TICKER_URL, ".TW"), (TPEx_TICKER_URL, ".TWO")):
        try:
            df = pd.read_csv(url, encoding="utf-8")
            for _, row in df.iterrows():
                ticker_id = str(row["公司代號"]).strip()
                if len(ticker_id) == 4:
                    ticker_map[ticker_id] = {"name": str(row["公司簡稱"]), "suffix": suffix}
        except Exception as exc:  # noqa: BLE001 - remote data issues must be logged
            logger.warning("Failed to load ticker list from %s: %s", url, exc)

    cache_file = "etf_cache.json"
    if os.path.exists(cache_file):
        with open(cache_file, "r", encoding="utf-8") as handle:
            etfs = json.load(handle).get("etfs", {})
        for ticker_id, info in etfs.items():
            if "<BR>" in ticker_id or "<br>" in ticker_id:
                continue
            suffix = ".TW" if info.get("market") == "TWSE" else ".TWO"
            ticker_map[ticker_id] = {"name": info["name"], "suffix": suffix}
    return ticker_map


def get_market_prices():
    """Fetch market benchmark prices."""
    for symbol in ("^TWII", "0050.TW"):
        try:
            market_prices = yf.download(symbol, period="2y", auto_adjust=True, progress=False)["Close"].squeeze()
            if len(market_prices) > 0:
                return market_prices
        except Exception as exc:  # noqa: BLE001 - fallback logging
            logger.warning("Failed to download market benchmark %s: %s", symbol, exc)
    raise RuntimeError("Failed to fetch market benchmark data")


def get_trading_dates() -> list[str]:
    """Fetch recent trading dates from TWSE."""
    try:
        response = requests.get(
            "https://www.twse.com.tw/rwd/zh/TAIEX/TAIEXChart",
            params={"response": "json"},
            timeout=15,
        )
        response.raise_for_status()
        return [row[0].replace("-", "") for row in response.json() if row[0]][-20:]
    except Exception as exc:  # noqa: BLE001 - explicit operator visibility
        logger.warning("Failed to fetch trading dates: %s", exc)
        return []


def fetch_inst_all(date_str: str) -> dict[str, dict[str, int]]:
    """Fetch TWSE institutional data for one day."""
    result = {}
    try:
        response = requests.get(
            TWSE_INST_URL,
            params={"response": "json", "date": date_str, "selectType": "ALL"},
            timeout=15,
        )
        response.raise_for_status()
        data = response.json()
        if data.get("stat") == "OK":
            for row in data["data"]:
                ticker_id = row[0].strip()
                result[ticker_id] = {
                    "foreign_net": safe_int(row[4]) // 1000,
                    "trust_net": safe_int(row[10]) // 1000,
                    "dealer_net": safe_int(row[11]) // 1000,
                }
    except Exception as exc:  # noqa: BLE001 - explicit operational logging
        logger.warning("Failed to fetch institutional data for %s: %s", date_str, exc)
    return result


def download_price_history(symbol: str):
    """Download price history for one stock."""
    history = yf.download(symbol, period="2y", auto_adjust=True, progress=False)["Close"].dropna().squeeze()
    if len(history) == 0:
        raise RuntimeError(f"No price data for {symbol}")
    return history


def safe_int(value) -> int:
    """Convert numeric string safely."""
    try:
        return int(str(value).replace(",", ""))
    except Exception:  # noqa: BLE001 - low-level parser fallback
        return 0


def build_light_payload(data_payload: dict[str, Any]) -> dict[str, Any]:
    """Build a validated light payload."""
    light_payload = copy.deepcopy(data_payload)
    light_payload["artifact_kind"] = "data_light"
    return light_payload


def json_default(obj):
    """Serialize pandas and numpy objects."""
    if isinstance(obj, (datetime, pd.Timestamp)):
        return obj.strftime("%Y-%m-%d")
    if isinstance(obj, np.bool_):
        return bool(obj)
    if isinstance(obj, (np.integer, np.floating, np.float64, np.int64)):
        return obj.item()
    raise TypeError(f"Type {type(obj)} not serializable")


class SingleStockUpdater:
    """Update one stock and publish the full artifact bundle safely."""

    def __init__(self):
        self.root_dir = os.path.dirname(os.path.abspath(__file__))
        self.ticker_info = get_all_tw_tickers()
        self.excel_proc = ExcelDataProcessor(self.root_dir)
        self.excel_ratings = self.excel_proc.load_health_check_data() or {}
        self.fund_holdings = self.excel_proc.load_fund_holdings_data() or {}
        self.industry_data = self.excel_proc.load_industry_data() or {}
        self.tej_processor = TEJProcessor()
        self.data_base_path = os.path.join(self.root_dir, "docs", "data_base.json")

    def build_summary(self, run_id: str, ticker: str, data_payload: dict[str, Any]) -> dict[str, Any]:
        """Build the single-stock publish summary."""
        return {
            "timestamp": data_payload["last_updated"],
            "update_type": "single stock update",
            "description": f"On-demand publish for {ticker}",
            "run_id": run_id,
            "data_stats": {
                "total_stocks": len(data_payload.get("stocks", {})),
                "updated_stocks": 1,
            },
            "published_targets": [
                "docs/data_base.json",
                "docs/data.json",
                "docs/data_light.json",
                "docs/data.json.gz",
                "docs/update_summary.json",
            ],
            "next_action": "Review the issue response and verify the updated symbol in GitHub Pages.",
        }

    def _utc_timestamp(self) -> str:
        """Return a UTC timestamp aligned with the shared publish contract."""
        return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")

    def _load_rotation_state(self) -> dict[str, Any]:
        """Load or seed durable freshness state for publish projections."""
        return load_rotation_state(path=DEFAULT_STATE_PATH)

    def _persist_single_stock_success(self, state: dict[str, Any], *, ticker: str, timestamp: str) -> dict[str, Any]:
        """Record fresh success metadata for the updated ticker."""
        next_state = save_rotation_state(state, path=None)
        batch_generation = str(next_state.get("rotation_generation", "")).strip() or f"on-demand-{ticker}"
        next_state["retry_queue"] = [entry for entry in next_state["retry_queue"] if entry.get("symbol") != ticker]
        next_state["freshness"][ticker] = {
            "last_attempted_at": timestamp,
            "last_succeeded_at": timestamp,
            "last_batch_generation": batch_generation,
            "source": "on_demand",
        }
        return save_rotation_state(next_state, path=DEFAULT_STATE_PATH)

    def update_stock(self, ticker: str) -> bool:
        """Update one ticker and publish all derived artifacts as one bundle."""
        if not re.match(r"^\d{4,6}$", ticker):
            logger.error("Invalid ticker format: %s. Only 4-6 digits are allowed.", ticker)
            return False

        info = self.ticker_info.get(ticker, {"name": ticker, "suffix": ".TW"})
        try:
            market_prices = get_market_prices()
            trading_dates = get_trading_dates()
            inst_by_date = {date: fetch_inst_all(date) for date in trading_dates}
            prices = download_price_history(f"{ticker}{info['suffix']}")
        except Exception as exc:  # noqa: BLE001 - explicit failure for on-demand path
            logger.error("Failed to collect on-demand data for %s: %s", ticker, exc)
            return False

        history = []
        for trading_date in reversed(trading_dates):
            if ticker in inst_by_date.get(trading_date, {}):
                history.append({"date": trading_date, **inst_by_date[trading_date][ticker]})

        is_etf = self.tej_processor.is_etf(ticker) or ticker.startswith("00")
        m_rs = calculate_mansfield_rs(prices, market_prices)
        rs_trend = calculate_rs_trend(prices, market_prices)
        n_score = check_n_factor(prices)
        l_score = calculate_l_factor(m_rs)
        i_score = bool(history) and sum(day["foreign_net"] + day["trust_net"] + day["dealer_net"] for day in history[:3]) > 0

        factors = {"C": False, "A": False, "N": n_score, "S": True, "L": l_score, "I": i_score, "M": True}
        if not is_etf and ticker in self.excel_ratings:
            rating = self.excel_ratings[ticker].get("eps_rating", 0)
            factors["C"] = factors["A"] = rating >= 60

        score = compute_canslim_score_etf(factors) if is_etf else compute_canslim_score(factors)
        grid = calculate_volatility_grid(prices, is_etf=is_etf) if (score >= 60 or is_etf) else None

        stock_entry = {
            "schema_version": "1.0",
            "symbol": ticker,
            "name": info["name"],
            "industry": "ETF" if is_etf else self.industry_data.get(ticker, {}).get("industry", "未知"),
            "is_etf": is_etf,
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
                "grid_strategy": grid,
                "excel_ratings": self.excel_ratings.get(ticker),
                "fund_holdings": self.fund_holdings.get(ticker),
            },
            "institutional": history[:20],
        }

        try:
            full_data = load_artifact_json(self.data_base_path, artifact_kind="data_base", logger=logger)
        except PublishValidationError as exc:
            logger.error("Failed to load validated base artifact: %s", exc)
            return False

        run_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        generated_at = self._utc_timestamp()
        full_data.setdefault("stocks", {})
        full_data.setdefault("schema_version", "1.0")
        full_data["artifact_kind"] = "data_base"
        full_data["stocks"][ticker] = stock_entry
        full_data["run_id"] = run_id
        full_data["generated_at"] = generated_at
        full_data["last_updated"] = generated_at

        data_payload = copy.deepcopy(full_data)
        data_payload["artifact_kind"] = "data"

        try:
            rotation_state = self._persist_single_stock_success(
                self._load_rotation_state(),
                ticker=ticker,
                timestamp=generated_at,
            )
        except PublishValidationError as exc:
            logger.error("Failed to load or persist rotation state: %s", exc)
            return False

        all_symbols = sorted(set(self.ticker_info) | set(full_data.get("stocks", {})))
        projected = build_publish_projection_bundle(
            output_data=data_payload,
            baseline_payload=full_data,
            ticker_info=self.ticker_info,
            freshness_state=rotation_state,
            failure_details=[],
            failure_stats={},
            refreshed_symbols=[ticker],
            all_symbols=all_symbols,
            selection=SimpleNamespace(core_set={ticker}),
            scheduled_batch={
                "batch_index": rotation_state.get("current_batch_index", 0),
                "rotation_generation": rotation_state.get("rotation_generation", ""),
                "symbols": [],
                "completed_symbols": [],
                "remaining_symbols": [],
            },
            as_of=generated_at,
        )
        summary = projected["update_summary"]
        summary.update(
            {
                "update_type": "single stock update",
                "description": f"On-demand publish for {ticker}",
                "published_targets": [
                    "docs/data_base.json",
                    "docs/data.json",
                    "docs/data_light.json",
                    "docs/data.json.gz",
                    "docs/stock_index.json",
                    "docs/update_summary.json",
                ],
                "next_action": "Review the issue response and verify the updated symbol in GitHub Pages.",
            }
        )

        try:
            publish_artifact_bundle(
                {
                    "docs/data_base.json": {"artifact_kind": "data_base", "payload": full_data},
                    "docs/data.json": {"artifact_kind": "data", "payload": projected["data"]},
                    "docs/data_light.json": {"artifact_kind": "data_light", "payload": build_light_payload(projected["data"])},
                    "docs/data.json.gz": {"artifact_kind": "data_gz", "payload": projected["data"]},
                    "docs/stock_index.json": {"artifact_kind": "stock_index", "payload": projected["stock_index"]},
                    "docs/update_summary.json": {"artifact_kind": "update_summary", "payload": summary},
                },
                lock_path="docs/.publish.lock",
                backup_dir="backups/last_good",
                logger=logger,
                json_default=json_default,
            )
        except (PublishValidationError, PublishTransactionError) as exc:
            logger.error("On-demand publish failed for %s: %s", ticker, exc)
            return False

        logger.info("✅ Updated %s and published data bundle", ticker)
        return True


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python update_single_stock.py <ticker>")
        sys.exit(1)

    ticker = sys.argv[1]
    sys.exit(0 if SingleStockUpdater().update_stock(ticker) else 1)
