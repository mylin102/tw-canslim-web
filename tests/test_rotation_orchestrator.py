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


def test_build_daily_plan_recomputes_future_groups_when_core_membership_changes():
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
