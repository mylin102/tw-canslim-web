# Feature Landscape: Strategy-Driven Stock Data Update Pipeline

**Domain:** API-limited market data pipeline with static dashboard outputs  
**Project:** tw-canslim-web (brownfield upgrade)  
**Researched:** 2025-04-18  
**Confidence:** HIGH (based on codebase analysis + domain expertise)

---

## Table Stakes

Features users expect from a strategy-driven update system. Missing = system feels incomplete or unreliable.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| **Daily core stock freshness guarantee** | Trading decisions require reliable daily updates for active positions | Medium | Core = signals + watchlist + high-volume leaders. Already architected in `update_strategy.md` |
| **Rotating batch coverage** | Full market coverage required but API-limited | Medium | 3-day rotation for ~2000 stocks at 1000/day. Pattern established in `batch_update_institutional.py` |
| **Per-stock freshness timestamps** | Users need to know data recency before trusting decisions | Low | Add `last_update` field to `stock_index.json` and individual stock records |
| **Update state persistence** | System must resume after failures without re-fetching entire dataset | Medium | State file tracks: last updated stocks, rotation index, failed stocks queue |
| **Static artifact outputs** | GitHub Pages deployment requires file-based exports | Low | Already implemented: `data.json`, `data_light.json`, `stock_index.json` |
| **Incremental update workflow** | Full rebuild on every run wastes API quota and time | High | Merge new data with existing `data_base.json` instead of regenerating everything |
| **API retry + backoff logic** | Rate limits and transient failures are inevitable | Low | Already exists in `FinMindProcessor._fetch_with_retry()` — verify TEJ/yfinance have same |
| **Failure isolation** | One stock's API failure shouldn't block entire batch | Low | Already implemented: per-stock try/catch in export loop |
| **Graceful degradation** | When API fails, serve stale data with visible warnings | Low | Frontend shows freshness indicators (🟢 today, 🟡 1-2 days, 🔴 3+ days) |
| **Search across all stocks** | Users expect full market search even if only subset is in screener | Medium | `stock_index.json` with all tickers + last_update + basic metadata |

---

## Differentiators

Features that set this pipeline apart. Not expected, but highly valued for trading workflows.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| **Signal-driven core selection** | Automatically prioritize stocks with active ORB/RS breakout signals | High | Game-changer: core list = base + volume leaders + RS > 80 + **signal stocks**. Ensures trade opportunities never go stale |
| **Multi-tier update priority queue** | Intelligent scheduling: signals > watchlist > volume > rotation | High | Priority queue (not just fixed lists): urgent signals bypass daily batch limits |
| **Adaptive batch sizing** | Dynamically adjust batch size based on API response times and quota remaining | High | Start with 1000/day, reduce to 500 if rate-limited, increase to 1500 if quota available |
| **Update summary dashboard** | Show which stocks updated today, batch progress, failures, next rotation group | Medium | `update_summary.json`: {updated: [...], failed: [...], next_batch: [...], quota_remaining: N} |
| **Hotswap data files** | Atomic updates prevent users from loading partially written JSON | Low | Write to `data.tmp.json`, rename after complete (atomic on POSIX) |
| **Historical freshness tracking** | Track how often each stock was updated over time (for debugging stale data) | Medium | Log: `freshness_history.json` with per-stock update timestamps |
| **Single-stock on-demand refresh** | Users can request immediate update for specific stock (within quota) | Medium | Endpoint/script: `update_single_stock.py 2330` — already exists! |
| **Diff-based frontend updates** | Dashboard only reloads changed stocks instead of full data.json | Medium | Include `data_diff.json` with only changed records since last publish |
| **Pre-market batch prep** | Run lower-priority batch updates at night, save high-priority for market hours | Low | Cron: 22:00 (post-market) = rotation batch, 06:00 (pre-market) = signal refresh |
| **Smart cache invalidation** | Invalidate frontend cache only for updated stocks | Low | Include `cache_version` per stock; frontend checks before using cached detail |

---

## Anti-Features

Features to explicitly NOT build (resource traps or misaligned with goals).

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| **Real-time websocket updates** | Incompatible with static GitHub Pages; requires live server | Stick to scheduled batch updates with clear freshness indicators |
| **Full-market every-run updates** | Guaranteed to hit API limits; unreliable at scale | Use rotating batch + priority core strategy documented in `update_strategy.md` |
| **Database-backed state** | Adds operational complexity (PostgreSQL/MySQL hosting) for marginal benefit | Use JSON state files (`state.json`) — simple, version-controlled, portable |
| **Individual stock JSON files** | Creates 2000+ files in `docs/stocks/`, slow GitHub Pages builds | Keep `stocks/*.json` only for detail views; main screener uses consolidated `data.json` |
| **Embedded data in HTML** | Inline JSON in `<script>` tag bloats page size, prevents caching | Serve `data.json.gz` separately with long cache headers |
| **Complex orchestration framework** | Tools like Airflow/Prefect overkill for single Python script workflow | Keep orchestration in simple Python scripts + GitHub Actions YAML |
| **User authentication** | Static site can't authenticate; adds complexity without value | Public read-only access is the design goal |
| **Configurable update schedules** | Users don't need to customize schedule; one maintainer controls it | Hardcode cron schedule in GitHub Actions (daily 16:30 UTC+8) |

---

## Feature Dependencies

```
Update State Persistence → Incremental Update Workflow
                         → Rotating Batch Coverage

Signal-Driven Core Selection → Multi-Tier Priority Queue
                             → Per-Stock Freshness Timestamps

Static Artifacts → Hotswap Data Files
                → Smart Cache Invalidation

Graceful Degradation → Per-Stock Freshness Timestamps
```

---

## Complexity Analysis

### Low Complexity (1-2 days each)
- Per-stock freshness timestamps
- Hotswap data files (atomic rename)
- Pre-market batch prep (cron split)
- Failure isolation (already mostly done)
- Smart cache invalidation (version tags)

### Medium Complexity (3-5 days each)
- Update state persistence (JSON state file design)
- Incremental update workflow (merge logic)
- Rotating batch coverage (rotation scheduler)
- Update summary dashboard (aggregation + UI)
- Single-stock on-demand refresh (already exists, needs integration)
- Search across all stocks (index generation)

### High Complexity (1-2 weeks each)
- **Signal-driven core selection** (integrate with alpha_integration_module.py, requires scoring logic)
- **Multi-tier priority queue** (scheduling algorithm, quota management)
- **Adaptive batch sizing** (monitor API response metrics, dynamic adjustment)
- **Incremental update workflow** (differential calculation for RS/MA/signals)

---

## MVP Recommendation

### Phase 1: Foundational Update Infrastructure (Core Table Stakes)
**Goal:** Make daily updates reliable and observable

**Priority:**
1. **Update state persistence** — Track what was updated when
2. **Incremental update workflow** — Merge new data instead of full rebuild
3. **Per-stock freshness timestamps** — Users see data age
4. **Rotating batch coverage** — 3-day market sweep (already designed)
5. **Update summary dashboard** — Show batch progress and failures

**Defer:**
- Signal-driven core selection (Phase 2)
- Adaptive batch sizing (optimization, not MVP)
- Diff-based frontend updates (nice-to-have)

**Why this order:**
- State persistence enables everything else
- Incremental updates drastically reduce API calls (sustainability)
- Freshness timestamps build user trust immediately
- Rotation coverage delivers on "full market coverage" promise
- Summary dashboard makes system observable (debugging, confidence)

---

### Phase 2: Trading-Optimized Intelligence (Key Differentiator)
**Goal:** Ensure signal stocks never go stale

**Priority:**
1. **Signal-driven core selection** — Auto-detect breakout/high-RS stocks
2. **Multi-tier priority queue** — Signals > volume > rotation
3. **Graceful degradation** — Show stale data warnings in UI
4. **Hotswap data files** — Prevent partial-update races

**Defer:**
- Adaptive batch sizing (Phase 3 optimization)
- Historical freshness tracking (analytics, not critical)

**Why this order:**
- Signal-driven core is the strategic advantage for trading
- Priority queue ensures hot stocks always fresh
- Degradation prevents users from trusting stale data unknowingly
- Hotswap prevents corruption during writes

---

### Phase 3: Optimization & Polish (Post-MVP)
**Priority:**
1. **Adaptive batch sizing** — Maximize API quota utilization
2. **Diff-based frontend updates** — Faster dashboard loads
3. **Historical freshness tracking** — Debugging/analytics
4. **Smart cache invalidation** — Fine-tuned performance

---

## Integration Points with Existing Codebase

| Feature | Existing Component | Integration Approach |
|---------|-------------------|---------------------|
| Incremental update | `export_canslim.py` CanslimEngine | Add `load_existing_state()` method; merge with `data_base.json` |
| Rotating batch | `batch_update_institutional.py` | Already implements 3-day rotation; wire into main workflow |
| Signal-driven core | `alpha_integration_module.py` | Extract signal stocks from ORB/counter_vwap/volume_spike detectors |
| Per-stock timestamps | `export_dashboard_data.py` | Add `last_update` field to stock records |
| State persistence | New: `update_state.json` | Store: `{rotation_index, last_run, updated_today, failed_stocks}` |
| Update summary | New: `docs/update_summary.json` | Published artifact for frontend dashboard widget |
| Priority queue | New: `priority_scheduler.py` | Merge core stocks + rotation batch, respect daily quota |

---

## Output Artifact Structure

### Recommended File Layout (Post-Upgrade)

```
docs/
├── data.json              # 1000-stock screener snapshot (top signals + volume + rotation)
├── data.json.gz           # Compressed version (92% savings)
├── data_light.json        # 100-stock fast-load version for homepage
├── stock_index.json       # ALL stocks with basic metadata + last_update timestamp
├── update_summary.json    # Daily update status report
├── state.json             # Internal: rotation state, quota tracking (not for frontend)
└── stocks/                # Individual stock detail (optional, on-demand)
    ├── 2330.json
    ├── 2454.json
    └── ...
```

### New: `stock_index.json` Schema

```json
{
  "last_updated": "2025-04-18 16:45:00",
  "total_stocks": 2173,
  "stocks": [
    {
      "symbol": "2330",
      "name": "台積電",
      "last_update": "2025-04-18",
      "freshness": "today",
      "in_screener": true,
      "has_signal": true
    },
    {
      "symbol": "2317",
      "name": "鴻海",
      "last_update": "2025-04-17",
      "freshness": "1_day",
      "in_screener": false,
      "has_signal": false
    }
  ]
}
```

### New: `update_summary.json` Schema

```json
{
  "run_date": "2025-04-18",
  "run_start": "16:30:00",
  "run_duration_seconds": 245,
  "stats": {
    "total_attempted": 1000,
    "successful": 987,
    "failed": 13,
    "api_calls_made": 3512,
    "api_quota_remaining": 6488
  },
  "updated_today": ["2330", "2317", "2454", ...],
  "failed_stocks": [
    {"symbol": "3565", "reason": "API timeout"},
    {"symbol": "6770", "reason": "No data available"}
  ],
  "next_batch": {
    "date": "2025-04-19",
    "rotation_index": 1,
    "stocks": ["1101", "1102", ...]
  },
  "core_selection": {
    "method": "signal_driven",
    "signals": ["2330", "2454"],
    "volume_leaders": ["2317", "2454"],
    "rs_leaders": ["2330", "5347"],
    "total_core": 487
  }
}
```

### Enhanced: `state.json` (Internal Only)

```json
{
  "last_update": "2025-04-18 16:45:00",
  "rotation_index": 0,
  "rotation_cycle_days": 3,
  "daily_batch_size": 1000,
  "stocks_by_freshness": {
    "today": ["2330", "2317", ...],
    "1_day": ["1101", "1102", ...],
    "2_days": [...],
    "stale": [...]
  },
  "failed_stocks_queue": [
    {"symbol": "3565", "failures": 3, "last_attempt": "2025-04-18"},
    {"symbol": "6770", "failures": 1, "last_attempt": "2025-04-18"}
  ],
  "api_quotas": {
    "finmind": {"daily_limit": 10000, "used_today": 3512, "reset_at": "2025-04-19 00:00:00"},
    "tej": {"daily_limit": 5000, "used_today": 1204, "reset_at": "2025-04-19 00:00:00"}
  }
}
```

---

## Frontend Behavior Changes

### Current Behavior
- Load `data.json` (all stocks in memory)
- Filter/search within loaded stocks
- No freshness indication

### Post-Upgrade Behavior

#### Search Flow
```
User types "台積電" or "2330"
    ↓
Frontend queries stock_index.json (lightweight, all stocks)
    ↓
Found → Check freshness indicator
    ↓
If in screener (data.json) → Load from screener
If not in screener → Fetch stocks/2330.json (if needed)
    ↓
Display with freshness badge: 🟢 Today | 🟡 1-2 days | 🔴 3+ days
```

#### Screener Flow
```
Load data.json (top 1000: signals + volume + current rotation batch)
    ↓
Display with freshness indicators
    ↓
User can see which stocks were updated today (green badges)
```

#### Update Summary Widget (New)
```
Small dashboard widget shows:
- Last update: 2025-04-18 16:45
- Updated today: 987 stocks ✅
- Failed: 13 ⚠️ [View details]
- Next batch: Group B (1000 stocks) on 2025-04-19
- API quota: 65% remaining
```

---

## Phased Rollout Strategy

### Week 1-2: State + Incremental Foundation
- Implement `state.json` persistence
- Build incremental merge logic in `CanslimEngine`
- Add `last_update` timestamps to all stock records
- **Validation:** Run side-by-side with old full-update, verify data matches

### Week 3-4: Rotation + Freshness
- Implement rotation scheduler (reuse `batch_update_institutional.py` pattern)
- Generate `stock_index.json` with all stocks + freshness
- Add freshness indicators to frontend
- **Validation:** 3-day cycle should cover all 2173 stocks

### Week 5-6: Signal-Driven Core (High Value)
- Extract signal stocks from `alpha_integration_module.py`
- Implement priority selection (signals + volume + RS)
- Ensure signal stocks update daily regardless of rotation
- **Validation:** Signal stocks should ALWAYS have `freshness: "today"`

### Week 7: Summary + Observability
- Generate `update_summary.json` after each run
- Build summary widget in frontend
- Add failure retry queue
- **Validation:** Can diagnose update issues from summary alone

---

## Open Questions for Phase-Specific Research

These couldn't be fully resolved in domain research — flag for later:

1. **Signal detection integration:** Does `alpha_integration_module.py` expose a `get_signal_stocks()` API, or do we need to parse its output?
   - **Research needed:** Phase 2 (signal-driven core)

2. **TEJ API quota structure:** What are actual daily limits? Does retry logic exist?
   - **Research needed:** Phase 1 (API resilience)

3. **GitHub Pages build time:** How long does it take to rebuild with 2000+ individual stock JSON files?
   - **Research needed:** If considering `stocks/*.json` pattern

4. **Frontend bundle size:** Will `stock_index.json` (~200KB uncompressed for 2173 stocks) cause load issues?
   - **Research needed:** Phase 1 (search implementation)

5. **Rotation group sizing:** Is 1000 stocks/day optimal, or should we start with 700 to leave API headroom?
   - **Research needed:** Phase 1 (after API quota tracking implemented)

---

## Success Metrics

### Reliability Metrics
- **Core stock freshness:** 100% of signal stocks updated within 24 hours
- **Market coverage:** All 2173 stocks updated within 3 days (rotation cycle)
- **API failure rate:** < 1% of update attempts fail
- **Update success rate:** > 95% of attempted stocks successfully updated

### Performance Metrics
- **Update duration:** < 10 minutes per daily run (down from current ~30 min full updates)
- **API calls per update:** < 5000 calls/day (fits within rate limits)
- **Frontend load time:** < 2 seconds for `data.json.gz` (already achieved)
- **Search responsiveness:** < 100ms to search `stock_index.json`

### User Experience Metrics
- **Freshness visibility:** 100% of stock views show freshness indicator
- **Stale data warnings:** Users warned if viewing 3+ day old data
- **Update transparency:** Summary widget shows batch progress and failures

---

## Risk Analysis

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| API quota exhausted mid-batch | Medium | High | Adaptive batch sizing; quota tracking in `state.json` |
| State file corruption | Low | Medium | Atomic writes; daily backups; regenerate from `data_base.json` |
| Signal detection false positives | Medium | Low | Tune thresholds in Phase 2; log signal reasons |
| Rotation group imbalance | Low | Low | Shuffle stocks within groups to avoid clustering |
| GitHub Actions timeout (30min) | Low | High | Split into multiple jobs if needed; prioritize core stocks |

---

## Sources

- **Codebase analysis** (HIGH confidence):
  - `/update_strategy.md` — Update strategy architecture
  - `/export_canslim.py` — Current full-update implementation
  - `/batch_update_institutional.py` — Rotating batch pattern
  - `/incremental_workflow.py` — Workflow orchestration
  - `/alpha_integration_module.py` — Signal detection
  - `/.github/workflows/update_data.yml` — GitHub Actions automation
  - `/docs/` — Current artifact structure

- **Domain expertise** (MEDIUM confidence):
  - Market data pipeline patterns (rotating batch coverage, priority queues)
  - Static site deployment constraints (atomic updates, cache invalidation)
  - Financial data freshness requirements (trading decisions require daily core updates)

- **Training data** (LOW confidence, flagged for validation):
  - Adaptive batch sizing patterns — need to verify API quota monitoring feasibility
  - Diff-based updates for SPAs — need to validate bundle size impact

---

**Confidence Assessment:**  
- **Table stakes:** HIGH — grounded in codebase analysis and explicit `update_strategy.md` requirements  
- **Differentiators:** MEDIUM-HIGH — signal-driven core is logical extension of existing alpha module; other features are standard pipeline patterns  
- **Anti-features:** HIGH — directly informed by PROJECT.md constraints (static GitHub Pages, API limits)  
- **Complexity:** HIGH — based on hands-on analysis of existing codebase structure  

**Primary gap:** Need to validate actual API quota limits (FinMind, TEJ, yfinance) to calibrate adaptive batch sizing and rotation parameters. Flagged for Phase 1 research.
