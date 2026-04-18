import pytest


pytestmark = pytest.mark.skip(reason="Task 2 implements publish_safety.py")


def test_validate_artifact_payload_distinguishes_stock_and_summary_contracts():
    """Later plans should prove stock artifacts and summary artifacts use different validators."""


def test_validate_resume_stock_entry_rejects_missing_nested_contract_fields(sample_stock_entry):
    """Later plans should prove resume skips reject schema-incompatible stock records."""
