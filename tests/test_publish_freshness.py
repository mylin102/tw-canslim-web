from importlib import import_module

import pytest


@pytest.mark.xfail(reason="Phase 4 publish freshness projection is not implemented yet")
def test_classify_freshness_uses_last_succeeded_at():
    module = import_module("publish_projection")

    freshness = module.classify_freshness(
        last_succeeded_at="2026-04-19T03:30:00Z",
        as_of="2026-04-19T12:00:00Z",
    )

    assert freshness["days_old"] == 0
    assert freshness["level"] == "today"
    assert freshness["label"] == "🟢 今日"


@pytest.mark.xfail(reason="Phase 4 publish freshness projection is not implemented yet")
def test_classify_freshness_keeps_one_to_two_day_records_visible():
    module = import_module("publish_projection")

    freshness = module.classify_freshness(
        last_succeeded_at="2026-04-17T08:00:00Z",
        as_of="2026-04-19T12:00:00Z",
    )

    assert freshness["days_old"] == 2
    assert freshness["level"] == "warning"
    assert freshness["label"] == "🟡 2天前"


@pytest.mark.xfail(reason="Phase 4 publish freshness projection is not implemented yet")
def test_classify_freshness_marks_three_day_gap_as_stale():
    module = import_module("publish_projection")

    freshness = module.classify_freshness(
        last_succeeded_at="2026-04-15T08:00:00Z",
        as_of="2026-04-19T12:00:00Z",
    )

    assert freshness["days_old"] >= 3
    assert freshness["level"] == "stale"
    assert freshness["label"] == "🔴 逾3天"
