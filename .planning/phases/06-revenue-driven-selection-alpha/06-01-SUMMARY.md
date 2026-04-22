---
phase: 06-revenue-driven-selection-alpha
plan: 01
subsystem: selection
tags: [revenue, core-selection, tdd]
requires: []
provides: [revenue_alpha_leaders]
affects: [build_core_universe, load_selector_inputs]
tech-stack: [python, pandas, pytest]
key-files: [core_selection.py, tests/test_revenue_selection.py]
decisions:
  - "Added revenue_alpha_leaders bucket after today_signals to prioritize stocks with accelerating revenue growth."
  - "Updated RankedCandidate and sorting logic to prioritize revenue_score over mansfield_rs."
metrics:
  duration: 10m
  completed_date: "2024-04-20"
---

# Phase 06 Plan 01: Revenue-Driven Selection Alpha Summary

## One-liner
Integrated revenue features (score and acceleration) into the core selection logic and prioritized them in the ranking.

## Key Changes
- Updated `RankedCandidate` dataclass to include `revenue_score`.
- Updated `_ranked_candidate_sort_key` to prioritize `revenue_score` as the primary sorting criterion.
- Updated `load_selector_inputs` to load revenue features from `docs/api/stock_features.json` and populate the new `revenue_alpha_leaders` bucket (score >= 5 and accelerating).
- Updated `build_core_universe` to handle the new bucket and allow passing an optional `revenue_path`.
- Added comprehensive unit tests in `tests/test_revenue_selection.py`.

## Deviations from Plan
None - plan executed exactly as written.

## Self-Check: PASSED
- `core_selection.py` exists: FOUND
- `tests/test_revenue_selection.py` exists: FOUND
- Commits exist: FOUND
- Tests pass: PASSED
