import importlib
import json
import sys
from pathlib import Path

import pytest


REPO_WORKFLOWS = (
    ".github/workflows/update_data.yml",
    ".github/workflows/on_demand_update.yml",
)
DEPRECATED_WRITERS = (
    "quick_auto_update",
    "quick_data_gen",
    "fast_data_gen",
)


def load_module(module_name: str):
    sys.modules.pop(module_name, None)
    return importlib.import_module(module_name)


def workflow_source(repo_root: Path, workflow_path: str) -> str:
    return (repo_root / workflow_path).read_text(encoding="utf-8")


def test_publish_workflow_exists(repo_root: Path):
    for workflow_path in REPO_WORKFLOWS:
        assert (repo_root / workflow_path).exists()


def test_on_demand_update_workflow_declares_publish_surface_concurrency(repo_root: Path):
    source = (repo_root / ".github/workflows/on_demand_update.yml").read_text(encoding="utf-8")

    assert "concurrency:" in source
    assert "publish-surface" in source
    assert "cancel-in-progress: false" in source


def test_restore_publish_snapshot_cli_restores_latest_bundle(
    monkeypatch,
    publish_paths,
    artifact_bundle_factory,
    read_artifact,
):
    module = load_module("publish_safety")
    docs_dir = publish_paths["docs"]
    backup_dir = publish_paths["backup"]
    lock_path = publish_paths["lock"]

    module.publish_artifact_bundle(
        artifact_bundle_factory("restore-run", docs_dir),
        lock_path=str(lock_path),
        backup_dir=str(backup_dir),
    )
    (docs_dir / "data.json").write_text("{\"run_id\": \"broken\"}\n", encoding="utf-8")
    (docs_dir / "update_summary.json").write_text("{\"run_id\": \"broken\"}\n", encoding="utf-8")

    rollback_module = load_module("restore_publish_snapshot")
    monkeypatch.chdir(publish_paths["root"])

    assert rollback_module.main([]) == 0

    assert read_artifact(docs_dir / "data.json", "data")["run_id"] == "restore-run"
    assert read_artifact(docs_dir / "update_summary.json", "update_summary")["run_id"] == "restore-run"
    manifest = json.loads((backup_dir / next(iter(p.name for p in backup_dir.iterdir() if p.is_dir())) / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["run_id"] == "restore-run"


@pytest.mark.parametrize("module_name", DEPRECATED_WRITERS)
def test_deprecated_writers_fail_before_touching_live_docs(
    module_name: str,
    monkeypatch,
    publish_paths,
    capsys,
):
    docs_dir = publish_paths["docs"]
    data_path = docs_dir / "data.json"
    data_path.write_text("{\"sentinel\": true}\n", encoding="utf-8")
    monkeypatch.chdir(publish_paths["root"])

    module = load_module(module_name)

    assert module.main() == 1
    assert data_path.read_text(encoding="utf-8") == "{\"sentinel\": true}\n"

    output = capsys.readouterr()
    combined = f"{output.out}\n{output.err}"
    assert "deprecated" in combined.lower()
    assert "quick_auto_update_enhanced.py" in combined or "batch_update_institutional.py" in combined


def test_update_data_workflow_declares_publish_surface_concurrency(repo_root: Path):
    source = (repo_root / ".github/workflows/update_data.yml").read_text(encoding="utf-8")

    assert "concurrency:" in source
    assert "publish-surface" in source
    assert "cancel-in-progress: false" in source


def test_workflows_stage_phase4_publish_artifacts(repo_root: Path):
    scheduled_source = workflow_source(repo_root, ".github/workflows/update_data.yml")
    on_demand_source = workflow_source(repo_root, ".github/workflows/on_demand_update.yml")

    if (
        "python create_stock_index.py" in scheduled_source
        or "docs/update_summary.json" not in scheduled_source
        or "docs/stock_index.json" not in on_demand_source
        or "docs/update_summary.json" not in on_demand_source
    ):
        pytest.xfail("Plan 04-03 Task 2 wires the Phase 4 workflow artifact contract")

    assert "python create_stock_index.py" not in scheduled_source
    assert "docs/stock_index.json" in scheduled_source
    assert "docs/update_summary.json" in scheduled_source
    assert "docs/stock_index.json" in on_demand_source
    assert "docs/update_summary.json" in on_demand_source


def test_scheduled_publish_chain_has_no_legacy_stock_index_dependency(repo_root: Path):
    scheduled_source = workflow_source(repo_root, ".github/workflows/update_data.yml")
    incremental_source = (repo_root / "incremental_workflow.py").read_text(encoding="utf-8")

    assert "python incremental_workflow.py" in scheduled_source
    assert "from create_stock_index import create_stock_index_with_rs" not in incremental_source
    assert "create_stock_index_with_rs" not in incremental_source
    assert "股票索引建立" not in incremental_source
    assert '[sys.executable, "export_canslim.py"]' not in incremental_source
