#!/usr/bin/env python3
"""
Deprecated legacy quick data generator entrypoint.
"""

from __future__ import annotations

import sys

DEPRECATION_MESSAGE = (
    "Deprecated legacy writer: quick_data_gen.py no longer writes live docs artifacts. "
    "Use batch_update_institutional.py or the scheduled .github/workflows/update_data.yml path instead."
)


def main() -> int:
    """Fail fast before any live docs write can happen."""
    print(DEPRECATION_MESSAGE, file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
