"""
Projection helpers for freshness-aware publish artifacts.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
from typing import Any

from rotation_orchestrator import ROTATION_GROUP_COUNT, build_daily_plan


SCHEMA_VERSION = "1.0"
UNKNOWN_FRESHNESS = {
    "days_old": None,
    "level": "unknown",
    "label": "⚪ 未更新",
}


def classify_freshness(*, last_succeeded_at: str | None, as_of: str | None = None) -> dict[str, Any]:
    """Classify per-symbol freshness from the last successful update timestamp."""
    if not last_succeeded_at:
        return dict(UNKNOWN_FRESHNESS)

    succeeded_at = _parse_timestamp(last_succeeded_at)
    compared_at = _parse_timestamp(as_of) if as_of else datetime.now(UTC)
    days_old = max((compared_at.date() - succeeded_at.date()).days, 0)

    if days_old <= 0:
        return {"days_old": 0, "level": "today", "label": "🟢 今日"}
    if days_old <= 2:
        return {"days_old": days_old, "level": "warning", "label": f"🟡 {days_old}天前"}
    return {"days_old": days_old, "level": "stale", "label": "🔴 逾3天"}


def build_data_projection(
    *,
    run_id: str,
    generated_at: str,
    snapshot_stocks: dict[str, dict],
    baseline_stocks: dict[str, dict],
    freshness_state: dict[str, Any],
    snapshot_symbols: set[str] | list[str] | tuple[str, ...] | None = None,
    as_of: str | None = None,
    last_updated: str | None = None,
    industry_strength: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build the merged data.json payload with baseline coverage as the floor."""
    symbols = _ordered_symbols(snapshot_symbols or set(baseline_stocks) | set(snapshot_stocks))
    freshness_by_symbol = dict(freshness_state.get("freshness", {}))

    payload = {
        "schema_version": SCHEMA_VERSION,
        "artifact_kind": "data",
        "run_id": run_id,
        "generated_at": generated_at,
        "last_updated": last_updated or generated_at,
        "stocks": {},
    }
    if industry_strength is not None:
        payload["industry_strength"] = deepcopy(industry_strength)

    for symbol in symbols:
        base_entry = deepcopy(baseline_stocks.get(symbol, {}))
        snapshot_entry = deepcopy(snapshot_stocks.get(symbol, {}))
        if not base_entry and not snapshot_entry:
            continue

        merged_entry = _merge_stock_entry(base_entry, snapshot_entry)
        merged_entry["schema_version"] = merged_entry.get("schema_version", SCHEMA_VERSION)
        merged_entry["symbol"] = merged_entry.get("symbol", symbol)
        merged_entry["name"] = merged_entry.get("name", symbol)
        merged_entry["industry"] = merged_entry.get("industry", "")

        last_succeeded_at = _effective_last_succeeded_at(
            symbol=symbol,
            freshness_by_symbol=freshness_by_symbol,
            snapshot_entry=snapshot_entry,
            baseline_entry=base_entry,
        )
        merged_entry["freshness"] = classify_freshness(last_succeeded_at=last_succeeded_at, as_of=as_of)
        merged_entry["last_succeeded_at"] = last_succeeded_at
        payload["stocks"][symbol] = merged_entry

    return payload


def build_stock_index_payload(
    *,
    run_id: str,
    generated_at: str,
    snapshot_stocks: dict[str, dict],
    baseline_stocks: dict[str, dict],
    ticker_info: dict[str, dict],
    freshness_state: dict[str, Any],
    as_of: str | None = None,
    last_updated: str | None = None,
) -> dict[str, Any]:
    """Build the full-universe stock_index.json payload."""
    symbols = _ordered_symbols(set(ticker_info) | set(baseline_stocks) | set(snapshot_stocks) | set(freshness_state.get("freshness", {})))
    freshness_by_symbol = dict(freshness_state.get("freshness", {}))

    payload = {
        "schema_version": SCHEMA_VERSION,
        "artifact_kind": "stock_index",
        "run_id": run_id,
        "generated_at": generated_at,
        "last_updated": last_updated or generated_at,
        "stocks": {},
    }

    for symbol in symbols:
        snapshot_entry = snapshot_stocks.get(symbol, {})
        baseline_entry = baseline_stocks.get(symbol, {})
        ticker_entry = ticker_info.get(symbol, {})
        last_succeeded_at = _effective_last_succeeded_at(
            symbol=symbol,
            freshness_by_symbol=freshness_by_symbol,
            snapshot_entry=snapshot_entry,
            baseline_entry=baseline_entry,
        )

        payload["stocks"][symbol] = {
            "symbol": symbol,
            "name": (
                snapshot_entry.get("name")
                or baseline_entry.get("name")
                or ticker_entry.get("name")
                or symbol
            ),
            "industry": snapshot_entry.get("industry") or baseline_entry.get("industry") or "",
            "freshness": classify_freshness(last_succeeded_at=last_succeeded_at, as_of=as_of),
            "last_succeeded_at": last_succeeded_at,
            "in_snapshot": symbol in snapshot_stocks,
        }

    return payload


def build_update_summary_payload(
    *,
    run_id: str,
    generated_at: str,
    output_data: dict[str, Any],
    failure_details: list[dict[str, Any]],
    refreshed_symbols: list[str],
    all_symbols: list[str],
    selection: Any,
    rotation_state: dict[str, Any],
    as_of: str | None = None,
    failure_stats: dict[str, Any] | None = None,
    scheduled_batch: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the operator-facing update summary without mutating live rotation state."""
    stats = dict(failure_stats or {})
    failed_symbols = _dedupe_preserving_order(
        str(detail.get("ticker"))
        for detail in failure_details
        if detail.get("ticker")
    )

    payload = {
        "schema_version": SCHEMA_VERSION,
        "artifact_kind": "update_summary",
        "run_id": run_id,
        "generated_at": generated_at,
        "status": "failed" if failed_symbols or stats.get("retry_failures", 0) else "success",
        "stats": {
            "retry_attempts": stats.get("retry_attempts", 0),
            "retry_failures": stats.get("retry_failures", 0),
            "resume_rejected": stats.get("resume_rejected", 0),
            "stock_failures": stats.get("stock_failures", 0),
            "provider_wait_seconds": stats.get("provider_wait_seconds", 0.0),
        },
        "timestamp": generated_at,
        "update_type": "canslim_export",
        "description": "Primary CANSLIM export publish summary",
        "api_status": {
            "retry_failures": stats.get("retry_failures", 0),
            "provider_wait_seconds": stats.get("provider_wait_seconds", 0.0),
        },
        "data_stats": {
            "total_stocks": len(output_data.get("stocks", {})),
            "updated_stocks": len(output_data.get("stocks", {})),
        },
        "failures": list(failure_details),
        "refreshed_symbols": list(refreshed_symbols),
        "failed_symbols": failed_symbols,
        "next_rotation": _preview_next_rotation(
            all_symbols=all_symbols,
            selection=selection,
            rotation_state=rotation_state,
            as_of=as_of,
            scheduled_batch=scheduled_batch,
        ),
        "freshness_counts": _count_freshness_levels(
            symbols=output_data.get("stocks", {}).keys(),
            freshness_state=rotation_state,
            as_of=as_of,
        ),
    }
    return payload


def build_publish_projection_bundle(
    *,
    output_data: dict[str, Any],
    baseline_payload: dict[str, Any],
    ticker_info: dict[str, dict],
    freshness_state: dict[str, Any],
    failure_details: list[dict[str, Any]],
    failure_stats: dict[str, Any],
    refreshed_symbols: list[str],
    all_symbols: list[str],
    selection: Any,
    scheduled_batch: dict[str, Any] | None = None,
    as_of: str | None = None,
) -> dict[str, dict[str, Any]]:
    """Build all Phase 4 publish artifacts from one consistent projection snapshot."""
    run_id = str(output_data.get("run_id", ""))
    generated_at = str(output_data.get("generated_at", "")) or datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    last_updated = str(output_data.get("last_updated", "")) or generated_at
    baseline_stocks = dict(baseline_payload.get("stocks", {}))
    snapshot_stocks = dict(output_data.get("stocks", {}))
    snapshot_symbols = set(baseline_stocks) | set(snapshot_stocks)

    data_payload = build_data_projection(
        run_id=run_id,
        generated_at=generated_at,
        snapshot_stocks=snapshot_stocks,
        baseline_stocks=baseline_stocks,
        freshness_state=freshness_state,
        snapshot_symbols=snapshot_symbols,
        as_of=as_of,
        last_updated=last_updated,
        industry_strength=output_data.get("industry_strength"),
    )
    stock_index_payload = build_stock_index_payload(
        run_id=run_id,
        generated_at=generated_at,
        snapshot_stocks=data_payload["stocks"],
        baseline_stocks=baseline_stocks,
        ticker_info=ticker_info,
        freshness_state=freshness_state,
        as_of=as_of,
        last_updated=last_updated,
    )
    summary_payload = build_update_summary_payload(
        run_id=run_id,
        generated_at=generated_at,
        output_data=data_payload,
        failure_details=failure_details,
        refreshed_symbols=refreshed_symbols,
        all_symbols=all_symbols,
        selection=selection,
        rotation_state=freshness_state,
        as_of=as_of,
        failure_stats=failure_stats,
        scheduled_batch=scheduled_batch,
    )
    return {
        "data": data_payload,
        "stock_index": stock_index_payload,
        "update_summary": summary_payload,
    }


def _count_freshness_levels(*, symbols, freshness_state: dict[str, Any], as_of: str | None) -> dict[str, int]:
    counts = {"today": 0, "warning": 0, "stale": 0}
    freshness_by_symbol = dict(freshness_state.get("freshness", {}))
    for symbol in symbols:
        freshness = classify_freshness(
            last_succeeded_at=str(freshness_by_symbol.get(symbol, {}).get("last_succeeded_at", "")),
            as_of=as_of,
        )
        level = freshness.get("level")
        if level in counts:
            counts[level] += 1
    return counts


def _preview_next_rotation(
    *,
    all_symbols: list[str],
    selection: Any,
    rotation_state: dict[str, Any],
    as_of: str | None,
    scheduled_batch: dict[str, Any] | None,
) -> dict[str, Any]:
    preview_state = deepcopy(rotation_state)
    batch_index = _current_batch_index(rotation_state=rotation_state, scheduled_batch=scheduled_batch)
    preview_state["current_batch_index"] = (batch_index + 1) % ROTATION_GROUP_COUNT
    preview_state["in_progress"] = None

    plan = build_daily_plan(
        all_symbols=all_symbols,
        selection=selection,
        state=preview_state,
        as_of=as_of,
    )
    return {
        "batch_index": plan["scheduled_batch"]["batch_index"],
        "symbols": list(plan["scheduled_batch"]["symbols"]),
        "retry_symbols": list(plan["retry_symbols"]),
    }


def _current_batch_index(*, rotation_state: dict[str, Any], scheduled_batch: dict[str, Any] | None) -> int:
    if scheduled_batch is not None:
        return int(scheduled_batch.get("batch_index", 0))
    in_progress = rotation_state.get("in_progress")
    if isinstance(in_progress, dict) and "batch_index" in in_progress:
        return int(in_progress.get("batch_index", 0))
    return int(rotation_state.get("current_batch_index", 0))


def _ordered_symbols(symbols: set[str] | list[str] | tuple[str, ...]) -> list[str]:
    if isinstance(symbols, (list, tuple)):
        return [str(symbol) for symbol in symbols]
    return sorted(str(symbol) for symbol in symbols)


def _merge_stock_entry(base_entry: dict[str, Any], overlay_entry: dict[str, Any]) -> dict[str, Any]:
    if not base_entry:
        return overlay_entry
    if not overlay_entry:
        return base_entry
    return _deep_merge(base_entry, overlay_entry)


def _deep_merge(base_value: Any, overlay_value: Any) -> Any:
    if isinstance(base_value, dict) and isinstance(overlay_value, dict):
        merged = deepcopy(base_value)
        for key, value in overlay_value.items():
            if key in merged:
                merged[key] = _deep_merge(merged[key], value)
            else:
                merged[key] = deepcopy(value)
        return merged

    if overlay_value in (None, ""):
        return deepcopy(base_value)
    return deepcopy(overlay_value)


def _effective_last_succeeded_at(
    *,
    symbol: str,
    freshness_by_symbol: dict[str, Any],
    snapshot_entry: dict[str, Any],
    baseline_entry: dict[str, Any],
) -> str:
    state_entry = dict(freshness_by_symbol.get(symbol, {}))
    candidate = str(state_entry.get("last_succeeded_at", "")).strip()
    if candidate:
        return candidate

    for entry in (snapshot_entry, baseline_entry):
        candidate = str(entry.get("last_succeeded_at", "")).strip()
        if candidate:
            return candidate
    return ""


def _dedupe_preserving_order(values) -> list[str]:
    seen = set()
    ordered = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        ordered.append(value)
    return ordered


def _parse_timestamp(value: str) -> datetime:
    normalized = str(value).strip()
    if not normalized:
        raise ValueError("timestamp must not be empty")

    try:
        parsed = datetime.fromisoformat(normalized.replace("Z", "+00:00"))
    except ValueError:
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
            try:
                parsed = datetime.strptime(normalized, fmt)
                break
            except ValueError:
                continue
        else:
            raise

    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)
