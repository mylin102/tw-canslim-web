from __future__ import annotations

import pandas as pd
import pytest

from core_selection import (
    RankedCandidate,
    build_core_universe,
    load_core_selection_config,
    load_selector_inputs,
)
from fuse_excel_data import fuse_data
from historical_generator import HistoricalGenerator


def test_fixed_buckets_dedupe_and_preserve_order(selector_config_factory):
    config_path, _ = selector_config_factory(
        {
            "base_symbols": ["1101", "2330"],
            "etf_symbols": ["0050", "2330"],
            "watchlist_symbols": ["8069", "1101"],
            "target_size": 8,
        }
    )
    config = load_core_selection_config(config_path)

    result = build_core_universe(
        all_symbols=["1101", "2330", "0050", "8069", "3565", "6770", "2303", "6805"],
        config=config,
        carryover_signal_symbols=["3565", "0050"],
        today_signal_symbols=["6770", "8069"],
        ranked_candidates=[
            RankedCandidate("2303", rs_metric=90, volume_metric=1_000_000, volume_rank=2),
            RankedCandidate("6805", rs_metric=80, volume_metric=900_000, volume_rank=3),
            RankedCandidate("2330", rs_metric=99, volume_metric=2_000_000, volume_rank=1),
        ],
    )

    assert result.fixed_symbols == ["1101", "2330", "0050", "8069", "3565", "6770"]
    assert result.core_symbols == ["1101", "2330", "0050", "8069", "3565", "6770", "2303", "6805"]


def test_signals_use_latest_fused_date_and_one_day_carryover(selector_artifact_factory):
    artifacts = selector_artifact_factory(
        fused_rows=[
            {"stock_id": "1101", "date": "2026-04-01", "score": 92, "latest_volume": 5000, "volume_rank": 5},
            {"stock_id": "2303", "date": "2026-04-02", "score": 82, "latest_volume": 7000, "volume_rank": 3},
            {"stock_id": "2330", "date": "2026-04-03", "score": 96, "latest_volume": 9000, "volume_rank": 1},
            {"stock_id": "2454", "date": "2026-04-03", "score": 74, "latest_volume": 8500, "volume_rank": 2},
        ],
        baseline_rs={"1101": 40, "2303": 65, "2330": 95, "2454": 88},
    )

    inputs = load_selector_inputs(
        artifacts["fused_path"],
        artifacts["master_path"],
        artifacts["baseline_path"],
    )

    assert inputs["today_signal_symbols"] == ["2330"]
    assert inputs["carryover_signal_symbols"] == ["2303"]
    assert inputs["previous_fused_date"].strftime("%Y-%m-%d") == "2026-04-02"


def test_ranking_prefers_rs_then_volume_rank_and_caps_fill(selector_config_factory):
    config_path, _ = selector_config_factory(
        {
            "base_symbols": ["1101"],
            "etf_symbols": ["0050"],
            "watchlist_symbols": [],
            "target_size": 5,
        }
    )
    config = load_core_selection_config(config_path)

    result = build_core_universe(
        all_symbols=["1101", "0050", "2303", "2454", "2603", "3008"],
        config=config,
        ranked_candidates=[
            RankedCandidate("2603", rs_metric=70, volume_metric=3_000_000, volume_rank=1),
            RankedCandidate("2454", rs_metric=90, volume_metric=2_000_000, volume_rank=4),
            RankedCandidate("2303", rs_metric=90, volume_metric=1_500_000, volume_rank=2),
            RankedCandidate("3008", rs_metric=88, volume_metric=4_000_000, volume_rank=1),
        ],
    )

    assert result.core_symbols == ["1101", "0050", "2303", "2454", "3008"]
    assert result.ranked_fill_symbols == ["2303", "2454", "3008"]


def test_stale_fused_requires_volume_fields_and_newer_or_equal_master(selector_artifact_factory):
    artifacts = selector_artifact_factory(
        fused_rows=[
            {"stock_id": "2330", "date": "2026-04-02", "score": 96, "latest_volume": 9000},
        ],
        master_rows=[
            {"stock_id": "2330", "date": "2026-04-03", "score": 96, "latest_volume": 9000},
        ],
        baseline_rs={"2330": 95},
    )

    with pytest.raises(ValueError, match="required columns|stale"):
        load_selector_inputs(
            artifacts["fused_path"],
            artifacts["master_path"],
            artifacts["baseline_path"],
        )


def test_process_ticker_includes_latest_volume_from_trading_volume(monkeypatch):
    generator = object.__new__(HistoricalGenerator)

    price_rows = pd.DataFrame(
        [
            {
                "stock_id": "2330",
                "date": "2026-04-01",
                "close": 100,
                "max": 100,
                "Trading_Volume": 1100,
            },
            {
                "stock_id": "2330",
                "date": "2026-04-02",
                "close": 101,
                "max": 101,
                "Trading_Volume": 2200,
            },
        ]
    )

    monkeypatch.setattr(
        generator,
        "fetch_raw_data",
        lambda stock_id, start_date, end_date: (pd.DataFrame(), pd.DataFrame(), price_rows.copy()),
    )

    result = generator.process_ticker("2330", "2026-04-01", "2026-04-02")

    assert "latest_volume" in result.columns
    assert result["latest_volume"].tolist() == [1100, 2200]


def test_run_full_market_persists_volume_rank(tmp_path, monkeypatch):
    generator = object.__new__(HistoricalGenerator)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("historical_generator.get_all_tw_tickers", lambda: {"2330": ".TW", "2303": ".TW"})
    monkeypatch.setattr(
        generator,
        "process_ticker",
        lambda stock_id, start_date, end_date: pd.DataFrame(
            [
                {
                    "stock_id": stock_id,
                    "date": pd.Timestamp("2026-04-03"),
                    "close": 100,
                    "one_year_return": 0.1 if stock_id == "2330" else 0.2,
                    "latest_volume": 9_000 if stock_id == "2330" else 7_000,
                    "C": True,
                    "I": True,
                    "N": True,
                    "S": True,
                    "A": True,
                }
            ]
        ),
    )

    generator.run_full_market("2026-04-01", "2026-04-03")

    master_df = pd.read_parquet(tmp_path / "master_canslim_signals.parquet").sort_values("stock_id")
    assert "volume_rank" in master_df.columns
    assert master_df.set_index("stock_id")["volume_rank"].to_dict() == {"2303": 2, "2330": 1}


def test_fuse_data_copies_volume_fields_into_fused_artifact(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    pd.DataFrame(
        [
            {
                "stock_id": "2330",
                "date": "2026-04-03",
                "score": 96,
                "latest_volume": 9000,
                "volume_rank": 1,
            }
        ]
    ).to_parquet(tmp_path / "master_canslim_signals.parquet", index=False)

    class FakeExcelProcessor:
        def __init__(self, root: str):
            self.root = root

        def load_health_check_data(self):
            return {
                "2330": {
                    "rs_rating": 95,
                    "composite_rating": 99,
                    "smr_rating": "A",
                }
            }

        def load_fund_holdings_data(self):
            return {"2330": {"change": 2}}

    monkeypatch.setattr("fuse_excel_data.ExcelDataProcessor", FakeExcelProcessor)

    fuse_data()

    fused_df = pd.read_parquet(tmp_path / "master_canslim_signals_fused.parquet")
    assert fused_df.loc[0, "latest_volume"] == 9000
    assert fused_df.loc[0, "volume_rank"] == 1


def test_load_selector_inputs_uses_persisted_volume_columns(selector_artifact_factory):
    artifacts = selector_artifact_factory(
        fused_rows=[
            {"stock_id": "2330", "date": "2026-04-03", "score": 96, "latest_volume": 9000, "volume_rank": 2},
            {"stock_id": "2454", "date": "2026-04-03", "score": 91, "latest_volume": 9500, "volume_rank": 1},
        ],
        baseline_rs={"2330": 95, "2454": 90},
    )

    inputs = load_selector_inputs(
        artifacts["fused_path"],
        artifacts["master_path"],
        artifacts["baseline_path"],
    )

    assert [candidate.symbol for candidate in inputs["ranked_candidates"]] == ["2330", "2454"]
    assert [candidate.volume_rank for candidate in inputs["ranked_candidates"]] == [2, 1]
