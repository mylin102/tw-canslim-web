from importlib import import_module
import json
import threading
import time


def load_publish_safety():
    return import_module("publish_safety")


def test_publish_artifact_bundle_serializes_concurrent_bundle_promotions(
    publish_paths,
    artifact_bundle_factory,
    read_artifact,
):
    module = load_publish_safety()
    docs_dir = publish_paths["docs"]
    backup_dir = publish_paths["backup"]
    lock_path = publish_paths["lock"]
    errors = []

    def publish(run_id: str, delay: float) -> None:
        time.sleep(delay)
        bundle = artifact_bundle_factory(run_id, docs_dir)
        try:
            module.publish_artifact_bundle(
                bundle,
                lock_path=str(lock_path),
                backup_dir=str(backup_dir),
            )
        except Exception as exc:  # pragma: no cover - asserted below
            errors.append(exc)

    first = threading.Thread(target=publish, args=("run-a", 0.05))
    second = threading.Thread(target=publish, args=("run-b", 0))
    first.start()
    second.start()
    first.join()
    second.join()

    assert not errors

    run_ids = {
        read_artifact(docs_dir / "data_base.json", "data_base")["run_id"],
        read_artifact(docs_dir / "data.json", "data")["run_id"],
        read_artifact(docs_dir / "data_light.json", "data_light")["run_id"],
        read_artifact(docs_dir / "data.json.gz", "data_gz")["run_id"],
        read_artifact(docs_dir / "update_summary.json", "update_summary")["run_id"],
    }
    assert len(run_ids) == 1


def test_publish_artifact_bundle_keeps_only_latest_validated_manifest(
    publish_paths,
    artifact_bundle_factory,
):
    module = load_publish_safety()
    docs_dir = publish_paths["docs"]
    backup_dir = publish_paths["backup"]
    lock_path = publish_paths["lock"]

    module.publish_artifact_bundle(
        artifact_bundle_factory("run-a", docs_dir),
        lock_path=str(lock_path),
        backup_dir=str(backup_dir),
    )
    module.publish_artifact_bundle(
        artifact_bundle_factory("run-b", docs_dir),
        lock_path=str(lock_path),
        backup_dir=str(backup_dir),
    )

    snapshots = sorted(path for path in backup_dir.iterdir() if path.is_dir())
    assert len(snapshots) == 1

    manifest = json.loads((snapshots[0] / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["run_id"] == "run-b"
    assert set(manifest["artifacts"]) == {
        str(docs_dir / "data_base.json"),
        str(docs_dir / "data.json"),
        str(docs_dir / "data_light.json"),
        str(docs_dir / "data.json.gz"),
        str(docs_dir / "update_summary.json"),
    }


def test_restore_latest_bundle_rewrites_requested_targets_atomically(
    publish_paths,
    artifact_bundle_factory,
    read_artifact,
):
    module = load_publish_safety()
    docs_dir = publish_paths["docs"]
    backup_dir = publish_paths["backup"]
    lock_path = publish_paths["lock"]

    module.publish_artifact_bundle(
        artifact_bundle_factory("run-a", docs_dir),
        lock_path=str(lock_path),
        backup_dir=str(backup_dir),
    )
    module.publish_artifact_bundle(
        artifact_bundle_factory("run-b", docs_dir),
        lock_path=str(lock_path),
        backup_dir=str(backup_dir),
    )

    for file_name in ("data_base.json", "data.json", "data_light.json", "update_summary.json"):
        (docs_dir / file_name).write_text("{\"run_id\": \"corrupt\"}", encoding="utf-8")

    result = module.restore_latest_bundle(
        lock_path=str(lock_path),
        backup_dir=str(backup_dir),
    )

    assert set(result["restored_targets"]) == {
        str(docs_dir / "data_base.json"),
        str(docs_dir / "data.json"),
        str(docs_dir / "data_light.json"),
        str(docs_dir / "data.json.gz"),
        str(docs_dir / "update_summary.json"),
    }
    assert read_artifact(docs_dir / "data_base.json", "data_base")["run_id"] == "run-b"
    assert read_artifact(docs_dir / "data.json", "data")["run_id"] == "run-b"
    assert read_artifact(docs_dir / "data_light.json", "data_light")["run_id"] == "run-b"
    assert read_artifact(docs_dir / "data.json.gz", "data_gz")["run_id"] == "run-b"
    assert read_artifact(docs_dir / "update_summary.json", "update_summary")["run_id"] == "run-b"
