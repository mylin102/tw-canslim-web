---
phase: 01-safety-hardening
plan: 03
subsystem: infra
tags: [python, github-actions, publish-safety, rollback, workflow-concurrency]
requires:
  - phase: 01-01
    provides: publish_safety bundle validation, locking, and restore helpers
provides:
  - bundle-safe operational quick and batch publishes
  - bundle-safe verification and single-stock publish flows
  - deterministic rollback CLI and serialized publish workflows
affects: [phase-2-orchestration, operational-maintenance, github-actions]
tech-stack:
  added: []
  patterns: [publish_artifact_bundle for operational writers, restore_latest_bundle CLI wrapper, shared workflow concurrency group]
key-files:
  created: [.planning/phases/01-safety-hardening/01-03-SUMMARY.md]
  modified: [quick_auto_update_enhanced.py, batch_update_institutional.py, verify_local.py, restore_publish_snapshot.py, update_single_stock.py, quick_auto_update.py, quick_data_gen.py, fast_data_gen.py, .github/workflows/update_data.yml, .github/workflows/on_demand_update.yml, tests/test_operational_publish_path.py, tests/test_publish_workflows.py]
key-decisions:
  - "Keep operational data/data_light payloads on the validated stock schema so all supported writers can publish through publish_artifact_bundle."
  - "Deprecate unsupported legacy direct writers instead of widening Phase 1 scope to migrate every historical utility."
  - "Use one publish-surface concurrency group across scheduled and on-demand workflows."
patterns-established:
  - "Operational writers must load validated artifacts and publish related docs outputs as one locked bundle."
  - "Rollback entrypoints should resolve the full validated bundle, not individual files."
requirements-completed: [SAFE-01, SAFE-02, SAFE-03, SAFE-04]
duration: 18min
completed: 2026-04-19
---

# Phase 1 Plan 03: Migrate incremental publish scripts and add rollback CLI validation Summary

**Bundle-safe quick, batch, verification, and on-demand publish flows with deterministic rollback and serialized GitHub Actions publish surfaces**

## Performance

- **Duration:** 18 min
- **Started:** 2026-04-19T05:13:10+08:00
- **Completed:** 2026-04-19T05:31:28+08:00
- **Tasks:** 3
- **Files modified:** 12

## Accomplishments
- Migrated supported operational quick and batch writers onto `publish_artifact_bundle(...)` with explicit retry/failure summary data.
- Hardened `verify_local.py`, `update_single_stock.py`, and new `restore_publish_snapshot.py` around the shared publish and rollback helpers.
- Deprecated unsupported live writers and serialized both GitHub Actions entry points with one publish-surface concurrency group.

## Task Commits

Each task was committed atomically:

1. **Task 1: Migrate supported quick and batch writers to bundle-safe publish with explicit update summaries** - `895a062`, `4e7dd75`
2. **Task 2: Harden verification, rollback, and on-demand single-stock publishing** - `900187d`, `9fc29de`
3. **Task 3: Deprecate unsupported live writers and serialize the scheduled workflow** - `d4e9411`, `97b2e20`

**Plan metadata:** pending final docs commit

## Files Created/Modified
- `quick_auto_update_enhanced.py` - Loads validated artifacts, records retries/failures, and publishes `data.json`, `data_light.json`, and `update_summary.json` as one bundle.
- `batch_update_institutional.py` - Migrates batch institutional updates to validated bundle publishing with next-batch summary metadata.
- `verify_local.py` - Adds explicit benchmark fallback logging and bundle-safe verification publish helper.
- `restore_publish_snapshot.py` - Wraps `restore_latest_bundle(...)` in a deterministic rollback CLI for the full publish bundle.
- `update_single_stock.py` - Updates `data_base.json` and derived artifacts through one bundle-safe publish transaction.
- `quick_auto_update.py` - Deprecated before any live `docs/` writes.
- `quick_data_gen.py` - Deprecated before any live `docs/` writes.
- `fast_data_gen.py` - Deprecated before any live `docs/` writes.
- `.github/workflows/update_data.yml` - Adds shared publish-surface concurrency for scheduled/manual runs.
- `.github/workflows/on_demand_update.yml` - Adds shared publish-surface concurrency and stages `update_summary.json`.
- `tests/test_operational_publish_path.py` - Adds executable regressions for quick, batch, verification, and single-stock publish paths.
- `tests/test_publish_workflows.py` - Adds rollback, concurrency, and deprecated-writer regression coverage.

## Decisions Made
- Used the shared publish helper for supported operational writers even when generating `data_light.json`, keeping payloads on the validated stock schema so bundle validation stays consistent.
- Added rollback as a dedicated CLI wrapper instead of bespoke file-copy logic to keep recovery deterministic and aligned with the manifest-backed snapshot contract.
- Explicitly deprecated unsupported writers rather than migrating them, matching the plan’s scope boundary for Phase 1.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Normalized rollback CLI targets to the current workspace**
- **Found during:** Task 3 (Deprecate unsupported live writers and serialize the scheduled workflow)
- **Issue:** `restore_publish_snapshot.py` needed to resolve bundle targets against the active workspace so manifest-backed snapshots created from absolute paths restore correctly in deterministic tests and local runs.
- **Fix:** Resolved default rollback targets to absolute workspace paths before calling `restore_latest_bundle(...)`.
- **Files modified:** `restore_publish_snapshot.py`
- **Verification:** `PYTHONPATH=. pytest tests/test_publish_workflows.py -q`
- **Committed in:** `97b2e20`

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** The fix was required for deterministic rollback correctness. No scope creep beyond the publish-safety contract.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Phase 1 publish paths now share one safe operational contract and deterministic rollback path.
- Phase 2 can build orchestration logic on top of serialized workflows and explicit update summaries without inheriting unsafe live writers.

## Self-Check: PASSED
