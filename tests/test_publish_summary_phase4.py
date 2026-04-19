from importlib import import_module
from types import SimpleNamespace

import pytest


def test_update_summary_previews_next_rotation_without_mutating_state(rotation_state_factory):
    module = import_module("publish_projection")

    state = rotation_state_factory(
        freshness={
            "2330": {
                "last_attempted_at": "2026-04-19T01:00:00Z",
                "last_succeeded_at": "2026-04-19T01:00:00Z",
                "last_batch_generation": "gen-1",
                "source": "core",
            },
            "2454": {
                "last_attempted_at": "2026-04-18T01:00:00Z",
                "last_succeeded_at": "2026-04-18T01:00:00Z",
                "last_batch_generation": "gen-1",
                "source": "rotation",
            },
        },
        current_batch_index=1,
        rotation_generation="gen-1",
    )
    selection = SimpleNamespace(core_set={"2330"})

    summary = module.build_update_summary_payload(
        run_id="run-phase4",
        generated_at="2026-04-19T12:00:00Z",
        output_data={"stocks": {"2330": {}, "2454": {}}},
        failure_details=[{"ticker": "1101", "message": "provider unavailable"}],
        refreshed_symbols=["2330", "2454"],
        all_symbols=["1101", "2330", "2454", "3008", "6805", "8069"],
        selection=selection,
        rotation_state=state,
        as_of="2026-04-19T12:00:00Z",
    )

    assert summary["schema_version"] == "1.0"
    assert summary["artifact_kind"] == "update_summary"
    assert summary["run_id"] == "run-phase4"
    assert summary["timestamp"] == "2026-04-19T12:00:00Z"
    assert summary["update_type"] == "canslim_export"
    assert summary["data_stats"] == {"total_stocks": 2, "updated_stocks": 2}
    assert summary["refreshed_symbols"] == ["2330", "2454"]
    assert summary["failed_symbols"] == ["1101"]
    assert summary["next_rotation"]["batch_index"] == 2
    assert summary["next_rotation"]["symbols"] == ["8069"]
    assert summary["freshness_counts"] == {"today": 1, "warning": 1, "stale": 0}
    assert state["current_batch_index"] == 1
