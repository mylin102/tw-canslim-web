#!/usr/bin/env python3
"""
批次更新機構持股資料。
"""

from __future__ import annotations

import argparse
import copy
import logging
import sys
from datetime import UTC, datetime, timedelta
from typing import Any

from publish_safety import (
    PublishTransactionError,
    PublishValidationError,
    is_publish_safety_error,
    load_artifact_json,
    publish_artifact_bundle,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("batch_institutional.log"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)

MAX_FETCH_ATTEMPTS = 2


class BatchInstitutionalUpdater:
    """批次更新機構持股資料。"""

    def __init__(self):
        self.total_stocks = 2173
        self.daily_limit = 1000
        self.processor = None

        try:
            from finmind_processor import FinMindProcessor

            self.processor = FinMindProcessor()
            if not self.processor.available:
                logger.warning("FinMind 處理器不可用")
                self.processor = None
        except Exception as exc:  # noqa: BLE001 - explicit operator visibility
            logger.warning("無法導入 FinMind 處理器: %s", exc)

    def load_stock_list(self) -> list[str]:
        """載入已驗證股票清單。"""
        logger.info("載入股票列表...")
        try:
            data = load_artifact_json("docs/data.json", artifact_kind="data", logger=logger)
        except PublishValidationError as exc:
            logger.error("❌ 載入股票列表失敗: %s", exc)
            return []

        stock_ids = list(data.get("stocks", {}).keys())
        logger.info("✅ 載入 %s 支股票", len(stock_ids))
        return stock_ids

    def calculate_batch_range(self, offset_day: int = 0) -> tuple[int, int, int]:
        """計算批次範圍。"""
        day_index = offset_day % 3
        start_idx = day_index * self.daily_limit
        end_idx = min(start_idx + self.daily_limit, self.total_stocks)
        batch_size = end_idx - start_idx
        logger.info("批次計算: 偏移天數=%s, 範圍=%s-%s", offset_day, start_idx, end_idx)
        return start_idx, end_idx, batch_size

    def fetch_institutional_data(self, stock_id: str, days: int = 20) -> dict[str, Any]:
        """獲取機構持股資料並回報重試結果。"""
        if not self.processor or not self.processor.available:
            logger.warning("%s: FinMind 處理器不可用", stock_id)
            return {"data": None, "retry_count": 0, "exhausted": False, "error": "processor unavailable"}

        retries_used = 0
        last_error = None
        for attempt in range(1, MAX_FETCH_ATTEMPTS + 1):
            try:
                recent_data = self.processor.fetch_recent_trading_days(stock_id, days=days)
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
                            "source": "FinMind API",
                        }
                    )

                if not real_data:
                    raise ValueError("無法轉換有效機構持股資料")

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
                    logger.warning("%s: 第 %s/%s 次抓取失敗，準備重試: %s", stock_id, attempt, MAX_FETCH_ATTEMPTS, exc)
                    continue

                logger.error("%s: 獲取機構持股資料失敗: %s", stock_id, exc)
                return {
                    "data": None,
                    "retry_count": retries_used,
                    "exhausted": True,
                    "error": last_error,
                }

    def build_light_payload(self, data: dict[str, Any]) -> dict[str, Any]:
        """建立輕量發佈資料。"""
        light_payload = copy.deepcopy(data)
        light_payload["artifact_kind"] = "data_light"
        return light_payload

    def build_summary(
        self,
        data: dict[str, Any],
        *,
        updated_count: int,
        real_data_count: int,
        sample_data_count: int,
        retry_count: int,
        exhausted_retries: int,
        failed_tickers: list[str],
        offset_day: int,
        refreshed_symbols: list[str],
    ) -> dict[str, Any]:
        """建立批次更新摘要。"""
        return {
            "schema_version": "1.0",
            "artifact_kind": "update_summary",
            "timestamp": data["last_updated"],
            "update_type": "機構持股批次更新",
            "description": "批次更新機構持股資料並以 bundle 安全發佈 data/data_light/update_summary。",
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
                "failed_steps": [],
            },
            "refreshed_symbols": list(refreshed_symbols),
            "failed_symbols": list(failed_tickers),
            "next_rotation": {
                "batch_index": (offset_day + 1) % 3,
                "symbols": [],
            },
            "freshness_counts": {
                "today": 0,
                "warning": 0,
                "stale": 0,
            },
            "next_batch": {
                "offset_day": (offset_day + 1) % 3,
                "expected_date": (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d"),
                "expected_time": "18:00",
            },
            "next_action": "檢查 failed_tickers，確認批次輪替前的來源穩定性。",
            "system_status": {
                "finmind_available": self.processor is not None and self.processor.available,
                "total_stocks": self.total_stocks,
                "daily_limit": self.daily_limit,
            },
        }

    def publish_bundle(self, data: dict[str, Any], summary: dict[str, Any]) -> dict[str, Any]:
        """發佈批次更新 bundle。"""
        return publish_artifact_bundle(
            {
                "docs/data.json": {
                    "artifact_kind": "data",
                    "payload": data,
                },
                "docs/data_light.json": {
                    "artifact_kind": "data_light",
                    "payload": self.build_light_payload(data),
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

    def update_batch(self, stock_ids: list[str], offset_day: int = 0) -> dict[str, Any]:
        """更新批次股票並安全發佈。"""
        logger.info("開始更新批次 (偏移天數: %s)", offset_day)
        try:
            data = load_artifact_json("docs/data.json", artifact_kind="data", logger=logger)
        except PublishValidationError as exc:
            logger.error("❌ 載入資料失敗: %s", exc)
            return {"success": False, "error": str(exc)}

        stocks = data.get("stocks", {})
        updated_count = 0
        real_data_count = 0
        sample_data_count = 0
        retry_count = 0
        exhausted_retries = 0
        failed_tickers: list[str] = []

        for stock_id in stock_ids:
            if stock_id not in stocks:
                logger.warning("%s: 不在資料中，跳過", stock_id)
                continue

            fetch_result = self.fetch_institutional_data(stock_id, days=20)
            retry_count += fetch_result["retry_count"]
            if fetch_result["exhausted"]:
                exhausted_retries += 1
                failed_tickers.append(stock_id)

            stock_data = stocks[stock_id]
            if fetch_result["data"]:
                stock_data["institutional"] = fetch_result["data"]
                stock_data["institutional_source"] = "FinMind API (批次更新)"
                real_data_count += 1
            else:
                today = datetime.now()
                stock_data["institutional"] = [
                    {
                        "date": (today - timedelta(days=index)).strftime("%Y%m%d"),
                        "foreign_net": 1000 + index * 100,
                        "trust_net": 500 + index * 50,
                        "dealer_net": 200 + index * 20,
                        "source": "範例資料 (批次更新)",
                    }
                    for index in range(5)
                ]
                stock_data["institutional_source"] = "範例資料 (批次更新)"
                sample_data_count += 1

            stock_data["institutional_updated"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            updated_count += 1

        data["run_id"] = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        data["last_updated"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        data["update_type"] = f"批次更新 (偏移: {offset_day})"
        data["batch_update_stats"] = {
            "total_updated": updated_count,
            "real_data_count": real_data_count,
            "sample_data_count": sample_data_count,
            "retry_count": retry_count,
            "exhausted_retries": exhausted_retries,
            "failed_tickers": failed_tickers,
            "offset_day": offset_day,
            "timestamp": datetime.now().isoformat(),
        }

        summary = self.build_summary(
            data,
            updated_count=updated_count,
            real_data_count=real_data_count,
            sample_data_count=sample_data_count,
            retry_count=retry_count,
            exhausted_retries=exhausted_retries,
            failed_tickers=failed_tickers,
            offset_day=offset_day,
            refreshed_symbols=stock_ids,
        )

        try:
            publish_result = self.publish_bundle(data, summary)
        except Exception as exc:  # noqa: BLE001 - re-raise non publish_safety failures
            if not is_publish_safety_error(exc):
                raise
            logger.error("❌ publish bundle 失敗: %s", exc)
            return {"success": False, "error": str(exc)}

        logger.info("✅ 批次更新完成，更新股票: %s", updated_count)
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


def main() -> int:
    """主函數。"""
    parser = argparse.ArgumentParser(description="批次更新機構持股資料")
    parser.add_argument("--offset-day", type=int, default=0, help="偏移天數 (0=今天, 1=昨天, 2=前天)")
    parser.add_argument("--limit", type=int, default=1000, help="每批次更新股票數量 (預設: 1000)")
    parser.add_argument("--test", action="store_true", help="測試模式 (只處理前10支股票)")
    args = parser.parse_args()

    logger.info("🚀 開始批次更新機構持股資料")
    updater = BatchInstitutionalUpdater()
    updater.daily_limit = args.limit

    all_stock_ids = updater.load_stock_list()
    if not all_stock_ids:
        logger.error("❌ 無法載入股票列表")
        return 1

    start_idx, end_idx, _ = updater.calculate_batch_range(args.offset_day)
    batch_stock_ids = all_stock_ids[start_idx:end_idx]
    if args.test:
        batch_stock_ids = batch_stock_ids[:10]

    results = updater.update_batch(batch_stock_ids, args.offset_day)
    if not results.get("success"):
        logger.error("❌ 批次更新失敗: %s", results.get("error", "未知錯誤"))
        return 1

    logger.info("🎉 批次更新成功完成！")
    return 0


if __name__ == "__main__":
    sys.exit(main())
