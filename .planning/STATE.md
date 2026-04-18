---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
status: unknown
last_updated: "2026-04-18T23:36:11.826Z"
progress:
  total_phases: 4
  completed_phases: 1
  total_plans: 6
  completed_plans: 5
  percent: 83
---

# State: tw-canslim-web

**Project:** tw-canslim-web  
**Milestone:** Strategy-Driven Update Pipeline Upgrade  
**Last Updated:** 2026-04-19 07:36 UTC+8

---

## Project Reference

**Core Value**: Keep the most actionable Taiwan stocks reliably fresh for trading decisions without losing broad market coverage.

**Current Focus**: Transform brownfield full-update pipeline into strategy-driven tiered update system with daily core stock freshness and 3-day rotating batch coverage.

**Key Context**: Brownfield upgrade of existing Python + GitHub Pages market-data pipeline. Proven CANSLIM calculation logic stays intact; adding orchestration intelligence to work sustainably within API rate limits (FinMind, TEJ, Yahoo Finance).

---

## Current Position

Phase: 02 (dynamic-core-selection) — EXECUTING
Plan: 3 of 3
**Phase**: 2 - Dynamic Core Selection  
**Plan**: 02 of 03 complete  
**Status**: In Progress  
**Progress**: `█████████████░░░░░░` 67%

**Current Work**: Phase 2 Plan 02 complete — selector artifacts now persist volume ranks and `core_selection.py` builds the required bucketed core universe ahead of export wiring.

**Blockers**: None

---

## Performance Metrics

### Completion Stats

- **Phases completed**: 1/4
- **Plans completed**: 5/6
- **Requirements validated**: 5/13
- **Current phase progress**: 67%

### Velocity

- **Plans per day**: 4/day
- **Days in current phase**: 1
- **Estimated phase completion**: Phase 2 in progress as of 2026-04-19

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

### Active TODOs

- [ ] Pre-Phase 1: Audit all 28 bare `except:` clauses identified by research (see CONCERNS.md)
- [ ] Pre-Phase 1: Test file locking proof-of-concept on macOS (fcntl availability)
- [ ] Pre-Phase 1: Map current API quota consumption baseline (run export_canslim.py with call counter)
- [x] Execute Phase 2 Plan 02 for artifact-backed volume-aware core-universe selection
- [ ] Execute Phase 2 Plan 03 to wire selector output into `export_canslim.py`

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

- Phase 2 Plan 02 persisted `latest_volume` and deterministic `volume_rank` fields into master/fused selector artifacts
- `core_selection.py` now loads config + artifact inputs, rejects stale fused data, and preserves required buckets for yesterday/today signals, RS leaders, and top-volume leaders
- Phase 2 selector verification now passes for persisted volume fields, overflow guards, and deterministic `mansfield_rs` fill ordering

### What's Next

1. Wire selector output into `export_canslim.py` in Phase 2 Plan 03 without regressing Phase 1 publish safety
2. Keep Phase 3 rotation work deferred until export wiring is complete

### Open Questions

- None (roadmap complete, awaiting user approval)

### Context for Next Agent

**If continuing after Phase 1 execution:**

**If continuing after Phase 2 Plan 02 execution:**

- `historical_generator.py` persists selector-ready `latest_volume` and `volume_rank` columns into `master_canslim_signals.parquet`
- `master_canslim_signals_fused.parquet` is now validated to carry those volume fields through `fuse_excel_data.py`
- `core_selection.py` returns bucket metadata plus `core_symbols`/`core_set`, preserving required buckets first and only using `docs/data_base.json` for `mansfield_rs` ranked fill

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
