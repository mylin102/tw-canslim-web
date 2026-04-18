---
phase: 02-dynamic-core-selection
plan: 01
subsystem: orchestration
tags: [python, pytest, parquet, selector]
requires:
  - phase: 01-safety-hardening
    provides: publish-safe artifact contracts and schema validation patterns
provides:
  - checked-in selector config for base, ETF, and watchlist buckets
  - artifact-backed selector helpers for fixed buckets, carryover signals, and ranked fill
  - pytest scaffolding for selector behavior and restored institutional test collection
affects: [phase-02-plan-02, phase-02-plan-03, phase-03-rotating-batch-orchestration]
tech-stack:
  added: []
  patterns: [validated json config, artifact-backed selector inputs, pytest parquet fixtures]
key-files:
  created: [core_selection.py, core_selection_config.json, tests/test_core_selection.py]
  modified: [tests/conftest.py, core/logic.py]
key-decisions:
  - "Keep fixed selector buckets in checked-in JSON with exact-key and 4-digit symbol validation."
  - "Derive today and carryover signal buckets from the latest two fused parquet dates and fail closed when fused data is stale."
  - "Restore institutional compatibility by wrapping calculate_accumulation_strength in calculate_i_factor and preserving the conviction bonus path."
patterns-established:
  - "Selector helpers accept persisted artifacts and return ordered dataclass-based results."
  - "Selector tests use temp parquet and baseline JSON fixtures instead of live repo artifacts."
requirements-completed: [ORCH-01]
duration: 2m
completed: 2026-04-18
---

# Phase 2 Plan 01: Establish selector contracts, config, and Wave 0 test scaffolding Summary

**Validated selector contracts with checked-in core buckets, fused-parquet signal carryover rules, and pytest fixtures for future export wiring.**

## Performance

- **Duration:** 2m
- **Started:** 2026-04-18T23:17:48Z
- **Completed:** 2026-04-18T23:19:19Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments
- Added `core_selection.py` with selector config loading, artifact validation, signal extraction, and ordered core-universe assembly.
- Added `core_selection_config.json` as the checked-in source of truth for base, ETF, watchlist, and 300-name target settings.
- Added selector pytest fixtures/tests and restored `tests/test_institutional_logic.py` compatibility through `calculate_i_factor`.

## Task Commits

1. **Task 0: Write selector contracts and checked-in bucket config** - `8458d8e` (feat)
2. **Task 1: Add selector fixtures/tests and restore pytest collection for Phase 2** - `2de3041` (test, RED)
3. **Task 1: Add selector fixtures/tests and restore pytest collection for Phase 2** - `5d67f6d` (fix, GREEN)

## Files Created/Modified
- `core_selection.py` - selector dataclasses plus config, artifact, and ranking helpers.
- `core_selection_config.json` - curated base/ETF/watchlist seed config with target size 300.
- `tests/test_core_selection.py` - fixed bucket, signal carryover, ranking, and stale fused coverage.
- `tests/conftest.py` - temp config/parquet/baseline factories for selector tests.
- `core/logic.py` - backwards-compatible `calculate_i_factor` helper and conviction bonus restoration.

## Decisions Made
- Stored fixed selector buckets in a checked-in JSON file instead of reintroducing any inline priority list.
- Validated selector config keys, symbol formats, and fused/master freshness in `core_selection.py` because the threat model treats those checks as correctness requirements.
- Kept Phase 2 verification on `PYTHONPATH=.` and used synthetic parquet fixtures so selector behavior stays deterministic.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Added selector input validation and stale fused rejection**
- **Found during:** Task 0 (Write selector contracts and checked-in bucket config)
- **Issue:** The plan asked for contracts, but the threat model required validating config shape, 4-digit symbols, persisted volume fields, and fused/master freshness before selector use.
- **Fix:** Implemented config-key validation, bucket symbol validation, required parquet column checks, and fail-closed stale fused detection inside `core_selection.py`.
- **Files modified:** `core_selection.py`
- **Verification:** `python3 -m py_compile core_selection.py`; `PYTHONPATH=. pytest -q tests/test_core_selection.py tests/test_primary_publish_path.py`
- **Committed in:** `8458d8e`

**2. [Rule 1 - Bug] Restored institutional conviction bonus semantics**
- **Found during:** Task 1 (Add selector fixtures/tests and restore pytest collection for Phase 2)
- **Issue:** `compute_canslim_score()` ignored the `institutional_strength` bonus path expected by the existing institutional tests.
- **Fix:** Reintroduced the >=0.5% conviction bonus while adding the backwards-compatible `calculate_i_factor()` helper.
- **Files modified:** `core/logic.py`
- **Verification:** `PYTHONPATH=. pytest -q tests/test_institutional_logic.py tests/test_core_selection.py`
- **Committed in:** `5d67f6d`

---

**Total deviations:** 2 auto-fixed (1 missing critical, 1 bug)
**Impact on plan:** Both fixes were required to satisfy the selector threat model and keep the existing Phase 2 validation entry points green.

## Issues Encountered
- `tests/test_institutional_logic.py` initially failed during collection because `calculate_i_factor` was missing; fixing that exposed a second scoring regression, both resolved inside the planned compatibility task.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Plan 02 can build on the checked-in config and selector fixtures to implement fuller artifact-backed selection behavior.
- Plan 03 can wire `build_core_universe()` into `export_canslim.py` without reintroducing inline bucket lists.

## Known Stubs
None.

## Self-Check: PASSED
- Verified summary and key implementation files exist on disk.
- Verified task commits `8458d8e`, `2de3041`, and `5d67f6d` exist in git history.
