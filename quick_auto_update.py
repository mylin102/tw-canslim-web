#!/usr/bin/env python3
"""
Deprecated legacy quick update entrypoint.
"""

from __future__ import annotations

import sys

DEPRECATION_MESSAGE = (
    "Deprecated legacy writer: quick_auto_update.py no longer publishes live docs artifacts. "
    "Use quick_auto_update_enhanced.py for supported quick updates or batch_update_institutional.py "
    "for the maintained operational path."
)


def main() -> int:
    """Fail fast before any live docs write can happen."""
    print(DEPRECATION_MESSAGE, file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
