---
phase: 06-revenue-driven-selection-alpha
plan: 02
subsystem: export
tags: [revenue, alpha, export]
requires: [06-01]
provides: [leaders.json]
affects: [CanslimEngine.run, _export_leaders_json]
tech-stack: [python, json, pytest]
key-files: [export_canslim.py, tests/test_export_revenue.py]
decisions:
  - "Blended composite_score in leaders.json using 70% CANSLIM score and 30% revenue score (normalized to 6.0)."
  - "Added 'rev_acc' and 'rev_strong' tags to the External Alpha payload for enhanced signal visibility."
metrics:
  duration: 15m
  completed_date: "2024-04-20"
---

# Phase 06 Plan 02: Revenue-Driven Selection Alpha Summary

## One-liner
Integrated revenue alpha into the main CANSLIM engine and the External Alpha export payload.

## Key Changes
- Updated `CanslimEngine.run` to load revenue features from `docs/api/stock_features.json`.
- Attached `revenue_score`, `rev_accelerating`, and `rev_strong` to the `canslim` section of each stock's data.
- Updated `_export_leaders_json` to calculate a blended `composite_score` (70% CANSLIM, 30% Revenue).
- Added `rev_acc` and `rev_strong` tags to stocks in `leaders.json`.
- Implemented integration tests in `tests/test_export_revenue.py`.

## Deviations from Plan
None - plan executed exactly as written.

## Self-Check: PASSED
- `export_canslim.py` exists: FOUND
- `tests/test_export_revenue.py` exists: FOUND
- Commits exist: FOUND
- Tests pass: PASSED
