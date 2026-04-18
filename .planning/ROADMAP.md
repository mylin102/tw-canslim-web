# Roadmap: tw-canslim-web Strategy-Driven Update Pipeline

**Project:** tw-canslim-web  
**Milestone:** Strategy-Driven Update Pipeline Upgrade  
**Created:** 2026-04-18  
**Granularity:** Standard (balanced)

---

## Overview

Transform the existing full-update pipeline into a strategy-driven tiered update system that keeps trading-critical stocks fresh daily while rotating the rest of the Taiwan market on a 3-day cycle. This brownfield upgrade builds on proven CANSLIM calculation logic while adding orchestration intelligence to work sustainably within API rate limits.

**Core Value:** Keep the most actionable Taiwan stocks reliably fresh for trading decisions without losing broad market coverage.

**Coverage:** 13/13 v1 requirements mapped ✓

---

## Phases

- [ ] **Phase 1: Safety Hardening** - Eliminate data corruption and silent failures before scaling orchestration
- [ ] **Phase 2: Dynamic Core Selection** - Implement signal-driven priority selection for daily core stock universe
- [ ] **Phase 3: Rotating Batch Orchestration** - Build 3-day rotation system with persistent state and resume capability
- [ ] **Phase 4: Publishing & Freshness Awareness** - Deliver merged outputs with explicit freshness metadata and update summaries

---

## Phase Details

### Phase 1: Safety Hardening
**Goal**: Maintainer can run concurrent update workflows without data corruption or silent API failures.

**Depends on**: Nothing (foundation phase)

**Requirements**: SAFE-01, SAFE-02, SAFE-03, SAFE-04

**Success Criteria** (what must be TRUE):
1. Maintainer can run multiple update scripts simultaneously without corrupting data.json or other JSON artifacts
2. Maintainer sees explicit error logs for every API failure instead of silent suppression
3. Maintainer can add new fields to exported stock schemas without breaking resume logic or existing data
4. Maintainer can abort a failed update run and rollback to the last validated snapshot within 5 minutes

**Plans**: TBD

---

### Phase 2: Dynamic Core Selection
**Goal**: Maintainer can automatically prioritize daily updates for stocks with active trading signals and market strength.

**Depends on**: Phase 1 (requires safe file coordination and schema versioning)

**Requirements**: ORCH-01

**Success Criteria** (what must be TRUE):
1. Maintainer gets a daily core stock list that automatically includes base symbols (2330, 0050, etc.), volume leaders (top 100), RS leaders (RS > 80), and stocks with active ORB/counter_vwap signals
2. Core selection updates dynamically each run without manual list maintenance
3. Core list size stays within 200-500 stocks to respect API budgets
4. Signal stocks (ORB breakouts, volume spikes) always appear in the core list on signal detection day

**Plans**: TBD

---

### Phase 3: Rotating Batch Orchestration
**Goal**: Maintainer can rotate non-core stocks through deterministic batches to achieve full market coverage within 3 days.

**Depends on**: Phase 2 (requires core selection to separate priority stocks from rotation pool)

**Requirements**: ORCH-02, ORCH-03, ORCH-04, ORCH-05

**Success Criteria** (what must be TRUE):
1. Non-core stocks rotate through 3 deterministic groups so the full Taiwan market completes one cycle every 3 days
2. Orchestration state (rotation position, per-stock freshness, failed stock tracking) persists across runs and survives crashes
3. Maintainer can resume a partial update run without re-fetching already-updated stocks from that batch
4. Daily pipeline completes within 20 minutes using throttling and retry behavior appropriate to each data source (FinMind, TEJ, Yahoo Finance)
5. Maintainer sees which stocks failed, which rotated, and which rotate next via persistent state tracking

**Plans**: TBD

**UI hint**: yes

---

### Phase 4: Publishing & Freshness Awareness
**Goal**: Dashboard user can see explicit freshness metadata and search the full market even when stocks aren't in the main screener snapshot.

**Depends on**: Phase 3 (requires merged baseline-plus-incremental data model and rotation state)

**Requirements**: PUB-01, PUB-02, PUB-03, PUB-04

**Success Criteria** (what must be TRUE):
1. Dashboard user sees freshness indicators (🟢 today, 🟡 1-2 days, 🔴 3+ days) for every stock and knows when data is stale
2. Dashboard user can search the full stock universe through stock_index.json even if a stock isn't in the top 1000 screener snapshot
3. Dashboard loads stock and screener data from merged baseline-plus-incremental outputs (data.json reflects both daily core updates and rotating batch coverage)
4. Maintainer sees an update summary artifact (update_summary.json) showing what refreshed, what failed, and what rotates next run

**Plans**: TBD

**UI hint**: yes

---

## Progress Table

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Safety Hardening | 0/0 | Not started | - |
| 2. Dynamic Core Selection | 0/0 | Not started | - |
| 3. Rotating Batch Orchestration | 0/0 | Not started | - |
| 4. Publishing & Freshness Awareness | 0/0 | Not started | - |

---

## Requirement Coverage

| Requirement | Phase | Category |
|-------------|-------|----------|
| SAFE-01 | Phase 1 | Safety & Reliability |
| SAFE-02 | Phase 1 | Safety & Reliability |
| SAFE-03 | Phase 1 | Safety & Reliability |
| SAFE-04 | Phase 1 | Safety & Reliability |
| ORCH-01 | Phase 2 | Orchestration |
| ORCH-02 | Phase 3 | Orchestration |
| ORCH-03 | Phase 3 | Orchestration |
| ORCH-04 | Phase 3 | Orchestration |
| ORCH-05 | Phase 3 | Orchestration |
| PUB-01 | Phase 4 | Publishing & UX |
| PUB-02 | Phase 4 | Publishing & UX |
| PUB-03 | Phase 4 | Publishing & UX |
| PUB-04 | Phase 4 | Publishing & UX |

**Total:** 13/13 requirements mapped ✓

---

## Dependencies & Sequencing

**Critical path:**
1. Phase 1 must complete before Phase 2 (safe file coordination enables concurrent core selection)
2. Phase 2 must complete before Phase 3 (core selection separates priority stocks from rotation pool)
3. Phase 3 must complete before Phase 4 (rotation state and merged data model enable freshness-aware publishing)

**Research flags:**
- Phase 2: Verify signal detection integration point (alpha_integration_module.py API)
- Phase 3: Calibrate optimal rotation group size (500 vs 700 vs 1000 stocks/day) after quota tracking implemented
- Phase 4: Measure frontend bundle size impact of stock_index.json (~200KB estimated)

---

## Notes

**Architecture approach**: Brownfield upgrade—reuse existing CanslimEngine and data processors, add orchestration layer on top. Minimal new dependencies (ratelimit, backoff, requests-cache).

**Research alignment**: This roadmap implements the 3-phase structure recommended by research (Foundation & Safety → Orchestration → Publishing), with Phase 2 split out for finer-grained dynamic core selection (Standard granularity).

**Key risks mitigated by sequencing:**
- File corruption (addressed Phase 1 before scaling)
- Static core list drift (addressed Phase 2 with dynamic selection)
- Rotation coordination failures (addressed Phase 3 with persistent state)
- Stale data confusion (addressed Phase 4 with freshness metadata)

---

*Last updated: 2026-04-18 after roadmap creation*
