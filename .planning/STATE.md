---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
status: in_progress
last_updated: "2026-04-18T21:07:46Z"
progress:
  total_phases: 4
  completed_phases: 0
  total_plans: 3
  completed_plans: 1
  percent: 33
---

# State: tw-canslim-web

**Project:** tw-canslim-web  
**Milestone:** Strategy-Driven Update Pipeline Upgrade  
**Last Updated:** 2026-04-19 05:07 UTC+8

---

## Project Reference

**Core Value**: Keep the most actionable Taiwan stocks reliably fresh for trading decisions without losing broad market coverage.

**Current Focus**: Transform brownfield full-update pipeline into strategy-driven tiered update system with daily core stock freshness and 3-day rotating batch coverage.

**Key Context**: Brownfield upgrade of existing Python + GitHub Pages market-data pipeline. Proven CANSLIM calculation logic stays intact; adding orchestration intelligence to work sustainably within API rate limits (FinMind, TEJ, Yahoo Finance).

---

## Current Position

**Phase**: 1 - Safety Hardening  
**Plan**: 02 of 03  
**Status**: In progress  
**Progress**: `███████░░░░░░░░░░░░░` 33%

**Current Work**: Plan 01 complete — artifact-aware publish safety helper and regression scaffolds are in place; Plan 02 is next.

**Blockers**: None

---

## Performance Metrics

### Completion Stats

- **Phases completed**: 0/4
- **Plans completed**: 1/3
- **Requirements validated**: 4/13
- **Current phase progress**: 33%

### Velocity

- **Plans per day**: 1/day
- **Days in current phase**: 1
- **Estimated phase completion**: TBD after Plans 02-03 velocity

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

### Active TODOs

- [ ] Pre-Phase 1: Audit all 28 bare `except:` clauses identified by research (see CONCERNS.md)
- [ ] Pre-Phase 1: Test file locking proof-of-concept on macOS (fcntl availability)
- [ ] Pre-Phase 1: Map current API quota consumption baseline (run export_canslim.py with call counter)
- [ ] Execute Plan 02 to migrate primary exporters to the shared publish helper
- [ ] Execute Plan 03 to migrate incremental writers and rollback CLI validation

### Known Issues

| Issue | Severity | Discovered | Status |
|-------|----------|------------|--------|
| 28 bare `except:` clauses causing silent API failures | HIGH | Research (CONCERNS.md) | Pending Phase 1 |
| 6 scripts write to data.json without coordination (race conditions) | CRITICAL | Research (CONCERNS.md) | Pending Phase 1 |
| No schema versioning (resume breaks when fields added) | HIGH | Research (CONCERNS.md) | Pending Phase 1 |
| No rollback mechanism (bad updates corrupt GitHub Pages) | MEDIUM | Research (POST_MORTEM) | Pending Phase 1 |

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

- Plan 01 completed for Phase 1 with bundle-safe publish helper, backup/restore support, and artifact-aware validation
- Regression coverage added for bundle locking, snapshot retention, restore flow, and resume compatibility
- Smoke scaffolds added for primary writers, operational writers, and workflow concurrency migration checks

### What's Next

1. Execute Plan 02 to migrate primary exporters to `publish_artifact_bundle`
2. Add workflow-level concurrency and explicit-failure publish wiring
3. Execute Plan 03 to migrate incremental/operational writers and validate rollback CLI flows

### Open Questions

- None (roadmap complete, awaiting user approval)

### Context for Next Agent

**If continuing Phase 1 execution:**

- `publish_safety.py` now provides `load_artifact_json`, `validate_artifact_payload`, `validate_resume_stock_entry`, `publish_artifact_bundle`, and `restore_latest_bundle`
- Plan 02 should wire primary exporters and workflows to the shared helper and activate skipped smoke assertions
- Plan 03 should migrate operational writers and turn on deprecated-writer guard assertions

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
