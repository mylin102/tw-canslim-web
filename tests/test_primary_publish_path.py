from pathlib import Path

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
