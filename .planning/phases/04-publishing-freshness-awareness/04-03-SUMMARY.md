---
phase: 04-publishing-freshness-awareness
plan: 03
subsystem: infra
tags: [github-actions, publish-bundle, stock-index, update-summary, testing]
requires:
  - phase: 04-publishing-freshness-awareness
    provides: publish_projection.py bundle-safe data, stock_index, and update_summary generation
provides:
  - single-stock publishes that reuse the shared Phase 4 projection bundle
  - scheduled and on-demand workflows that both stage stock_index and update_summary artifacts
  - regression coverage for workflow artifact staging and single-stock Phase 4 outputs
affects: [publishing, workflows, on-demand-update, github-pages]
tech-stack:
  added: []
  patterns:
    - shared projection helper reuse for all publish paths
    - workflow staging tests that auto-activate once runtime wiring lands
key-files:
  created: [.planning/phases/04-publishing-freshness-awareness/04-03-SUMMARY.md]
  modified:
    - update_single_stock.py
    - .github/workflows/update_data.yml
    - .github/workflows/on_demand_update.yml
    - tests/test_operational_publish_path.py
    - tests/test_publish_workflows.py
key-decisions:
  - "Single-stock publishing now reuses build_publish_projection_bundle so data.json, stock_index.json, and update_summary.json stay synchronized."
  - "Workflow regressions use runtime xfail gates so Task 1 could land safely before Task 2 removed the legacy gaps."
patterns-established:
  - "Publish paths should stage stock_index.json and update_summary.json explicitly in workflow commits."
  - "On-demand freshness updates should persist through rotation_state before rebuilding publish projections."
requirements-completed: [PUB-02, PUB-03, PUB-04]
duration: 7 min
completed: 2026-04-19
---

# Phase 4 Plan 03: Publishing automation alignment Summary

**Shared Phase 4 publish-bundle reuse for single-stock updates plus workflow commits that keep stock_index.json and update_summary.json durable in CI.**

## Performance

- **Duration:** 7 min
- **Started:** 2026-04-19T06:01:30Z
- **Completed:** 2026-04-19T06:08:56Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments
- Added workflow and operational regressions for Phase 4 artifact staging and single-stock bundle outputs.
- Rewired `update_single_stock.py` to reuse `build_publish_projection_bundle(...)` and publish `stock_index.json` with refreshed rotation-state freshness.
- Removed scheduled reliance on `create_stock_index.py` and made both workflows stage `docs/stock_index.json` plus `docs/update_summary.json`.

## Task Commits

Each task was committed atomically:

1. **Task 1: Add regressions for Phase 4 artifact staging in workflow and single-stock publish paths** - `0c4a339` (test)
2. **Task 2: Reuse the Phase 4 projection helper in single-stock publishing and align both workflows** - `e61c469` (feat)

## Files Created/Modified
- `tests/test_publish_workflows.py` - Guards workflow staging for `stock_index.json`, `update_summary.json`, and removal of `create_stock_index.py`.
- `tests/test_operational_publish_path.py` - Verifies single-stock publishing emits `stock_index.json` from the shared bundle.
- `update_single_stock.py` - Persists on-demand freshness and rebuilds projected publish artifacts through the shared helper.
- `.github/workflows/update_data.yml` - Removes the standalone stock-index step and stages Phase 4 artifacts explicitly.
- `.github/workflows/on_demand_update.yml` - Stages `docs/stock_index.json` and `docs/update_summary.json` alongside existing publish artifacts.

## Decisions Made
- Reused `build_publish_projection_bundle(...)` in the on-demand path instead of duplicating index/summary generation logic.
- Kept workflow regression tests merge-safe by using conditional `xfail` until the runtime wiring landed in Task 2.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Seeded non-empty on-demand batch generation for rotation-state freshness writes**
- **Found during:** Task 2 (Reuse the Phase 4 projection helper in single-stock publishing and align both workflows)
- **Issue:** The first single-stock test run failed because a newly seeded rotation state had an empty `rotation_generation`, which violated freshness validation for `last_batch_generation`.
- **Fix:** Added an `on-demand-{ticker}` fallback batch-generation value before persisting single-stock freshness.
- **Files modified:** `update_single_stock.py`
- **Verification:** `PYTHONPATH=. pytest -q tests/test_operational_publish_path.py tests/test_publish_workflows.py -x`
- **Committed in:** `e61c469`

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** Required for the new shared publish path to validate and publish correctly. No scope creep.

## Issues Encountered
- Task 1 needed regression coverage before runtime wiring existed, so tests were written to auto-activate once Task 2 removed the legacy gaps.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Phase 4 now has aligned scheduled and on-demand publish paths for all required artifacts.
- Verification can focus on end-to-end artifact durability rather than workflow contract drift.

## Self-Check: PASSED
