---
phase: 04-publishing-freshness-awareness
plan: 01
subsystem: infra
tags: [python, pytest, publishing, freshness, stock-index]
requires:
  - phase: 03-rotating-batch-orchestration
    provides: "Per-stock freshness state, deterministic batch planning, and finalize-after-publish rotation semantics"
provides:
  - "Merged data.json projection with per-stock freshness metadata"
  - "Validated stock_index.json full-universe search payload"
  - "Update summary preview with refreshed, failed, and next-rotation details"
affects: [frontend-search, publish-bundle, operator-summary]
tech-stack:
  added: []
  patterns: [projection-layer publishing, bundle-safe multi-artifact export, per-symbol freshness disclosure]
key-files:
  created: [publish_projection.py, tests/test_publish_freshness.py, tests/test_stock_index.py, tests/test_publish_merge.py, tests/test_publish_summary_phase4.py]
  modified: [export_canslim.py, publish_safety.py, tests/conftest.py, tests/test_export_schema.py, tests/test_publish_safety.py, tests/test_primary_publish_path.py]
key-decisions:
  - "Added publish_projection.py as the single seam that derives merged data, stock index, and summary payloads from one snapshot."
  - "Used docs/data_base.json as the merged snapshot floor while keeping non-snapshot symbols discoverable only through stock_index.json."
  - "Previewed next rotation from cloned state with an advanced batch index so finalize_success remains the only live cursor mutation."
patterns-established:
  - "Projection helpers enrich published artifacts from durable orchestration state instead of creating another persistence layer."
  - "Primary publish path validates and promotes data.json, stock_index.json, and update_summary.json together."
requirements-completed: [PUB-01, PUB-02, PUB-03, PUB-04]
duration: 6min
completed: 2026-04-19
---

# Phase 4 Plan 01: Publishing Projection Summary

**Freshness-aware publish projection now emits merged screener data, a full-universe stock index, and rotation-safe operator summaries from Phase 3 state.**

## Performance

- **Duration:** 6 min
- **Started:** 2026-04-19T04:31:12Z
- **Completed:** 2026-04-19T04:36:48Z
- **Tasks:** 2
- **Files modified:** 11

## Accomplishments
- Added Phase 4 regression coverage for freshness labels, merged snapshot precedence, stock index generation, and next-rotation summary previews.
- Implemented `publish_projection.py` to derive `data.json`, `stock_index.json`, and `update_summary.json` from current output, baseline coverage, and durable freshness state.
- Extended `publish_safety.py` and `export_canslim.py` so the primary publish bundle validates and promotes all three artifacts together without advancing live rotation state early.

## Task Commits

Each task was committed atomically:

1. **Task 1: Add Phase 4 publish regression scaffolding before implementation** - `5e92fdb` (test)
2. **Task 2: Implement the publish projection layer and wire it into the primary export bundle** - `ae8ec96` (test), `4b3bc02` (feat)

## Files Created/Modified
- `publish_projection.py` - Builds merged publish payloads, stock index entries, freshness labels, and next-rotation summary previews.
- `export_canslim.py` - Projects and publishes `data.json`, `stock_index.json`, and `update_summary.json` in one bundle-safe transaction.
- `publish_safety.py` - Validates `stock_index.json` artifacts before promotion.
- `tests/conftest.py` - Adds shared fixtures for freshness state, stock-index payloads, and Phase 4 publish bundles.
- `tests/test_publish_freshness.py` - Covers 3-level freshness projection from per-symbol `last_succeeded_at`.
- `tests/test_stock_index.py` - Covers full-universe index membership and non-snapshot symbol handling.
- `tests/test_publish_merge.py` - Covers baseline-floor merge behavior with fresher snapshot overrides.
- `tests/test_publish_summary_phase4.py` - Covers refreshed/failed summary fields and next-rotation previews.
- `tests/test_primary_publish_path.py` - Verifies the primary publish bundle now includes `stock_index.json`.
- `tests/test_publish_safety.py` - Verifies bundle publishing promotes `stock_index.json` with the primary artifacts.
- `tests/test_export_schema.py` - Verifies stock-index payloads are accepted by publish validation.

## Decisions Made
- Added a dedicated publish projection layer rather than embedding merge/index logic directly in `export_canslim.py`, keeping the brownfield exporter readable.
- Kept `data.json` focused on merged snapshot membership while `stock_index.json` carries full ticker-universe discoverability for non-snapshot symbols.
- Derived next-rotation previews from cloned state with an advanced batch index so Phase 3's finalize-after-publish contract remains intact.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Corrected the next-rotation preview expectation in new regression coverage**
- **Found during:** Task 2 (Implement the publish projection layer and wire it into the primary export bundle)
- **Issue:** The newly added summary regression expected the wrong third rotation group for the deterministic 3-way partition.
- **Fix:** Updated `tests/test_publish_summary_phase4.py` to match the actual `build_daily_plan(...)` grouping contract before finalizing the implementation.
- **Files modified:** `tests/test_publish_summary_phase4.py`
- **Verification:** `PYTHONPATH=. pytest -q tests/test_publish_summary_phase4.py tests/test_primary_publish_path.py -x`
- **Committed in:** `4b3bc02`

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** The correction aligned new scaffolding with Phase 3's verified rotation semantics; no scope creep was introduced.

## Issues Encountered
- Runtime publish tests initially resolved `data_base.json` from the repo-level `docs/` directory after `OUTPUT_DIR` monkeypatching. The exporter now resolves baseline and stock-index paths from the active output directory at publish time.

## User Setup Required

None - no external service configuration required.

## Known Stubs

| File | Line | Reason |
|------|------|--------|
| `tests/test_primary_publish_path.py` | 771 | `"placeholder"` is a test-only parquet fixture marker, not a user-facing runtime stub. |
| `tests/test_primary_publish_path.py` | 838 | `"placeholder"` is a test-only parquet fixture marker, not a user-facing runtime stub. |

## Next Phase Readiness
- Backend publish contracts now expose the freshness-aware data needed for frontend search and rendering work in later Phase 4 plans.
- No blockers were introduced; Phase 3 rotation semantics remain preserved.

## Self-Check: PASSED

- Verified summary and projection/test files exist on disk.
- Verified task commits `5e92fdb`, `ae8ec96`, and `4b3bc02` exist in git history.
