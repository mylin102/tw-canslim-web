from pathlib import Path

import pytest


WORKFLOWS = (
    ".github/workflows/update_data.yml",
    ".github/workflows/on_demand_update.yml",
)

DEPRECATED_WRITERS = (
    "quick_auto_update_enhanced.py",
    "batch_update_institutional.py",
    "verify_local.py",
)


@pytest.mark.parametrize("workflow_path", WORKFLOWS)
def test_publish_workflow_exists(repo_root: Path, workflow_path: str):
    assert (repo_root / workflow_path).exists()


@pytest.mark.skip(reason="Plan 01-02 adds workflow-level publish concurrency")
@pytest.mark.parametrize("workflow_path", WORKFLOWS)
def test_publish_workflow_declares_concurrency(repo_root: Path, workflow_path: str):
    source = (repo_root / workflow_path).read_text(encoding="utf-8")
    assert "concurrency:" in source


@pytest.mark.skip(reason="Plan 01-03 adds deprecated-writer guards before live docs writes")
@pytest.mark.parametrize("script_name", DEPRECATED_WRITERS)
def test_deprecated_writers_fail_before_touching_live_docs(repo_root: Path, script_name: str):
    source = (repo_root / script_name).read_text(encoding="utf-8")
    assert "PublishValidationError" in source or "PublishTransactionError" in source
