from importlib import import_module

import pytest


def test_merge_snapshot_keeps_baseline_floor_and_prefers_refreshed_snapshot_records():
    module = import_module("publish_projection")

    payload = module.build_data_projection(
        run_id="run-phase4",
        generated_at="2026-04-19T12:00:00Z",
        snapshot_stocks={
            "2330": {
                "symbol": "2330",
                "name": "台積電",
                "industry": "",
                "canslim": {"score": 99, "mansfield_rs": 95.0, "grid_strategy": {"mode": "swing"}},
                "institutional": [],
            }
        },
        baseline_stocks={
            "2330": {
                "symbol": "2330",
                "name": "台積電",
                "industry": "Semiconductor",
                "canslim": {"score": 70, "mansfield_rs": 55.0, "grid_strategy": {"mode": "legacy"}},
                "institutional": [{"date": "20260415"}],
            },
            "1101": {
                "symbol": "1101",
                "name": "台泥",
                "industry": "Cement",
                "canslim": {"score": 61, "mansfield_rs": 22.0, "grid_strategy": {"mode": "baseline"}},
                "institutional": [],
            },
        },
        freshness_state={
            "freshness": {
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
            }
        },
        snapshot_symbols={"2330", "1101"},
        as_of="2026-04-19T12:00:00Z",
    )

    assert set(payload["stocks"]) == {"2330", "1101"}
    assert payload["stocks"]["2330"]["industry"] == "Semiconductor"
    assert payload["stocks"]["2330"]["canslim"]["score"] == 99
    assert payload["stocks"]["2330"]["canslim"]["mansfield_rs"] == 95.0
    assert payload["stocks"]["1101"]["canslim"]["score"] == 61
    assert payload["stocks"]["1101"]["freshness"]["label"] == "🔴 逾3天"
