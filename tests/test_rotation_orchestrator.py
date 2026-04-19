from importlib import import_module

from core_selection import CoreSelectionResult


def load_rotation_orchestrator_module():
    return import_module("rotation_orchestrator")


def build_selection(core_symbols: list[str]) -> CoreSelectionResult:
    return CoreSelectionResult(
        core_symbols=core_symbols,
        ranked_fill_symbols=[],
        target_size=len(core_symbols),
        bucket_symbols={},
        bucket_counts={},
    )


def test_build_rotation_groups_partitions_sorted_non_core_symbols_into_three_stable_groups():
    module = load_rotation_orchestrator_module()

    groups = module.build_rotation_groups(
        all_symbols=["2454", "1102", "2330", "1101", "2317", "0050", "1301"],
        core_set={"2330", "0050"},
    )

    assert groups == [
        ["1101", "1102"],
        ["1301", "2317"],
        ["2454"],
    ]


def test_build_daily_plan_recomputes_generation_when_core_membership_changes():
    module = load_rotation_orchestrator_module()
    all_symbols = ["2454", "1102", "2330", "1101", "2317", "0050", "1301"]
    initial_state = {
        "current_batch_index": 1,
        "rotation_generation": "",
        "retry_queue": [],
        "freshness": {},
        "in_progress": None,
        "last_completed_batch": None,
    }

    first_plan = module.build_daily_plan(
        all_symbols=all_symbols,
        selection=build_selection(["2330", "0050"]),
        state=initial_state,
    )
    second_plan = module.build_daily_plan(
        all_symbols=all_symbols,
        selection=build_selection(["2330", "0050", "1102"]),
        state=initial_state,
    )

    assert first_plan["rotation_generation"] != second_plan["rotation_generation"]
    assert first_plan["scheduled_batch"]["batch_index"] == 1
    assert first_plan["scheduled_batch"]["symbols"] == ["1301", "2317"]
    assert second_plan["scheduled_batch"]["symbols"] == ["2317"]


def test_build_daily_plan_keeps_frozen_in_progress_batch_for_resume():
    module = load_rotation_orchestrator_module()

    plan = module.build_daily_plan(
        all_symbols=["2454", "1102", "2330", "1101", "2317", "0050", "1301"],
        selection=build_selection(["2330", "0050", "1102"]),
        state={
            "current_batch_index": 2,
            "rotation_generation": "1101|1301|2317|2454",
            "retry_queue": [],
            "freshness": {},
            "in_progress": {
                "batch_index": 1,
                "rotation_generation": "1101|1102|1301|2317|2454",
                "symbols": ["1301", "2317"],
                "completed_symbols": ["1301"],
                "remaining_symbols": ["2317"],
            },
            "last_completed_batch": None,
        },
    )

    assert plan["rotation_generation"] == "1101|1102|1301|2317|2454"
    assert plan["scheduled_batch"] == {
        "batch_index": 1,
        "rotation_generation": "1101|1102|1301|2317|2454",
        "symbols": ["1301", "2317"],
        "completed_symbols": ["1301"],
        "remaining_symbols": ["2317"],
        "is_resume": True,
    }


def test_build_daily_plan_schedules_due_retries_before_fresh_rotation_work():
    module = load_rotation_orchestrator_module()

    plan = module.build_daily_plan(
        all_symbols=["2454", "1102", "2330", "1101", "2317", "0050", "1301"],
        selection=build_selection(["2330", "0050"]),
        state={
            "current_batch_index": 0,
            "rotation_generation": "",
            "retry_queue": [
                {
                    "symbol": "2454",
                    "provider": "requests",
                    "error": "timeout",
                    "attempt_count": 1,
                    "failed_at": "2026-04-19T00:00:00Z",
                    "due_at": "2026-04-19T00:05:00Z",
                    "batch_index": 2,
                    "rotation_generation": "older-generation",
                },
                {
                    "symbol": "1301",
                    "provider": "requests",
                    "error": "still cooling down",
                    "attempt_count": 2,
                    "failed_at": "2026-04-19T00:00:00Z",
                    "due_at": "2026-04-19T01:05:00Z",
                    "batch_index": 2,
                    "rotation_generation": "older-generation",
                },
            ],
            "freshness": {},
            "in_progress": None,
            "last_completed_batch": None,
        },
        daily_budget=3,
        as_of="2026-04-19T00:30:00Z",
    )

    assert plan["retry_symbols"] == ["2454"]
    assert plan["scheduled_batch"]["symbols"] == ["1101", "1102"]
    assert plan["worklist"] == ["2454", "1101", "1102"]


def test_write_in_progress_persists_frozen_batch_metadata(rotation_state_paths):
    module = load_rotation_orchestrator_module()

    state = module.load_state(path=str(rotation_state_paths["state"]))
    plan = module.build_daily_plan(
        all_symbols=["2454", "1102", "2330", "1101", "2317", "0050", "1301"],
        selection=build_selection(["2330", "0050"]),
        state=state,
    )

    persisted = module.write_in_progress(
        state,
        planned_batch=plan["scheduled_batch"],
        path=str(rotation_state_paths["state"]),
    )

    assert persisted["in_progress"] == {
        "batch_index": 0,
        "rotation_generation": "1101|1102|1301|2317|2454",
        "symbols": ["1101", "1102"],
        "completed_symbols": [],
        "remaining_symbols": ["1101", "1102"],
    }


def test_mark_symbol_completed_persists_freshness_across_resume(rotation_state_paths):
    module = load_rotation_orchestrator_module()

    state = module.load_state(path=str(rotation_state_paths["state"]))
    written = module.write_in_progress(
        state,
        planned_batch={
            "batch_index": 0,
            "rotation_generation": "1101|1102|1301|2317|2454",
            "symbols": ["1101", "1102"],
            "completed_symbols": [],
            "remaining_symbols": ["1101", "1102"],
            "is_resume": False,
        },
        path=str(rotation_state_paths["state"]),
    )

    completed = module.mark_symbol_completed(
        written,
        symbol="1101",
        attempted_at="2026-04-19T02:00:00Z",
        succeeded_at="2026-04-19T02:00:05Z",
        path=str(rotation_state_paths["state"]),
    )

    assert completed["freshness"]["1101"] == {
        "last_attempted_at": "2026-04-19T02:00:00Z",
        "last_succeeded_at": "2026-04-19T02:00:05Z",
        "last_batch_generation": "1101|1102|1301|2317|2454",
        "source": "rotation",
    }
    assert completed["in_progress"]["completed_symbols"] == ["1101"]
    assert completed["in_progress"]["remaining_symbols"] == ["1102"]
    assert module.load_state(path=str(rotation_state_paths["state"]))["freshness"]["1101"] == completed["freshness"]["1101"]


def test_finalize_success_advances_cursor_after_retry_queue_finalize(rotation_state_paths):
    module = load_rotation_orchestrator_module()

    state = module.load_state(path=str(rotation_state_paths["state"]))
    state["freshness"]["1102"] = {
        "last_attempted_at": "2026-04-18T01:00:00Z",
        "last_succeeded_at": "2026-04-18T01:00:05Z",
        "last_batch_generation": "older-generation",
        "source": "rotation",
    }
    state = module.write_in_progress(
        state,
        planned_batch={
            "batch_index": 0,
            "rotation_generation": "1101|1102|1301|2317|2454",
            "symbols": ["1101", "1102"],
            "completed_symbols": [],
            "remaining_symbols": ["1101", "1102"],
            "is_resume": False,
        },
        path=str(rotation_state_paths["state"]),
    )
    state = module.mark_symbol_completed(
        state,
        symbol="1101",
        attempted_at="2026-04-19T02:00:00Z",
        succeeded_at="2026-04-19T02:00:05Z",
        path=str(rotation_state_paths["state"]),
    )

    failed = module.finalize_failure(
        state,
        symbol="1102",
        provider="requests",
        error="timeout",
        failed_at="2026-04-19T02:00:10Z",
        due_at="2026-04-19T02:05:10Z",
        path=str(rotation_state_paths["state"]),
    )

    assert failed["current_batch_index"] == 0
    assert failed["retry_queue"] == [
        {
            "symbol": "1102",
            "provider": "requests",
            "error": "timeout",
            "attempt_count": 1,
            "failed_at": "2026-04-19T02:00:10Z",
            "due_at": "2026-04-19T02:05:10Z",
            "batch_index": 0,
            "rotation_generation": "1101|1102|1301|2317|2454",
        }
    ]
    assert failed["freshness"]["1102"] == {
        "last_attempted_at": "2026-04-18T01:00:00Z",
        "last_succeeded_at": "2026-04-18T01:00:05Z",
        "last_batch_generation": "older-generation",
        "source": "rotation",
    }

    finalized = module.finalize_success(
        failed,
        completed_at="2026-04-19T02:10:00Z",
        path=str(rotation_state_paths["state"]),
    )

    assert finalized["current_batch_index"] == 1
    assert finalized["in_progress"] is None
    assert finalized["last_completed_batch"] == {
        "batch_index": 0,
        "rotation_generation": "1101|1102|1301|2317|2454",
        "completed_at": "2026-04-19T02:10:00Z",
        "symbol_count": 2,
    }
