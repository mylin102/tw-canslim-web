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


def test_verify_local_publish_rebuild_bundle_uses_validated_helper(
    monkeypatch: pytest.MonkeyPatch,
    publish_paths,
    stock_payload_factory,
    read_artifact,
):
    root = publish_paths["root"]
    docs_dir = publish_paths["docs"]
    monkeypatch.chdir(root)

    module = load_module("verify_local")
    payload = stock_payload_factory("verify-run")

    result = module.publish_rebuild_bundle(payload, ["2330"])

    data_payload = read_artifact(docs_dir / "data.json", "data")
    summary_payload = read_artifact(docs_dir / "update_summary.json", "update_summary")

    assert result["run_id"] == "verify-run"
    assert data_payload["run_id"] == "verify-run"
    assert summary_payload["data_stats"]["updated_stocks"] == 1
    assert "2330" in summary_payload["description"]
    assert "except Exception as exc" in Path(module.__file__).read_text(encoding="utf-8")


def test_update_single_stock_publishes_base_and_derived_bundle(
    monkeypatch: pytest.MonkeyPatch,
    publish_paths,
    stock_payload_factory,
    read_artifact,
):
    root = publish_paths["root"]
    docs_dir = publish_paths["docs"]
    monkeypatch.chdir(root)
    write_json(docs_dir / "data_base.json", stock_payload_factory("seed-run"))

    module = load_module("update_single_stock")
    updater = module.SingleStockUpdater.__new__(module.SingleStockUpdater)
    updater.root_dir = str(root)
    updater.ticker_info = {"2330": {"name": "TSMC", "suffix": ".TW"}}
    updater.excel_ratings = {"2330": {"eps_rating": 90}}
    updater.fund_holdings = {"2330": {"funds": 3}}
    updater.industry_data = {"2330": {"industry": "Semis"}}
    updater.tej_processor = types.SimpleNamespace(is_etf=lambda ticker: False)
    updater.data_base_path = str(docs_dir / "data_base.json")

    monkeypatch.setattr(module, "get_market_prices", lambda: [1, 2, 3])
    monkeypatch.setattr(module, "get_trading_dates", lambda: ["20260418"])
    monkeypatch.setattr(module, "fetch_inst_all", lambda date_str: {"2330": {"foreign_net": 1, "trust_net": 2, "dealer_net": 3}})
    monkeypatch.setattr(module, "download_price_history", lambda symbol: [10, 11, 12])
    monkeypatch.setattr(module, "calculate_mansfield_rs", lambda prices, market: 88.4)
    monkeypatch.setattr(module, "calculate_rs_trend", lambda prices, market: "up")
    monkeypatch.setattr(module, "check_n_factor", lambda prices: True)
    monkeypatch.setattr(module, "calculate_l_factor", lambda mansfield_rs: True)
    monkeypatch.setattr(module, "compute_canslim_score", lambda factors: 92)
    monkeypatch.setattr(module, "compute_canslim_score_etf", lambda factors: 92)
    monkeypatch.setattr(module, "calculate_volatility_grid", lambda prices, is_etf=False: {"mode": "swing"})

    if "docs/stock_index.json" not in Path(module.__file__).read_text(encoding="utf-8"):
        pytest.xfail("Plan 04-03 Task 2 wires single-stock publishes into the Phase 4 bundle")

    assert updater.update_stock("2330") is True

    base_payload = read_artifact(docs_dir / "data_base.json", "data_base")
    data_payload = read_artifact(docs_dir / "data.json", "data")
    light_payload = read_artifact(docs_dir / "data_light.json", "data_light")
    stock_index_payload = read_artifact(docs_dir / "stock_index.json", "stock_index")
    summary_payload = read_artifact(docs_dir / "update_summary.json", "update_summary")

    assert base_payload["stocks"]["2330"]["canslim"]["score"] == 92
    assert data_payload["run_id"] == light_payload["run_id"] == summary_payload["run_id"]
    assert stock_index_payload["stocks"]["2330"]["symbol"] == "2330"
    assert "docs/data_base.json" in summary_payload["published_targets"]
