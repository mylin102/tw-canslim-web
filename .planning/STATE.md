---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
status: unknown
last_updated: "2026-04-19T02:42:55.814Z"
progress:
  total_phases: 4
  completed_phases: 3
  total_plans: 9
  completed_plans: 9
  percent: 100
---

# State: tw-canslim-web

**Project:** tw-canslim-web  
**Milestone:** Strategy-Driven Update Pipeline Upgrade  
**Last Updated:** 2026-04-19 10:21 UTC+8

---

## Project Reference

**Core Value**: Keep the most actionable Taiwan stocks reliably fresh for trading decisions without losing broad market coverage.

**Current Focus**: Transform brownfield full-update pipeline into strategy-driven tiered update system with daily core stock freshness and 3-day rotating batch coverage.

**Key Context**: Brownfield upgrade of existing Python + GitHub Pages market-data pipeline. Proven CANSLIM calculation logic stays intact; adding orchestration intelligence to work sustainably within API rate limits (FinMind, TEJ, Yahoo Finance).

---

## Current Position

Phase: 04 (publishing-freshness-awareness) — READY
Plan: 0 of 0
**Phase**: 4 - Publishing & Freshness Awareness  
**Plan**: 00 of 00 complete  
**Status**: Ready to plan  
**Progress**: `████████████████████` 100%

**Current Work**: Phase 3 is complete and verified — deterministic three-way rotation, durable resume state, provider-policy wiring, workflow restore/persist checkpoints, and runtime budget gating are now live.

**Blockers**: None

---

## Performance Metrics

### Completion Stats

- **Phases completed**: 3/4
- **Plans completed**: 9/9
- **Requirements validated**: 13/13
- **Current phase progress**: 100%

### Velocity

- **Plans per day**: 9/day
- **Days in current phase**: 1
- **Estimated phase completion**: Phase 3 completed on 2026-04-19

### Quality

- **Failed plans (current phase)**: 0
- **Rework ratio**: 0%
- **Blocker incidents**: 0

---

## Accumulated Context

### Decisions Made

| Date | Decision | Rationale | Impact |
|------|----------|-----------|--------|
| 2026-04-18 | Split research-recommended 3 phases into 4 phases (separate dynamic core selection from rotation) | Standard granularity guidance + core selection is high-value differentiator | Phase 2 focuses solely on signal-driven priority logic; Phase 3 handles rotation mechanics |
| 2026-04-18 | Sequence safety hardening before orchestration | Research flagged 28 bare exceptions, file coordination issues, and production corruption incidents | Phase 1 foundation prevents amplifying existing problems |
| 2026-04-18 | Brownfield approach: reuse CanslimEngine, add orchestration layer | Codebase analysis shows proven calculation logic; problem is update strategy, not scoring | Minimal refactor risk, faster delivery |
| 2026-04-19 | Use one docs/.publish.lock file to serialize related artifact bundle publishes | Bundle-level lock prevents mixed live versions across related docs artifacts | Plans 02-03 can migrate writers onto one shared publish contract |
| 2026-04-19 | Keep only the latest manifest-backed snapshot under backups/last_good | Restore must be deterministic and operator-friendly during publish failures | Rollback path is simple and bounded to the most recent validated bundle |
| Phase 01-safety-hardening P02 | 16m | 2 tasks | 3 files |

- [Phase 01-safety-hardening]: Fallback to helper-first resume loading, then raw stock-level revalidation when a whole artifact is incompatible.
- [Phase 01-safety-hardening]: Keep dashboard exports on the shared data artifact contract by adding validator-required metadata and CANSLIM fields.

| Phase 01-safety-hardening P03 | 18min | 3 tasks | 12 files |

- [Phase 01-safety-hardening]: Keep operational data/data_light payloads on the validated stock schema so supported writers can share publish_artifact_bundle.
- [Phase 01-safety-hardening]: Deprecate unsupported legacy direct writers instead of migrating every historical utility in Phase 1.
- [Phase 01-safety-hardening]: Use one publish-surface concurrency group across scheduled and on-demand workflows.

| Phase 02 P01 | 2m | 2 tasks | 5 files |

- [Phase 02]: Keep fixed selector buckets in checked-in JSON with exact-key and 4-digit symbol validation.
- [Phase 02]: Derive today and carryover signal buckets from the latest two fused parquet dates and fail closed when fused data is stale.
- [Phase 02]: Restore institutional compatibility with calculate_i_factor while preserving the conviction bonus path.

| Phase 02 P02 | 4m | 2 tasks | 4 files |

- [Phase 02]: Persist latest_volume and date-level volume_rank in the master parquet so selector volume leaders stay artifact-driven.
- [Phase 02]: Fail closed when fused parquet freshness or selector-required columns drift from master artifacts.
- [Phase 02]: Preserve all required selector buckets first, expand only up to 500 names, then fill by (-mansfield_rs, volume_rank, symbol).

| Phase 02 P03 | 21m | 2 tasks | 3 files |

- [Phase 02]: Kept export wiring on build_core_universe(...) by extending the selector helper to accept artifact paths without breaking existing selector unit tests.
- [Phase 02]: Preserved the brownfield non-core tail exactly as selection.core_symbols plus the first 2000 remaining sorted tickers.

| Phase 03 P01 | 3min | 2 tasks | 6 files |

- [Phase 03]: Persist rotation state only in .orchestration/rotation_state.json with strict schema validation and atomic os.replace writes.
- [Phase 03]: Keep provider retry and throttling defaults in a pure ProviderPolicy table while preserving the 1000-symbol non-core daily budget.

| Phase 03 P02 | 4m | 2 tasks | 4 files |

- [Phase 03]: Used a stable sorted non-core partition plus a joined-symbol generation fingerprint so universe churn is explicit without date offsets or hashing.
- [Phase 03]: Reserved scheduled-batch capacity before selecting due retries and advanced current_batch_index only inside finalize_success().

| Phase 03 P03 | 13min | 2 tasks | 10 files |

- [Phase 03]: Reuse the Phase 3 rotation/state seams from export_canslim.py and add export-side persistence helpers for retry/core freshness instead of introducing a new orchestration layer.
- [Phase 03]: Keep provider pacing and retry accounting in one shared runtime-state contract so export summaries and runtime-budget artifacts derive from the same counters.
- [Phase 03]: Restore rotation checkpoints through a named GitHub artifact before each workflow run and still commit the fixed .orchestration/rotation_state.json path on scheduled publishes.

### Active TODOs

- [ ] Pre-Phase 1: Audit all 28 bare `except:` clauses identified by research (see CONCERNS.md)
- [ ] Pre-Phase 1: Test file locking proof-of-concept on macOS (fcntl availability)
- [ ] Pre-Phase 1: Map current API quota consumption baseline (run export_canslim.py with call counter)
- [x] Execute Phase 2 Plan 02 for artifact-backed volume-aware core-universe selection
- [x] Execute Phase 2 Plan 03 to wire selector output into `export_canslim.py`
- [x] Execute Phase 3 Plan 01 for durable rotation state and shared provider policy contracts

### Known Issues

| Issue | Severity | Discovered | Status |
|-------|----------|------------|--------|
| 28 bare `except:` clauses causing silent API failures | HIGH | Research (CONCERNS.md) | Mitigated on supported publish paths in Phase 1 |
| 6 scripts write to data.json without coordination (race conditions) | CRITICAL | Research (CONCERNS.md) | Resolved for supported/operational publish paths in Phase 1 |
| No schema versioning (resume breaks when fields added) | HIGH | Research (CONCERNS.md) | Resolved for supported publish artifacts in Phase 1 |
| No rollback mechanism (bad updates corrupt GitHub Pages) | MEDIUM | Research (POST_MORTEM) | Resolved with manifest-backed bundle restore CLI in Phase 1 |

---

## Research Insights

**Key Findings** (from research/SUMMARY.md):

- Research confidence: HIGH (grounded in codebase analysis, production incidents, update_strategy.md)
- Recommended stack: Minimal dependencies (ratelimit, backoff, requests-cache)
- Critical pitfalls identified: 8 major risks catalogued, all addressed by phase sequencing
- Existing prototypes: batch_update_institutional.py already implements modulo-3 rotation pattern

**Research Flags for Phases**:

- Phase 2: Verify alpha_integration_module.py signal detection API
- Phase 3: Calibrate rotation group size (500 vs 700 vs 1000 stocks/day)
- Phase 4: Measure stock_index.json frontend bundle impact (~200KB)

**Strategic Recommendations**:

- Build on existing CanslimEngine (don't rebuild)
- Fix file coordination and error handling BEFORE scaling orchestration
- Dynamic core selection (base + volume + RS + signals) is high-value differentiator
- 3-day rotation cycle balances API limits with full market coverage

---

## Session Continuity

### What Just Happened

- Phase 3 Plan 03 wired `build_daily_plan(...)`, `write_in_progress(...)`, and `finalize_*()` into `export_canslim.py` without breaking Phase 1 publish safety.
- Shared provider pacing/retry policies now cover requests, FinMind, TEJ, and yfinance through one explicit contract.
- Scheduled and on-demand workflows now restore and persist `.orchestration/rotation_state.json`, and the runtime budget gate records `.orchestration/runtime_budget.json`.

### What's Next

1. Start Phase 4 planning for publishing and freshness-aware outputs.
2. Keep building on the Phase 3 rotation/workflow seams without introducing a database or replacing the existing publish contract.

### Open Questions

- None

### Context for Next Agent

**If continuing after Phase 1 execution:**

**If continuing after Phase 3 completion:**

- `export_canslim.py` now assembles `selection.core_symbols + daily_plan["worklist"]`, checkpoints scheduled batches with `write_in_progress(...)`, records per-symbol freshness, and advances the cursor only after final publish success.
- Provider policy enforcement is centralized in `provider_policies.py`, with live wiring in `export_canslim.py`, `finmind_processor.py`, `tej_processor.py`, and `yfinance_provider.py`.
- Tests now exist at `tests/test_rotation_state.py`, `tests/test_rotation_orchestrator.py`, `tests/test_provider_policies.py`, and rotation-aware `tests/test_primary_publish_path.py`; continue using `PYTHONPATH=. pytest ...` for all verification.

**If user requests revision:**

- Common revision requests: granularity adjustment, phase merging/splitting, success criteria clarification
- All requirements must stay mapped (100% coverage non-negotiable)

---

## Milestone Context

**Milestone Goal**: Deliver strategy-driven update pipeline that keeps core trading candidates fresh daily while achieving full market coverage within 3 days.

**Milestone Scope**: 

- v1: Safety hardening, dynamic core selection, rotating batch orchestration, freshness-aware publishing
- v2 (deferred): Adaptive batch sizing, diff-oriented updates, historical freshness tracking, alpha-weighted scoring, industry rotation

**Milestone Success Criteria**:

- Core stocks (signals + volume + RS) achieve 100% daily freshness
- Full Taiwan market covered within 3-day rotation cycle
- Dashboard shows explicit freshness indicators for all stocks
- Zero data corruption incidents (down from current sporadic issues)
- Update time <20 minutes per daily run

---

*State initialized: 2026-04-18 after roadmap creation*
