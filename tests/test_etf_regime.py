"""Tests for ETF Regime Engine."""

import json
import os
from pathlib import Path
from unittest.mock import MagicMock
import pytest
import pandas as pd
import numpy as np

from export_etf_regime import (
    build_etf_regime_payload,
    classify_regime,
    compute_features,
    compute_bucket_returns,
    ETF_GROUPS,
)


def _make_price_series(start_price: float = 100.0, days: int = 10, drift: float = 0.0) -> pd.Series:
    """Create a deterministic fake price series with daily drift (no randomness)."""
    import pandas as pd
    from datetime import datetime, timedelta

    prices = [start_price * (1.0 + drift) ** i for i in range(days)]

    dates = [datetime(2026, 5, 4) - timedelta(days=days - 1 - i) for i in range(days)]
    return pd.Series(prices, index=dates)


def _fake_price_history(symbol: str, period: str = "2y") -> pd.Series | None:
    """Mock price history function for testing.

    Returns bullish prices (uptrend) for market_proxy and growth ETFs,
    flat for defensive, down for inverse.
    """
    if symbol in ("0050", "006208"):
        return _make_price_series(100.0, days=10, drift=0.004)
    elif symbol in ("00881", "00927"):
        return _make_price_series(100.0, days=10, drift=0.006)
    elif symbol in ("0056", "00878", "00919"):
        return _make_price_series(100.0, days=10, drift=0.001)
    elif symbol in ("0051", "00733"):
        return _make_price_series(100.0, days=10, drift=0.005)
    elif symbol in ("00632R",):
        return _make_price_series(100.0, days=10, drift=-0.003)
    elif symbol in ("00679B", "00720B"):
        return _make_price_series(100.0, days=10, drift=0.001)
    return None


def _bearish_price_history(symbol: str, period: str = "2y") -> pd.Series | None:
    """Mock bearish market: market down, inverse up, bonds up."""
    if symbol in ("0050", "006208"):
        return _make_price_series(100.0, days=10, drift=-0.005)
    elif symbol in ("00881", "00927"):
        return _make_price_series(100.0, days=10, drift=-0.007)
    elif symbol in ("0056", "00878", "00919"):
        return _make_price_series(100.0, days=10, drift=-0.002)
    elif symbol in ("0051", "00733"):
        return _make_price_series(100.0, days=10, drift=-0.006)
    elif symbol in ("00632R",):
        return _make_price_series(100.0, days=10, drift=0.008)
    elif symbol in ("00679B", "00720B"):
        return _make_price_series(100.0, days=10, drift=0.005)
    return None


def _defensive_price_history(symbol: str, period: str = "2y") -> pd.Series | None:
    """Mock defensive: market flat/slightly down, defensive up, bonds mildly up."""
    if symbol in ("0050", "006208"):
        return _make_price_series(100.0, days=10, drift=-0.001)
    elif symbol in ("00881", "00927"):
        return _make_price_series(100.0, days=10, drift=-0.003)
    elif symbol in ("0056", "00878", "00919"):
        return _make_price_series(100.0, days=10, drift=0.003)
    elif symbol in ("0051", "00733"):
        return _make_price_series(100.0, days=10, drift=-0.002)
    elif symbol in ("00632R",):
        return _make_price_series(100.0, days=10, drift=0.0005)
    elif symbol in ("00679B", "00720B"):
        return _make_price_series(100.0, days=10, drift=0.0015)
    return None


class TestClassifyRegime:
    def test_risk_on_all_signals(self):
        """All RISK_ON conditions met: market up, growth beating defensive, small beating large, hedge down."""
        features = {
            "market_momentum": 0.02,
            "growth_vs_defensive": 0.015,
            "small_vs_large": 0.01,
            "hedge_demand": -0.01,
            "bond_bid": -0.005,
        }
        regime, confidence = classify_regime(features)
        assert regime == "RISK_ON", f"Expected RISK_ON, got {regime}"
        assert confidence > 0.5, f"Expected confidence > 0.5, got {confidence}"

    def test_risk_on_missing_one_feature(self):
        """RISK_ON with one feature missing should still classify."""
        features = {
            "market_momentum": 0.02,
            "growth_vs_defensive": 0.015,
            "small_vs_large": None,
            "hedge_demand": -0.01,
            "bond_bid": -0.005,
        }
        regime, confidence = classify_regime(features)
        # small_vs_large=None so risk_on_total=4 but only 3 checked → still 3/3
        assert regime == "RISK_ON", f"Expected RISK_ON, got {regime}"

    def test_risk_off_hedge_demand(self):
        """Hedge demand positive = RISK_OFF."""
        features = {
            "market_momentum": -0.02,
            "growth_vs_defensive": -0.01,
            "small_vs_large": -0.01,
            "hedge_demand": 0.03,
            "bond_bid": -0.005,
        }
        regime, confidence = classify_regime(features)
        assert regime == "RISK_OFF", f"Expected RISK_OFF, got {regime}"

    def test_risk_off_bond_bid(self):
        """Bond bid > 0.01 = RISK_OFF."""
        features = {
            "market_momentum": -0.01,
            "growth_vs_defensive": -0.01,
            "small_vs_large": -0.005,
            "hedge_demand": -0.01,
            "bond_bid": 0.02,
        }
        regime, confidence = classify_regime(features)
        assert regime == "RISK_OFF", f"Expected RISK_OFF, got {regime}"

    def test_defensive_growth_weak_bonds_flat(self):
        """Growth underperforms defensive + bonds non-negative = DEFENSIVE."""
        features = {
            "market_momentum": 0.0,
            "growth_vs_defensive": -0.02,
            "small_vs_large": -0.01,
            "hedge_demand": 0.0,
            "bond_bid": 0.0,
        }
        regime, confidence = classify_regime(features)
        assert regime == "DEFENSIVE", f"Expected DEFENSIVE, got {regime}"

    def test_chop_default(self):
        """Mixed signals that don't clearly match any regime = CHOP."""
        features = {
            "market_momentum": 0.005,
            "growth_vs_defensive": 0.005,
            "small_vs_large": -0.005,
            "hedge_demand": 0.005,
            "bond_bid": -0.002,
        }
        regime, confidence = classify_regime(features)
        assert regime == "CHOP", f"Expected CHOP, got {regime}"

    def test_too_few_features(self):
        """Less than 2 valid features defaults to CHOP with 0 confidence."""
        features = {
            "market_momentum": None,
            "growth_vs_defensive": None,
            "small_vs_large": None,
            "hedge_demand": 0.01,
            "bond_bid": None,
        }
        regime, confidence = classify_regime(features)
        assert regime == "CHOP"
        assert confidence == 0.0


class TestComputeFeatures:
    def test_bullish_features(self):
        """Bullish market produces positive momentum and growth_vs_defensive."""
        features = compute_features(_fake_price_history)
        assert features["market_momentum"] is not None
        assert features["market_momentum"] > 0
        assert features["growth_vs_defensive"] is not None
        assert features["hedge_demand"] is not None
        assert features["hedge_demand"] < 0  # inverse ETF goes down in bull

    def test_bearish_features(self):
        """Bearish market: negative momentum, positive hedge demand."""
        features = compute_features(_bearish_price_history)
        assert features["market_momentum"] is not None
        assert features["market_momentum"] < 0
        assert features["hedge_demand"] is not None
        assert features["hedge_demand"] > 0  # inverse ETF goes up
        assert features["bond_bid"] is not None
        assert features["bond_bid"] > 0  # bonds go up in flight to safety

    def test_all_etf_groups_covered(self):
        """Every ETF group should have at least one valid feature."""
        features = compute_features(_fake_price_history)
        # Check each group contributes to at least one feature
        assert features["market_momentum"] is not None
        assert features["growth_vs_defensive"] is not None
        assert features["small_vs_large"] is not None
        assert features["hedge_demand"] is not None
        assert features["bond_bid"] is not None


class TestBuildPayload:
    def test_payload_structure(self):
        """Payload should have correct schema."""
        payload = build_etf_regime_payload(_fake_price_history, as_of="2026-05-04T12:00:00Z")
        assert payload["schema_version"] == 1
        assert payload["date"] == "2026-05-04"
        assert payload["regime"] in ("RISK_ON", "RISK_OFF", "DEFENSIVE", "CHOP")
        assert 0.0 <= payload["confidence"] <= 1.0
        assert isinstance(payload["features"], dict)
        for k in ("market_momentum", "growth_vs_defensive", "small_vs_large", "hedge_demand", "bond_bid"):
            assert k in payload["features"]

    def test_bullish_predicts_risk_on(self):
        """Bullish fake data should consistently produce RISK_ON."""
        payload = build_etf_regime_payload(_fake_price_history, as_of="2026-05-04T12:00:00Z")
        assert payload["regime"] == "RISK_ON", f"Expected RISK_ON, got {payload['regime']}"

    def test_bearish_predicts_risk_off(self):
        """Bearish fake data should produce RISK_OFF."""
        payload = build_etf_regime_payload(_bearish_price_history, as_of="2026-05-04T12:00:00Z")
        assert payload["regime"] == "RISK_OFF", f"Expected RISK_OFF, got {payload['regime']}"

    def test_defensive_predicts_defensive(self):
        """Defensive fake data should produce DEFENSIVE."""
        payload = build_etf_regime_payload(_defensive_price_history, as_of="2026-05-04T12:00:00Z")
        assert payload["regime"] == "DEFENSIVE", f"Expected DEFENSIVE, got {payload['regime']}"
