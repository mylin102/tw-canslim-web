import pandas as pd
import pytest

from export_canslim import CanslimEngine
from tej_processor import TEJProcessor


def _build_price_engine():
    """Minimal CanslimEngine for exercising get_price_history in isolation."""
    engine = object.__new__(CanslimEngine)
    engine.ticker_info = {"1101": {"name": "台泥", "suffix": ".TW"}}
    engine.failure_stats = {"retry_attempts": 0, "retry_failures": 0, "provider_wait_seconds": 0.0}
    return engine


def test_get_price_history_passes_explicit_date_range_to_tej(monkeypatch):
    """2026-10-05: get_price_history() called get_daily_prices(count=500, ...),
    but get_daily_prices() never uses `count` at all -- its own internal
    yfinance fallback reads start_date/end_date verbatim, and with both left
    None (the prior call never passed them either) it silently returned
    yfinance's bare-default short window instead of ~2 years."""
    engine = _build_price_engine()
    engine.tej_processor = object.__new__(TEJProcessor)
    engine.tej_processor.initialized = True

    captured = {}

    def fake_get_daily_prices(coid, **kwargs):
        captured.update(kwargs)
        dates = pd.date_range("2024-10-01", periods=484, freq="D")
        return pd.DataFrame({"date": dates, "close": [100.0] * 484})

    engine.tej_processor.get_daily_prices = fake_get_daily_prices

    result = engine.get_price_history("1101", period="2y")

    assert "start_date" in captured and captured["start_date"] is not None
    assert "end_date" in captured and captured["end_date"] is not None
    assert "count" not in captured
    assert result is not None and len(result) == 484


def test_get_price_history_rejects_tej_result_shorter_than_mansfield_rs_window(monkeypatch):
    """A short TEJ/internal-fallback result (e.g. the 19-row bug above) must
    not be accepted as "the" price history -- calculate_mansfield_rs needs
    >=60 rows (core/logic.py) or it silently returns 0.0. Falling through to
    the next tier (FinMind) gives mansfield_rs an actual chance to compute."""
    engine = _build_price_engine()
    engine.tej_processor = object.__new__(TEJProcessor)
    engine.tej_processor.initialized = True
    engine.tej_processor.get_daily_prices = lambda coid, **kwargs: pd.DataFrame(
        {"date": pd.date_range("2026-09-01", periods=19, freq="D"), "close": [100.0] * 19}
    )

    finmind_dates = pd.date_range("2024-10-01", periods=484, freq="D")
    engine.finmind_processor = object.__new__(__import__("finmind_processor").FinMindProcessor)
    engine.finmind_processor.fetch_price_history = lambda *a, **k: pd.Series(
        [100.0] * 484, index=finmind_dates
    )

    result = engine.get_price_history("1101", period="2y")

    assert result is not None
    assert len(result) == 484  # from FinMind, not the rejected 19-row TEJ result


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
