"""
Deterministic non-core rotation planning helpers.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Sequence

from core_selection import CoreSelectionResult
from orchestration_state import DEFAULT_STATE_PATH, enqueue_retry_failure, load_rotation_state, save_rotation_state
from provider_policies import DEFAULT_NON_CORE_DAILY_BUDGET
from publish_safety import PublishValidationError


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
    as_of: str | None = None,
) -> dict[str, Any]:
    """Build the current daily rotation plan, preserving any frozen in-progress batch."""
    if daily_budget <= 0:
        raise ValueError("daily_budget must be positive")

    in_progress = state.get("in_progress")
    if in_progress is not None:
        planned_batch = _require_planned_batch(in_progress, "in_progress")
        retry_symbols = _select_due_retry_symbols(
            retry_queue=state.get("retry_queue", []),
            as_of=as_of,
            retry_capacity=max(0, daily_budget - len(planned_batch["remaining_symbols"])),
            excluded_symbols=set(planned_batch["symbols"]),
        )
        worklist = retry_symbols + list(planned_batch["remaining_symbols"])
        return {
            "rotation_generation": planned_batch["rotation_generation"],
            "groups": build_rotation_groups(all_symbols=all_symbols, core_set=selection.core_set),
            "scheduled_batch": {**planned_batch, "is_resume": True},
            "retry_symbols": retry_symbols,
            "worklist": worklist,
            "daily_budget": daily_budget,
        }

    groups = build_rotation_groups(all_symbols=all_symbols, core_set=selection.core_set)
    batch_index = int(state.get("current_batch_index", 0)) % ROTATION_GROUP_COUNT
    generation = compute_rotation_generation(all_symbols=all_symbols, core_set=selection.core_set)
    scheduled_symbols = list(groups[batch_index])
    retry_symbols = _select_due_retry_symbols(
        retry_queue=state.get("retry_queue", []),
        as_of=as_of,
        retry_capacity=max(0, daily_budget - len(scheduled_symbols)),
        excluded_symbols=set(scheduled_symbols),
    )
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
        "retry_symbols": retry_symbols,
        "worklist": retry_symbols + scheduled_symbols,
        "daily_budget": daily_budget,
    }


def load_state(path: str = str(DEFAULT_STATE_PATH)) -> dict[str, Any]:
    """Load durable rotation state through the shared state helper seam."""
    return load_rotation_state(path=path)


def write_in_progress(
    state: dict[str, Any],
    *,
    planned_batch: dict[str, Any],
    path: str | None = str(DEFAULT_STATE_PATH),
) -> dict[str, Any]:
    """Persist the selected batch before any symbol processing starts."""
    next_state = _validated_state_copy(state)
    frozen_batch = _require_planned_batch(planned_batch, "planned_batch")
    next_state["rotation_generation"] = frozen_batch["rotation_generation"]
    next_state["in_progress"] = frozen_batch
    return _persist_state(next_state, path=path)


def mark_symbol_completed(
    state: dict[str, Any],
    *,
    symbol: str,
    attempted_at: str,
    succeeded_at: str,
    source: str = "rotation",
    path: str | None = str(DEFAULT_STATE_PATH),
) -> dict[str, Any]:
    """Persist successful symbol completion and advance remaining in-progress work."""
    next_state = _validated_state_copy(state)
    in_progress = _require_in_progress_state(next_state)
    validated_symbol = _require_symbol_in_batch(symbol, in_progress["symbols"])

    if validated_symbol not in in_progress["completed_symbols"]:
        in_progress["completed_symbols"].append(validated_symbol)
    in_progress["remaining_symbols"] = [
        remaining_symbol
        for remaining_symbol in in_progress["remaining_symbols"]
        if remaining_symbol != validated_symbol
    ]
    next_state["freshness"][validated_symbol] = {
        "last_attempted_at": _require_non_empty_string(attempted_at, "attempted_at"),
        "last_succeeded_at": _require_non_empty_string(succeeded_at, "succeeded_at"),
        "last_batch_generation": in_progress["rotation_generation"],
        "source": _require_non_empty_string(source, "source"),
    }
    return _persist_state(next_state, path=path)


def finalize_failure(
    state: dict[str, Any],
    *,
    symbol: str,
    provider: str,
    error: str,
    failed_at: str,
    due_at: str,
    path: str | None = str(DEFAULT_STATE_PATH),
) -> dict[str, Any]:
    """Queue a failed scheduled symbol without advancing the batch cursor."""
    next_state = _validated_state_copy(state)
    in_progress = _require_in_progress_state(next_state)
    validated_symbol = _require_symbol_in_batch(symbol, in_progress["symbols"])

    next_state = enqueue_retry_failure(
        next_state,
        path=None,
        symbol=validated_symbol,
        provider=provider,
        error=error,
        due_at=due_at,
        failed_at=failed_at,
        batch_index=in_progress["batch_index"],
        rotation_generation=in_progress["rotation_generation"],
    )
    next_in_progress = _require_in_progress_state(next_state)
    next_in_progress["remaining_symbols"] = [
        remaining_symbol
        for remaining_symbol in next_in_progress["remaining_symbols"]
        if remaining_symbol != validated_symbol
    ]
    return _persist_state(next_state, path=path)


def finalize_success(
    state: dict[str, Any],
    *,
    completed_at: str,
    path: str | None = str(DEFAULT_STATE_PATH),
) -> dict[str, Any]:
    """Finalize a finished scheduled batch and advance the cursor exactly once."""
    next_state = _validated_state_copy(state)
    in_progress = _require_in_progress_state(next_state)
    if in_progress["remaining_symbols"]:
        raise PublishValidationError("Cannot finalize success while in_progress.remaining_symbols is not empty")

    next_state["current_batch_index"] = (in_progress["batch_index"] + 1) % ROTATION_GROUP_COUNT
    next_state["rotation_generation"] = in_progress["rotation_generation"]
    next_state["last_completed_batch"] = {
        "batch_index": in_progress["batch_index"],
        "rotation_generation": in_progress["rotation_generation"],
        "completed_at": _require_non_empty_string(completed_at, "completed_at"),
        "symbol_count": len(in_progress["symbols"]),
    }
    next_state["in_progress"] = None
    return _persist_state(next_state, path=path)


def _sorted_non_core_symbols(*, all_symbols: Sequence[str], core_set: set[str]) -> list[str]:
    """Return the stable sorted non-core universe."""
    return sorted(str(symbol) for symbol in all_symbols if str(symbol) not in core_set)


def _select_due_retry_symbols(
    *,
    retry_queue: Sequence[dict[str, Any]],
    as_of: str | None,
    retry_capacity: int,
    excluded_symbols: set[str],
) -> list[str]:
    """Return due retry symbols up to the leftover capacity reserved for retries."""
    if retry_capacity <= 0:
        return []

    selected: list[str] = []
    seen = set(excluded_symbols)
    for entry in sorted(
        retry_queue,
        key=lambda item: (
            str(item.get("due_at", "")),
            str(item.get("failed_at", "")),
            str(item.get("symbol", "")),
        ),
    ):
        symbol = str(entry.get("symbol", ""))
        due_at = str(entry.get("due_at", ""))
        if not symbol or symbol in seen:
            continue
        if as_of is not None and due_at > as_of:
            continue
        seen.add(symbol)
        selected.append(symbol)
        if len(selected) >= retry_capacity:
            break
    return selected


def _validated_state_copy(state: dict[str, Any]) -> dict[str, Any]:
    """Return a deep-copied, schema-validated state payload."""
    return deepcopy(save_rotation_state(state, path=None))


def _persist_state(state: dict[str, Any], *, path: str | None) -> dict[str, Any]:
    """Persist a validated state when requested, otherwise return it directly."""
    if path is None:
        return save_rotation_state(state, path=None)
    return save_rotation_state(state, path=path)


def _require_in_progress_state(state: dict[str, Any]) -> dict[str, Any]:
    """Return the current in-progress batch or raise a blocking schema error."""
    in_progress = state.get("in_progress")
    if in_progress is None:
        raise PublishValidationError("Rotation state is missing in_progress data")
    state["in_progress"] = _require_planned_batch(in_progress, "in_progress")
    return state["in_progress"]


def _require_planned_batch(batch: dict[str, Any], field_name: str) -> dict[str, Any]:
    """Validate the frozen batch structure used across plan/finalization seams."""
    if not isinstance(batch, dict):
        raise PublishValidationError(f"{field_name} must be an object")

    required_keys = {
        "batch_index",
        "rotation_generation",
        "symbols",
        "completed_symbols",
        "remaining_symbols",
    }
    missing = sorted(required_keys.difference(batch))
    if missing:
        raise PublishValidationError(f"{field_name} is missing required keys: {missing}")

    return {
        "batch_index": _require_non_negative_int(batch.get("batch_index"), f"{field_name}.batch_index"),
        "rotation_generation": _require_non_empty_string(
            batch.get("rotation_generation"),
            f"{field_name}.rotation_generation",
        ),
        "symbols": _require_string_list(batch.get("symbols"), f"{field_name}.symbols"),
        "completed_symbols": _require_string_list(
            batch.get("completed_symbols"),
            f"{field_name}.completed_symbols",
        ),
        "remaining_symbols": _require_string_list(
            batch.get("remaining_symbols"),
            f"{field_name}.remaining_symbols",
        ),
    }


def _require_symbol_in_batch(symbol: str, symbols: Sequence[str]) -> str:
    """Validate that a symbol belongs to the frozen batch."""
    validated_symbol = _require_non_empty_string(symbol, "symbol")
    if validated_symbol not in symbols:
        raise PublishValidationError(f"symbol {validated_symbol!r} is not part of the frozen batch")
    return validated_symbol


def _require_non_empty_string(value: Any, field_name: str) -> str:
    """Return a non-empty string or raise a blocking validation error."""
    if not isinstance(value, str):
        raise PublishValidationError(f"{field_name} must be a string")
    if not value:
        raise PublishValidationError(f"{field_name} must not be empty")
    return value


def _require_non_negative_int(value: Any, field_name: str) -> int:
    """Return a non-negative integer or raise a blocking validation error."""
    if not isinstance(value, int) or isinstance(value, bool):
        raise PublishValidationError(f"{field_name} must be an integer")
    if value < 0:
        raise PublishValidationError(f"{field_name} must be >= 0")
    return value


def _require_string_list(value: Any, field_name: str) -> list[str]:
    """Return a validated list of non-empty strings."""
    if not isinstance(value, list):
        raise PublishValidationError(f"{field_name} must be a list")
    return [_require_non_empty_string(item, f"{field_name}[{index}]") for index, item in enumerate(value)]
