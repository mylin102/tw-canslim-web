---
phase: 03-rotating-batch-orchestration
plan: 03
subsystem: infra
tags: [python, pytest, github-actions, rotation-state, yfinance, finmind, tej]
requires:
  - phase: 03-02
    provides: "Deterministic rotation planning, frozen in-progress batches, and finalize-success cursor seams"
provides:
  - "Shared provider-policy retries and pacing for requests, FinMind, TEJ, and yfinance export paths"
  - "Retry-first rotation-aware export planning with durable freshness and publish-boundary cursor advancement"
  - "Workflow artifact restore/persist for .orchestration/rotation_state.json plus runtime budget validation"
affects: [export_canslim.py, github-actions, provider-policies, phase-4-publishing]
tech-stack:
  added: []
  patterns: [shared provider policy runtime state, retry-first rotation worklists, artifact-backed workflow state restore]
key-files:
  created: [yfinance_provider.py, .orchestration/runtime_budget.json, .planning/phases/03-rotating-batch-orchestration/03-03-SUMMARY.md]
  modified: [export_canslim.py, provider_policies.py, finmind_processor.py, tej_processor.py, tests/test_provider_policies.py, tests/test_primary_publish_path.py, .github/workflows/update_data.yml, .github/workflows/on_demand_update.yml]
key-decisions:
  - "Reuse the Phase 3 rotation/state seams from export_canslim.py and add export-side persistence helpers for retry/core freshness instead of introducing a new orchestration layer."
  - "Keep provider pacing and retry accounting in one shared runtime-state contract so export summaries and runtime-budget artifacts derive from the same counters."
  - "Restore rotation checkpoints through a named GitHub artifact before each workflow run and still commit the fixed .orchestration/rotation_state.json path on scheduled publishes."
patterns-established:
  - "Export scan order is now core symbols followed by due retries and the scheduled batch returned by build_daily_plan(...)."
  - "Rotation cursor advancement happens only after the final publish succeeds; symbol-level successes/failures persist immediately to durable state."
  - "Workflow reruns restore the latest named rotation-state artifact with gh run download and always upload the refreshed state afterward."
requirements-completed: [ORCH-02, ORCH-04, ORCH-05]
duration: 13min
completed: 2026-04-19
---

# Phase 3 Plan 03: Rotation-aware export wiring and workflow persistence Summary

**Retry-first rotation exports now share provider pacing, persist crash-survivable state, and validate daily runtime budget inside the GitHub Actions pipeline**

## Performance

- **Duration:** 13 min
- **Started:** 2026-04-19T10:27:33+08:00
- **Completed:** 2026-04-19T10:40:15+08:00
- **Tasks:** 2
- **Files modified:** 10

## Accomplishments
- Routed requests, FinMind, TEJ, and yfinance export calls through one shared provider-policy helper with retry/wait accounting.
- Replaced the static non-core tail in `export_canslim.py` with selector core symbols plus `build_daily_plan(...)` retry/scheduled worklists.
- Added workflow restore/upload steps for `.orchestration/rotation_state.json` and enforced runtime-budget validation from `.orchestration/runtime_budget.json`.

## Task Commits

Each task was committed atomically:

1. **Task 1: Route provider calls through the shared policy layer** - `8a80977` (test), `6db13a3` (feat)
2. **Task 2: Replace the static non-core tail with rotation-aware export planning and persist crash-survivable state across workflow runs** - `17b6203` (test), `27be5b5` (feat)

**Plan metadata:** pending final docs commit

## Files Created/Modified
- `provider_policies.py` - Adds shared pacing/retry execution with runtime counters and retry exhaustion errors.
- `export_canslim.py` - Builds retry-first rotation plans, persists freshness/retry state, writes runtime budget metrics, and finalizes the cursor only after publish success.
- `finmind_processor.py` - Wraps FinMind loader fetches in the shared provider policy contract.
- `tej_processor.py` - Routes TEJ table fetches through `_tej_get_with_policy(...)`.
- `yfinance_provider.py` - Provides shared yfinance price-history fetching with provider pacing.
- `tests/test_provider_policies.py` - Covers shared requests pacing plus FinMind/TEJ/yfinance routing.
- `tests/test_primary_publish_path.py` - Covers rotation-aware worklists, publish-boundary finalization, and retry-queue persistence.
- `.github/workflows/update_data.yml` - Restores/uploads named rotation-state artifacts and validates runtime budget.
- `.github/workflows/on_demand_update.yml` - Restores/uploads the same rotation-state artifact contract for on-demand runs.
- `.orchestration/runtime_budget.json` - Tracks `elapsed_seconds`, retry counts, and provider wait time for workflow validation.

## Decisions Made
- Reused `rotation_orchestrator.py` and `orchestration_state.py` seams from Phase 3 plan 02 rather than adding a second orchestration subsystem.
- Counted provider retries and wait time in the same mutable runtime state used by export summary generation so runtime-budget and publish telemetry stay aligned.
- Kept scheduled workflow persistence on the fixed `.orchestration/rotation_state.json` path while using a named artifact as the cross-run restore path.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
- Existing export publish-path tests started reading the workspace rotation state once `export_canslim.py` loaded durable orchestration state, so non-rotation tests were updated to stub `load_state(...)` and `build_daily_plan(...)` explicitly.

## User Setup Required

None - no external service configuration required.

## Known Stubs

- `tests/test_primary_publish_path.py:660` - Intentional `"placeholder"` parquet fixture content for export-dashboard tests; test-only stub, not production wiring.
- `tests/test_primary_publish_path.py:727` - Intentional `"placeholder"` parquet fixture content for publish-failure regression setup; test-only stub, not production wiring.

## Next Phase Readiness
- Phase 3 export/runtime behavior now matches the roadmap contract for retry-first rotation, durable resume state, and provider-aware throttling.
- Phase 4 can build freshness-aware merged publish outputs on top of the persisted rotation state and runtime-budget telemetry.

## Self-Check: PASSED

---
*Phase: 03-rotating-batch-orchestration*
*Completed: 2026-04-19*
