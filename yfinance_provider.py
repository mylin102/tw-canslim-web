"""
Shared yfinance provider policy helpers for export paths.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

import pandas as pd
import yfinance as yf

from provider_policies import ProviderRetryExhaustedError, call_with_provider_policy, get_provider_policy


logger = logging.getLogger(__name__)


def get_price_history_with_policy(
    ticker: str,
    *,
    period: str | None = None,
    start: str | None = None,
    end: str | None = None,
    auto_adjust: bool = True,
    runtime_state: dict[str, Any] | None = None,
) -> Optional[pd.Series]:
    """Fetch yfinance close-price history through the shared provider policy contract."""
    policy = get_provider_policy("yfinance")
    logger.debug(
        "yfinance provider policy: min_interval_seconds=%s quota_window_seconds=%s max_requests_per_window=%s",
        policy.min_interval_seconds,
        policy.quota_window_seconds,
        policy.max_requests_per_window,
    )

    history_kwargs = {"auto_adjust": auto_adjust}
    if period is not None:
        history_kwargs["period"] = period
    if start is not None:
        history_kwargs["start"] = start
    if end is not None:
        history_kwargs["end"] = end

    try:
        history = call_with_provider_policy(
            "yfinance",
            lambda: yf.Ticker(ticker).history(**history_kwargs),
            runtime_state=runtime_state,
        )
    except ProviderRetryExhaustedError as exc:
        logger.error(f"yfinance retries exhausted for {ticker}: {exc}")
        return None
    except Exception as exc:
        logger.debug(f"yfinance history failed for {ticker}: {exc}")
        return None

    if history is None or history.empty or "Close" not in history:
        return None
    return history["Close"]
