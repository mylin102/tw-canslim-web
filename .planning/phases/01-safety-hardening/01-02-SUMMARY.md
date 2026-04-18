---
phase: 01-safety-hardening
plan: 02
subsystem: infra
tags: [python, pytest, publish-safety, github-pages]
requires:
  - phase: 01-01
    provides: "publish_safety.py bundle publishing, backup, and artifact validation helpers"
provides:
  - "Bundle-safe primary CANSLIM publishing with resume validation and failure summaries"
  - "Bundle-safe dashboard publishing with metadata envelopes and loud input/publish failures"
  - "Executable regression coverage for both primary export scripts"
affects: [01-03, primary-exporters, publish-path]
tech-stack:
  added: []
  patterns: [artifact-aware resume validation, bundle-safe exporter publishing, explicit failure summaries]
key-files:
  created: []
  modified: [export_canslim.py, export_dashboard_data.py, tests/test_primary_publish_path.py]
key-decisions:
  - "Fallback to a raw resume scan only after load_artifact_json rejects the whole artifact so compatible stock records can still be revalidated individually."
  - "Keep dashboard output on artifact_kind=data and add the required metadata plus minimum CANSLIM fields needed by the shared validator."
patterns-established:
  - "Primary exporters publish live docs artifacts only through publish_artifact_bundle."
  - "Primary exporters surface resume, retry, and publish failures in explicit logs or summary payloads."
requirements-completed: [SAFE-01, SAFE-02, SAFE-03, SAFE-04]
duration: 16m
completed: 2026-04-18
---

# Phase 1 Plan 02: Primary Export Publish Hardening Summary

**Bundle-safe CANSLIM and dashboard exports with record-level resume validation, failure summaries, and loud publish errors**

## Performance

- **Duration:** 16 min
- **Started:** 2026-04-18T21:13:53Z
- **Completed:** 2026-04-18T21:30:09Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments

- Routed `export_canslim.py` through `load_artifact_json`, `validate_resume_stock_entry`, and `publish_artifact_bundle`
- Added explicit retry/resume/stock failure summary stats and bundle publishing for `docs/data.json` plus `docs/update_summary.json`
- Hardened `export_dashboard_data.py` with artifact metadata, bundle publishing, and non-silent input/publish failure handling
- Extended `tests/test_primary_publish_path.py` with executable regression coverage for both primary exporters

## Task Commits

Each task was committed atomically:

1. **Task 1: Route `export_canslim.py` through artifact-aware resume validation and bundle publish** - `ba650b0` (test), `113f5d1` (feat)
2. **Task 2: Harden `export_dashboard_data.py` with artifact-aware validation and script smoke coverage** - `575bb2d` (test), `3a66335` (feat)

_Note: TDD tasks used separate failing-test and implementation commits._

## Files Created/Modified

- `export_canslim.py` - Adds artifact envelope metadata, retry/failure counters, record-level resume validation, and bundle-safe publish flow
- `export_dashboard_data.py` - Publishes dashboard data through the shared helper with metadata and explicit failure propagation
- `tests/test_primary_publish_path.py` - Adds executable regression coverage for CANSLIM and dashboard publish paths

## Decisions Made

- Used `load_artifact_json` first, then fell back to raw JSON only when the whole artifact failed validation, so resume can still salvage compatible stock records while forcing invalid ones to rebuild
- Kept dashboard exports on the shared `data` artifact contract and filled the validator-required CANSLIM fields rather than inventing a new artifact kind mid-phase

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Preserved per-stock resume validation when the helper rejected the full existing artifact**
- **Found during:** Task 1 (Route `export_canslim.py` through artifact-aware resume validation and bundle publish)
- **Issue:** `load_artifact_json(...)` validates the full stock artifact, which would discard all resume candidates if any one saved stock was incompatible
- **Fix:** Attempted helper validation first, then fell back to a raw JSON scan and applied `validate_resume_stock_entry(...)` before every skip decision
- **Files modified:** `export_canslim.py`
- **Verification:** `python3 -m py_compile export_canslim.py publish_safety.py && PYTHONPATH=. pytest tests/test_publish_safety.py tests/test_export_schema.py tests/test_primary_publish_path.py -k export_canslim -q`
- **Committed in:** `113f5d1`

**2. [Rule 3 - Blocking] Adapted dashboard payloads to the existing stock artifact validator**
- **Found during:** Task 2 (Harden `export_dashboard_data.py` with artifact-aware validation and script smoke coverage)
- **Issue:** The shared `data` artifact validator requires per-stock `canslim.mansfield_rs` and `canslim.grid_strategy` fields that the dashboard exporter did not emit
- **Fix:** Added metadata envelope fields plus minimum validator-compatible CANSLIM fields while preserving the existing dashboard snapshot shape
- **Files modified:** `export_dashboard_data.py`
- **Verification:** `python3 -m py_compile export_dashboard_data.py publish_safety.py && PYTHONPATH=. pytest tests/test_primary_publish_path.py -k export_dashboard_data -q`
- **Committed in:** `3a66335`

---

**Total deviations:** 2 auto-fixed (2 blocking)
**Impact on plan:** Both deviations were compatibility fixes required to use the shared publish-safety contract without losing resume behavior or breaking dashboard validation.

## Issues Encountered

- The shared validator still expects legacy `update_summary` fields, so the CANSLIM publish summary carries both the new Phase 1 metadata envelope and the legacy keys required by `publish_safety.py`

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Plan 03 can reuse the same `publish_artifact_bundle` pattern for the remaining operational writers
- Primary exporters now fail loudly enough for workflow-level rollback and rollback validation work

## Self-Check: PASSED
