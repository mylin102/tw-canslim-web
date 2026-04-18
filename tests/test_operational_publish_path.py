import importlib
import json
import sys
import types
from pathlib import Path

import pytest

from publish_safety import PublishTransactionError


def load_module(module_name: str):
    sys.modules.pop(module_name, None)
    return importlib.import_module(module_name)


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def install_finmind_stub(monkeypatch: pytest.MonkeyPatch, responses: dict[str, object]) -> None:
    class StubProcessor:
        available = True

        def fetch_recent_trading_days(self, stock_id: str, days: int = 20):
            response = responses.get(stock_id, {})
            if isinstance(response, Exception):
                raise response
            return response

    stub_module = types.SimpleNamespace(FinMindProcessor=StubProcessor)
    monkeypatch.setitem(sys.modules, "finmind_processor", stub_module)


def test_quick_auto_update_enhanced_publishes_locked_bundle_and_summary(
    monkeypatch: pytest.MonkeyPatch,
    publish_paths,
    stock_payload_factory,
    read_artifact,
):
    root = publish_paths["root"]
    docs_dir = publish_paths["docs"]
    run_id = "seed-run"
    payload = stock_payload_factory(run_id)
    payload["stocks"]["2317"]["institutional"] = []
    write_json(docs_dir / "data.json", payload)

    install_finmind_stub(
        monkeypatch,
        {
            "2330": {
                "20260418": {
                    "date": "20260418",
                    "foreign_net": 9,
                    "trust_net": 8,
                    "dealer_net": 7,
                }
            },
            "2317": RuntimeError("FinMind unavailable"),
        },
    )
    monkeypatch.chdir(root)

    module = load_module("quick_auto_update_enhanced")

    assert module.main() is True

    data_payload = read_artifact(docs_dir / "data.json", "data")
    light_payload = read_artifact(docs_dir / "data_light.json", "data_light")
    summary_payload = read_artifact(docs_dir / "update_summary.json", "update_summary")

    assert data_payload["run_id"] == light_payload["run_id"] == summary_payload["run_id"]
    assert data_payload["stocks"]["2330"]["institutional"][0]["foreign_net"] == 9
    assert summary_payload["data_stats"]["retry_count"] >= 1
    assert "2317" in summary_payload["data_stats"]["failed_tickers"]
    assert summary_payload["next_action"]
    assert (root / "backups" / "last_good").exists()


def test_batch_update_institutional_publishes_summary_with_retry_metadata(
    monkeypatch: pytest.MonkeyPatch,
    publish_paths,
    stock_payload_factory,
    read_artifact,
):
    root = publish_paths["root"]
    docs_dir = publish_paths["docs"]
    payload = stock_payload_factory("seed-run")
    write_json(docs_dir / "data.json", payload)

    install_finmind_stub(
        monkeypatch,
        {
            "2330": {
                "20260418": {
                    "date": "20260418",
                    "foreign_net": 5,
                    "trust_net": 4,
                    "dealer_net": 3,
                }
            },
            "2317": RuntimeError("request failed"),
        },
    )
    monkeypatch.chdir(root)

    module = load_module("batch_update_institutional")
    updater = module.BatchInstitutionalUpdater()

    result = updater.update_batch(["2330", "2317"], offset_day=1)

    assert result["success"] is True

    data_payload = read_artifact(docs_dir / "data.json", "data")
    summary_payload = read_artifact(docs_dir / "update_summary.json", "update_summary")

    assert data_payload["stocks"]["2330"]["institutional"][0]["foreign_net"] == 5
    assert summary_payload["data_stats"]["retry_count"] >= 1
    assert "2317" in summary_payload["data_stats"]["failed_tickers"]
    assert summary_payload["next_batch"]["offset_day"] == 2
    assert summary_payload["next_action"]


def test_quick_auto_update_enhanced_returns_failure_when_bundle_publish_fails(
    monkeypatch: pytest.MonkeyPatch,
    publish_paths,
    stock_payload_factory,
    caplog: pytest.LogCaptureFixture,
):
    root = publish_paths["root"]
    docs_dir = publish_paths["docs"]
    write_json(docs_dir / "data.json", stock_payload_factory("seed-run"))
    install_finmind_stub(monkeypatch, {"2330": {}, "2317": {}})
    monkeypatch.chdir(root)

    module = load_module("quick_auto_update_enhanced")
    monkeypatch.setattr(
        module,
        "publish_artifact_bundle",
        lambda *args, **kwargs: (_ for _ in ()).throw(PublishTransactionError("boom")),
    )

    with caplog.at_level("ERROR"):
        assert module.main() is False

    assert "publish" in caplog.text.lower()


def test_batch_update_institutional_returns_failure_when_bundle_publish_fails(
    monkeypatch: pytest.MonkeyPatch,
    publish_paths,
    stock_payload_factory,
    caplog: pytest.LogCaptureFixture,
):
    root = publish_paths["root"]
    docs_dir = publish_paths["docs"]
    write_json(docs_dir / "data.json", stock_payload_factory("seed-run"))
    install_finmind_stub(monkeypatch, {"2330": {}, "2317": {}})
    monkeypatch.chdir(root)

    module = load_module("batch_update_institutional")
    updater = module.BatchInstitutionalUpdater()
    monkeypatch.setattr(
        module,
        "publish_artifact_bundle",
        lambda *args, **kwargs: (_ for _ in ()).throw(PublishTransactionError("boom")),
    )

    with caplog.at_level("ERROR"):
        result = updater.update_batch(["2330", "2317"], offset_day=0)

    assert result["success"] is False
    assert "publish" in caplog.text.lower()
