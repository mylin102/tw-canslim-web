"""
Deterministic non-core rotation planning helpers.
"""

from __future__ import annotations

from typing import Any, Sequence

from core_selection import CoreSelectionResult
from provider_policies import DEFAULT_NON_CORE_DAILY_BUDGET


ROTATION_GROUP_COUNT = 3


def build_rotation_groups(
    *,
    all_symbols: Sequence[str],
    core_set: set[str],
) -> list[list[str]]:
    """Partition the stable sorted non-core universe into three deterministic groups."""
    non_core_sorted = _sorted_non_core_symbols(all_symbols=all_symbols, core_set=core_set)
    base_size, remainder = divmod(len(non_core_sorted), ROTATION_GROUP_COUNT)

    groups: list[list[str]] = []
    start = 0
    for index in range(ROTATION_GROUP_COUNT):
        group_size = base_size + (1 if index < remainder else 0)
        end = start + group_size
        groups.append(non_core_sorted[start:end])
        start = end
    return groups


def compute_rotation_generation(
    *,
    all_symbols: Sequence[str],
    core_set: set[str],
) -> str:
    """Return a deterministic fingerprint for the current ordered non-core universe."""
    return "|".join(_sorted_non_core_symbols(all_symbols=all_symbols, core_set=core_set))


def build_daily_plan(
    *,
    all_symbols: Sequence[str],
    selection: CoreSelectionResult,
    state: dict[str, Any],
    daily_budget: int = DEFAULT_NON_CORE_DAILY_BUDGET,
) -> dict[str, Any]:
    """Build the current daily rotation plan, preserving any frozen in-progress batch."""
    if daily_budget <= 0:
        raise ValueError("daily_budget must be positive")

    in_progress = state.get("in_progress")
    if in_progress is not None:
        return {
            "rotation_generation": in_progress["rotation_generation"],
            "groups": build_rotation_groups(all_symbols=all_symbols, core_set=selection.core_set),
            "scheduled_batch": {
                "batch_index": in_progress["batch_index"],
                "rotation_generation": in_progress["rotation_generation"],
                "symbols": list(in_progress["symbols"]),
                "completed_symbols": list(in_progress["completed_symbols"]),
                "remaining_symbols": list(in_progress["remaining_symbols"]),
                "is_resume": True,
            },
            "retry_symbols": [],
            "daily_budget": daily_budget,
        }

    groups = build_rotation_groups(all_symbols=all_symbols, core_set=selection.core_set)
    batch_index = int(state.get("current_batch_index", 0)) % ROTATION_GROUP_COUNT
    generation = compute_rotation_generation(all_symbols=all_symbols, core_set=selection.core_set)
    scheduled_symbols = list(groups[batch_index])
    return {
        "rotation_generation": generation,
        "groups": groups,
        "scheduled_batch": {
            "batch_index": batch_index,
            "rotation_generation": generation,
            "symbols": scheduled_symbols,
            "completed_symbols": [],
            "remaining_symbols": scheduled_symbols,
            "is_resume": False,
        },
        "retry_symbols": [],
        "daily_budget": daily_budget,
    }


def _sorted_non_core_symbols(*, all_symbols: Sequence[str], core_set: set[str]) -> list[str]:
    """Return the stable sorted non-core universe."""
    return sorted(str(symbol) for symbol in all_symbols if str(symbol) not in core_set)
