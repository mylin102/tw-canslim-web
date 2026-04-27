"""
Shared publish safety helpers for docs artifact bundles.
"""

from __future__ import annotations

import gzip
import json
import logging
import os
import shutil
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import fcntl


DEFAULT_SCHEMA_VERSION = "1.0"

SUPPORTED_ARTIFACT_KINDS = {
    "data_base",
    "data",
    "data_light",
    "data_gz",
    "stock_index",
    "update_summary",
    "leaders",
}

REQUIRED_STOCK_PATHS = (
    "symbol",
    "name",
    "canslim.score",
    "canslim.mansfield_rs",
    "canslim.grid_strategy",
)

ARTIFACT_KIND_BY_NAME = {
    "data_base.json": "data_base",
    "data.json": "data",
    "data_light.json": "data_light",
    "data.json.gz": "data_gz",
    "stock_index.json": "stock_index",
    "update_summary.json": "update_summary",
    "leaders.json": "leaders",
}

STOCK_ARTIFACT_KINDS = {
    "data_base",
    "data",
    "data_light",
    "data_gz",
}


class PublishValidationError(Exception):
    """Raised when an artifact payload fails validation."""


class PublishTransactionError(Exception):
    """Raised when bundle promotion fails."""


class PublishRestoreError(Exception):
    """Raised when bundle restore fails."""


def is_publish_safety_error(exc: BaseException) -> bool:
    """Return whether an exception belongs to the publish_safety error family."""
    return exc.__class__.__module__ == __name__ and exc.__class__.__name__ in {
        "PublishValidationError",
        "PublishTransactionError",
        "PublishRestoreError",
    }


def load_artifact_json(path: str, *, artifact_kind: str, logger=None) -> dict:
    """Load and validate a published artifact."""
    target = Path(path)
    try:
        if artifact_kind == "data_gz":
            with gzip.open(target, "rt", encoding="utf-8") as handle:
                payload = json.load(handle)
        else:
            with target.open("r", encoding="utf-8") as handle:
                payload = json.load(handle)
    except OSError as exc:
        raise PublishValidationError(f"Unable to read artifact {target}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise PublishValidationError(f"Artifact {target} is not valid JSON: {exc}") from exc

    validate_artifact_payload(payload, artifact_kind=artifact_kind)
    _get_logger(logger).info("Validated artifact %s (%s)", target, artifact_kind)
    return payload


def validate_artifact_payload(
    payload: dict,
    *,
    artifact_kind: str,
    schema_version: str = DEFAULT_SCHEMA_VERSION,
) -> None:
    """Validate a payload before it is published live."""
    if artifact_kind not in SUPPORTED_ARTIFACT_KINDS:
        raise PublishValidationError(f"Unsupported artifact kind: {artifact_kind}")

    if not isinstance(payload, dict):
        raise PublishValidationError(f"{artifact_kind} payload must be a JSON object")

    if artifact_kind in STOCK_ARTIFACT_KINDS:
        _validate_stock_payload(payload, artifact_kind=artifact_kind, schema_version=schema_version)
        return

    if artifact_kind == "stock_index":
        _validate_stock_index_payload(payload, schema_version=schema_version)
        return

    if artifact_kind == "leaders":
        _validate_leaders_payload(payload)
        return

    _validate_summary_payload(payload)


def _validate_leaders_payload(payload: dict) -> None:
    """Validate external alpha leaders contract."""
    if payload.get("schema_version") != 1:
        raise PublishValidationError(f"leaders schema_version mismatch: expected 1, got {payload.get('schema_version')!r}")
    
    if not isinstance(payload.get("date"), str):
        raise PublishValidationError("leaders payload missing string field: date")
        
    universe = payload.get("universe")
    if not isinstance(universe, list):
        raise PublishValidationError("leaders payload universe must be a list")
        
    for entry in universe:
        if not isinstance(entry, dict):
            raise PublishValidationError("leaders universe entry must be an object")
        for key in ("symbol", "rs_rating", "composite_score", "tags"):
            if key not in entry:
                raise PublishValidationError(f"leaders universe entry missing required field: {key}")
        if not isinstance(entry["tags"], list):
            raise PublishValidationError(f"leaders universe entry {entry['symbol']} tags must be a list")


def validate_resume_stock_entry(
    stock_id: str,
    stock_entry: dict,
    *,
    schema_version: str = DEFAULT_SCHEMA_VERSION,
    required_paths: tuple[str, ...] = REQUIRED_STOCK_PATHS,
) -> bool:
    """GSD Hardening: Validate resume record. Return False if invalid to trigger re-fetch."""
    if not isinstance(stock_entry, dict):
        _get_logger(None).warning(f"Resume record {stock_id} must be an object. Skipping.")
        return False

    entry_schema = stock_entry.get("schema_version")
    if entry_schema != schema_version:
        _get_logger(None).debug(f"Resume record {stock_id} schema mismatch. Skipping.")
        return False

    for path in required_paths:
        value = _resolve_path(stock_entry, path)
        if value is None:
            _get_logger(None).debug(f"Resume record {stock_id} missing required field: {path}. Skipping.")
            return False
    return True


def publish_artifact_bundle(
    bundle: dict[str, dict],
    *,
    lock_path: str = "docs/.publish.lock",
    backup_dir: str = "backups/last_good",
    logger=None,
    json_default=None,
) -> dict:
    """Validate, publish, and snapshot a related artifact bundle under one lock."""
    if not bundle:
        raise PublishValidationError("Artifact bundle is empty")

    resolved_logger = _get_logger(logger)
    normalized = _normalize_bundle(bundle)

    lock_file = Path(lock_path)
    lock_file.parent.mkdir(parents=True, exist_ok=True)
    backup_root = Path(backup_dir)
    backup_root.mkdir(parents=True, exist_ok=True)

    with lock_file.open("a+", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        staged_files = []
        try:
            for artifact in normalized:
                staged_files.append(
                    _write_temp_artifact(
                        artifact["target"],
                        artifact["payload"],
                        artifact["artifact_kind"],
                        json_default=json_default,
                    )
                )

            for artifact, staged_path in zip(normalized, staged_files, strict=True):
                os.replace(staged_path, artifact["target"])

            snapshot_dir = _create_snapshot(normalized, backup_root)
            _prune_old_snapshots(backup_root, keep=snapshot_dir)
        except PublishValidationError:
            raise
        except Exception as exc:
            _cleanup_temp_files(staged_files)
            raise PublishTransactionError(f"Bundle publish failed: {exc}") from exc
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)

    run_id = _extract_bundle_run_id(normalized)
    resolved_logger.info("Published %s artifacts under %s", len(normalized), lock_file)
    return {
        "published_targets": [str(artifact["target"]) for artifact in normalized],
        "snapshot_dir": str(snapshot_dir),
        "manifest_path": str(snapshot_dir / "manifest.json"),
        "run_id": run_id,
    }


def restore_latest_bundle(
    *,
    lock_path: str = "docs/.publish.lock",
    backup_dir: str = "backups/last_good",
    logger=None,
    targets: tuple[str, ...] | None = None,
) -> dict:
    """Restore the latest validated bundle snapshot back into docs/."""
    resolved_logger = _get_logger(logger)
    lock_file = Path(lock_path)
    lock_file.parent.mkdir(parents=True, exist_ok=True)
    backup_root = Path(backup_dir)

    with lock_file.open("a+", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            snapshot_dir = _latest_snapshot_dir(backup_root)
            manifest_path = snapshot_dir / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            requested = {str(Path(target).resolve()) for target in targets} if targets else None

            artifacts = manifest["artifacts"]
            entries = [
                {
                    "target": target,
                    "artifact_kind": entry["artifact_kind"],
                    "backup_file": entry["backup_file"],
                }
                for target, entry in artifacts.items()
                if requested is None or str(Path(target).resolve()) in requested
            ]
            if requested and len(entries) != len(requested):
                present = {str(Path(entry["target"]).resolve()) for entry in entries}
                missing = sorted(requested.difference(present))
                raise PublishRestoreError(f"Snapshot missing requested targets: {missing}")

            staged_files = []
            destinations = []
            for entry in entries:
                target = Path(entry["target"])
                source = snapshot_dir / entry["backup_file"]
                if not source.exists():
                    raise PublishRestoreError(f"Snapshot file missing for {target}: {source}")
                staged_files.append(_copy_to_temp(source, target))
                destinations.append(target)

            for staged_path, target in zip(staged_files, destinations, strict=True):
                os.replace(staged_path, target)
        except PublishRestoreError:
            raise
        except Exception as exc:
            raise PublishRestoreError(f"Restore failed: {exc}") from exc
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)

    resolved_logger.info("Restored %s artifacts from %s", len(entries), snapshot_dir)
    return {
        "restored_targets": [entry["target"] for entry in entries],
        "manifest_path": str(manifest_path),
        "snapshot_dir": str(snapshot_dir),
        "run_id": manifest.get("run_id"),
    }


def _normalize_bundle(bundle: dict[str, dict]) -> list[dict[str, Any]]:
    normalized = []
    for raw_target, spec in bundle.items():
        if not isinstance(spec, dict):
            raise PublishValidationError(f"Artifact spec for {raw_target} must be an object")

        target = Path(raw_target)
        artifact_kind = spec.get("artifact_kind") or ARTIFACT_KIND_BY_NAME.get(target.name)
        if artifact_kind not in SUPPORTED_ARTIFACT_KINDS:
            raise PublishValidationError(f"Unsupported artifact kind for {target}: {artifact_kind}")

        payload = spec.get("payload", spec)
        validate_artifact_payload(payload, artifact_kind=artifact_kind)
        normalized.append(
            {
                "target": target,
                "artifact_kind": artifact_kind,
                "payload": payload,
            }
        )

    return normalized


def _validate_stock_payload(payload: dict, *, artifact_kind: str, schema_version: str) -> None:
    if payload.get("schema_version") != schema_version:
        raise PublishValidationError(
            f"{artifact_kind} schema mismatch: expected {schema_version}, got {payload.get('schema_version')!r}"
        )

    stocks = payload.get("stocks")
    if not isinstance(stocks, dict):
        raise PublishValidationError(f"{artifact_kind} payload requires a stocks object")

    if "last_updated" not in payload:
        raise PublishValidationError(f"{artifact_kind} payload missing last_updated")

    for stock_id, stock_entry in stocks.items():
        validate_resume_stock_entry(stock_id, stock_entry, schema_version=schema_version)


def _validate_stock_index_payload(payload: dict, *, schema_version: str) -> None:
    if payload.get("schema_version") != schema_version:
        raise PublishValidationError(
            f"stock_index schema mismatch: expected {schema_version}, got {payload.get('schema_version')!r}"
        )

    stocks = payload.get("stocks")
    if not isinstance(stocks, dict):
        raise PublishValidationError("stock_index payload requires a stocks object")

    if "last_updated" not in payload:
        raise PublishValidationError("stock_index payload missing last_updated")

    for stock_id, stock_entry in stocks.items():
        if not isinstance(stock_entry, dict):
            raise PublishValidationError(f"stock_index entry {stock_id} must be an object")
        if stock_entry.get("symbol") != stock_id:
            raise PublishValidationError(f"stock_index entry {stock_id} symbol mismatch")
        for key in ("name", "industry", "last_succeeded_at"):
            if not isinstance(stock_entry.get(key), str):
                raise PublishValidationError(f"stock_index entry {stock_id} missing string field: {key}")
        if not isinstance(stock_entry.get("in_snapshot"), bool):
            raise PublishValidationError(f"stock_index entry {stock_id} missing bool field: in_snapshot")

        freshness = stock_entry.get("freshness")
        if not isinstance(freshness, dict):
            raise PublishValidationError(f"stock_index entry {stock_id} freshness must be an object")
        days_old = freshness.get("days_old")
        if days_old is not None and (not isinstance(days_old, int) or isinstance(days_old, bool) or days_old < 0):
            raise PublishValidationError(f"stock_index entry {stock_id} freshness.days_old must be null or >= 0")
        for key in ("level", "label"):
            if not isinstance(freshness.get(key), str):
                raise PublishValidationError(f"stock_index entry {stock_id} freshness.{key} must be a string")


def _validate_summary_payload(payload: dict) -> None:
    required_keys = (
        "schema_version",
        "artifact_kind",
        "run_id",
        "timestamp",
        "update_type",
        "data_stats",
        "refreshed_symbols",
        "failed_symbols",
        "next_rotation",
        "freshness_counts",
    )
    for key in required_keys:
        if key not in payload:
            raise PublishValidationError(f"update_summary payload missing {key}")

    if payload.get("schema_version") != DEFAULT_SCHEMA_VERSION:
        raise PublishValidationError(
            f"update_summary schema mismatch: expected {DEFAULT_SCHEMA_VERSION}, got {payload.get('schema_version')!r}"
        )

    if payload.get("artifact_kind") != "update_summary":
        raise PublishValidationError(
            f"update_summary artifact_kind mismatch: expected 'update_summary', got {payload.get('artifact_kind')!r}"
        )

    if not isinstance(payload.get("run_id"), str) or not payload["run_id"]:
        raise PublishValidationError("update_summary run_id must be a non-empty string")

    data_stats = payload.get("data_stats")
    if not isinstance(data_stats, dict):
        raise PublishValidationError("update_summary data_stats must be an object")

    for key in ("total_stocks", "updated_stocks"):
        if key not in data_stats:
            raise PublishValidationError(f"update_summary data_stats missing {key}")

    for key in ("refreshed_symbols", "failed_symbols"):
        if not isinstance(payload.get(key), list):
            raise PublishValidationError(f"update_summary {key} must be a list")

    next_rotation = payload.get("next_rotation")
    if not isinstance(next_rotation, dict):
        raise PublishValidationError("update_summary next_rotation must be an object")
    for key in ("batch_index", "symbols"):
        if key not in next_rotation:
            raise PublishValidationError(f"update_summary next_rotation missing {key}")
    if not isinstance(next_rotation.get("symbols"), list):
        raise PublishValidationError("update_summary next_rotation.symbols must be a list")

    freshness_counts = payload.get("freshness_counts")
    if not isinstance(freshness_counts, dict):
        raise PublishValidationError("update_summary freshness_counts must be an object")
    for key in ("today", "warning", "stale"):
        value = freshness_counts.get(key)
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            raise PublishValidationError(f"update_summary freshness_counts.{key} must be an integer >= 0")


def _resolve_path(data: dict, path: str):
    current = data
    for part in path.split("."):
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current


def _serialize_payload(payload: dict, artifact_kind: str, *, json_default=None) -> bytes:
    dumped = json.dumps(
        payload,
        ensure_ascii=False,
        indent=2,
        default=json_default,
    ).encode("utf-8")
    if artifact_kind == "data_gz":
        return gzip.compress(dumped, compresslevel=9)
    return dumped + b"\n"


def _write_temp_artifact(target: Path, payload: dict, artifact_kind: str, *, json_default=None) -> str:
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_path = tempfile.mkstemp(
        prefix=f".{target.name}.",
        suffix=".tmp",
        dir=str(target.parent),
    )
    try:
        data = _serialize_payload(payload, artifact_kind, json_default=json_default)
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        return temp_path
    except Exception:
        os.close(fd)
        if os.path.exists(temp_path):
            os.unlink(temp_path)
        raise


def _create_snapshot(normalized: list[dict[str, Any]], backup_root: Path) -> Path:
    snapshot_dir = backup_root / datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    snapshot_dir.mkdir(parents=True, exist_ok=True)

    manifest = {
        "created_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "run_id": _extract_bundle_run_id(normalized),
        "artifacts": {},
    }

    for artifact in normalized:
        target = artifact["target"]
        backup_name = target.name
        backup_path = snapshot_dir / backup_name
        shutil.copy2(target, backup_path)
        manifest["artifacts"][str(target)] = {
                "artifact_kind": artifact["artifact_kind"],
                "backup_file": backup_name,
            }

    (snapshot_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return snapshot_dir


def _prune_old_snapshots(backup_root: Path, *, keep: Path) -> None:
    for path in backup_root.iterdir():
        if path == keep:
            continue
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink()


def _latest_snapshot_dir(backup_root: Path) -> Path:
    if not backup_root.exists():
        raise PublishRestoreError(f"Backup directory does not exist: {backup_root}")

    snapshots = sorted(
        path for path in backup_root.iterdir() if path.is_dir() and (path / "manifest.json").exists()
    )
    if not snapshots:
        raise PublishRestoreError(f"No manifest-backed snapshots found in {backup_root}")
    return snapshots[-1]


def _copy_to_temp(source: Path, target: Path) -> str:
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_path = tempfile.mkstemp(
        prefix=f".{target.name}.",
        suffix=".tmp",
        dir=str(target.parent),
    )
    try:
        with source.open("rb") as source_handle, os.fdopen(fd, "wb") as target_handle:
            shutil.copyfileobj(source_handle, target_handle)
            target_handle.flush()
            os.fsync(target_handle.fileno())
        return temp_path
    except Exception:
        os.close(fd)
        if os.path.exists(temp_path):
            os.unlink(temp_path)
        raise


def _cleanup_temp_files(paths: list[str]) -> None:
    for path in paths:
        if path and os.path.exists(path):
            os.unlink(path)


def _extract_bundle_run_id(normalized: list[dict[str, Any]]) -> str | None:
    run_ids = {
        artifact["payload"].get("run_id")
        for artifact in normalized
        if isinstance(artifact.get("payload"), dict) and artifact["payload"].get("run_id") is not None
    }
    if len(run_ids) == 1:
        return next(iter(run_ids))
    return None


def _get_logger(logger) -> logging.Logger:
    if logger is not None:
        return logger
    return logging.getLogger(__name__)
