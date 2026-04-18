---
phase: 02-dynamic-core-selection
plan: 02
subsystem: orchestration
tags: [python, pytest, parquet, selector, volume-ranking]
requires:
  - phase: 01-safety-hardening
    provides: publish-safe artifact contracts and schema validation patterns
  - phase: 02-dynamic-core-selection
    provides: selector config, fixtures, and Wave 0 contracts from Plan 01
provides:
  - persisted latest-volume and volume-rank fields in master/fused selector artifacts
  - artifact-backed core selection with fused freshness guards and required leader buckets
  - deterministic overflow-safe selector ordering for Phase 3 export wiring
affects: [phase-02-plan-03, phase-03-rotating-batch-orchestration]
tech-stack:
  added: []
  patterns: [artifact-backed selector inputs, deterministic bucket ordering, persisted volume ranking]
key-files:
  created: []
  modified: [historical_generator.py, fuse_excel_data.py, core_selection.py, tests/test_core_selection.py]
key-decisions:
  - "Persist latest_volume and date-level volume_rank in the master parquet so selector volume leaders stay artifact-driven."
  - "Fail closed when fused parquet freshness or selector-required columns drift from master artifacts."
  - "Preserve all required selector buckets first, expand only up to 500 names, then fill by (-mansfield_rs, volume_rank, symbol)."
patterns-established:
  - "Selector inputs come from the latest fused parquet date plus exactly one previous carryover date."
  - "Required buckets are assembled in fixed order before any ranked fill candidate is considered."
requirements-completed: [ORCH-01]
duration: 4m
completed: 2026-04-19
---

# Phase 2 Plan 02: Implement artifact-backed volume-aware core-universe selection Summary

**Artifact-backed core selection now promotes trusted fused signals, RS leaders, and top-volume leaders from persisted parquet data without any live prepass.**

## Performance

- **Duration:** 4m
- **Started:** 2026-04-18T23:30:47Z
- **Completed:** 2026-04-18T23:35:02Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments
- Persisted `latest_volume` and deterministic per-date `volume_rank` into master selector artifacts.
- Kept fused selector artifacts volume-aware so Phase 2 can rank top-volume leaders from parquet alone.
- Implemented the required bucketed core selector with stale-fused rejection, RS/volume leader guarantees, and overflow protection up to 500 names.

## Task Commits

1. **Task 1: Persist latest-volume metrics into the master/fused signal artifacts** - `45286b3` (test, RED)
2. **Task 1: Persist latest-volume metrics into the master/fused signal artifacts** - `6132736` (feat, GREEN)
3. **Task 2: Implement artifact-backed core-universe selection with freshness guards** - `139ece5` (test, RED)
4. **Task 2: Implement artifact-backed core-universe selection with freshness guards** - `820ad60` (feat, GREEN)

## Files Created/Modified
- `historical_generator.py` - persists `latest_volume` and date-level `volume_rank` into `master_canslim_signals.parquet`.
- `fuse_excel_data.py` - validates selector-ready master columns before writing fused parquet outputs.
- `core_selection.py` - loads trusted selector artifacts, builds required buckets, enforces freshness guards, and ranks fill by `mansfield_rs`.
- `tests/test_core_selection.py` - proves persisted volume fields, required bucket ordering, overflow guards, and deterministic selector fill.

## Decisions Made
- Used persisted fused/master artifacts as the only selector source for signals, RS leaders, and volume leaders in this plan.
- Kept the required bucket stream fixed as `base -> ETF -> watchlist -> yesterday -> today -> rs -> top volume` before any ranked fill.
- Treated required-bucket overflow as correctness logic: expand only to the required membership size up to 500, otherwise raise loudly.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Added fused-artifact schema validation before merge-through**
- **Found during:** Task 1 (Persist latest-volume metrics into the master/fused signal artifacts)
- **Issue:** The plan required volume fields to survive into the fused parquet, but `fuse_excel_data.py` would have silently written a selector-incompatible artifact if the master parquet dropped `latest_volume` or `volume_rank`.
- **Fix:** Added explicit required-column validation for `stock_id`, `date`, `score`, `latest_volume`, and `volume_rank` before writing `master_canslim_signals_fused.parquet`.
- **Files modified:** `fuse_excel_data.py`
- **Verification:** `PYTHONPATH=. pytest -q tests/test_core_selection.py -k volume`; `python3 -m py_compile historical_generator.py fuse_excel_data.py core_selection.py`
- **Committed in:** `6132736`

---

**Total deviations:** 1 auto-fixed (1 missing critical)
**Impact on plan:** The added validation keeps selector artifacts fail-closed without expanding scope beyond Phase 2 Plan 02.

## Issues Encountered
- None.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- `build_core_universe(...)` now returns ordered core symbols plus bucket metadata for export wiring in Plan 03.
- `export_canslim.py` can now consume selector-ready fused/master artifacts without introducing any live volume prepass.

## Known Stubs
None.

## Self-Check: PASSED
- Verified summary target path and modified implementation files exist on disk.
- Verified task commits `45286b3`, `6132736`, `139ece5`, and `820ad60` exist in git history.
