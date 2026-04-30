"""
Deterministic provider retry and throttling policy contracts.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Callable


DEFAULT_NON_CORE_DAILY_BUDGET = 1000


@dataclass(frozen=True)
class ProviderPolicy:
    """Shared retry and throttling contract for one provider."""

    name: str
    max_attempts: int
    base_backoff_seconds: float
    min_interval_seconds: float
    quota_window_seconds: int
    max_requests_per_window: int
    retryable_statuses: tuple[int, ...]
    retryable_exception_names: tuple[str, ...]
    daily_budget_target: int = DEFAULT_NON_CORE_DAILY_BUDGET


class ProviderRetryExhaustedError(RuntimeError):
    """Raised when a provider exhausts its configured retry budget."""

    def __init__(self, provider_name: str, attempts: int, detail: str):
        super().__init__(f"{provider_name} retries exhausted after {attempts} attempts: {detail}")
        self.provider_name = provider_name
        self.attempts = attempts
        self.detail = detail


_POLICIES = {
    "requests": ProviderPolicy(
        name="requests",
        max_attempts=3,
        base_backoff_seconds=1.0,
        min_interval_seconds=0.2,
        quota_window_seconds=60,
        max_requests_per_window=120,
        retryable_statuses=(429, 500, 502, 503, 504),
        retryable_exception_names=("RequestException", "ConnectionError", "Timeout"),
    ),
    "finmind": ProviderPolicy(
        name="finmind",
        max_attempts=4,
        base_backoff_seconds=2.0,
        min_interval_seconds=1.0,
        quota_window_seconds=60,
        max_requests_per_window=30,
        retryable_statuses=(402, 429, 500, 502, 503, 504),
        retryable_exception_names=("ConnectionError", "Timeout", "RuntimeError"),
    ),
    "tej": ProviderPolicy(
        name="tej",
        max_attempts=3,
        base_backoff_seconds=3.0,
        min_interval_seconds=1.5,
        quota_window_seconds=60,
        max_requests_per_window=20,
        retryable_statuses=(429, 500, 502, 503, 504),
        retryable_exception_names=("ConnectionError", "Timeout", "RuntimeError"),
    ),
    "yfinance": ProviderPolicy(
        name="yfinance",
        max_attempts=3,
        base_backoff_seconds=1.5,
        min_interval_seconds=0.5,
        quota_window_seconds=60,
        max_requests_per_window=60,
        retryable_statuses=(429, 500, 502, 503, 504),
        retryable_exception_names=("HTTPError", "ConnectionError", "Timeout"),
    ),
}


def get_provider_policy(provider_name: str) -> ProviderPolicy:
    """Return the explicit policy for a known provider."""
    normalized = provider_name.strip().lower()
    if normalized not in _POLICIES:
        raise KeyError(f"Unknown provider policy: {provider_name}")
    return _POLICIES[normalized]


def compute_backoff_seconds(policy: ProviderPolicy, attempt: int) -> float:
    """Compute deterministic exponential backoff for a retry attempt."""
    if attempt < 1:
        raise ValueError("attempt must be >= 1")
    return policy.base_backoff_seconds * (2 ** (attempt - 1))


def call_with_provider_policy(
    provider_name: str,
    operation: Callable[[], Any],
    *,
    runtime_state: dict[str, Any] | None = None,
    should_retry: Callable[[Any], bool] | None = None,
    max_attempts: int | None = None,
    sleep_fn: Callable[[float], None] = time.sleep,
    monotonic_fn: Callable[[], float] = time.monotonic,
) -> Any:
    """Execute an operation with shared pacing, backoff, and retry accounting."""
    policy = get_provider_policy(provider_name)
    metrics = _ensure_runtime_metrics(runtime_state)
    attempt_limit = policy.max_attempts if max_attempts is None else max(1, min(policy.max_attempts, max_attempts))

    for attempt in range(1, attempt_limit + 1):
        _wait_for_provider_slot(
            policy,
            runtime_state=metrics,
            sleep_fn=sleep_fn,
            monotonic_fn=monotonic_fn,
        )

        try:
            result = operation()
        except Exception as exc:
            if not _is_retryable_exception(policy, exc):
                raise
            _record_retry_attempt(metrics)
            if attempt >= attempt_limit:
                _record_retry_failure(metrics)
                raise ProviderRetryExhaustedError(policy.name, attempt, type(exc).__name__) from exc
            _sleep_with_accounting(
                compute_backoff_seconds(policy, attempt),
                runtime_state=metrics,
                sleep_fn=sleep_fn,
            )
            continue

        if should_retry is not None and should_retry(result):
            _record_retry_attempt(metrics)
            if attempt >= attempt_limit:
                _record_retry_failure(metrics)
                status_code = getattr(result, "status_code", "unknown")
                raise ProviderRetryExhaustedError(policy.name, attempt, f"status {status_code}")
            _sleep_with_accounting(
                compute_backoff_seconds(policy, attempt),
                runtime_state=metrics,
                sleep_fn=sleep_fn,
            )
            continue

        return result

    raise ProviderRetryExhaustedError(policy.name, attempt_limit, "unreachable retry loop termination")


def _ensure_runtime_metrics(runtime_state: dict[str, Any] | None) -> dict[str, Any]:
    """Ensure provider runtime metrics and pacing state exist."""
    metrics = runtime_state if runtime_state is not None else {}
    metrics.setdefault("retry_attempts", 0)
    metrics.setdefault("retry_failures", 0)
    metrics.setdefault("provider_wait_seconds", 0.0)
    metrics.setdefault("_provider_policy_state", {})
    return metrics


def _wait_for_provider_slot(
    policy: ProviderPolicy,
    *,
    runtime_state: dict[str, Any],
    sleep_fn: Callable[[float], None],
    monotonic_fn: Callable[[], float],
) -> None:
    """Honor provider pacing before dispatching the next request."""
    provider_state = runtime_state["_provider_policy_state"].setdefault(
        policy.name,
        {
            "last_request_monotonic": None,
            "window_started_monotonic": None,
            "window_request_count": 0,
        },
    )

    now = monotonic_fn()
    wait_seconds = 0.0

    last_request = provider_state["last_request_monotonic"]
    if last_request is not None:
        wait_seconds = max(wait_seconds, policy.min_interval_seconds - max(0.0, now - last_request))

    window_started = provider_state["window_started_monotonic"]
    window_count = provider_state["window_request_count"]
    if window_started is None or now - window_started >= policy.quota_window_seconds:
        provider_state["window_started_monotonic"] = now
        provider_state["window_request_count"] = 0
    elif window_count >= policy.max_requests_per_window:
        wait_seconds = max(wait_seconds, policy.quota_window_seconds - (now - window_started))

    if wait_seconds > 0:
        _sleep_with_accounting(wait_seconds, runtime_state=runtime_state, sleep_fn=sleep_fn)
        now = monotonic_fn()
        if now - provider_state["window_started_monotonic"] >= policy.quota_window_seconds:
            provider_state["window_started_monotonic"] = now
            provider_state["window_request_count"] = 0

    if provider_state["window_started_monotonic"] is None:
        provider_state["window_started_monotonic"] = now
    provider_state["last_request_monotonic"] = now
    provider_state["window_request_count"] += 1


def _sleep_with_accounting(
    seconds: float,
    *,
    runtime_state: dict[str, Any],
    sleep_fn: Callable[[float], None],
) -> None:
    """Sleep for a positive duration and track provider wait time."""
    wait_seconds = max(0.0, float(seconds))
    if wait_seconds <= 0:
        return
    sleep_fn(wait_seconds)
    runtime_state["provider_wait_seconds"] += wait_seconds


def _record_retry_attempt(runtime_state: dict[str, Any]) -> None:
    """Track one retryable failure attempt."""
    runtime_state["retry_attempts"] += 1


def _record_retry_failure(runtime_state: dict[str, Any]) -> None:
    """Track one exhausted retry sequence."""
    runtime_state["retry_failures"] += 1


def _is_retryable_exception(policy: ProviderPolicy, exc: Exception) -> bool:
    """Return whether an exception matches the provider retry contract."""
    err_str = str(exc)
    # Explicitly DO NOT retry permission or quota errors that won't resolve with time
    if any(keyword in err_str for keyword in ["Forbidden", "ForbiddenError", "403"]):
        return False

    class_names = {cls.__name__ for cls in type(exc).__mro__}
    return any(name in class_names for name in policy.retryable_exception_names)
