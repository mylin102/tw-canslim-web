import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import feature_pipeline


def test_export_results_keeps_last_good_artifacts_when_provider_returns_empty(tmp_path, monkeypatch):
    monkeypatch.setattr(feature_pipeline, "OUTPUT_DIR", str(tmp_path))
    existing_features = {"2330": {"revenue_score": 6}}
    existing_rankings = {"2330": {"total_score": 6}}
    (tmp_path / "stock_features.json").write_text(
        json.dumps(existing_features), encoding="utf-8"
    )
    (tmp_path / "ranking.json").write_text(
        json.dumps(existing_rankings), encoding="utf-8"
    )

    pipeline = object.__new__(feature_pipeline.FeaturePipeline)
    pipeline.export_results({"stock_features": {}, "rankings": {}})

    assert json.loads((tmp_path / "stock_features.json").read_text(encoding="utf-8")) == existing_features
    assert json.loads((tmp_path / "ranking.json").read_text(encoding="utf-8")) == existing_rankings


def test_run_excludes_etfs_when_loading_symbols_from_data_json(tmp_path, monkeypatch):
    """2026-10-05: ETFs have no monthly-revenue concept, so every ETF symbol
    was guaranteed a wasted full TEJ/FinMind/yfinance fallback attempt --
    ~216 symbols' worth of dead time that contributed to the pipeline
    exceeding the workflow's 30-minute budget once FinMind's login bug
    (fixed in 3a15d12) stopped making those calls fail instantly."""
    monkeypatch.chdir(tmp_path)
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "data.json").write_text(
        json.dumps({
            "stocks": {
                "2330": {"is_etf": False},
                "0050": {"is_etf": True},
                "1101": {"is_etf": False},
            }
        }),
        encoding="utf-8",
    )

    pipeline = object.__new__(feature_pipeline.FeaturePipeline)
    seen_symbols = []

    def fake_process_stocks(symbols):
        seen_symbols.extend(symbols)
        return {"stock_features": {}, "rankings": {}}

    monkeypatch.setattr(pipeline, "process_stocks", fake_process_stocks)
    monkeypatch.setattr(pipeline, "export_results", lambda results: None)

    pipeline.run()

    assert sorted(seen_symbols) == ["1101", "2330"]


def test_export_results_accepts_first_successful_export(tmp_path, monkeypatch):
    monkeypatch.setattr(feature_pipeline, "OUTPUT_DIR", str(tmp_path))
    pipeline = object.__new__(feature_pipeline.FeaturePipeline)
    features = {"2330": {"revenue_score": 6}}
    rankings = {"2330": {"total_score": 6}}

    pipeline.export_results({"stock_features": features, "rankings": rankings})

    assert json.loads((tmp_path / "stock_features.json").read_text(encoding="utf-8")) == features
    assert json.loads((tmp_path / "ranking.json").read_text(encoding="utf-8")) == rankings
