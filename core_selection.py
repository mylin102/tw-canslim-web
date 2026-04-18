"""
Core selection contracts and artifact-backed selector helpers.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Sequence

import pandas as pd

logger = logging.getLogger(__name__)

SIGNAL_SCORE_THRESHOLD = 75
REQUIRED_CONFIG_KEYS = {
    "base_symbols",
    "etf_symbols",
    "watchlist_symbols",
    "target_size",
}
REQUIRED_FUSED_COLUMNS = {
    "stock_id",
    "date",
    "score",
    "latest_volume",
    "volume_rank",
}
REQUIRED_MASTER_COLUMNS = {"stock_id", "date"}


@dataclass(frozen=True)
class CoreSelectionConfig:
    """Checked-in fixed bucket configuration."""

    base_symbols: list[str]
    etf_symbols: list[str]
    watchlist_symbols: list[str]
    target_size: int


@dataclass(frozen=True)
class RankedCandidate:
    """Rankable candidate for the remaining selector slots."""

    symbol: str
    rs_metric: float = 0.0
    volume_metric: float = 0.0
    volume_rank: int | None = None


@dataclass(frozen=True)
class CoreSelectionResult:
    """Ordered selector output for downstream export wiring."""

    core_symbols: list[str]
    fixed_symbols: list[str]
    carryover_signal_symbols: list[str]
    today_signal_symbols: list[str]
    ranked_fill_symbols: list[str]
    target_size: int
    overflow_symbols: list[str] = field(default_factory=list)
    debug_counts: dict[str, int] = field(default_factory=dict)

    @property
    def core_set(self) -> set[str]:
        """Convenience set for scan-list construction."""
        return set(self.core_symbols)


def load_core_selection_config(config_path: str | Path = "core_selection_config.json") -> CoreSelectionConfig:
    """Load and validate the checked-in core selection configuration."""
    config_file = Path(config_path)
    with config_file.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)

    if set(payload.keys()) != REQUIRED_CONFIG_KEYS:
        raise ValueError(
            f"Config keys must exactly match {sorted(REQUIRED_CONFIG_KEYS)}; got {sorted(payload.keys())}"
        )

    target_size = payload["target_size"]
    if not isinstance(target_size, int) or target_size <= 0:
        raise ValueError("target_size must be a positive integer")

    return CoreSelectionConfig(
        base_symbols=_validate_symbol_bucket("base_symbols", payload["base_symbols"]),
        etf_symbols=_validate_symbol_bucket("etf_symbols", payload["etf_symbols"]),
        watchlist_symbols=_validate_symbol_bucket("watchlist_symbols", payload["watchlist_symbols"]),
        target_size=target_size,
    )


def load_selector_inputs(
    fused_path: str | Path,
    master_path: str | Path,
    baseline_path: str | Path,
    signal_score_threshold: int = SIGNAL_SCORE_THRESHOLD,
) -> dict[str, Any]:
    """Load selector inputs and derive signal/candidate buckets from persisted artifacts."""
    fused_df = pd.read_parquet(fused_path).copy()
    master_df = pd.read_parquet(master_path).copy()

    _require_columns("fused parquet", fused_df, REQUIRED_FUSED_COLUMNS)
    _require_columns("master parquet", master_df, REQUIRED_MASTER_COLUMNS)

    fused_df["stock_id"] = fused_df["stock_id"].astype(str)
    master_df["stock_id"] = master_df["stock_id"].astype(str)
    fused_df["date"] = pd.to_datetime(fused_df["date"]).dt.normalize()
    master_df["date"] = pd.to_datetime(master_df["date"]).dt.normalize()

    if fused_df.empty or master_df.empty:
        raise ValueError("Selector inputs require non-empty fused and master parquet files")

    latest_fused_date = fused_df["date"].max()
    latest_master_date = master_df["date"].max()
    if latest_fused_date < latest_master_date:
        raise ValueError(
            f"Fused parquet is stale: latest fused date {latest_fused_date.date()} "
            f"is older than master date {latest_master_date.date()}"
        )

    latest_rows = fused_df[fused_df["date"] == latest_fused_date].copy()
    if latest_rows["latest_volume"].isna().any() or latest_rows["volume_rank"].isna().any():
        raise ValueError("Fused parquet must persist latest_volume and volume_rank for every latest-date row")

    unique_dates = sorted(fused_df["date"].dropna().unique())
    previous_fused_date = unique_dates[-2] if len(unique_dates) > 1 else None

    today_signal_symbols = _dedupe_preserve_order(
        latest_rows.loc[latest_rows["score"].fillna(0) >= signal_score_threshold, "stock_id"].tolist()
    )

    carryover_signal_symbols: list[str] = []
    if previous_fused_date is not None:
        previous_rows = fused_df[fused_df["date"] == previous_fused_date]
        carryover_signal_symbols = [
            symbol
            for symbol in _dedupe_preserve_order(
                previous_rows.loc[
                    previous_rows["score"].fillna(0) >= signal_score_threshold,
                    "stock_id",
                ].tolist()
            )
            if symbol not in today_signal_symbols
        ]

    rs_metrics = _load_baseline_rs_metrics(baseline_path)
    ranked_candidates = sorted(
        [
            RankedCandidate(
                symbol=symbol,
                rs_metric=float(rs_metrics.get(symbol, 0.0)),
                volume_metric=float(row["latest_volume"]),
                volume_rank=int(row["volume_rank"]),
            )
            for symbol, row in latest_rows.drop_duplicates("stock_id", keep="last").set_index("stock_id").iterrows()
            if _is_valid_symbol(symbol)
        ],
        key=_ranked_candidate_sort_key,
    )

    return {
        "today_signal_symbols": today_signal_symbols,
        "carryover_signal_symbols": carryover_signal_symbols,
        "ranked_candidates": ranked_candidates,
        "latest_fused_date": latest_fused_date.to_pydatetime(),
        "previous_fused_date": previous_fused_date.to_pydatetime() if previous_fused_date is not None else None,
        "latest_master_date": latest_master_date.to_pydatetime(),
    }


def build_core_universe(
    all_symbols: Sequence[str],
    config: CoreSelectionConfig,
    ranked_candidates: Sequence[RankedCandidate] | None = None,
    today_signal_symbols: Sequence[str] | None = None,
    carryover_signal_symbols: Sequence[str] | None = None,
    target_size: int | None = None,
) -> CoreSelectionResult:
    """Build the ordered core universe from fixed buckets and ranked fill candidates."""
    effective_target_size = target_size or config.target_size
    if effective_target_size <= 0:
        raise ValueError("target_size must be positive")

    allowed_symbols = {
        symbol
        for symbol in (str(value) for value in all_symbols)
        if _is_valid_symbol(symbol)
    }

    fixed_symbols = [
        symbol
        for symbol in _dedupe_preserve_order(
            config.base_symbols
            + config.etf_symbols
            + config.watchlist_symbols
            + list(carryover_signal_symbols or [])
            + list(today_signal_symbols or [])
        )
        if symbol in allowed_symbols
    ]

    ranked_fill_symbols: list[str] = []
    selected_symbols = set(fixed_symbols)
    remaining_slots = max(0, effective_target_size - len(fixed_symbols))

    for candidate in sorted(ranked_candidates or [], key=_ranked_candidate_sort_key):
        if candidate.symbol not in allowed_symbols or candidate.symbol in selected_symbols:
            continue
        ranked_fill_symbols.append(candidate.symbol)
        selected_symbols.add(candidate.symbol)
        if len(ranked_fill_symbols) >= remaining_slots:
            break

    overflow_symbols = fixed_symbols[effective_target_size:] if len(fixed_symbols) > effective_target_size else []
    core_symbols = fixed_symbols + ranked_fill_symbols

    return CoreSelectionResult(
        core_symbols=core_symbols,
        fixed_symbols=fixed_symbols,
        carryover_signal_symbols=list(carryover_signal_symbols or []),
        today_signal_symbols=list(today_signal_symbols or []),
        ranked_fill_symbols=ranked_fill_symbols,
        target_size=effective_target_size,
        overflow_symbols=overflow_symbols,
        debug_counts={
            "fixed_symbols": len(fixed_symbols),
            "ranked_fill_symbols": len(ranked_fill_symbols),
            "core_symbols": len(core_symbols),
        },
    )


def _validate_symbol_bucket(bucket_name: str, value: Any) -> list[str]:
    """Validate a configured symbol bucket."""
    if not isinstance(value, list):
        raise ValueError(f"{bucket_name} must be a list of 4-digit symbol strings")

    validated: list[str] = []
    for symbol in value:
        normalized = str(symbol)
        if not _is_valid_symbol(normalized):
            raise ValueError(f"{bucket_name} contains invalid symbol {symbol!r}")
        validated.append(normalized)
    return validated


def _is_valid_symbol(symbol: str) -> bool:
    """Return True when the selector symbol matches repo expectations."""
    return len(symbol) == 4 and symbol.isdigit()


def _dedupe_preserve_order(symbols: Sequence[str]) -> list[str]:
    """Deduplicate symbols while preserving the first occurrence."""
    ordered: list[str] = []
    seen: set[str] = set()
    for value in symbols:
        symbol = str(value)
        if not _is_valid_symbol(symbol) or symbol in seen:
            continue
        seen.add(symbol)
        ordered.append(symbol)
    return ordered


def _require_columns(label: str, frame: pd.DataFrame, required_columns: set[str]) -> None:
    """Raise a readable error when a persisted artifact is missing required columns."""
    missing_columns = sorted(required_columns - set(frame.columns))
    if missing_columns:
        raise ValueError(f"{label} is missing required columns: {', '.join(missing_columns)}")


def _load_baseline_rs_metrics(baseline_path: str | Path) -> dict[str, float]:
    """Load Mansfield RS values from the baseline publish artifact."""
    baseline_file = Path(baseline_path)
    with baseline_file.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)

    stocks = payload.get("stocks", {})
    metrics: dict[str, float] = {}
    for symbol, entry in stocks.items():
        if not _is_valid_symbol(str(symbol)):
            continue
        canslim_payload = entry.get("canslim", {}) if isinstance(entry, dict) else {}
        metrics[str(symbol)] = float(canslim_payload.get("mansfield_rs") or 0.0)
    return metrics


def _ranked_candidate_sort_key(candidate: RankedCandidate) -> tuple[float, int, float, str]:
    """Stable selector ordering after fixed buckets."""
    volume_rank = candidate.volume_rank if candidate.volume_rank is not None else 10**9
    return (-candidate.rs_metric, volume_rank, -candidate.volume_metric, candidate.symbol)
