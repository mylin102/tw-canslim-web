"""
Advanced Data Verifier & Rebuilder - Smart Expansion Mode.
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
from publish_safety import PublishTransactionError, PublishValidationError, is_publish_safety_error, publish_artifact_bundle

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


def sanitize_payload(obj):
    """Deep sanitize to ensure no NaN/Inf enter the JSON file."""
    if isinstance(obj, dict):
        return {k: sanitize_payload(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [sanitize_payload(x) for x in obj]
    if isinstance(obj, float) and (np.isnan(obj) or np.isinf(obj)):
        return None
    if isinstance(obj, (np.integer, np.floating)):
        val = obj.item()
        if isinstance(val, float) and (np.isnan(val) or np.isinf(val)):
            return None
        return val
    return obj


def publish_rebuild_bundle(output: dict[str, Any], target_tickers: list[str]) -> dict[str, Any]:
    """Publish rebuilt verification artifacts through the shared bundle helper."""
    # 強制深度清理 NaN
    safe_output = sanitize_payload(output)
    
    summary = {
        "schema_version": "1.0",
        "artifact_kind": "update_summary",
        "timestamp": safe_output["last_updated"],
        "update_type": "smart expansion",
        "description": f"Expanded market coverage with {len(target_tickers)} stocks.",
        "run_id": safe_output["run_id"],
        "data_stats": {
            "total_stocks": len(safe_output.get("stocks", {})),
            "updated_stocks": len(target_tickers),
        },
        "refreshed_symbols": list(target_tickers),
        "failed_symbols": [],
        "next_rotation": {"batch_index": 0, "symbols": []},
        "freshness_counts": {"today": len(target_tickers), "warning": 0, "stale": 0},
        "published_targets": ["docs/data.json", "docs/data_light.json", "docs/update_summary.json"],
        "next_action": "Continue smart expansion to rebuild full market cache.",
    }
    publish_artifact_bundle(
        {
            "docs/data.json": {"artifact_kind": "data", "payload": safe_output},
            "docs/data_light.json": {"artifact_kind": "data_light", "payload": build_light_payload(safe_output)},
            "docs/update_summary.json": {"artifact_kind": "update_summary", "payload": summary},
        },
        lock_path="docs/.publish.lock",
        backup_dir="backups/last_good",
        logger=logger,
        json_default=json_default,
    )
    return {"run_id": safe_output["run_id"]}


def json_default(obj):
    """Serialize pandas and numpy values for JSON output, handling NaN/Inf."""
    if isinstance(obj, (datetime, pd.Timestamp)):
        return obj.strftime("%Y-%m-%d")
    if isinstance(obj, np.bool_):
        return bool(obj)
    if isinstance(obj, (np.integer, np.floating)):
        val = obj.item()
        if isinstance(val, float) and (np.isnan(val) or np.isinf(val)):
            return None
        return val
    # 處理原生 float 的 NaN
    if isinstance(obj, float) and (np.isnan(obj) or np.isinf(obj)):
        return None
    return obj


def rebuild(batch_size: int = 50, sleep_seconds: float = 0.5) -> bool:
    """Rebuild and expand market data cache."""
    engine = CanslimEngine()
    
    # 1. 載入現有資料
    try:
        with open("docs/data.json", "r") as f:
            existing_data = json.load(f)
            stocks = existing_data.get("stocks", {})
    except:
        stocks = {}

    # 2. 找出尚未抓取的股票
    all_market_symbols = list(engine.ticker_info.keys())
    # 排除已抓取的，並挑選前 batch_size 檔
    to_fetch = [s for s in all_market_symbols if s not in stocks][:batch_size]
    
    if not to_fetch:
        logger.info("All market stocks are already cached!")
        return True

    logger.info(f"🚀 Smart Expansion: Targeted {len(to_fetch)} new stocks.")

    market_hist = get_market_benchmark()
    run_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    
    # 繼承舊資料，只更新/新增 to_fetch 部分
    output = {
        "schema_version": "1.0",
        "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "run_id": run_id,
        "stocks": stocks, 
    }

    refreshed = []
    for ticker in to_fetch:
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
                # 試試 .TWO 尾綴
                stock_hist = yf.download(
                    f"{ticker}.TWO",
                    period="2y",
                    auto_adjust=True,
                    progress=False,
                )["Close"].squeeze()
                
            if stock_hist.empty:
                logger.warning("Skipping %s: no price history", ticker)
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
                tej_ca = engine.tej_processor.calculate_canslim_c_and_a(ticker) or {}
                c_pass = bool(tej_ca.get("C", False))
                a_pass = bool(tej_ca.get("A", False))
                if not c_pass and engine.excel_ratings and ticker in engine.excel_ratings:
                    eps_rating = engine.excel_ratings[ticker].get("eps_rating")
                    if eps_rating is not None and isinstance(eps_rating, (int, float)) and eps_rating >= 60:
                        c_pass = a_pass = True

            i_pass = engine.check_i_institutional(history) if history else False
            factors = {"C": c_pass, "A": a_pass, "N": n_score, "S": True, "L": l_score, "I": i_pass, "M": True}
            score = compute_canslim_score_etf(factors) if is_etf else compute_canslim_score(factors)
            
            grid = {}
            try:
                if (score >= 60 or is_etf) and stock_hist is not None and not stock_hist.empty:
                    grid = calculate_volatility_grid(stock_hist, is_etf=is_etf) or {}
            except Exception as grid_exc:
                logger.warning("Grid calculation failed for %s: %s", ticker, grid_exc)

            # 確保 industry 是純字串
            industry_val = engine.industry_data.get(ticker, "未知")
            if isinstance(industry_val, dict):
                industry_val = industry_val.get("industry", "其他")
            industry_val = str(industry_val) if industry_val else "其他"

            output["stocks"][ticker] = {
                "schema_version": "1.0",
                "symbol": ticker,
                "name": info["name"],
                "is_etf": is_etf,
                "industry": "ETF" if is_etf else industry_val,
                "canslim": {
                    "C": bool(factors["C"]), "A": bool(factors["A"]), "N": bool(factors["N"]),
                    "S": bool(factors["S"]), "L": bool(factors["L"]), "I": bool(factors["I"]),
                    "M": bool(factors["M"]), "score": int(score), "mansfield_rs": float(m_rs),
                    "rs_trend": rs_trend, "rs_ratio": 1.0, "grid_strategy": grid,
                    "inst_details": {"source": "smart_expansion"}
                },
                "institutional": history[:10] if history else [],
                "last_succeeded_at": output["last_updated"],
            }
            refreshed.append(ticker)
            logger.info(f"✅ Processed {ticker} ({len(refreshed)}/{len(to_fetch)})")
            time.sleep(sleep_seconds)
        except Exception as exc:
            logger.error(f"Failed {ticker}: {exc}")

    if refreshed:
        publish_rebuild_bundle(output, refreshed)
        logger.info(f"🎉 Successfully expanded with {len(refreshed)} stocks.")
    
    return True


if __name__ == "__main__":
    rebuild(batch_size=50)
