---
phase: 03-rotating-batch-orchestration
plan: 01
subsystem: infra
tags: [python, pytest, json, orchestration, retries]
requires:
  - phase: 02-dynamic-core-selection
    provides: selector-derived core/non-core boundaries reused by later rotation work
provides:
  - durable repo-backed rotation state with atomic JSON persistence
  - explicit provider throttling and retry/backoff contracts
  - regression coverage for state durability and provider policies
affects: [03-02, export_canslim.py, finmind_processor.py, tej_processor.py]
tech-stack:
  added: []
  patterns: [atomic temp-file-plus-replace state writes, strict typed JSON schema validation, explicit provider policy table]
key-files:
  created:
    - .orchestration/rotation_state.json
    - orchestration_state.py
    - provider_policies.py
    - tests/test_rotation_state.py
    - tests/test_provider_policies.py
  modified:
    - tests/conftest.py
key-decisions:
  - "Persist rotation state only in .orchestration/rotation_state.json and reject malformed payloads instead of repairing them silently."
  - "Keep provider retry/throttle behavior in a pure ProviderPolicy table and preserve the 1000-symbol non-core daily budget as shared metadata."
patterns-established:
  - "Pattern 1: Seed missing orchestration state by atomically writing the schema-valid default payload."
  - "Pattern 2: Model provider pacing and backoff through deterministic dataclass contracts, not ad hoc sleeps."
requirements-completed: [ORCH-03, ORCH-05]
duration: 3min
completed: 2026-04-19
---

# Phase 03 Plan 01: Establish durable rotation state and shared provider-policy contracts Summary

**Atomic JSON rotation-state persistence plus explicit provider retry/throttle contracts for later batch orchestration wiring**

## Performance

- **Duration:** 3 min
- **Started:** 2026-04-19T02:05:39Z
- **Completed:** 2026-04-19T02:08:23Z
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments
- Added `orchestration_state.py` with strict schema validation, temp-file writes, and durable retry-queue persistence.
- Seeded `.orchestration/rotation_state.json` with the tracked empty-but-valid state payload required for deterministic repo updates.
- Added `provider_policies.py` and targeted pytest coverage for concrete throttling/backoff defaults across requests, FinMind, TEJ, and yfinance.

## Task Commits

Each task was committed atomically:

1. **Task 1: Create durable orchestration-state contracts and regression coverage** - `4afdf3c` (test), `29759a1` (feat)
2. **Task 2: Define provider retry/backoff policy contracts with executable tests** - `ef4b946` (test), `ca826bb` (feat)

## Files Created/Modified
- `.orchestration/rotation_state.json` - Checked-in durable seed state for Phase 3 orchestration.
- `orchestration_state.py` - Load/save helpers, strict schema validation, and retry queue persistence.
- `provider_policies.py` - Frozen provider policy dataclass table and deterministic backoff helper.
- `tests/conftest.py` - Shared fixture for temp rotation-state paths.
- `tests/test_rotation_state.py` - Regression coverage for default seeding, atomic saves, and retry queue durability.
- `tests/test_provider_policies.py` - Regression coverage for explicit provider contracts and backoff semantics.

## Decisions Made
- Stored orchestration state in `.orchestration/rotation_state.json` only, using temp-file writes plus `os.replace` to mitigate corruption at the repo file boundary.
- Preserved the default non-core daily budget at 1000 in `provider_policies.py` and required all supported providers to declare throttling fields explicitly.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Verification used `python3` because `python` is unavailable in this environment**
- **Found during:** Task 1
- **Issue:** The acceptance-criteria probe for `.orchestration/rotation_state.json` failed because the local shell has `python3` but not `python`.
- **Fix:** Re-ran the verification step with `python3` while keeping all repo test commands on the required `PYTHONPATH=. pytest ...` form.
- **Files modified:** None
- **Verification:** `python3 -c "import json; ..."` and `PYTHONPATH=. pytest -q tests/test_rotation_state.py`
- **Committed in:** none (verification-only adjustment)

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** Verification-only adjustment; shipped scope stayed exactly within the planned files and contracts.

## Issues Encountered
- Local shell lacks a `python` alias; verification needed `python3`.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Ready for Plan 03-02 to build deterministic partitioning and retry-first planning on top of the new durable state and provider-policy seams.
- `export_canslim.py`, `finmind_processor.py`, and `tej_processor.py` can now consume centralized provider contracts without inventing new retry metadata formats.

## Deviations from Threat Model
None - implemented mitigations match the plan's state-tampering and retry-policy threat register.

## Self-Check: PASSED
