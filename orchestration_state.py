"""
Durable file-backed rotation orchestration state helpers.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any, TypedDict

from publish_safety import PublishValidationError


STATE_SCHEMA_VERSION = "1.0"
DEFAULT_STATE_PATH = Path(".orchestration/rotation_state.json")


class RetryQueueEntry(TypedDict):
    symbol: str
    provider: str
    error: str
    attempt_count: int
    failed_at: str
    due_at: str
    batch_index: int
    rotation_generation: str


class FreshnessEntry(TypedDict):
    last_success_at: str
    source: str


class InProgressState(TypedDict):
    batch_index: int
    rotation_generation: str
    symbols: list[str]
    completed_symbols: list[str]
    remaining_symbols: list[str]


class CompletedBatchState(TypedDict):
    batch_index: int
    rotation_generation: str
    completed_at: str
    symbol_count: int


class RotationState(TypedDict):
    schema_version: str
    current_batch_index: int
    rotation_generation: str
    retry_queue: list[RetryQueueEntry]
    freshness: dict[str, FreshnessEntry]
    in_progress: InProgressState | None
    last_completed_batch: CompletedBatchState | None


def load_rotation_state(path: str | Path = DEFAULT_STATE_PATH) -> RotationState:
    """Load durable rotation state, seeding a default payload when absent."""
    state_path = Path(path)
    if not state_path.exists():
        state = _default_rotation_state()
        save_rotation_state(state, path=state_path)
        return state

    try:
        with state_path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except OSError as exc:
        raise PublishValidationError(f"Unable to read rotation state {state_path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise PublishValidationError(f"Rotation state {state_path} is not valid JSON: {exc}") from exc

    return _validate_rotation_state(payload)


def save_rotation_state(state: RotationState | dict[str, Any], path: str | Path = DEFAULT_STATE_PATH) -> RotationState:
    """Validate and atomically persist rotation state."""
    validated = _validate_rotation_state(state)
    state_path = Path(path)
    state_path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_path = tempfile.mkstemp(
        prefix=f".{state_path.name}.",
        suffix=".tmp",
        dir=str(state_path.parent),
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(validated, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, str(state_path))
    except Exception:
        if os.path.exists(temp_path):
            os.unlink(temp_path)
        raise
    return validated


def enqueue_retry_failure(
    *,
    path: str | Path = DEFAULT_STATE_PATH,
    symbol: str,
    provider: str,
    error: str,
    due_at: str,
    failed_at: str,
    batch_index: int,
    rotation_generation: str,
    attempt_count: int = 1,
) -> RotationState:
    """Append a retryable failure to durable state and persist it."""
    state = load_rotation_state(path=path)
    entry: RetryQueueEntry = {
        "symbol": _require_non_empty_string(symbol, "retry_queue.symbol"),
        "provider": _require_non_empty_string(provider, "retry_queue.provider"),
        "error": _require_non_empty_string(error, "retry_queue.error"),
        "attempt_count": _require_non_negative_int(attempt_count, "retry_queue.attempt_count", minimum=1),
        "failed_at": _require_non_empty_string(failed_at, "retry_queue.failed_at"),
        "due_at": _require_non_empty_string(due_at, "retry_queue.due_at"),
        "batch_index": _require_non_negative_int(batch_index, "retry_queue.batch_index"),
        "rotation_generation": _require_non_empty_string(
            rotation_generation,
            "retry_queue.rotation_generation",
        ),
    }
    state["retry_queue"].append(entry)
    return save_rotation_state(state, path=path)


def _default_rotation_state() -> RotationState:
    return {
        "schema_version": STATE_SCHEMA_VERSION,
        "current_batch_index": 0,
        "rotation_generation": "",
        "retry_queue": [],
        "freshness": {},
        "in_progress": None,
        "last_completed_batch": None,
    }


def _validate_rotation_state(payload: RotationState | dict[str, Any]) -> RotationState:
    if not isinstance(payload, dict):
        raise ValueError("rotation state payload must be an object")

    expected_keys = {
        "schema_version",
        "current_batch_index",
        "rotation_generation",
        "retry_queue",
        "freshness",
        "in_progress",
        "last_completed_batch",
    }
    payload_keys = set(payload)
    if payload_keys != expected_keys:
        missing = sorted(expected_keys.difference(payload_keys))
        extra = sorted(payload_keys.difference(expected_keys))
        detail = []
        if missing:
            detail.append(f"missing={missing}")
        if extra:
            detail.append(f"extra={extra}")
        raise PublishValidationError(f"Rotation state schema mismatch ({', '.join(detail)})")

    freshness = payload["freshness"]
    if not isinstance(freshness, dict):
        raise PublishValidationError("freshness must be an object")

    validated_freshness: dict[str, FreshnessEntry] = {}
    for symbol, entry in freshness.items():
        validated_freshness[_require_non_empty_string(symbol, "freshness key")] = _validate_freshness_entry(entry)

    return {
        "schema_version": _validate_schema_version(payload["schema_version"]),
        "current_batch_index": _require_non_negative_int(payload["current_batch_index"], "current_batch_index"),
        "rotation_generation": _require_string(payload["rotation_generation"], "rotation_generation"),
        "retry_queue": _validate_retry_queue(payload["retry_queue"]),
        "freshness": validated_freshness,
        "in_progress": _validate_in_progress(payload["in_progress"]),
        "last_completed_batch": _validate_last_completed_batch(payload["last_completed_batch"]),
    }


def _validate_schema_version(value: Any) -> str:
    schema_version = _require_non_empty_string(value, "schema_version")
    if schema_version != STATE_SCHEMA_VERSION:
        raise PublishValidationError(
            f"Rotation state schema mismatch: expected {STATE_SCHEMA_VERSION}, got {schema_version!r}"
        )
    return schema_version


def _validate_retry_queue(value: Any) -> list[RetryQueueEntry]:
    if not isinstance(value, list):
        raise PublishValidationError("retry_queue must be a list")

    validated: list[RetryQueueEntry] = []
    for index, entry in enumerate(value):
        if not isinstance(entry, dict):
            raise PublishValidationError(f"retry_queue[{index}] must be an object")
        validated.append(
            {
                "symbol": _require_non_empty_string(entry.get("symbol"), f"retry_queue[{index}].symbol"),
                "provider": _require_non_empty_string(entry.get("provider"), f"retry_queue[{index}].provider"),
                "error": _require_non_empty_string(entry.get("error"), f"retry_queue[{index}].error"),
                "attempt_count": _require_non_negative_int(
                    entry.get("attempt_count"),
                    f"retry_queue[{index}].attempt_count",
                    minimum=1,
                ),
                "failed_at": _require_non_empty_string(entry.get("failed_at"), f"retry_queue[{index}].failed_at"),
                "due_at": _require_non_empty_string(entry.get("due_at"), f"retry_queue[{index}].due_at"),
                "batch_index": _require_non_negative_int(
                    entry.get("batch_index"),
                    f"retry_queue[{index}].batch_index",
                ),
                "rotation_generation": _require_non_empty_string(
                    entry.get("rotation_generation"),
                    f"retry_queue[{index}].rotation_generation",
                ),
            }
        )
    return validated


def _validate_freshness_entry(value: Any) -> FreshnessEntry:
    if not isinstance(value, dict):
        raise PublishValidationError("freshness entries must be objects")
    return {
        "last_success_at": _require_non_empty_string(value.get("last_success_at"), "freshness.last_success_at"),
        "source": _require_non_empty_string(value.get("source"), "freshness.source"),
    }


def _validate_in_progress(value: Any) -> InProgressState | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        raise PublishValidationError("in_progress must be an object or null")
    return {
        "batch_index": _require_non_negative_int(value.get("batch_index"), "in_progress.batch_index"),
        "rotation_generation": _require_non_empty_string(
            value.get("rotation_generation"),
            "in_progress.rotation_generation",
        ),
        "symbols": _require_string_list(value.get("symbols"), "in_progress.symbols"),
        "completed_symbols": _require_string_list(
            value.get("completed_symbols"),
            "in_progress.completed_symbols",
        ),
        "remaining_symbols": _require_string_list(
            value.get("remaining_symbols"),
            "in_progress.remaining_symbols",
        ),
    }


def _validate_last_completed_batch(value: Any) -> CompletedBatchState | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        raise PublishValidationError("last_completed_batch must be an object or null")
    return {
        "batch_index": _require_non_negative_int(value.get("batch_index"), "last_completed_batch.batch_index"),
        "rotation_generation": _require_non_empty_string(
            value.get("rotation_generation"),
            "last_completed_batch.rotation_generation",
        ),
        "completed_at": _require_non_empty_string(value.get("completed_at"), "last_completed_batch.completed_at"),
        "symbol_count": _require_non_negative_int(value.get("symbol_count"), "last_completed_batch.symbol_count"),
    }


def _require_string(value: Any, field_name: str) -> str:
    if not isinstance(value, str):
        raise PublishValidationError(f"{field_name} must be a string")
    return value


def _require_non_empty_string(value: Any, field_name: str) -> str:
    string_value = _require_string(value, field_name)
    if not string_value:
        raise PublishValidationError(f"{field_name} must not be empty")
    return string_value


def _require_non_negative_int(value: Any, field_name: str, *, minimum: int = 0) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise PublishValidationError(f"{field_name} must be an integer")
    if value < minimum:
        raise PublishValidationError(f"{field_name} must be >= {minimum}")
    return value


def _require_string_list(value: Any, field_name: str) -> list[str]:
    if not isinstance(value, list):
        raise PublishValidationError(f"{field_name} must be a list")
    validated = []
    for index, item in enumerate(value):
        validated.append(_require_non_empty_string(item, f"{field_name}[{index}]"))
    return validated
