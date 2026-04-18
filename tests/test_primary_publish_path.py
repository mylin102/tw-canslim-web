import json
from importlib import import_module
from pathlib import Path
from types import SimpleNamespace

import pandas as pd

import pytest


PRIMARY_PUBLISH_SCRIPTS = (
    "export_canslim.py",
    "export_dashboard_data.py",
)


@pytest.mark.parametrize("script_name", PRIMARY_PUBLISH_SCRIPTS)
def test_primary_publish_script_exists(repo_root: Path, script_name: str):
    assert (repo_root / script_name).exists()


@pytest.mark.skip(reason="Plan 01-02 migrates primary writers to publish_artifact_bundle")
@pytest.mark.parametrize("script_name", PRIMARY_PUBLISH_SCRIPTS)
def test_primary_publish_script_uses_bundle_helper(repo_root: Path, script_name: str):
    source = (repo_root / script_name).read_text(encoding="utf-8")
    assert "publish_artifact_bundle" in source


def _load_module(name: str):
    return import_module(name)


def _build_engine(module, tickers: tuple[str, ...] = ("1101", "2330", "3565", "6770", "2303", "8069", "6805")):
    engine = object.__new__(module.CanslimEngine)
    engine.output_data = {"last_updated": "", "stocks": {}}
    engine.ticker_info = {ticker: {"name": f"Stock {ticker}", "suffix": ".TW"} for ticker in tickers}
    engine.excel_processor = None
    engine.finmind_processor = None
    engine.tej_processor = SimpleNamespace(
        initialized=False,
        calculate_canslim_c_and_a=lambda ticker: {},
        get_quarterly_financials=lambda ticker: None,
    )
    engine.etf_list = {}
    engine.excel_ratings = None
    engine.fund_holdings = None
    engine.industry_data = None
    engine.industry_strength = None
    return engine


def _stub_engine_dependencies(monkeypatch: pytest.MonkeyPatch, module, engine, *, broken_ticker: str | None = None):
    def fake_history(ticker: str, period: str = "2y"):
        return pd.Series([100.0, 105.0, 110.0, 120.0, 130.0] * 30)

    monkeypatch.setattr(engine, "fetch_institutional_data_finmind", lambda ticker, days=60: [{"date": "20260418", "foreign_net": 5, "trust_net": 1, "dealer_net": 0}])

    def fake_financial_data(ticker: str):
        if ticker == broken_ticker:
            return None
        return {
            "price": 100.0,
            "market_cap": 1000000.0,
            "sharesOutstanding": 10000.0,
            "volume": 5000.0,
            "avg_volume": 1000.0,
        }

    monkeypatch.setattr(engine, "fetch_financial_data", fake_financial_data)
    monkeypatch.setattr(engine, "get_price_history", fake_history)
    monkeypatch.setattr(engine, "get_market_return_6m", lambda: 0.1)
    monkeypatch.setattr(module, "check_n_factor", lambda stock_hist: True)
    monkeypatch.setattr(module, "calculate_accumulation_strength", lambda chip_df, total_shares, days=20: 0.0)
    monkeypatch.setattr(module, "calculate_mansfield_rs", lambda stock_hist, market_hist: 88.1)
    monkeypatch.setattr(module, "calculate_l_factor", lambda mansfield_rs: True)
    monkeypatch.setattr(module, "compute_canslim_score", lambda factors, institutional_strength=0.0: 90)
    monkeypatch.setattr(module, "compute_canslim_score_etf", lambda factors, institutional_strength=0.0: 90)


def test_export_canslim_resume_rebuilds_incompatible_records_and_publishes_summary_bundle(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    module = _load_module("export_canslim")
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    data_path = docs_dir / "data.json"
    summary_path = docs_dir / "update_summary.json"
    data_path.write_text(json.dumps({"stocks": {"2330": {"symbol": "2330", "name": "Old"}}}), encoding="utf-8")

    engine = _build_engine(module)
    _stub_engine_dependencies(monkeypatch, module, engine)

    load_calls = []
    validated = []
    published = {}

    def fake_load_artifact_json(path: str, *, artifact_kind: str, logger=None):
        load_calls.append((path, artifact_kind))
        return {
            "schema_version": "1.0",
            "last_updated": "2026-04-18 20:00:00",
            "run_id": "resume-run",
            "stocks": {
                "2330": {
                    "schema_version": "1.0",
                    "symbol": "2330",
                    "name": "Resume 2330",
                    "canslim": {
                        "score": 95,
                        "grid_strategy": {"mode": "swing"},
                    },
                    "institutional": [],
                }
            },
        }

    def fake_validate_resume_stock_entry(stock_id: str, stock_entry: dict, **kwargs):
        validated.append(stock_id)
        raise module.PublishValidationError(f"{stock_id} missing mansfield_rs")

    def fake_publish_artifact_bundle(bundle: dict[str, dict], **kwargs):
        published["bundle"] = bundle
        return {"published_targets": list(bundle), "run_id": "run-1", "snapshot_dir": str(tmp_path / "backups" / "last_good" / "run-1")}

    monkeypatch.setattr(module, "OUTPUT_DIR", str(docs_dir))
    monkeypatch.setattr(module, "DATA_FILE", str(data_path))
    monkeypatch.setattr(module, "load_artifact_json", fake_load_artifact_json)
    monkeypatch.setattr(module, "validate_resume_stock_entry", fake_validate_resume_stock_entry)
    monkeypatch.setattr(module, "publish_artifact_bundle", fake_publish_artifact_bundle)

    engine.run()

    assert load_calls == [(str(data_path), "data")]
    assert validated == ["2330"]
    bundle = published["bundle"]
    assert set(bundle) == {str(data_path), str(summary_path)}
    data_payload = bundle[str(data_path)]["payload"]
    assert "mansfield_rs" in data_payload["stocks"]["2330"]["canslim"]
    summary_payload = bundle[str(summary_path)]["payload"]
    assert summary_payload["stats"]["resume_rejected"] == 1


def test_export_canslim_tracks_retry_attempts_and_stock_failures_in_summary(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    module = _load_module("export_canslim")
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    data_path = docs_dir / "data.json"
    summary_path = docs_dir / "update_summary.json"

    engine = _build_engine(module)
    _stub_engine_dependencies(monkeypatch, module, engine, broken_ticker="3565")

    class DummyRequestException(module.requests.RequestException):
        pass

    attempts = {"count": 0}

    def fake_get(url: str, params=None, timeout=15):
        attempts["count"] += 1
        raise DummyRequestException("provider unavailable")

    published = {}

    def fake_publish_artifact_bundle(bundle: dict[str, dict], **kwargs):
        published["bundle"] = bundle
        return {"published_targets": list(bundle), "run_id": "run-2", "snapshot_dir": str(tmp_path / "backups" / "last_good" / "run-2")}

    monkeypatch.setattr(module, "OUTPUT_DIR", str(docs_dir))
    monkeypatch.setattr(module, "DATA_FILE", str(data_path))
    monkeypatch.setattr(module.requests, "get", fake_get)
    monkeypatch.setattr(module.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(module, "publish_artifact_bundle", fake_publish_artifact_bundle)

    assert engine._fetch_with_retry("https://example.com/fail", max_retries=2) is None
    engine.run()

    assert attempts["count"] == 2
    summary_payload = published["bundle"][str(summary_path)]["payload"]
    assert summary_payload["stats"]["retry_attempts"] == 2
    assert summary_payload["stats"]["retry_failures"] == 1
    assert summary_payload["stats"]["stock_failures"] == 1


def test_export_canslim_reraises_publish_transaction_failures(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    module = _load_module("export_canslim")
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    data_path = docs_dir / "data.json"

    engine = _build_engine(module)
    _stub_engine_dependencies(monkeypatch, module, engine)

    monkeypatch.setattr(module, "OUTPUT_DIR", str(docs_dir))
    monkeypatch.setattr(module, "DATA_FILE", str(data_path))
    monkeypatch.setattr(
        module,
        "publish_artifact_bundle",
        lambda bundle, **kwargs: (_ for _ in ()).throw(module.PublishTransactionError("publish failed")),
    )

    with pytest.raises(module.PublishTransactionError):
        engine.run()


def test_export_dashboard_data_publishes_artifact_aware_bundle(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    module = _load_module("export_dashboard_data")
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    fused_path = tmp_path / "signals.parquet"
    fused_path.write_text("placeholder", encoding="utf-8")
    output_path = docs_dir / "data.json"
    published = {}

    dataframe = pd.DataFrame(
        [
            {
                "date": pd.Timestamp("2026-04-18"),
                "stock_id": "2330",
                "C": True,
                "I": True,
                "N": True,
                "S": True,
                "score": 95,
                "rs_rating": 88.5,
                "fund_change": 4.2,
                "smr_rating": "A",
            }
        ]
    )

    monkeypatch.setattr(module, "FUSED_DATA_PATH", str(fused_path))
    monkeypatch.setattr(module, "OUTPUT_JSON_PATH", str(output_path))
    monkeypatch.setattr(module.pd, "read_parquet", lambda path: dataframe)
    monkeypatch.setattr(module, "get_all_tw_tickers", lambda: {"2330": {"name": "TSMC", "suffix": ".TW"}})
    monkeypatch.setattr(
        module,
        "publish_artifact_bundle",
        lambda bundle, **kwargs: published.setdefault("bundle", bundle),
        raising=False,
    )

    module.export_data()

    bundle = published["bundle"]
    payload = bundle[str(output_path)]["payload"]
    assert bundle[str(output_path)]["artifact_kind"] == "data"
    assert payload["schema_version"] == "1.0"
    assert payload["artifact_kind"] == "data"
    assert payload["run_id"]
    assert payload["generated_at"]
    assert payload["stocks"]["2330"]["canslim"]["mansfield_rs"] == pytest.approx(88.5)
    assert payload["stocks"]["2330"]["canslim"]["grid_strategy"]["mode"] == "dashboard_snapshot"


def test_export_dashboard_data_raises_on_missing_input(monkeypatch: pytest.MonkeyPatch):
    module = _load_module("export_dashboard_data")
    logger_calls = []

    monkeypatch.setattr(module, "FUSED_DATA_PATH", "missing.parquet")
    monkeypatch.setattr(module.os.path, "exists", lambda path: False)
    monkeypatch.setattr(module.logger, "exception", lambda message, *args: logger_calls.append((message, args)))

    with pytest.raises(FileNotFoundError):
        module.export_data()

    assert logger_calls


def test_export_dashboard_data_reraises_publish_failures(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    module = _load_module("export_dashboard_data")
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    fused_path = tmp_path / "signals.parquet"
    fused_path.write_text("placeholder", encoding="utf-8")
    output_path = docs_dir / "data.json"

    dataframe = pd.DataFrame(
        [
            {
                "date": pd.Timestamp("2026-04-18"),
                "stock_id": "2330",
                "C": True,
                "I": True,
                "N": True,
                "S": True,
                "score": 95,
                "rs_rating": 88.5,
                "fund_change": 4.2,
                "smr_rating": "A",
            }
        ]
    )

    monkeypatch.setattr(module, "FUSED_DATA_PATH", str(fused_path))
    monkeypatch.setattr(module, "OUTPUT_JSON_PATH", str(output_path))
    monkeypatch.setattr(module.pd, "read_parquet", lambda path: dataframe)
    monkeypatch.setattr(module, "get_all_tw_tickers", lambda: {"2330": {"name": "TSMC", "suffix": ".TW"}})
    monkeypatch.setattr(
        module,
        "publish_artifact_bundle",
        lambda bundle, **kwargs: (_ for _ in ()).throw(module.PublishTransactionError("publish failed")),
        raising=False,
    )

    with pytest.raises(module.PublishTransactionError):
        module.export_data()
