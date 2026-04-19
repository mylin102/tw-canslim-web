#!/usr/bin/env python3
"""
Restore the latest validated publish bundle.
"""

from __future__ import annotations

import argparse
import logging
import sys

from publish_safety import PublishRestoreError, restore_latest_bundle

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def main(argv: list[str] | None = None) -> int:
    """Restore the latest manifest-backed publish snapshot."""
    parser = argparse.ArgumentParser(description="Restore the latest validated publish bundle")
    parser.add_argument("--lock-path", default="docs/.publish.lock")
    parser.add_argument("--backup-dir", default="backups/last_good")
    parser.add_argument(
        "--target",
        action="append",
        dest="targets",
        help="Specific artifact target to restore. Repeat to restore multiple targets.",
    )
    args = parser.parse_args(argv)

    try:
        result = restore_latest_bundle(
            lock_path=args.lock_path,
            backup_dir=args.backup_dir,
            targets=tuple(args.targets) if args.targets else None,
            logger=logger,
        )
    except PublishRestoreError as exc:
        logger.error("Rollback failed: %s", exc)
        return 1

    logger.info("Restored publish bundle from %s", result["snapshot_dir"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
