"""
ETF Regime Classifier — market environment from ETF relative strength.

Output: data/etf_regime.json (daily regime + features + confidence)
Data flow: Shioaji kbars (primary) → yfinance_provider (fallback) → stale cache (final)
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any, Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# ── ETF Groups ──
ETF_GROUPS: dict[str, list[str]] = {
    "market_proxy": ["0050", "006208"],
    "growth": ["00881", "00927"],
    "dividend_defensive": ["0056", "00878", "00919"],
    "small_mid": ["0051", "00733"],
    "inverse": ["00632R"],
    "bond": ["00679B", "00720B"],
}

LOOKBACK_DAYS = 7  # enough for 5d returns

REGIME_PRIORITY = ["RISK_ON", "RISK_OFF", "DEFENSIVE", "CHOP"]


def get_etf_close_prices(
    symbol: str,
    price_history_fn: Any,
) -> Optional[pd.Series]:
    """Fetch close prices for an ETF symbol.

    Uses the provided price_history_fn (e.g. CanslimEngine.get_price_history)
    which internally chains Shioaji → TEJ → yfinance.
    Returns a pandas Series with date index, or None on failure.
    """
    try:
        series = price_history_fn(symbol, period="1mo")
        if series is not None and len(series) >= LOOKBACK_DAYS:
            return series
    except Exception as exc:
        logger.debug("ETF price fetch failed for %s: %s", symbol, exc)
    return None


def compute_bucket_returns(
    group_symbols: list[str],
    price_history_fn: Any,
    lookback: int = 5,
) -> Optional[float]:
    """Compute average 5-day return for an ETF bucket.

    Averages returns of all available symbols in the bucket.
    Returns None if all symbols in the bucket are missing.
    """
    returns: list[float] = []
    for symbol in group_symbols:
        series = get_etf_close_prices(symbol, price_history_fn)
        if series is None or len(series) < lookback + 1:
            logger.debug("ETF %s: insufficient data, skipping", symbol)
            continue

        # Get the most recent lookback-day return
        recent = series.iloc[-lookback - 1:]
        if len(recent) < lookback + 1:
            continue

        ret_5d = (recent.iloc[-1] / recent.iloc[0]) - 1.0
        returns.append(ret_5d)

    if not returns:
        return None
    return float(np.mean(returns))


def compute_market_momentum(
    price_history_fn: Any,
) -> Optional[float]:
    """Market momentum via 0050 5-day return."""
    return compute_bucket_returns(ETF_GROUPS["market_proxy"], price_history_fn)


def compute_growth_vs_defensive(
    price_history_fn: Any,
) -> Optional[float]:
    """Growth sector minus defensive dividend stocks."""
    growth_ret = compute_bucket_returns(ETF_GROUPS["growth"], price_history_fn)
    defensive_ret = compute_bucket_returns(ETF_GROUPS["dividend_defensive"], price_history_fn)
    if growth_ret is None or defensive_ret is None:
        return None
    return growth_ret - defensive_ret


def compute_small_vs_large(
    price_history_fn: Any,
) -> Optional[float]:
    """Small/mid-cap minus large-cap (0050)."""
    small_ret = compute_bucket_returns(ETF_GROUPS["small_mid"], price_history_fn)
    market_ret = compute_market_momentum(price_history_fn)
    if small_ret is None or market_ret is None:
        return None
    return small_ret - market_ret


def compute_hedge_demand(
    price_history_fn: Any,
    lookback: int = 3,
) -> Optional[float]:
    """Inverse ETF 3-day return — proxy for hedging demand."""
    return compute_bucket_returns(ETF_GROUPS["inverse"], price_history_fn, lookback=lookback)


def compute_bond_bid(
    price_history_fn: Any,
) -> Optional[float]:
    """Bond ETF average 5-day return."""
    return compute_bucket_returns(ETF_GROUPS["bond"], price_history_fn)


def compute_features(
    price_history_fn: Any,
) -> dict[str, Any]:
    """Compute all ETF regime features.

    Returns dict with feature names as keys and float or None as values.
    """
    momentum = compute_market_momentum(price_history_fn)
    gvd = compute_growth_vs_defensive(price_history_fn)
    svl = compute_small_vs_large(price_history_fn)
    hedge = compute_hedge_demand(price_history_fn)
    bond = compute_bond_bid(price_history_fn)

    features: dict[str, Any] = {
        "market_momentum": momentum,
        "growth_vs_defensive": gvd,
        "small_vs_large": svl,
        "hedge_demand": hedge,
        "bond_bid": bond,
    }

    # Log which features are valid
    valid = sum(1 for v in features.values() if v is not None)
    total = len(features)
    logger.info(
        "ETF regime features: %d/%d valid (momentum=%s gvd=%s svl=%s hedge=%s bond=%s)",
        valid, total,
        _fmt(momentum), _fmt(gvd), _fmt(svl), _fmt(hedge), _fmt(bond),
    )
    return features


def _fmt(v: Any) -> str:
    if v is None:
        return "None"
    return f"{v:+.4f}"


def classify_regime(features: dict[str, Any]) -> tuple[str, float]:
    """Classify market regime from ETF features.

    Priority order: RISK_ON → RISK_OFF → DEFENSIVE → CHOP

    Returns (regime: str, confidence: float).
    Confidence = valid_feature_ratio * agreement_ratio.
    """
    f = features
    valid_features = {k: v for k, v in f.items() if v is not None}
    valid_count = len(valid_features)
    total_count = len(f)
    valid_ratio = valid_count / total_count if total_count > 0 else 0.0

    if valid_count < 2:
        logger.warning("ETF regime: too few valid features (%d/%d), defaulting to CHOP", valid_count, total_count)
        return "CHOP", 0.0

    # Check RISK_ON
    risk_on_signals = 0
    risk_on_total = 0
    for key in ("market_momentum", "growth_vs_defensive", "small_vs_large"):
        if f.get(key) is not None and f[key] > 0:
            risk_on_signals += 1
        if f.get(key) is not None:
            risk_on_total += 1
    if f.get("hedge_demand") is not None and f["hedge_demand"] < 0:
        risk_on_signals += 1
    if f.get("hedge_demand") is not None:
        risk_on_total += 1

    if risk_on_total > 0 and risk_on_signals == risk_on_total:
        return "RISK_ON", valid_ratio * 1.0

    # Check RISK_OFF — needs strong signals (|z| > threshold)
    risk_off_signals = 0
    risk_off_total = 0
    if f.get("hedge_demand") is not None and f["hedge_demand"] > 0.01:
        risk_off_signals += 1
        risk_off_total += 1
    elif f.get("hedge_demand") is not None:
        risk_off_total += 1
    if f.get("bond_bid") is not None and f["bond_bid"] > 0.01:
        risk_off_signals += 1
        risk_off_total += 1
    elif f.get("bond_bid") is not None:
        risk_off_total += 1

    if risk_off_total > 0 and risk_off_signals > 0:
        agreement = risk_off_signals / risk_off_total
        return "RISK_OFF", valid_ratio * agreement

    # Check DEFENSIVE — bonds mildly positive (< 0.01 threshold) + growth weak
    defensive_signals = 0
    defensive_total = 0
    if f.get("growth_vs_defensive") is not None and f["growth_vs_defensive"] < 0:
        defensive_signals += 1
        defensive_total += 1
    elif f.get("growth_vs_defensive") is not None:
        defensive_total += 1
    if f.get("bond_bid") is not None and 0 <= f["bond_bid"] <= 0.01:
        defensive_signals += 1
        defensive_total += 1
    elif f.get("bond_bid") is not None:
        defensive_total += 1

    if defensive_total > 0 and defensive_signals == defensive_total:
        return "DEFENSIVE", valid_ratio * 1.0

    # Default: CHOP
    return "CHOP", valid_ratio * 0.5


def build_etf_regime_payload(
    price_history_fn: Any,
    as_of: str | None = None,
) -> dict[str, Any]:
    """Build the complete etf_regime.json payload.

    Args:
        price_history_fn: Callable(symbol, period) -> pd.Series | None
        as_of: ISO timestamp override (for testing)

    Returns:
        dict ready to serialize as etf_regime.json
    """
    features = compute_features(price_history_fn)
    regime, confidence = classify_regime(features)

    payload = {
        "schema_version": 1,
        "date": (datetime.now(UTC) if as_of is None else datetime.fromisoformat(as_of.replace("Z", "+00:00"))).strftime("%Y-%m-%d"),
        "generated_at": (as_of or datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")),
        "regime": regime,
        "confidence": round(confidence, 4),
        "features": {
            k: (round(v, 6) if v is not None else None) for k, v in features.items()
        },
    }

    logger.info(
        "ETF regime: %s (confidence=%.4f) | momentum=%s gvd=%s svl=%s hedge=%s bond=%s",
        regime, confidence,
        _fmt(features.get("market_momentum")),
        _fmt(features.get("growth_vs_defensive")),
        _fmt(features.get("small_vs_large")),
        _fmt(features.get("hedge_demand")),
        _fmt(features.get("bond_bid")),
    )
    return payload
