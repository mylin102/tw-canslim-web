from importlib import import_module

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


@pytest.mark.xfail(reason="Phase 4 stock_index schema support is not implemented yet")
def test_validate_artifact_payload_accepts_stock_index_contract(stock_index_payload_factory):
    module = load_publish_safety()

    module.validate_artifact_payload(
        stock_index_payload_factory("run-index"),
        artifact_kind="stock_index",
    )
