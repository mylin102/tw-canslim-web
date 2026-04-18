import pytest


pytestmark = pytest.mark.skip(reason="Task 2 implements publish_safety.py")


def test_publish_artifact_bundle_serializes_concurrent_bundle_promotions(publish_paths, artifact_bundle_factory):
    """Later plans should prove concurrent bundle publishes never leave mixed run ids."""


def test_publish_artifact_bundle_keeps_only_latest_validated_manifest(publish_paths, artifact_bundle_factory):
    """Later plans should prove backup retention keeps one latest manifest-backed bundle."""


def test_restore_latest_bundle_rewrites_requested_targets_atomically(
    publish_paths,
    artifact_bundle_factory,
    read_artifact,
):
    """Later plans should prove restore rewrites every requested target from one snapshot."""
