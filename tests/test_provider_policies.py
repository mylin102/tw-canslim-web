from importlib import import_module
from types import SimpleNamespace

import pandas as pd
import pytest


def load_provider_policies_module():
    return import_module("provider_policies")


@pytest.mark.parametrize("provider_name", ["requests", "finmind", "tej", "yfinance"])
def test_get_provider_policy_returns_explicit_provider_contracts(provider_name):
    module = load_provider_policies_module()

    policy = module.get_provider_policy(provider_name)

    assert policy.name == provider_name
    assert policy.max_attempts >= 1
    assert policy.base_backoff_seconds > 0
    assert policy.min_interval_seconds > 0
    assert policy.quota_window_seconds > 0
    assert policy.max_requests_per_window > 0


def test_compute_backoff_seconds_is_deterministic_and_positive():
    module = load_provider_policies_module()
    policy = module.get_provider_policy("requests")

    first = module.compute_backoff_seconds(policy, attempt=1)
    second = module.compute_backoff_seconds(policy, attempt=2)
    repeated = module.compute_backoff_seconds(policy, attempt=2)

    assert first > 0
    assert second > first
    assert repeated == second


def test_call_with_provider_policy_applies_pacing_and_retry_accounting():
    module = load_provider_policies_module()
    policy = module.get_provider_policy("requests")

    runtime_state = {
        "_provider_policy_state": {
            "requests": {
                "last_request_monotonic": 0.0,
                "window_started_monotonic": 0.0,
                "window_request_count": 1,
            }
        }
    }
    sleeps = []
    clock = {"now": 0.0}
    responses = [SimpleNamespace(status_code=503), SimpleNamespace(status_code=200)]

    def fake_sleep(seconds: float):
        sleeps.append(seconds)
        clock["now"] += seconds

    def fake_monotonic():
        return clock["now"]

    result = module.call_with_provider_policy(
        "requests",
        lambda: responses.pop(0),
        runtime_state=runtime_state,
        sleep_fn=fake_sleep,
        monotonic_fn=fake_monotonic,
        should_retry=lambda response: response.status_code in policy.retryable_statuses,
    )

    assert result.status_code == 200
    assert runtime_state["retry_attempts"] == 1
    assert runtime_state["retry_failures"] == 0
    assert runtime_state["provider_wait_seconds"] == pytest.approx(
        policy.min_interval_seconds + module.compute_backoff_seconds(policy, attempt=1)
    )


def test_export_canslim_routes_requests_fetch_retry_through_shared_policy(monkeypatch):
    module = import_module("export_canslim")

    class DummyResponse:
        status_code = 200

        def raise_for_status(self):
            return None

    engine = object.__new__(module.CanslimEngine)
    engine.failure_stats = {
        "retry_attempts": 0,
        "retry_failures": 0,
        "resume_rejected": 0,
        "stock_failures": 0,
        "provider_wait_seconds": 0.0,
    }
    engine.failure_details = []
    engine.output_data = {"stocks": {}}
    observed = []

    monkeypatch.setattr(
        module,
        "call_with_provider_policy",
        lambda provider_name, operation, **kwargs: observed.append((provider_name, kwargs.get("runtime_state"))) or operation(),
        raising=False,
    )
    monkeypatch.setattr(module.requests, "get", lambda *args, **kwargs: DummyResponse())

    response = engine._fetch_with_retry("https://example.com/provider", max_retries=2)

    assert response is not None
    assert observed == [("requests", engine.failure_stats)]


def test_finmind_fetch_institutional_investors_uses_shared_policy_wrapper(monkeypatch):
    module = import_module("finmind_processor")
    observed = []
    expected = pd.DataFrame([{"date": "2026-04-19", "name": "Foreign_Investor", "buy": 1, "sell": 0}])

    monkeypatch.setattr(
        module,
        "call_with_provider_policy",
        lambda provider_name, operation, **kwargs: observed.append(provider_name) or operation(),
        raising=False,
    )
    monkeypatch.setattr(
        module,
        "DataLoader",
        lambda: SimpleNamespace(taiwan_stock_institutional_investors=lambda **kwargs: expected),
        raising=False,
    )

    processor = module.FinMindProcessor()

    assert processor.fetch_institutional_investors("2330", "2026-04-01", "2026-04-19") is expected
    assert observed == ["finmind"]


def test_tej_processor_routes_table_fetches_through_shared_policy(monkeypatch):
    module = import_module("tej_processor")
    observed = []
    frame = pd.DataFrame(
        [
            {
                "coid": "2330",
                "mdate": "2026-04-19",
                "open_d": 1,
                "high_d": 2,
                "low_d": 1,
                "close_d": 2,
                "vol_nk": 3,
            }
        ]
    )

    monkeypatch.setattr(
        module,
        "call_with_provider_policy",
        lambda provider_name, operation, **kwargs: observed.append(provider_name) or operation(),
        raising=False,
    )
    monkeypatch.setattr(
        module,
        "tejapi",
        SimpleNamespace(
            get=lambda table, **kwargs: frame,
            ApiConfig=SimpleNamespace(api_key=None, ignoretz=False),
        ),
        raising=False,
    )

    processor = module.TEJProcessor(api_key="test-key")

    assert processor.get_daily_prices("2330") is not None
    assert processor.get_company_info("2330") is not None
    assert observed == ["tej", "tej"]


def test_yfinance_price_history_helper_uses_shared_policy(monkeypatch):
    module = import_module("yfinance_provider")
    observed = []
    frame = pd.DataFrame({"Close": [100.0, 101.0]})

    monkeypatch.setattr(
        module,
        "call_with_provider_policy",
        lambda provider_name, operation, **kwargs: observed.append(provider_name) or operation(),
        raising=False,
    )
    monkeypatch.setattr(
        module.yf,
        "Ticker",
        lambda ticker: SimpleNamespace(history=lambda **kwargs: frame),
    )

    result = module.get_price_history_with_policy("2330.TW", period="1mo")

    assert list(result) == [100.0, 101.0]
    assert observed == ["yfinance"]


def test_default_non_core_budget_remains_one_thousand():
    module = load_provider_policies_module()

    assert module.DEFAULT_NON_CORE_DAILY_BUDGET == 1000


def test_unknown_provider_fails_closed():
    module = load_provider_policies_module()

    with pytest.raises(KeyError):
        module.get_provider_policy("unknown-provider")
