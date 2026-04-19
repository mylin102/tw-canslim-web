import json
from importlib import import_module
from pathlib import Path

import pytest


def load_publish_safety():
    return import_module("publish_safety")


def test_validate_artifact_payload_distinguishes_stock_and_summary_contracts(
    stock_payload_factory,
    summary_payload_factory,
):
    module = load_publish_safety()
    stock_payload = stock_payload_factory("run-a")
    summary_payload = summary_payload_factory("run-a")

    module.validate_artifact_payload(stock_payload, artifact_kind="data")
    module.validate_artifact_payload(stock_payload, artifact_kind="data_base")
    module.validate_artifact_payload(summary_payload, artifact_kind="update_summary")

    with pytest.raises(module.PublishValidationError):
        module.validate_artifact_payload(summary_payload, artifact_kind="data")

    with pytest.raises(module.PublishValidationError):
        module.validate_artifact_payload(stock_payload, artifact_kind="update_summary")


def test_validate_resume_stock_entry_rejects_missing_nested_contract_fields(sample_stock_entry):
    module = load_publish_safety()
    valid_entry = sample_stock_entry("2330")
    module.validate_resume_stock_entry("2330", valid_entry)

    wrong_version = sample_stock_entry("2330", schema_version="0.9")
    with pytest.raises(module.PublishValidationError):
        module.validate_resume_stock_entry("2330", wrong_version)

    missing_grid = sample_stock_entry("2330")
    del missing_grid["canslim"]["grid_strategy"]
    with pytest.raises(module.PublishValidationError):
        module.validate_resume_stock_entry("2330", missing_grid)

    missing_rs = sample_stock_entry("2330")
    del missing_rs["canslim"]["mansfield_rs"]
    with pytest.raises(module.PublishValidationError):
        module.validate_resume_stock_entry("2330", missing_rs)


def test_validate_artifact_payload_accepts_stock_index_contract(stock_index_payload_factory):
    module = load_publish_safety()

    module.validate_artifact_payload(
        stock_index_payload_factory("run-index"),
        artifact_kind="stock_index",
    )


def test_validate_artifact_payload_accepts_leaders_contract():
    module = load_publish_safety()
    valid_payload = {
        "schema_version": 1,
        "date": "2026-04-19",
        "generated_at": "2026-04-19T06:30:00Z",
        "universe": [
            {
                "symbol": "2330",
                "name": "台積電",
                "rs_rating": 92,
                "composite_score": 0.87,
                "tags": ["leader", "breakout_candidate"]
            }
        ]
    }
    module.validate_artifact_payload(valid_payload, artifact_kind="leaders")

    with pytest.raises(module.PublishValidationError, match="schema_version mismatch"):
        invalid_version = valid_payload.copy()
        invalid_version["schema_version"] = 2
        module.validate_artifact_payload(invalid_version, artifact_kind="leaders")

    with pytest.raises(module.PublishValidationError, match="missing required field: composite_score"):
        invalid_entry = {
            "schema_version": 1,
            "date": "2026-04-19",
            "universe": [{"symbol": "2330", "rs_rating": 90, "tags": []}]
        }
        module.validate_artifact_payload(invalid_entry, artifact_kind="leaders")


def test_checked_in_update_summary_uses_phase4_contract(repo_root: Path):
    module = load_publish_safety()
    payload = json.loads((repo_root / "docs/update_summary.json").read_text(encoding="utf-8"))

    module.validate_artifact_payload(payload, artifact_kind="update_summary")


def test_checked_in_phase4_publish_bundle_shares_run_id(repo_root: Path):
    docs_dir = repo_root / "docs"
    data_payload = json.loads((docs_dir / "data.json").read_text(encoding="utf-8"))
    stock_index_payload = json.loads((docs_dir / "stock_index.json").read_text(encoding="utf-8"))
    summary_payload = json.loads((docs_dir / "update_summary.json").read_text(encoding="utf-8"))

    assert data_payload["run_id"] == stock_index_payload["run_id"] == summary_payload["run_id"]
