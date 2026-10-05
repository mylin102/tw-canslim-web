import pandas as pd
import pytest

from tej_processor import TEJProcessor


def _unavailable_processor(monkeypatch):
    """A TEJProcessor with TEJ disabled, so get_monthly_revenue falls through
    to the FinMind/yfinance fallback chain without hitting the real TEJ API."""
    processor = object.__new__(TEJProcessor)
    processor.error_count = 0
    processor.max_errors = 3
    processor._finmind_processor = None
    processor.provider_runtime_state = {
        "retry_attempts": 0,
        "retry_failures": 0,
        "provider_wait_seconds": 0.0,
    }
    processor.api_key = None
    processor.initialized = False
    return processor


def test_get_monthly_revenue_falls_back_to_finmind_when_tej_unavailable(monkeypatch):
    """TEJ_API_KEY expired (2026-10-04 incident): get_monthly_revenue must use
    FinMind's real TaiwanStockMonthRevenue dataset instead of silently
    returning nothing, which left docs/api/stock_features.json empty."""
    processor = _unavailable_processor(monkeypatch)

    finmind_df = pd.DataFrame(
        {
            "date": ["2026-08-01", "2026-09-01"],
            "stock_id": ["2330", "2330"],
            "revenue": [467580548000, 514805337000],
        }
    )

    fake_finmind = object.__new__(__import__("finmind_processor").FinMindProcessor)
    fake_finmind.available = True
    fake_finmind.dl = type(
        "DL", (), {"taiwan_stock_month_revenue": lambda self, **kwargs: finmind_df}
    )()
    fake_finmind.provider_runtime_state = {}
    monkeypatch.setattr(processor, "_get_finmind_processor", lambda: fake_finmind)
    monkeypatch.setattr(
        "tej_processor.call_with_provider_policy",
        lambda provider_name, operation, **kwargs: operation(),
    )

    df = processor.get_monthly_revenue("2330")

    assert df is not None
    assert list(df["revenue"]) == [467580548000, 514805337000]
    assert pd.api.types.is_datetime64_any_dtype(df["date"])


def test_get_monthly_revenue_falls_back_to_yfinance_proxy_when_finmind_also_fails(monkeypatch):
    """Last-resort fallback must still work when both TEJ and FinMind are
    unavailable. Also guards against the 'Invalid frequency: ME' regression
    (pandas <2.2 doesn't recognize the 'ME' alias, only 'M')."""
    processor = _unavailable_processor(monkeypatch)
    monkeypatch.setattr(processor, "_get_finmind_monthly_revenue", lambda coid: None)

    price_df = pd.DataFrame(
        {
            "date": pd.date_range("2026-07-01", periods=90, freq="D"),
            "close": [100.0 + i * 0.1 for i in range(90)],
        }
    )
    monkeypatch.setattr(processor, "get_daily_prices", lambda *a, **k: price_df)

    df = processor.get_monthly_revenue("2330")

    assert df is not None
    assert not df.empty
    assert "revenue" in df.columns
