# Research Summary: Strategy-Driven Update Pipeline Upgrade

**Project:** tw-canslim-web  
**Domain:** Taiwan stock CANSLIM analysis pipeline (brownfield)  
**Synthesized:** 2026-04-18  
**Overall Confidence:** HIGH

---

## Executive Summary

This is a brownfield pipeline upgrade, not a greenfield rebuild. The existing Python-based CANSLIM analysis system works—it ingests multi-source Taiwan market data, calculates scores, and publishes static JSON to GitHub Pages. The problem is sustainability: the current "update everything on every run" approach is breaking under API rate limits and causing reliability issues.

**The recommended path forward:** Transform the pipeline into a strategy-driven tiered update system that keeps trading-critical stocks fresh daily while rotating the rest of the market on a 3-day cycle. This requires adding orchestration intelligence (which stocks to update when) without touching the proven CANSLIM calculation engine.

**Key architectural insight:** This is not about optimizing API calls or adding caching—those are Phase 3 concerns. The core work is building a daily orchestrator that determines update scope based on market signals, maintaining rotation state across runs, and publishing merged outputs with explicit freshness metadata. The biggest risks are file coordination (6 scripts write to same JSON without locks), API quota exhaustion (silent failures hide data degradation), and schema evolution (resume logic breaks when new fields added).

Success means: core stocks (signals + volume leaders + high RS) get 100% daily freshness, full market covered within 3 days, frontend shows data age transparently, and the system degrades gracefully when APIs fail instead of silently corrupting data.

---

## Key Findings by Research Area

### From STACK.md: Minimal Dependencies, Maximum Brownfield Compatibility

**Recommended additions (3 libraries total):**
- `ratelimit` (2.2.1+) — Decorator-based API rate limiting
- `backoff` (2.2.1+) — Exponential retry on transient failures
- `requests-cache` (1.2.0+) — HTTP response caching to reduce duplicate calls

**Core technology decisions:**
- **Orchestration:** Custom Python script (not Airflow/Prefect) — GitHub Actions already provides scheduling, we just need task routing logic
- **State management:** JSON files in git (not database) — Fits existing workflow, survives ephemeral GitHub Actions runners
- **Rate limiting:** Decorators on existing API functions — No refactor, just wrap with `@limits(calls=60, period=60)`
- **Configuration:** JSON config + environment variables — Secrets isolated, parameters version-controlled
- **Testing:** pytest (already in requirements.txt)

**Why minimal:**
Brownfield compatibility is critical. The existing `CanslimEngine`, data processors, and publishing scripts work. Adding heavyweight frameworks (Airflow, async rewrites, databases) adds risk without value. The orchestrator just controls which stocks enter the existing processing loop.

**Migration path validated:**
- Phase 1: Add orchestrator (dry-run mode, no behavior change)
- Phase 2: Route existing scripts through orchestrator
- Phase 3: Add rate limiting decorators
- Phase 4: Enable caching for optimization

---

### From FEATURES.md: Table Stakes vs. Strategic Differentiators

**Table stakes (must-have for credibility):**
1. Daily core stock freshness guarantee (core = signals + watchlist + volume leaders)
2. Rotating batch coverage (3-day cycle for ~2000 stocks at 1000/day)
3. Per-stock freshness timestamps (users need to know data age)
4. Update state persistence (resume after failures without re-fetching)
5. Static artifact outputs (GitHub Pages requires file-based exports)
6. Graceful degradation (serve stale data with warnings when APIs fail)

**Differentiators (not expected but high-value):**
1. **Signal-driven core selection** — Auto-prioritize stocks with active ORB/RS breakout signals (game-changer for trading)
2. Multi-tier update priority queue (signals > watchlist > volume > rotation)
3. Update summary dashboard (show batch progress, failures, next rotation group)
4. Hotswap data files (atomic rename prevents partial-update races)
5. Single-stock on-demand refresh (script already exists: `update_single_stock.py`)

**Anti-features (explicitly avoid):**
- Real-time websocket updates (incompatible with static GitHub Pages)
- Full-market every-run updates (guaranteed API limit breach)
- Database-backed state (operational complexity for marginal benefit)
- Complex orchestration frameworks (overkill for single Python script)

**Feature dependencies that matter for phasing:**
- Update state persistence enables incremental updates AND rotating batches
- Signal-driven core selection requires multi-tier priority queue
- Graceful degradation requires per-stock freshness timestamps

---

### From ARCHITECTURE.md: Component Boundaries and Build Order

**Recommended architecture (7 components):**

```
DailyUpdateOrchestrator (NEW)
    ├─> CoreStockSelector (NEW) → 4 sources: base + volume + RS + signals
    ├─> BatchRotator (NEW) → modulo-3 rotation with state persistence
    └─> UpdatePipeline (EXISTING) → CanslimEngine, data processors (reuse as-is)
         ├─> DataMerger (NEW) → merge fresh updates with baseline
         └─> Publisher (ENHANCED) → export data.json, stock_index.json, stocks/*.json
```

**Critical integration points:**
- **State file:** `.planning/state/update_state.json` (rotation index, stock freshness, API quota tracking)
- **Baseline store:** `docs/data_base.json` (full market snapshot, merged with daily updates)
- **Output artifacts:** Keep existing `data.json`, add `stock_index.json` (all stocks + freshness), `update_summary.json` (run metadata)

**Suggested build order (validated against dependencies):**

**Phase 1: Core Orchestration (3-5 days)**
- DailyUpdateOrchestrator class
- CoreStockSelector (base stocks + volume Top 100 + RS > 80 + signals)
- BatchRotator (modulo-3 rotation logic)
- StateManager (JSON persistence)
- Modify GitHub Actions to call orchestrator instead of `export_canslim.py`

**Phase 2: Publishing & Freshness (2-3 days)**
- DataMerger (combine fresh updates with baseline)
- Enhanced Publisher (stock_index.json, freshness metadata)
- Frontend changes (display freshness indicators, lazy-load detail)

**Phase 3: Optimization (2-3 days, optional)**
- Batch API calls where supported
- Caching layer (ETF list, industry classification already cached)
- Retry logic enhancement (exponential backoff)
- Monitoring (API call counts, quota tracking)

**Phase 4: Advanced Selection (3-4 days, future)**
- AlphaScoreCalculator (weighted scoring: rs + volume + signal strength)
- Industry rotation support (ensure sector diversity)
- Watchlist integration (user-defined priority stocks)

**Architectural patterns to follow:**
- Single responsibility (CoreSelector selects, Pipeline calculates, Publisher exports)
- Data immutability at boundaries (return new data, don't mutate shared state)
- Configuration over code (strategy parameters in JSON, not hardcoded)
- Graceful degradation (system works with reduced quality when components fail)
- Explicit state management (state changes logged and auditable)

---

### From PITFALLS.md: Critical Risks and Prevention Strategies

**CRITICAL pitfalls (must address in Phase 1):**

1. **Priority list becomes stale static config**
   - Risk: Hardcoded core list misses hot stocks as market shifts
   - Prevention: Dynamic core selection from 4 sources (base + volume + RS + signals), regenerated every run
   - Detection: Core list unchanged for >7 days, user complaints about stale hot stocks

2. **No staleness metadata → user sees inconsistent freshness**
   - Risk: Trading decisions on 3-day-old data with no warning
   - Prevention: Add `last_updated` timestamp to every stock record, frontend staleness indicators (🟢 today, 🟡 1-2 days, 🔴 3+ days)
   - Detection: No timestamps in exports, users asking "when was this updated?"

3. **Output format fragmentation → frontend breaks silently**
   - Risk: Core stocks have full fields, rotated stocks missing `institutional` → null pointer crashes
   - Prevention: Define explicit schemas per tier, populate all fields with defaults, frontend defensive rendering
   - Detection: White screen crashes when searching certain stocks (already documented in POST_MORTEM)

4. **Race conditions between multiple update scripts**
   - Risk: 6 scripts write to same `data.json` without locks → corruption
   - Prevention: Implement file locking with `fcntl`, atomic writes (write to temp, rename), GitHub Actions concurrency control
   - Detection: Corrupt JSON files (86 bytes documented in CONCERNS.md), random data reversions

5. **API rate limits trigger silent cascading failures**
   - Risk: 28 instances of bare `except: pass` → API failures return zero data, CANSLIM scores silently degrade
   - Prevention: Replace all bare exceptions, implement quota tracking, circuit breaker pattern, fallback to cached data
   - Detection: Sudden unexplained score drops, zero values in institutional fields, silence in logs despite failures

6. **Resume logic breaks schema evolution**
   - Risk: Add new field to code, resume skips existing stocks → half the data missing `volatility_grid`
   - Prevention: Schema versioning, field validation before resume, migration scripts for schema changes
   - Detection: New features don't appear in dashboard despite code deployment

7. **Rotating batch scheduling becomes coordination nightmare**
   - Risk: Crash loses track of rotation state → some stocks never update, coverage drifts from 3-day to 7-day
   - Prevention: Persistent rotation state in JSON, deterministic group assignment via hash, coverage validation
   - Detection: Some stocks stale despite rotation "running daily"

8. **No rollback strategy when updates corrupt data**
   - Risk: Bad update committed to GitHub Pages → website broken, no way to recover
   - Prevention: Pre-update backup, validation before commit, health checks, rollback script
   - Detection: Extended outages, forced emergency full regenerations

**Phase-specific sequencing constraints:**

| Phase | Must Have Before Proceeding |
|-------|------------------------------|
| **Phase 1** | File locking, bare exception audit, schema versioning design |
| **Phase 2** | Schema versioning implemented, rotation state persistence, freshness metadata |
| **Phase 3** | Validation gate tested, rollback procedure documented |

**Existing technical debt (from CONCERNS.md):**
- 28 bare `except:` clauses (catalog in CONCERNS.md)
- 6 scripts write to `data.json` without coordination
- No schema versioning (volatility_grid, mansfield_rs already drifting)
- POST_MORTEM documents: logic regression, white screen crashes, data corruption

---

## Implications for Roadmap

### Recommended Phase Structure (3 phases)

**Phase 1: Foundation & Safety (CRITICAL — 1 week)**

*Rationale:* Must fix file coordination and error handling BEFORE any incremental work. Building orchestration on top of race conditions and silent failures will amplify existing problems.

*Delivers:*
- File locking on all data.json writes (prevents corruption)
- Bare exception removal + logging infrastructure (makes failures visible)
- Schema versioning system (enables safe evolution)
- State persistence design (rotation_state.json structure)
- Orchestrator skeleton (dry-run mode, no behavior change yet)

*Features from FEATURES.md:*
- Update state persistence (foundation)
- Per-stock freshness timestamps (infrastructure)

*Pitfalls avoided:*
- Pitfall 4 (race conditions)
- Pitfall 5 (silent API failures)
- Pitfall 6 (resume breaks schema evolution)

*Success criteria:*
- Zero race conditions in file writes
- All API errors logged with context
- Schema version in all exports
- State file persists correctly across test runs

---

**Phase 2: Smart Orchestration & Rotation (HIGH VALUE — 2 weeks)**

*Rationale:* This is the core upgrade. Dynamic core selection + rotating batches deliver the strategic value (trading-critical stocks always fresh). Must build on Phase 1 foundation.

*Delivers:*
- DailyUpdateOrchestrator (determines daily scope)
- CoreStockSelector (4-source dynamic selection: base + volume + RS + signals)
- BatchRotator (3-day rotation with state persistence)
- DataMerger (combine fresh + baseline with freshness tags)
- Enhanced Publisher (stock_index.json, update_summary.json)
- GitHub Actions integration (replace export_canslim.py)
- Frontend freshness indicators (🟢🟡🔴 badges)

*Features from FEATURES.md:*
- Daily core freshness guarantee
- Rotating batch coverage (3-day cycle)
- Signal-driven core selection (differentiator)
- Multi-tier priority queue
- Update summary dashboard
- Search across all stocks (via stock_index.json)

*Pitfalls avoided:*
- Pitfall 1 (static core list)
- Pitfall 2 (no staleness metadata)
- Pitfall 3 (format fragmentation via schema validation)
- Pitfall 7 (rotation coordination via persistent state)

*Success criteria:*
- Core stocks (signals + volume + RS) updated daily (100% freshness)
- Full market covered within 3 days (>95%)
- Dashboard shows freshness indicators
- Search works across all stocks (not just top 1000)
- Rotation state survives crashes and resumes correctly

---

**Phase 3: Resilience & Operations (POLISH — 1 week)**

*Rationale:* System works but needs production hardening. Validation gates prevent bad data publication, monitoring makes failures visible, optimization reduces API pressure.

*Delivers:*
- Pre-commit validation gate (prevents corrupt data publication)
- Backup + rollback mechanism (fast recovery from bad updates)
- API quota tracking dashboard (visibility into limit consumption)
- Rate limiting decorators (prevent quota exhaustion)
- Request caching (reduce duplicate API calls)
- Coverage monitoring (alert if >10% stocks stale)
- Health check endpoint (docs/health.json)

*Features from FEATURES.md:*
- Graceful degradation (serve stale with warnings)
- Hotswap data files (atomic rename)
- API retry + backoff logic

*Pitfalls avoided:*
- Pitfall 8 (no rollback strategy)
- Pitfall 11 (update time budget exceeded)
- Pitfall 14 (no monitoring/observability)

*Success criteria:*
- Validation catches corrupt data before publish
- Rollback tested and <5 minutes
- API quota tracking visible
- Update time <20 minutes
- Alert fires if coverage degrades >10%

---

### Research Flags: Which Phases Need Deeper Investigation

| Phase | Research Needed | Confidence | When |
|-------|-----------------|------------|------|
| **Phase 1** | Actual API quota limits (FinMind, TEJ, TWSE) | MEDIUM | Before orchestrator design finalized |
| **Phase 2** | Signal detection integration point (does alpha_integration_module.py expose API?) | LOW | During core selection implementation |
| **Phase 2** | Optimal rotation group size (500 vs 700 vs 1000 stocks/day) | MEDIUM | After quota tracking implemented |
| **Phase 3** | GitHub Pages build time with 2000+ individual stock JSON files | LOW | Only if implementing per-stock detail files |
| **Phase 3** | Frontend bundle size impact of stock_index.json (~200KB) | LOW | After stock_index.json schema finalized |

**Phases with well-documented patterns (skip additional research):**
- Phase 1: File locking (stdlib fcntl), schema versioning (standard pattern)
- Phase 2: Modulo-based rotation (already prototyped in batch_update_institutional.py)
- Phase 3: Validation gates (pytest + GitHub Actions integration established)

---

## Confidence Assessment

| Area | Confidence | Rationale |
|------|------------|-----------|
| **Stack** | HIGH | Recommendations based on existing working patterns, minimal new dependencies (3 libraries), proven libraries (ratelimit, backoff in wide use) |
| **Features** | HIGH | Grounded in codebase analysis (update_strategy.md requirements) + existing prototypes (batch_update_institutional.py) |
| **Architecture** | HIGH | Based on existing component inspection (CanslimEngine, data processors) + brownfield integration patterns + clear component boundaries |
| **Pitfalls** | HIGH | 8 critical pitfalls sourced from CONCERNS.md (25KB audit), POST_MORTEM (production incidents), codebase inspection (28 bare exceptions catalogued) |

**Overall synthesis confidence:** HIGH

**Primary evidence sources:**
- Existing codebase analysis (ARCHITECTURE.md, CONCERNS.md, POST_MORTEM)
- Explicit strategy specification (update_strategy.md)
- Production incident history (POST_MORTEM_20260415.md)
- 6 update scripts analyzed for coordination patterns
- PROJECT.md constraints (brownfield, GitHub Pages, API limits)

---

## Gaps to Address During Planning

**Known unknowns that won't block roadmap creation:**

1. **API quota limits not documented**
   - FinMind: 5,000/month mentioned but not verified
   - TEJ: Undocumented, observed ~1,000/hour
   - TWSE: No documented limits
   - *Action:* Add quota tracking in Phase 1, calibrate batch size based on observed consumption

2. **Signal detection integration point unclear**
   - Does `alpha_integration_module.py` expose `get_signal_stocks()` API?
   - Or must we parse output files?
   - *Action:* Code inspection during Phase 2 core selection implementation

3. **Rotation group size needs calibration**
   - 1000 stocks/day estimate assumes 4-5 API calls per stock
   - May need to reduce to 700 if API latency higher than expected
   - *Action:* Monitor actual API call count in Phase 1, adjust group size in Phase 2

4. **Frontend bundle size impact unknown**
   - `stock_index.json` estimated at ~200KB for 2173 stocks
   - Acceptable but not tested with actual data
   - *Action:* Generate sample stock_index.json in Phase 2, measure load time

5. **Cache invalidation strategy needs tuning**
   - When to expire cached API responses? (1 hour guessed)
   - ETF list cache already exists, but institutional data cache not designed
   - *Action:* Start with conservative 1-hour TTL in Phase 3, tune based on freshness requirements

**These gaps are flagged but don't block roadmap creation** because:
- They're implementation details, not architecture blockers
- Default values exist (1000 stocks/day, 1-hour cache TTL)
- Can be tuned during implementation based on observed behavior
- Don't change the fundamental orchestration design

---

## Critical Path Recommendations

**Pre-Phase 1 preparation (before any code):**
- [ ] Audit all 28 bare `except:` clauses → create replacement plan
- [ ] Test file locking proof-of-concept on macOS (fcntl availability)
- [ ] Design schema versioning structure (schema_version field format)
- [ ] Map current API quota consumption baseline (run export_canslim.py with call counter)

**Phase 1 must-haves (non-negotiable):**
- [ ] File locking on ALL scripts that write data.json (not just orchestrator)
- [ ] Bare exception removal (or at minimum, logging added to all 28)
- [ ] Schema version in all JSON exports
- [ ] State file atomic writes (temp + rename pattern)

**Phase 2 dependencies (can't start until Phase 1 complete):**
- [ ] File locking deployed and tested (prevents Phase 2 corruption)
- [ ] Schema versioning implemented (enables safe field additions)
- [ ] Rotation state persistence working (enables crash recovery)

**Phase 3 gates (don't deploy to production without):**
- [ ] Validation catches at least 3 corruption patterns (test with synthetic bad data)
- [ ] Rollback tested successfully (restore from backup in <5 min)
- [ ] Coverage monitoring alerts fire correctly (test with simulated stale data)

---

## Success Metrics (Across All Phases)

### Reliability Metrics
- Core stock freshness: 100% of signal stocks updated within 24 hours
- Market coverage: All stocks updated within 3 days (rotation cycle complete)
- API failure rate: <1% of update attempts fail
- Update success rate: >95% of attempted stocks successfully updated
- Data corruption incidents: Zero (down from current sporadic issues)

### Performance Metrics
- Update duration: <20 minutes per daily run (down from ~30+ min full updates)
- API calls per run: <1200 calls/day (down from ~3000 in full-update mode)
- Frontend load time: <2 seconds for data.json.gz (already achieved, maintain)
- Search responsiveness: <100ms to search stock_index.json

### User Experience Metrics
- Freshness visibility: 100% of stock views show freshness indicator
- Stale data warnings: Users warned if viewing 3+ day old data
- Update transparency: Summary widget shows batch progress and failures
- Search completeness: Full market searchable (not just top 1000)

### Technical Health Metrics
- Bare exceptions: 0 (down from 28)
- File coordination: 100% of writes use locking
- Schema compliance: 100% of outputs have schema_version field
- Rotation coverage: <10% of stocks stale >3 days (alert threshold)

---

## Aggregated Sources

**Codebase Analysis (HIGH confidence):**
- `/update_strategy.md` — Explicit rotation and priority strategy specification
- `/.planning/codebase/CONCERNS.md` — 25KB comprehensive technical debt audit (28 bare exceptions, file coordination issues, schema drift)
- `/POST_MORTEM_20260415.md` — Production incidents: logic regression, white screen crashes, data corruption, GitHub Actions overwrites
- `/export_canslim.py` — Current full-update implementation (CanslimEngine)
- `/batch_update_institutional.py` — Rotating batch pattern prototype (modulo-3 already implemented)
- `/incremental_workflow.py` — Workflow orchestration patterns
- `/alpha_integration_module.py` — Signal detection (ORB, counter_vwap, volume spike)
- `/.github/workflows/update_data.yml` — GitHub Actions automation structure
- `/docs/` — Current artifact structure (data.json, data_light.json, stock_index.json)

**Domain Expertise (MEDIUM-HIGH confidence):**
- Market data pipeline patterns (rotating batch coverage, priority queues)
- Static site deployment constraints (atomic updates, cache invalidation)
- Financial data freshness requirements (trading decisions need daily core updates)
- Brownfield migration patterns (coordination, state management, graceful degradation)

**Training Data (LOW-MEDIUM confidence, flagged for validation):**
- Adaptive batch sizing patterns — need to verify API quota monitoring feasibility
- Circuit breaker implementation details — need to test with actual API behavior
- Cache hit rate estimates (30-40%) — need to validate with actual request patterns

**Confidence-weighted recommendations:**
All Phase 1 recommendations (file locking, schema versioning, bare exception removal) are HIGH confidence—sourced directly from codebase inspection and production incidents.

Phase 2 recommendations (orchestration, rotation, core selection) are HIGH confidence—grounded in update_strategy.md specification and existing prototypes.

Phase 3 recommendations (optimization, monitoring) are MEDIUM confidence—based on standard patterns but need calibration with actual API behavior and user feedback.

---

## Ready for Requirements Definition

This summary provides actionable guidance for:
1. **Requirements engineer:** Table stakes vs. differentiators, success metrics, user-facing features
2. **Roadmap planner:** Validated phase structure, build order dependencies, research flags
3. **Implementation team:** Component boundaries, integration points, pitfall prevention strategies
4. **Testing team:** Success criteria per phase, validation gates, rollback procedures

**Next step:** Use this summary to define detailed requirements for Phase 1 (Foundation & Safety), focusing on file coordination, error handling, and schema versioning—the critical foundation for all subsequent work.

---

*Research synthesis complete. All findings grounded in codebase analysis, production history, and explicit strategy specifications. Confidence: HIGH. Gaps identified but non-blocking. Ready for roadmap creation.*
