import pytest

from core_selection import (
    RankedCandidate,
    build_core_universe,
    load_core_selection_config,
    load_selector_inputs,
)


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
