---
phase: 02-dynamic-core-selection
plan: 03
subsystem: testing
tags: [python, pytest, selector, publish-safety]
requires:
  - phase: 02-02
    provides: "Artifact-backed core selection with persisted volume ranking inputs"
provides:
  - "export_canslim.py builds its scan list from the dynamic core selector"
  - "Primary export regressions prove selector-first ordering and bundle-safe publishing"
  - "Selector validation errors now surface directly from the export path"
affects: [export_canslim.py, core_selection.py, publish-path]
tech-stack:
  added: []
  patterns: [artifact-backed selector wiring, core-first scan ordering, publish bundle regression coverage]
key-files:
  created: []
  modified: [export_canslim.py, core_selection.py, tests/test_primary_publish_path.py]
key-decisions:
  - "Kept export wiring on build_core_universe(...) by extending the selector helper to accept artifact paths without breaking existing selector unit tests."
  - "Preserved the brownfield non-core tail exactly as selection.core_symbols plus the first 2000 remaining sorted tickers."
patterns-established:
  - "Primary export ordering must come from selector artifacts and fail loudly on selector validation issues."
  - "Publish-path regressions stub selector output so Phase 1 bundle assertions stay isolated from parquet fixtures."
requirements-completed: [ORCH-01]
duration: 21m
completed: 2026-04-19
---

# Phase 2 Plan 03: Dynamic selector-driven export scan summary

**Artifact-backed core selection now drives CANSLIM export scan order while Phase 1 bundle publishing and failure summaries remain intact**

## Performance

- **Duration:** 21 min
- **Started:** 2026-04-18T23:44:00Z
- **Completed:** 2026-04-19T00:04:47Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments

- Wired `export_canslim.py` to call `build_core_universe(...)` with the checked-in config and persisted selector artifacts
- Preserved the brownfield tail as the first 2000 non-core tickers after the ordered selector core set
- Added export-level regression coverage for selector-driven order, selector validation failures, and unchanged publish bundle behavior

## Task Commits

Each task was committed atomically:

1. **Task 1: Add export-level regression coverage for dynamic core selection** - `5b19b94` (test)
2. **Task 2: Wire `export_canslim.py` to the selector and keep Phase 1 publish safety intact** - `b61eca3` (test), `36278e4` (feat)

_Note: TDD task 2 used separate failing-test and implementation commits._

## Files Created/Modified

- `export_canslim.py` - Replaces the static priority seam with selector-driven `scan_list` construction and selector telemetry logging
- `core_selection.py` - Accepts artifact-path inputs through `build_core_universe(...)` and validates both 4-digit and 5-digit repo symbols
- `tests/test_primary_publish_path.py` - Adds selector-order/failure regressions and isolates existing publish-path tests from real selector artifacts

## Decisions Made

- Extended `build_core_universe(...)` instead of adding a second export-only wrapper so export wiring could follow the plan contract while existing selector tests remained stable
- Let selector validation errors propagate from `export_canslim.py` to preserve the plan's fail-loud trust semantics

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Allowed checked-in 5-digit ETF symbols in selector validation**
- **Found during:** Task 2 (Wire `export_canslim.py` to the selector and keep Phase 1 publish safety intact)
- **Issue:** The checked-in selector config includes ETF `00878`, but selector validation only accepted 4-digit symbols, causing export wiring to fail before any publish-path tests could run
- **Fix:** Broadened selector symbol validation to accept 4-digit and 5-digit numeric symbols so the committed config and ETF cache remain usable from the export path
- **Files modified:** `core_selection.py`
- **Verification:** `python3 -m py_compile export_canslim.py core_selection.py && PYTHONPATH=. pytest -q tests/test_core_selection.py tests/test_primary_publish_path.py`
- **Committed in:** `36278e4`

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** The auto-fix was required to make the planned selector wiring work with the repo's checked-in ETF config. No Phase 3 or Phase 4 scope was pulled in.

## Issues Encountered

- Existing export publish-path tests started loading real selector artifacts after the wiring change, so the tests were updated to stub selector output and stay focused on publish behavior

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Phase 2 is complete: export ordering now honors the dynamic selector end-to-end
- Phase 3 can build rotation/state behavior on top of the selector-produced core/non-core split without revisiting publish safety

## Self-Check: PASSED

---
*Phase: 02-dynamic-core-selection*
*Completed: 2026-04-19*
