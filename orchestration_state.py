"""
Durable file-backed rotation orchestration state helpers.
"""

from __future__ import annotations

import json
import os
import tempfile
import re
from copy import deepcopy
from pathlib import Path
from typing import Any, TypedDict

from publish_safety import PublishValidationError

STATE_SCHEMA_VERSION = "1.0"
DEFAULT_STATE_PATH = Path(".orchestration") / "rotation_state.json"

class RetryQueueEntry(TypedDict):
    symbol: str
    provider: str
    error: str
    attempt_count: int
    failed_at: str
    due_at: str
    batch_index: int
    rotation_generation: str

class RotationState(TypedDict):
    schema_version: str
    current_batch_index: int
    rotation_generation: str
    retry_queue: list[RetryQueueEntry]
    freshness: dict[str, dict[str, str]]
    in_progress: dict[str, Any] | None
    last_completed_batch: dict[str, Any] | None

def _clean_gsd_string(s: Any) -> str:
    """GSD Standard: Never trust external strings. Pure alphanumeric and separators only."""
    if not s: return ""
    # Remove HTML and bracket noise
    s = str(s).split('<br>')[0].split('(')[0]
    # Allow only specific safe characters: letters, numbers, pipe, dot, underscore, dash
    return re.sub(r'[^a-zA-Z0-9|._-]', '', s).strip()

def load_rotation_state(path: str | Path | None = DEFAULT_STATE_PATH) -> RotationState:
    """Load and validate the rotation state from a durable file."""
    if path is None or not os.path.exists(path):
        return _default_rotation_state()
    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        return _validate_rotation_state(data)
    except (json.JSONDecodeError, OSError, PublishValidationError) as exc:
        print(f"⚠️ Rotation state load failed ({exc}). Using default.")
        return _default_rotation_state()

def save_rotation_state(state: dict[str, Any], path: str | Path | None = DEFAULT_STATE_PATH) -> dict[str, Any]:
    """Save the rotation state with GSD-grade string sanitization."""
    if path is None:
        return _validate_rotation_state(deepcopy(state))

    # Pre-cleaning to prevent corruption
    cleaned = deepcopy(state)
    if "rotation_generation" in cleaned:
        cleaned["rotation_generation"] = _clean_gsd_string(cleaned["rotation_generation"])
    
    validated = _validate_rotation_state(cleaned)
    state_path = Path(path)
    state_path.parent.mkdir(parents=True, exist_ok=True)

    temp_fd, temp_path = tempfile.mkstemp(dir=str(state_path.parent), prefix=".tmp-")
    try:
        with os.fdopen(temp_fd, "w", encoding="utf-8") as handle:
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

def _validate_rotation_state(data: dict[str, Any]) -> RotationState:
    """Ensure a rotation state dict matches the expected schema and value constraints."""
    if not isinstance(data, dict):
        raise PublishValidationError("Rotation state must be a JSON object")
    
    schema_version = data.get("schema_version")
    if schema_version != STATE_SCHEMA_VERSION:
        raise PublishValidationError(f"Unsupported state schema version: {schema_version}")

    return {
        "schema_version": STATE_SCHEMA_VERSION,
        "current_batch_index": _require_non_negative_int(data.get("current_batch_index"), "current_batch_index"),
        "rotation_generation": _require_non_empty_string(data.get("rotation_generation"), "rotation_generation"),
        "retry_queue": _require_retry_queue(data.get("retry_queue"), "retry_queue"),
        "freshness": _require_dict(data.get("freshness"), "freshness"),
        "in_progress": data.get("in_progress"),
        "last_completed_batch": data.get("last_completed_batch"),
    }

def _require_non_negative_int(value: Any, field_name: str, minimum: int = 0) -> int:
    if not isinstance(value, int) or value < minimum:
        raise PublishValidationError(f"{field_name} must be an integer >= {minimum}")
    return value

def _require_non_empty_string(value: Any, field_name: str) -> str:
    # GSD: We clean it before validation
    val = _clean_gsd_string(value)
    if not isinstance(val, str) or not val:
        # Fallback instead of crashing if possible, or raise
        if field_name == "rotation_generation": return "initial"
        raise PublishValidationError(f"{field_name} must be a non-empty string")
    return val

def _require_dict(value: Any, field_name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise PublishValidationError(f"{field_name} must be a dictionary")
    return value

def _require_retry_queue(value: Any, field_name: str) -> list[RetryQueueEntry]:
    if not isinstance(value, list):
        raise PublishValidationError(f"{field_name} must be a list")
    validated = []
    for index, item in enumerate(value):
        if not isinstance(item, dict): continue
        validated.append(item)
    return validated

def _default_rotation_state() -> RotationState:
    return {
        "schema_version": STATE_SCHEMA_VERSION,
        "current_batch_index": 0,
        "rotation_generation": "initial",
        "retry_queue": [],
        "freshness": {},
        "in_progress": None,
        "last_completed_batch": None,
    }

def enqueue_retry_failure(
    state: RotationState | dict[str, Any] | None = None,
    *,
    path: str | Path | None = DEFAULT_STATE_PATH,
    symbol: str,
    provider: str,
    error: str,
    due_at: str,
    failed_at: str,
    batch_index: int,
    rotation_generation: str,
    attempt_count: int = 1,
) -> RotationState:
    state_to_update = load_rotation_state(path=path) if state is None else _validate_rotation_state(deepcopy(state))
    entry: RetryQueueEntry = {
        "symbol": symbol,
        "provider": provider,
        "error": str(error),
        "attempt_count": attempt_count,
        "failed_at": failed_at,
        "due_at": due_at,
        "batch_index": batch_index,
        "rotation_generation": rotation_generation,
    }
    state_to_update["retry_queue"].append(entry)
    if path is None:
        return _validate_rotation_state(state_to_update)
    return save_rotation_state(state_to_update, path=path)
