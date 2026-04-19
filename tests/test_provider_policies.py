from importlib import import_module

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


def test_default_non_core_budget_remains_one_thousand():
    module = load_provider_policies_module()

    assert module.DEFAULT_NON_CORE_DAILY_BUDGET == 1000


def test_unknown_provider_fails_closed():
    module = load_provider_policies_module()

    with pytest.raises(KeyError):
        module.get_provider_policy("unknown-provider")
