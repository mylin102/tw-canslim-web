from pathlib import Path

import pytest


OPERATIONAL_WRITERS = (
    "quick_auto_update_enhanced.py",
    "batch_update_institutional.py",
    "verify_local.py",
    "update_single_stock.py",
)


@pytest.mark.parametrize("script_name", OPERATIONAL_WRITERS)
def test_operational_script_exists(repo_root: Path, script_name: str):
    assert (repo_root / script_name).exists()


@pytest.mark.skip(reason="Plan 01-03 migrates operational writers to publish_artifact_bundle")
@pytest.mark.parametrize("script_name", OPERATIONAL_WRITERS)
def test_operational_script_uses_bundle_helper(repo_root: Path, script_name: str):
    source = (repo_root / script_name).read_text(encoding="utf-8")
    assert "publish_artifact_bundle" in source
