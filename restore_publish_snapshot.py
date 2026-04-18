#!/usr/bin/env python3
"""
Restore the latest validated publish bundle.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from publish_safety import PublishRestoreError, restore_latest_bundle

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

DEFAULT_TARGETS = (
    "docs/data_base.json",
    "docs/data.json",
    "docs/data_light.json",
    "docs/data.json.gz",
    "docs/update_summary.json",
)


def main(argv: list[str] | None = None) -> int:
    """Restore the latest manifest-backed publish snapshot."""
    parser = argparse.ArgumentParser(description="Restore the latest validated publish bundle")
    parser.add_argument("--lock-path", default="docs/.publish.lock")
    parser.add_argument("--backup-dir", default="backups/last_good")
    args = parser.parse_args(argv)

    try:
        result = restore_latest_bundle(
            lock_path=args.lock_path,
            backup_dir=args.backup_dir,
            targets=tuple(str(Path(target).resolve()) for target in DEFAULT_TARGETS),
            logger=logger,
        )
    except PublishRestoreError as exc:
        logger.error("Rollback failed: %s", exc)
        return 1

    logger.info("Restored publish bundle from %s", result["snapshot_dir"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
