#!/usr/bin/env python3
"""
快速更新前10支股票的機構持股資料 - 加強版。
"""

from __future__ import annotations

import copy
import logging
import sys
from datetime import UTC, datetime, timedelta
from typing import Any

from publish_safety import (
    PublishTransactionError,
    PublishValidationError,
    load_artifact_json,
    publish_artifact_bundle,
)

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("debug_log.txt"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)

MAX_FETCH_ATTEMPTS = 2


def load_existing_data(path: str = "docs/data.json") -> dict[str, Any] | None:
    """載入現有已驗證資料。"""
    logger.info("🔍 載入現有資料...")
    try:
        data = load_artifact_json(path, artifact_kind="data", logger=logger)
    except PublishValidationError as exc:
        logger.error("❌ 載入資料失敗: %s", exc)
        return None

    logger.info("✅ 成功載入 %s 支股票資料", len(data.get("stocks", {})))
    return data


def fetch_real_institutional_data(stock_id, processor, days: int = 20) -> dict[str, Any]:
    """獲取真實機構持股資料並回報重試資訊。"""
    retries_used = 0
    last_error = None

    for attempt in range(1, MAX_FETCH_ATTEMPTS + 1):
        try:
            recent_data = processor.fetch_recent_trading_days(stock_id, days=days)
            if not isinstance(recent_data, dict) or not recent_data:
                raise ValueError("recent_data 為空或格式錯誤")

            real_data = []
            for date in sorted(recent_data.keys(), reverse=True)[:days]:
                data = recent_data[date]
                if not isinstance(data, dict):
                    raise ValueError(f"{stock_id} {date} 資料格式錯誤")

                real_data.append(
                    {
                        "date": data.get("date", date),
                        "foreign_net": data.get("foreign_net", 0),
                        "trust_net": data.get("trust_net", 0),
                        "dealer_net": data.get("dealer_net", 0),
                    }
                )

            if not real_data:
                raise ValueError("無法轉換有效機構持股資料")

            logger.info("✅ %s: 成功獲取 %s 筆真實機構持股資料", stock_id, len(real_data))
            return {
                "data": real_data,
                "retry_count": retries_used,
                "exhausted": False,
                "error": None,
            }
        except Exception as exc:  # noqa: BLE001 - explicit operational logging
            last_error = str(exc)
            if attempt < MAX_FETCH_ATTEMPTS:
                retries_used += 1
                logger.warning(
                    "%s: 第 %s/%s 次抓取失敗，準備重試: %s",
                    stock_id,
                    attempt,
                    MAX_FETCH_ATTEMPTS,
                    exc,
                )
                continue

            logger.error("❌ 獲取 %s 機構持股資料失敗: %s", stock_id, exc)
            return {
                "data": None,
                "retry_count": retries_used,
                "exhausted": True,
                "error": last_error,
            }


def build_light_payload(data: dict[str, Any]) -> dict[str, Any]:
    """建立可通過共享驗證的輕量發佈資料。"""
    light_payload = copy.deepcopy(data)
    light_payload["artifact_kind"] = "data_light"
    return light_payload


def build_update_summary(
    data: dict[str, Any],
    *,
    updated_count: int,
    real_data_count: int,
    sample_data_count: int,
    retry_count: int,
    exhausted_retries: int,
    failed_tickers: list[str],
    failed_steps: list[str],
) -> dict[str, Any]:
    """建立更新摘要。"""
    return {
        "timestamp": data["last_updated"],
        "update_type": "快速自動更新 (加強版)",
        "description": "更新前10支股票機構持股資料，並以 bundle 安全發佈相關 artifacts。",
        "run_id": data["run_id"],
        "api_status": {
            "finmind": "partial" if failed_tickers else "ok",
            "publish": "ready",
        },
        "data_stats": {
            "total_stocks": len(data.get("stocks", {})),
            "updated_stocks": updated_count,
            "real_data_count": real_data_count,
            "sample_data_count": sample_data_count,
            "retry_count": retry_count,
            "exhausted_retries": exhausted_retries,
            "failed_tickers": failed_tickers,
            "failed_steps": failed_steps,
        },
        "next_action": "檢查 failed_tickers 並在下一次完整排程更新前確認資料來源。",
        "next_scheduled_update": "今天 18:00 (台灣時間)",
        "github_actions": "https://github.com/mylin102/tw-canslim-web/actions",
        "debug_log": "debug_log.txt",
    }


def publish_operational_bundle(data: dict[str, Any], summary: dict[str, Any]) -> dict[str, Any]:
    """發佈完整 bundle。"""
    return publish_artifact_bundle(
        {
            "docs/data.json": {
                "artifact_kind": "data",
                "payload": data,
            },
            "docs/data_light.json": {
                "artifact_kind": "data_light",
                "payload": build_light_payload(data),
            },
            "docs/update_summary.json": {
                "artifact_kind": "update_summary",
                "payload": summary,
            },
        },
        lock_path="docs/.publish.lock",
        backup_dir="backups/last_good",
        logger=logger,
    )


def update_top_stocks_institutional() -> dict[str, Any]:
    """更新前10支股票的機構持股資料並安全發佈。"""
    logger.info("🚀 開始更新前10支股票的機構持股資料")

    data = load_existing_data()
    if data is None:
        return {"success": False, "error": "無法載入已驗證資料"}

    stocks = data.get("stocks", {})
    top_stocks = list(stocks.keys())[:10]
    if not top_stocks:
        logger.error("❌ 沒有可更新的股票")
        return {"success": False, "error": "沒有可更新的股票"}

    try:
        from finmind_processor import FinMindProcessor

        processor = FinMindProcessor()
        if not processor.available:
            logger.warning("⚠️ FinMind 處理器不可用，將使用範例資料")
            processor = None
    except Exception as exc:  # noqa: BLE001 - import failure should be visible
        logger.warning("⚠️ 無法導入 FinMind 處理器: %s", exc)
        processor = None

    updated_count = 0
    real_data_count = 0
    sample_data_count = 0
    retry_count = 0
    exhausted_retries = 0
    failed_tickers: list[str] = []

    for stock_id in top_stocks:
        stock_data = stocks[stock_id]
        fetch_result = {"data": None, "retry_count": 0, "exhausted": False, "error": None}

        if processor and processor.available:
            fetch_result = fetch_real_institutional_data(stock_id, processor, days=20)
            retry_count += fetch_result["retry_count"]
            if fetch_result["exhausted"]:
                exhausted_retries += 1
                failed_tickers.append(stock_id)

        if fetch_result["data"]:
            stock_data["institutional"] = fetch_result["data"]
            stock_data["institutional_source"] = "FinMind API (真實資料)"
            real_data_count += 1
        else:
            today = datetime.now()
            sample_data = []
            for index in range(5):
                date = (today - timedelta(days=index)).strftime("%Y%m%d")
                sample_data.append(
                    {
                        "date": date,
                        "foreign_net": 1000 + index * 100,
                        "trust_net": 500 + index * 50,
                        "dealer_net": 200 + index * 20,
                        "source": "範例資料",
                    }
                )

            stock_data["institutional"] = sample_data
            stock_data["institutional_source"] = "範例資料"
            sample_data_count += 1

        updated_count += 1

    run_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    data["run_id"] = run_id
    data["last_updated"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    data["update_type"] = "快速更新 (前10支股票)"
    data["update_stats"] = {
        "total_updated": updated_count,
        "real_data_count": real_data_count,
        "sample_data_count": sample_data_count,
        "retry_count": retry_count,
        "exhausted_retries": exhausted_retries,
        "failed_tickers": failed_tickers,
        "timestamp": datetime.now().isoformat(),
    }

    summary = build_update_summary(
        data,
        updated_count=updated_count,
        real_data_count=real_data_count,
        sample_data_count=sample_data_count,
        retry_count=retry_count,
        exhausted_retries=exhausted_retries,
        failed_tickers=failed_tickers,
        failed_steps=[],
    )

    try:
        publish_result = publish_operational_bundle(data, summary)
    except (PublishValidationError, PublishTransactionError) as exc:
        logger.error("❌ publish bundle 失敗: %s", exc)
        return {"success": False, "error": str(exc)}

    logger.info("✅ 已更新 %s 支股票並完成 bundle 發佈", updated_count)
    return {
        "success": True,
        "updated_count": updated_count,
        "real_data_count": real_data_count,
        "sample_data_count": sample_data_count,
        "retry_count": retry_count,
        "exhausted_retries": exhausted_retries,
        "failed_tickers": failed_tickers,
        "publish_result": publish_result,
    }


def verify_update() -> bool:
    """驗證更新結果。"""
    logger.info("\n🔍 驗證更新結果...")
    try:
        data = load_artifact_json("docs/data.json", artifact_kind="data", logger=logger)
        summary = load_artifact_json("docs/update_summary.json", artifact_kind="update_summary", logger=logger)
    except PublishValidationError as exc:
        logger.error("❌ 驗證失敗: %s", exc)
        return False

    logger.info("✅ 資料完整性檢查通過")
    logger.info("   股票數量: %s", len(data.get("stocks", {})))
    logger.info("   最後更新: %s", data.get("last_updated"))
    logger.info("   重試次數: %s", summary["data_stats"].get("retry_count", 0))
    return True


def main() -> bool:
    """主函數。"""
    logger.info("🚀 開始快速自動更新 (加強版)\n")
    result = update_top_stocks_institutional()
    if not result.get("success"):
        logger.error("❌ 更新失敗: %s", result.get("error", "未知錯誤"))
        return False

    verify_ok = verify_update()
    if verify_ok:
        logger.info("🎉 快速自動更新完成！")
    else:
        logger.error("⚠️ 更新後驗證失敗")
    return verify_ok


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
