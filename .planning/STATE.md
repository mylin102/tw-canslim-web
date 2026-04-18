# State: tw-canslim-web

**Project:** tw-canslim-web  
**Milestone:** Strategy-Driven Update Pipeline Upgrade  
**Last Updated:** 2026-04-18 11:30 UTC+8

---

## Project Reference

**Core Value**: Keep the most actionable Taiwan stocks reliably fresh for trading decisions without losing broad market coverage.

**Current Focus**: Transform brownfield full-update pipeline into strategy-driven tiered update system with daily core stock freshness and 3-day rotating batch coverage.

**Key Context**: Brownfield upgrade of existing Python + GitHub Pages market-data pipeline. Proven CANSLIM calculation logic stays intact; adding orchestration intelligence to work sustainably within API rate limits (FinMind, TEJ, Yahoo Finance).

---

## Current Position

**Phase**: 1 - Safety Hardening  
**Plan**: None (awaiting `/gsd-plan-phase 1`)  
**Status**: Not started  
**Progress**: `░░░░░░░░░░░░░░░░░░░░` 0%

**Current Work**: Roadmap complete, awaiting phase planning.

**Blockers**: None

---

## Performance Metrics

### Completion Stats
- **Phases completed**: 0/4
- **Plans completed**: 0/0
- **Requirements validated**: 0/13
- **Current phase progress**: 0%

### Velocity
- **Plans per day**: N/A (no plans executed yet)
- **Days in current phase**: 0
- **Estimated phase completion**: TBD after planning

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

### Active TODOs

- [ ] Run `/gsd-plan-phase 1` to decompose Safety Hardening into executable plans
- [ ] Pre-Phase 1: Audit all 28 bare `except:` clauses identified by research (see CONCERNS.md)
- [ ] Pre-Phase 1: Test file locking proof-of-concept on macOS (fcntl availability)
- [ ] Pre-Phase 1: Map current API quota consumption baseline (run export_canslim.py with call counter)

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
- Roadmap created from approved requirements (13 v1 requirements mapped to 4 phases)
- Phase structure derived from research recommendations (Foundation → Selection → Rotation → Publishing)
- 100% requirement coverage validated (no orphans)
- Success criteria derived using goal-backward methodology (2-5 observable behaviors per phase)

### What's Next
1. User reviews roadmap (ROADMAP.md)
2. If approved: Run `/gsd-plan-phase 1` to plan Safety Hardening
3. Phase 1 will decompose into plans for: file locking, bare exception removal, schema versioning, state persistence design

### Open Questions
- None (roadmap complete, awaiting user approval)

### Context for Next Agent
**If planning Phase 1:**
- Focus on foundation (file coordination, error visibility, schema evolution)
- Research flagged 28 bare exceptions in CONCERNS.md—audit needed
- File locking must cover ALL 6 scripts writing to data.json (not just new orchestrator)
- Schema versioning design must enable safe field additions without breaking resume

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
