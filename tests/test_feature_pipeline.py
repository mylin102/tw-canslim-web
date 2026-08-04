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


def test_export_results_accepts_first_successful_export(tmp_path, monkeypatch):
    monkeypatch.setattr(feature_pipeline, "OUTPUT_DIR", str(tmp_path))
    pipeline = object.__new__(feature_pipeline.FeaturePipeline)
    features = {"2330": {"revenue_score": 6}}
    rankings = {"2330": {"total_score": 6}}

    pipeline.export_results({"stock_features": features, "rankings": rankings})

    assert json.loads((tmp_path / "stock_features.json").read_text(encoding="utf-8")) == features
    assert json.loads((tmp_path / "ranking.json").read_text(encoding="utf-8")) == rankings
