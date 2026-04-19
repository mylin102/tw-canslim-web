from importlib import import_module

import pytest


@pytest.mark.xfail(reason="Phase 4 stock index projection is not implemented yet")
def test_stock_index_includes_non_snapshot_symbols(rotation_state_factory):
    module = import_module("publish_projection")

    payload = module.build_stock_index_payload(
        run_id="run-phase4",
        generated_at="2026-04-19T12:00:00Z",
        snapshot_stocks={
            "2330": {"symbol": "2330", "name": "台積電", "industry": "Semiconductor"},
        },
        baseline_stocks={
            "1101": {"symbol": "1101", "name": "台泥", "industry": "Cement"},
        },
        ticker_info={
            "2330": {"name": "台積電"},
            "1101": {"name": "台泥"},
            "2454": {"name": "聯發科"},
        },
        freshness_state=rotation_state_factory(
            freshness={
                "2330": {
                    "last_attempted_at": "2026-04-19T01:00:00Z",
                    "last_succeeded_at": "2026-04-19T01:00:00Z",
                    "last_batch_generation": "gen-1",
                    "source": "core",
                },
                "1101": {
                    "last_attempted_at": "2026-04-16T01:00:00Z",
                    "last_succeeded_at": "2026-04-16T01:00:00Z",
                    "last_batch_generation": "gen-1",
                    "source": "rotation",
                },
                "2454": {
                    "last_attempted_at": "2026-04-17T01:00:00Z",
                    "last_succeeded_at": "2026-04-17T01:00:00Z",
                    "last_batch_generation": "gen-1",
                    "source": "retry",
                },
            }
        ),
        as_of="2026-04-19T12:00:00Z",
    )

    assert set(payload["stocks"]) == {"2330", "1101", "2454"}
    assert payload["stocks"]["2330"]["in_snapshot"] is True
    assert payload["stocks"]["1101"]["in_snapshot"] is False
    assert payload["stocks"]["2454"]["freshness"]["label"] == "🟡 2天前"
    assert payload["stocks"]["1101"] == {
        "symbol": "1101",
        "name": "台泥",
        "industry": "Cement",
        "freshness": {
            "days_old": 3,
            "level": "stale",
            "label": "🔴 逾3天",
        },
        "last_succeeded_at": "2026-04-16T01:00:00Z",
        "in_snapshot": False,
    }
