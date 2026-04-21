"""
Core selection contracts and artifact-backed selector helpers.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

import pandas as pd

logger = logging.getLogger(__name__)

SIGNAL_SCORE_THRESHOLD = 75
RS_LEADER_THRESHOLD = 80
MAX_REQUIRED_BUCKET_SIZE = 500
TOP_VOLUME_LEADER_COUNT = 100
BUCKET_ORDER = (
    "base_symbols",
    "etf_symbols",
    "watchlist_symbols",
    "yesterday_signals",
    "today_signals",
    "revenue_alpha_leaders",
    "rs_leaders",
    "top_volume_leaders",
)
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
    "rs_rating",
    "latest_volume",
    "volume_rank",
}
REQUIRED_MASTER_COLUMNS = {
    "stock_id",
    "date",
    "score",
    "latest_volume",
    "volume_rank",
}


@dataclass(frozen=True)
class CoreSelectionConfig:
    """Checked-in fixed bucket configuration."""

    base_symbols: list[str]
    etf_symbols: list[str]
    watchlist_symbols: list[str]
    target_size: int


@dataclass(frozen=True)
class RankedCandidate:
    """Rankable candidate for selector fill slots."""

    symbol: str
    mansfield_rs: float = 0.0
    revenue_score: float = 0.0
    volume_rank: int | None = None


@dataclass(frozen=True)
class CoreSelectionResult:
    """Ordered selector output for downstream export wiring."""

    core_symbols: list[str]
    ranked_fill_symbols: list[str]
    target_size: int
    bucket_symbols: dict[str, list[str]]
    bucket_counts: dict[str, int]

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
    *,
    config_path: str | Path,
    fused_path: str | Path,
    master_path: str | Path,
    baseline_path: str | Path,
    revenue_path: str | Path = "docs/api/stock_features.json",
    signal_score_threshold: int = SIGNAL_SCORE_THRESHOLD,
) -> dict[str, Any]:
    """Load selector inputs and derive persisted buckets from trusted artifacts."""
    config = load_core_selection_config(config_path)
    fused_df = pd.read_parquet(fused_path).copy()
    master_df = pd.read_parquet(master_path).copy()

    _require_columns("fused parquet", fused_df, REQUIRED_FUSED_COLUMNS)
    _require_columns("master parquet", master_df, REQUIRED_MASTER_COLUMNS)

    if fused_df.empty or master_df.empty:
        raise ValueError("Selector inputs require non-empty fused and master parquet files")

    fused_df = _normalize_selector_frame(fused_df)
    master_df = _normalize_selector_frame(master_df)

    latest_fused_date = fused_df["date"].max()
    latest_master_date = master_df["date"].max()
    if latest_fused_date < latest_master_date:
        raise ValueError(
            f"Fused parquet is stale: latest fused date {latest_fused_date.date()} "
            f"is older than master date {latest_master_date.date()}"
        )

    latest_rows = _latest_rows(fused_df, latest_fused_date)
    previous_fused_date = _previous_date(fused_df)
    previous_rows = (
        _latest_rows(fused_df, previous_fused_date)
        if previous_fused_date is not None
        else pd.DataFrame(columns=fused_df.columns)
    )

    today_signal_symbols = _ordered_symbols(
        latest_rows.loc[latest_rows["score"].fillna(0) >= signal_score_threshold, "stock_id"].tolist()
    )
    yesterday_signal_symbols = [
        symbol
        for symbol in _ordered_symbols(
            previous_rows.loc[previous_rows["score"].fillna(0) >= signal_score_threshold, "stock_id"].tolist()
        )
        if symbol not in today_signal_symbols
    ]

    # Explicit RS leader bucket: rs_rating >= 80 on the repo's 0-100 scale.
    rs_leaders = _ordered_symbols(
        latest_rows.loc[latest_rows["rs_rating"].fillna(0) >= 80, "stock_id"].tolist()
    )
    top_volume_rows = latest_rows.sort_values(["volume_rank", "stock_id"]).head(TOP_VOLUME_LEADER_COUNT)
    top_volume_leaders = _ordered_symbols(top_volume_rows["stock_id"].tolist())

    # Load revenue features
    revenue_data = {}
    rev_path = Path(revenue_path)
    if rev_path.exists():
        with rev_path.open("r", encoding="utf-8") as handle:
            revenue_data = json.load(handle)

    revenue_alpha_leaders = []
    for symbol, features in revenue_data.items():
        if not isinstance(features, dict):
            continue
        score = features.get("revenue_score", 0)
        accelerating = features.get("rev_accelerating", False)
        if score >= 5 and accelerating is True:
            if _is_valid_symbol(str(symbol)):
                revenue_alpha_leaders.append(str(symbol))

    mansfield_rs_metrics = _load_baseline_rs_metrics(baseline_path)
    ranked_candidates = [
        RankedCandidate(
            symbol=str(row["stock_id"]),
            mansfield_rs=float(mansfield_rs_metrics.get(str(row["stock_id"]), 0.0)),
            revenue_score=float(revenue_data.get(str(row["stock_id"]), {}).get("revenue_score", 0.0)),
            volume_rank=_to_int_or_none(row["volume_rank"]),
        )
        for _, row in latest_rows.iterrows()
        if _is_valid_symbol(str(row["stock_id"]))
    ]
    ranked_candidates.sort(key=_ranked_candidate_sort_key)

    return {
        "config": config,
        "all_symbols": latest_rows["stock_id"].tolist(),
        "today_signal_symbols": today_signal_symbols,
        "yesterday_signal_symbols": yesterday_signal_symbols,
        "revenue_alpha_leaders": revenue_alpha_leaders,
        "rs_leaders": rs_leaders,
        "top_volume_leaders": top_volume_leaders,
        "ranked_candidates": ranked_candidates,
        "latest_fused_date": latest_fused_date.to_pydatetime(),
        "previous_fused_date": previous_fused_date.to_pydatetime() if previous_fused_date is not None else None,
        "latest_master_date": latest_master_date.to_pydatetime(),
    }


def build_core_universe(
    *,
    all_symbols: Sequence[str],
    config: CoreSelectionConfig | None = None,
    config_path: str | Path | None = None,
    fused_path: str | Path | None = None,
    master_path: str | Path | None = None,
    baseline_path: str | Path | None = None,
    revenue_path: str | Path | None = None,
    ranked_candidates: Sequence[RankedCandidate] | None = None,
    today_signal_symbols: Sequence[str] | None = None,
    yesterday_signal_symbols: Sequence[str] | None = None,
    revenue_alpha_leaders: Sequence[str] | None = None,
    rs_leaders: Sequence[str] | None = None,
    top_volume_leaders: Sequence[str] | None = None,
    target_size: int | None = None,
) -> CoreSelectionResult:
    """Build the ordered core universe from required buckets plus deterministic fill."""
    if config is None:
        artifact_paths = {
            "config_path": config_path,
            "fused_path": fused_path,
            "master_path": master_path,
            "baseline_path": baseline_path,
        }
        missing_paths = [name for name, value in artifact_paths.items() if value is None]
        if missing_paths:
            raise ValueError(
                "build_core_universe requires either config or all selector artifact paths; "
                f"missing {', '.join(sorted(missing_paths))}"
            )
        
        load_kwargs = {
            "config_path": config_path,
            "fused_path": fused_path,
            "master_path": master_path,
            "baseline_path": baseline_path,
        }
        if revenue_path is not None:
            load_kwargs["revenue_path"] = revenue_path

        selector_inputs = load_selector_inputs(**load_kwargs)
        return build_core_universe(
            all_symbols=all_symbols,
            config=selector_inputs["config"],
            ranked_candidates=selector_inputs["ranked_candidates"],
            today_signal_symbols=selector_inputs["today_signal_symbols"],
            yesterday_signal_symbols=selector_inputs["yesterday_signal_symbols"],
            revenue_alpha_leaders=selector_inputs["revenue_alpha_leaders"],
            rs_leaders=selector_inputs["rs_leaders"],
            top_volume_leaders=selector_inputs["top_volume_leaders"],
            target_size=target_size,
        )

    base_target_size = target_size or config.target_size
    if base_target_size <= 0:
        raise ValueError("target_size must be positive")

    allowed_symbols = {symbol for symbol in map(str, all_symbols) if _is_valid_symbol(symbol)}
    bucket_inputs = {
        "base_symbols": config.base_symbols,
        "etf_symbols": config.etf_symbols,
        "watchlist_symbols": config.watchlist_symbols,
        "yesterday_signals": list(yesterday_signal_symbols or []),
        "today_signals": list(today_signal_symbols or []),
        "revenue_alpha_leaders": list(revenue_alpha_leaders or []),
        "rs_leaders": list(rs_leaders or []),
        "top_volume_leaders": list(top_volume_leaders or []),
    }

    bucket_symbols: dict[str, list[str]] = {}
    required_symbols: list[str] = []
    required_seen: set[str] = set()
    for bucket_name in BUCKET_ORDER:
        bucket_members = []
        for symbol in _ordered_symbols(bucket_inputs[bucket_name]):
            if symbol not in allowed_symbols or symbol in required_seen:
                continue
            required_seen.add(symbol)
            bucket_members.append(symbol)
        bucket_symbols[bucket_name] = bucket_members
        required_symbols.extend(bucket_members)

    required_total = len(required_symbols)
    if required_total > MAX_REQUIRED_BUCKET_SIZE:
        raise ValueError(
            f"required bucket membership exceeds {MAX_REQUIRED_BUCKET_SIZE}; "
            f"required bucket total is {required_total}"
        )

    effective_target_size = base_target_size
    if required_total > base_target_size:
        effective_target_size = required_total

    ranked_fill_symbols: list[str] = []
    selected_symbols = set(required_symbols)
    remaining_slots = max(0, effective_target_size - required_total)
    for candidate in sorted(ranked_candidates or [], key=_ranked_candidate_sort_key):
        if candidate.symbol not in allowed_symbols or candidate.symbol in selected_symbols:
            continue
        ranked_fill_symbols.append(candidate.symbol)
        selected_symbols.add(candidate.symbol)
        if len(ranked_fill_symbols) >= remaining_slots:
            break

    core_symbols = required_symbols + ranked_fill_symbols
    bucket_counts = {bucket_name: len(bucket_symbols[bucket_name]) for bucket_name in BUCKET_ORDER}
    bucket_counts["required_total"] = required_total
    bucket_counts["ranked_fill_symbols"] = len(ranked_fill_symbols)
    bucket_counts["core_symbols"] = len(core_symbols)

    return CoreSelectionResult(
        core_symbols=core_symbols,
        ranked_fill_symbols=ranked_fill_symbols,
        target_size=effective_target_size,
        bucket_symbols=bucket_symbols,
        bucket_counts=bucket_counts,
    )


def _normalize_selector_frame(frame: pd.DataFrame) -> pd.DataFrame:
    """Normalize persisted selector artifacts for deterministic loading."""
    normalized = frame.copy()
    normalized["stock_id"] = normalized["stock_id"].astype(str)
    normalized["date"] = pd.to_datetime(normalized["date"]).dt.normalize()
    if "volume_rank" in normalized.columns:
        normalized["volume_rank"] = pd.to_numeric(normalized["volume_rank"], errors="coerce")
    return normalized


def _latest_rows(frame: pd.DataFrame, target_date: pd.Timestamp | None) -> pd.DataFrame:
    """Return latest unique stock rows for the requested date."""
    if target_date is None:
        return pd.DataFrame(columns=frame.columns)
    return (
        frame[frame["date"] == target_date]
        .sort_values(["stock_id", "volume_rank"], na_position="last")
        .drop_duplicates("stock_id", keep="first")
        .sort_values(["volume_rank", "stock_id"], na_position="last")
        .reset_index(drop=True)
    )


def _previous_date(frame: pd.DataFrame) -> pd.Timestamp | None:
    """Return the immediately previous fused date when available."""
    unique_dates = sorted(frame["date"].dropna().unique())
    if len(unique_dates) < 2:
        return None
    return pd.Timestamp(unique_dates[-2])


def _validate_symbol_bucket(bucket_name: str, value: Any) -> list[str]:
    """Validate a configured symbol bucket."""
    if not isinstance(value, list):
        raise ValueError(f"{bucket_name} must be a list of 4- or 5-digit symbol strings")
    return _ordered_symbols(value, bucket_name=bucket_name)


def _ordered_symbols(symbols: Sequence[str], bucket_name: str | None = None) -> list[str]:
    """Deduplicate symbols while preserving first appearance."""
    ordered: list[str] = []
    seen: set[str] = set()
    for value in symbols:
        symbol = str(value)
        if not _is_valid_symbol(symbol):
            if bucket_name is not None:
                raise ValueError(f"{bucket_name} contains invalid symbol {value!r}")
            continue
        if symbol in seen:
            continue
        seen.add(symbol)
        ordered.append(symbol)
    return ordered


def _is_valid_symbol(symbol: str) -> bool:
    """Return True when the selector symbol matches repo expectations."""
    return len(symbol) in {4, 5} and symbol.isdigit()


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


def _to_int_or_none(value: Any) -> int | None:
    """Convert persisted volume_rank values into deterministic ints."""
    if pd.isna(value):
        return None
    return int(value)


def _ranked_candidate_sort_key(candidate: RankedCandidate) -> tuple[float, float, int, str]:
    """Stable selector ordering after required buckets: (-revenue_score, -mansfield_rs, volume_rank, symbol)."""
    volume_rank = candidate.volume_rank if candidate.volume_rank is not None else 10**9
    return (-candidate.revenue_score, -candidate.mansfield_rs, volume_rank, candidate.symbol)
