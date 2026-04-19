---
phase: 03-rotating-batch-orchestration
plan: 02
subsystem: orchestration
tags: [python, pytest, rotation, retries, state-machine]
requires:
  - phase: 03-01
    provides: durable rotation state and provider budget contracts
  - phase: 02-dynamic-core-selection
    provides: selector-derived core/non-core boundaries
provides:
  - deterministic three-way non-core rotation planning
  - retry-first daily worklists with reserved scheduled-batch capacity
  - explicit write/resume/finalize seams for durable batch orchestration
affects: [03-03, export_canslim.py, orchestration_state.py]
tech-stack:
  added: []
  patterns: [deterministic sorted partitioning, frozen in-progress batch resumes, finalize-success-only cursor advancement]
key-files:
  created:
    - rotation_orchestrator.py
    - tests/test_rotation_orchestrator.py
  modified:
    - orchestration_state.py
    - tests/test_rotation_state.py
key-decisions:
  - "Used a stable sorted non-core partition plus a joined-symbol generation fingerprint so universe churn is explicit without date offsets or hashing."
  - "Reserved scheduled-batch capacity before selecting due retries and advanced current_batch_index only inside finalize_success()."
patterns-established:
  - "Pattern 1: Freeze the scheduled batch in durable state before processing and resume only remaining_symbols."
  - "Pattern 2: Queue failed symbols separately from freshness so prior successful freshness survives retry scheduling."
requirements-completed: [ORCH-02, ORCH-03, ORCH-04]
duration: 4min
completed: 2026-04-19
---

# Phase 03 Plan 02: Implement deterministic partitioning, retry-first planning, and resume/finalization seams Summary

**Deterministic three-way non-core rotation with frozen-batch resume seams, due-retry prioritization, and success-only cursor advancement**

## Performance

- **Duration:** 4 min
- **Started:** 2026-04-19T02:16:38Z
- **Completed:** 2026-04-19T02:20:18Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments

- Added `rotation_orchestrator.py` with deterministic non-core grouping, generation tracking, retry-first plan assembly, and explicit state-machine seams.
- Extended rotation state freshness metadata so successful symbol completion persists `last_attempted_at`, `last_succeeded_at`, and `last_batch_generation`.
- Locked in resume/finalization behavior with regression coverage for frozen in-progress batches, retry queue handling, and finalize-success-only cursor movement.

## Task Commits

Each task was committed atomically:

1. **Task 1: Implement deterministic 3-way partitioning and generation-aware batch planning** - `a2ca903` (test), `ca5fdf1` (feat)
2. **Task 2: Add retry-first resume/finalization seams with success-based cursor advancement** - `e84c399` (test), `edee468` (feat)

_Note: Both tasks used TDD RED → GREEN commits._

## Files Created/Modified

- `rotation_orchestrator.py` - Pure orchestration helper with partitioning, retry planning, frozen batch writes, and finalize seams.
- `orchestration_state.py` - Expanded durable freshness schema and flexible retry-queue mutation support for in-memory finalization paths.
- `tests/test_rotation_orchestrator.py` - Covers partitioning, generation churn, retry-first planning, resume freezing, and finalize behavior.
- `tests/test_rotation_state.py` - Verifies the richer persisted freshness payload survives atomic save/load.

## Decisions Made

- Represented `rotation_generation` as the joined ordered non-core universe so generation changes are deterministic and human-inspectable.
- Treated retry-first scheduling as a leftover-capacity policy: due retries run first, but only from capacity not reserved for the scheduled batch.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Expanded `enqueue_retry_failure(...)` to support in-memory state mutation before the final atomic save**
- **Found during:** Task 2
- **Issue:** The existing helper only supported disk-first load/mutate/save usage, which blocked the planned verifier-friendly finalization seams from queueing failures and then completing one atomic state rewrite.
- **Fix:** Made `enqueue_retry_failure(...)` accept a validated in-memory state payload plus optional persistence so `finalize_failure()` and `finalize_success()` can compose durable state transitions safely.
- **Files modified:** `orchestration_state.py`
- **Verification:** `PYTHONPATH=. pytest -q tests/test_rotation_state.py tests/test_rotation_orchestrator.py -k "resume or retry or queue or finalize"`
- **Committed in:** `edee468`

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** The adjustment stayed within the planned orchestration files and was required to expose the explicit step-boundary seams the plan asked for.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- `export_canslim.py` can now replace its static non-core tail with `build_daily_plan(...)` plus `write_in_progress(...)` / `finalize_*()` orchestration hooks.
- Phase 03 Plan 03 can wire provider execution and publish checkpoints onto the new deterministic state machine without revisiting selector logic.

## Self-Check: PASSED

- Verified summary and implementation files exist on disk.
- Verified task commits `a2ca903`, `ca5fdf1`, `e84c399`, and `edee468` exist in git history.
