# Architecture Patterns for Brownfield Pipeline Upgrade

**Domain:** Taiwan Stock CANSLIM Analysis Pipeline  
**Researched:** 2025-04-18  
**Confidence:** HIGH (based on existing codebase analysis and industry patterns)

---

## Executive Summary

This upgrade transforms a full-refresh Python data pipeline into a **strategy-driven tiered update system** that respects API rate limits while maintaining trading-critical freshness. The architecture must integrate with existing components (CanslimEngine, data processors, GitHub Actions, static JSON outputs) while introducing **daily core-stock refresh**, **rotating market batches**, and **smart core selection**.

**Critical Insight:** This is not a greenfield architecture problem—it's a brownfield integration challenge where new update orchestration must coexist with proven CANSLIM calculation logic and static publishing flows.

---

## Recommended Architecture

### System Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                    DAILY UPDATE ORCHESTRATOR                     │
│  (New Component - Phase 1)                                      │
│  - Determines today's update scope                              │
│  - Coordinates core + batch selection                           │
│  - Manages state persistence                                    │
└─────────────────────────────────────────────────────────────────┘
                                   │
                   ┌───────────────┴───────────────┐
                   ▼                               ▼
         ┌─────────────────┐            ┌─────────────────┐
         │  CORE SELECTOR  │            │ BATCH ROTATOR   │
         │  (Phase 1)      │            │  (Phase 1)      │
         │                 │            │                 │
         │ - Base stocks   │            │ - Market split  │
         │ - Volume Top N  │            │ - Day % 3 logic │
         │ - RS leaders    │            │ - State aware   │
         │ - Signals       │            │                 │
         └─────────────────┘            └─────────────────┘
                   │                               │
                   └───────────────┬───────────────┘
                                   ▼
                        ┌─────────────────┐
                        │  UPDATE PIPELINE │
                        │  (Existing)      │
                        │                  │
                        │ - CanslimEngine  │
                        │ - Data processors│
                        │ - CANSLIM logic  │
                        └─────────────────┘
                                   │
                   ┌───────────────┴───────────────┐
                   ▼                               ▼
         ┌─────────────────┐            ┌─────────────────┐
         │  DATA MERGER    │            │ PUBLISHER       │
         │  (Phase 2)      │            │ (Phase 2)       │
         │                 │            │                 │
         │ - Core priority │            │ - data.json     │
         │ - Batch merge   │            │ - data_light    │
         │ - Freshness tag │            │ - stock_index   │
         │ - Parquet store │            │ - stocks/*.json │
         └─────────────────┘            └─────────────────┘
                                                   │
                                                   ▼
                                        ┌─────────────────┐
                                        │  GITHUB PAGES   │
                                        │  (Existing)     │
                                        └─────────────────┘
```

---

## Component Boundaries

### 1. Daily Update Orchestrator (NEW - Phase 1)

**Responsibility:**  
Entry point that determines what to update today based on time, state, and strategy rules.

**Interface:**
```python
class DailyUpdateOrchestrator:
    def determine_update_scope() -> UpdateScope
    def coordinate_updates(scope: UpdateScope) -> UpdateResult
    def persist_state(result: UpdateResult) -> None
```

**Communicates With:**
- CoreSelector (to get priority stocks)
- BatchRotator (to get today's batch)
- UpdatePipeline (delegates stock list for processing)
- StateManager (reads/writes rotation state)

**Integration Points:**
- **Entry:** `python3 daily_update.py` (new CLI script)
- **Invoked By:** GitHub Actions workflow (replacing current `export_canslim.py` direct call)
- **State File:** `.planning/state/update_state.json` (rotation index, last update timestamp)

**Why This Boundary:**  
Isolates strategy logic from calculation logic. Existing CANSLIM engine remains pure—it just receives different stock lists on different days.

---

### 2. Core Stock Selector (NEW - Phase 1)

**Responsibility:**  
Identifies which stocks must be updated daily (trading-critical, high-activity, signal stocks).

**Interface:**
```python
class CoreStockSelector:
    def select_core_stocks(market_data: MarketSnapshot) -> List[str]
    def get_base_stocks() -> List[str]  # Fixed list (2330, ETFs)
    def get_volume_leaders(n: int) -> List[str]
    def get_rs_leaders(threshold: float) -> List[str]
    def get_signal_stocks() -> List[str]  # From previous day signals
```

**Communicates With:**
- MarketSnapshot (yesterday's volume/RS data from `data_base.json`)
- SignalEngine (existing—reads from previous `signals.json` if exists)
- DailyUpdateOrchestrator (returns core list)

**Integration Points:**
- **Data Source:** `docs/data_base.json` (full market baseline)
- **Output:** List of stock IDs (e.g., 200-500 symbols)
- **Weighting:** Signal stocks always included, volume + RS scored/ranked

**Why This Boundary:**  
Dynamic core selection is the key innovation. Separating this allows independent evolution of selection criteria without touching update/calculation logic.

---

### 3. Batch Rotator (NEW - Phase 1)

**Responsibility:**  
Determines today's batch slice from the remaining market (non-core stocks).

**Interface:**
```python
class BatchRotator:
    def get_today_batch(all_stocks: List[str], core_stocks: List[str]) -> List[str]
    def calculate_batch_index(date: datetime) -> int  # day % 3
    def split_market(stocks: List[str], n_groups: int) -> List[List[str]]
```

**Communicates With:**
- StateManager (reads rotation offset from state file)
- DailyUpdateOrchestrator (returns batch list)

**Integration Points:**
- **State File:** `.planning/state/update_state.json` (`{"rotation_index": 0, "last_rotation_date": "2025-04-18"}`)
- **Algorithm:** Simple modulo-based (`day_index = offset_day % 3`, groups = [0-999, 1000-1999, 2000+])
- **Output:** List of ~1000 stock IDs

**Why This Boundary:**  
Rotation logic is stateful and date-driven. Isolating it makes it easy to switch strategies (e.g., hourly batches, priority scoring) without refactoring orchestrator.

---

### 4. Update Pipeline (EXISTING - Reused)

**Responsibility:**  
Executes data fetching, CANSLIM calculation, and scoring for a given list of stocks.

**Components (Unchanged):**
- `CanslimEngine` (from `export_canslim.py`)
- `FinMindProcessor`, `TEJProcessor`, `ExcelDataProcessor`
- `core/logic.py` (factor calculations)

**Modifications Needed:**
```python
# Current (export_canslim.py):
engine = CanslimEngine()
all_stocks = get_all_tw_tickers()
for stock_id in all_stocks:  # ❌ Full market every time
    engine.run_analysis(stock_id)

# New (called by orchestrator):
engine = CanslimEngine()
scope = orchestrator.determine_update_scope()  # Core + Batch
for stock_id in scope.target_stocks:  # ✅ Scoped list
    engine.run_analysis(stock_id)
```

**Integration Points:**
- **Input:** Stock list from orchestrator
- **Output:** Parquet files (`master_canslim_signals.parquet` with date column)
- **Existing Exports:** Continue writing to parquet, but don't overwrite `data.json` directly

**Why This Boundary:**  
No major refactor needed. The engine already processes stocks in a loop—we just control which stocks enter the loop.

---

### 5. Data Merger (NEW - Phase 2)

**Responsibility:**  
Combines today's fresh updates with yesterday's baseline to produce complete market snapshot.

**Interface:**
```python
class DataMerger:
    def merge_updates(fresh: DataFrame, baseline: DataFrame) -> DataFrame
    def tag_freshness(df: DataFrame) -> DataFrame  # Add 'last_update' column
    def prioritize_core(df: DataFrame, core_ids: List[str]) -> DataFrame
```

**Communicates With:**
- UpdatePipeline (receives today's parquet output)
- BaselineStore (`data_base.json` - full market from last complete cycle)
- Publisher (outputs merged dataset)

**Integration Points:**
- **Input 1:** `master_canslim_signals.parquet` (today's updates)
- **Input 2:** `docs/data_base.json` (baseline snapshot)
- **Output:** Merged DataFrame with freshness metadata (`{"stock_id": "2330", "last_update": "2025-04-18", ...}`)

**Algorithm:**
```python
# Pseudocode
baseline = load_json("data_base.json")
fresh = load_parquet("master_canslim_signals.parquet").filter(date == today)

for stock_id in fresh:
    baseline[stock_id] = fresh[stock_id]  # Overwrite with fresh data
    baseline[stock_id]['last_update'] = today

return baseline
```

**Why This Boundary:**  
Merging is distinct from calculation and publishing. It's the glue that enables partial updates while maintaining full market coverage.

---

### 6. Publisher (ENHANCED - Phase 2)

**Responsibility:**  
Exports merged data to multiple JSON artifacts consumed by frontend.

**Existing Outputs (Keep):**
- `docs/data.json` - Top 1000 stocks (screener)
- `docs/data_light.json` - Summary metrics
- `docs/update_summary.json` - Metadata

**New Outputs (Add):**
- `docs/stock_index.json` - All stocks with freshness tags (searchable index)
- `docs/stocks/{symbol}.json` - Per-stock detail files (lazy load for detail view)

**Interface:**
```python
class Publisher:
    def export_screener(df: DataFrame, limit: int = 1000) -> None  # data.json
    def export_index(df: DataFrame) -> None  # stock_index.json
    def export_individual_stocks(df: DataFrame, symbols: List[str]) -> None
    def export_summary(metadata: Dict) -> None
```

**Communicates With:**
- DataMerger (receives merged dataset)
- GitHub Pages (outputs consumed by Vue.js dashboard)

**Integration Points:**
- **Existing Script:** `export_dashboard_data.py` (reuse structure, add freshness field)
- **New Output Structure:**
```json
// docs/stock_index.json
{
  "stocks": [
    {"symbol": "2330", "name": "台積電", "last_update": "2025-04-18", "score": 85},
    {"symbol": "2317", "name": "鴻海", "last_update": "2025-04-16", "score": 72}
  ]
}

// docs/stocks/2330.json
{
  "symbol": "2330",
  "name": "台積電",
  "last_update": "2025-04-18",
  "canslim": { /* full CANSLIM data */ },
  "institutional": [ /* history */ ]
}
```

**Why This Boundary:**  
Publishing is presentation logic. By separating it, we can evolve frontend data contracts (e.g., add GraphQL, compression) without touching calculation/merge layers.

---

### 7. State Manager (NEW - Phase 1)

**Responsibility:**  
Persists and retrieves rotation state to ensure consistent batch scheduling across runs.

**Interface:**
```python
class StateManager:
    def get_current_rotation_index() -> int
    def update_rotation_state(index: int, date: datetime) -> None
    def get_last_update_timestamp(stock_id: str) -> Optional[datetime]
```

**Storage:**
- **Location:** `.planning/state/update_state.json` (committed to repo)
- **Schema:**
```json
{
  "rotation_index": 0,
  "last_rotation_date": "2025-04-18",
  "last_full_cycle": "2025-04-15",
  "stock_freshness": {
    "2330": "2025-04-18",
    "2317": "2025-04-18",
    "1234": "2025-04-16"
  }
}
```

**Communicates With:**
- BatchRotator (provides rotation index)
- DailyUpdateOrchestrator (reads/writes state at run boundaries)

**Why This Boundary:**  
Stateful scheduling requires durable storage. Keeping state in a single JSON file makes debugging easy and avoids database dependencies.

---

## Data Flow

### Daily Update Flow (Complete)

```
1. Trigger (GitHub Actions: daily 18:00 Taiwan time)
       ↓
2. DailyUpdateOrchestrator.run()
       ├─→ StateManager.get_current_rotation_index()  →  index = 0
       ├─→ CoreStockSelector.select_core_stocks()     →  core = [2330, 2317, ...] (250 stocks)
       ├─→ BatchRotator.get_today_batch(index)        →  batch = [Group0] (1000 stocks)
       └─→ merge(core, batch) → dedupe → scope.target_stocks (1200 unique)
       ↓
3. UpdatePipeline.run_analysis(scope.target_stocks)
       ├─→ FinMindProcessor.fetch_institutional_investors(1200 stocks)
       ├─→ TEJProcessor.fetch_eps(1200 stocks)
       ├─→ yfinance.download(1200 stocks)
       └─→ core/logic.py: calculate_c_factor(), compute_canslim_score()
       ↓
4. Save to master_canslim_signals.parquet (append today's date column)
       ↓
5. DataMerger.merge_updates()
       ├─→ Load baseline: data_base.json
       ├─→ Load fresh: filter(date == today) from parquet
       ├─→ Overwrite baseline with fresh data
       └─→ Tag freshness: last_update = "2025-04-18"
       ↓
6. Publisher.export_all()
       ├─→ export_screener() → docs/data.json (top 1000 by score)
       ├─→ export_index() → docs/stock_index.json (all stocks with freshness)
       ├─→ export_individual_stocks() → docs/stocks/*.json (core + signal stocks)
       └─→ export_summary() → docs/update_summary.json
       ↓
7. StateManager.update_rotation_state(index + 1, today)
       ↓
8. Git commit + push (GitHub Actions step)
       ↓
9. GitHub Pages auto-deploy
```

**Time Estimates:**
- Step 1-2: 5 seconds (orchestration + selection)
- Step 3: 10-15 minutes (API fetching for 1200 stocks)
- Step 4-5: 30 seconds (parquet I/O + merge)
- Step 6: 1 minute (JSON export)
- Step 7-9: 30 seconds (git operations)

**Total:** ~17 minutes (within GitHub Actions 30-minute job limit)

---

### Freshness Propagation

```
Day 1: Update Core (250) + Batch 0 (1000)
    ↓
data_base.json updated with 1250 stocks tagged "2025-04-18"
Remaining 923 stocks still tagged "2025-04-15" (last full cycle)
    ↓
Day 2: Update Core (250) + Batch 1 (1000)
    ↓
data_base.json now has 2250 stocks with recent tags
Remaining stocks tagged older dates
    ↓
Day 3: Update Core (250) + Batch 2 (173 remaining)
    ↓
Full market now covered (all stocks have data within 3 days)
    ↓
Cycle repeats
```

**Frontend Display:**
- 🟢 **Green** (Today or yesterday): High confidence, trade-ready
- 🟡 **Yellow** (2 days ago): Acceptable, monitor
- 🔴 **Red** (3+ days ago): Stale, use with caution

---

## Integration Points with Existing Systems

### 1. GitHub Actions Workflow

**Current (update_data.yml):**
```yaml
- name: 🔄 執行增量更新
  run: |
    python export_canslim.py  # ❌ Full market update
    python incremental_workflow.py
```

**New (Phase 1):**
```yaml
- name: 🔄 執行策略更新
  run: |
    python3 daily_update.py  # ✅ Smart orchestrator
    python3 publish_dashboard.py
```

**Integration Risk:** LOW  
- Existing workflow structure unchanged (same triggers, same steps)
- Just swap script names
- Rollback: revert to old script names

---

### 2. CANSLIM Engine (export_canslim.py)

**Current:**
```python
# Monolithic: fetches all, calculates all, exports all
if __name__ == "__main__":
    engine = CanslimEngine()
    all_stocks = get_all_tw_tickers()
    for stock_id in all_stocks:
        engine.run_analysis(stock_id)
    engine.save_to_json("docs/data.json")
```

**New (Refactored):**
```python
# Modular: accepts stock list from orchestrator
def run_update(stock_ids: List[str], output_path: str):
    engine = CanslimEngine()
    for stock_id in stock_ids:
        engine.run_analysis(stock_id)
    engine.save_to_parquet(output_path)  # Don't overwrite data.json directly

if __name__ == "__main__":
    # CLI mode: accept stock list from args or file
    import sys
    stock_ids = sys.argv[1:] or load_stock_list("stock_list.txt")
    run_update(stock_ids, "master_canslim_signals.parquet")
```

**Integration Risk:** MEDIUM  
- **Modification:** Add `run_update()` function, keep `__main__` for backward compatibility
- **Testing:** Ensure existing tests still pass
- **Rollback:** Keep old monolithic code path as `--full-update` flag

---

### 3. Data Processors (FinMind, TEJ, yfinance)

**Current:**
- Called inside `CanslimEngine.run_analysis()` per stock
- No batch optimization

**Opportunity (Phase 3 - Optional):**
```python
# Current: N API calls for N stocks
for stock_id in stock_ids:
    data = processor.fetch_institutional_investors(stock_id)

# Optimized: Batch API if supported
data_batch = processor.fetch_institutional_investors_batch(stock_ids)
```

**Integration Risk:** LOW (Phase 3 only)  
- Keep current per-stock fetching in Phase 1-2
- Add batch methods in Phase 3 if API limits still hit

---

### 4. Dashboard Frontend (docs/app.js)

**Current:**
- Loads `data.json` (assumes all stocks equally fresh)
- Search via client-side filter

**New (Phase 2):**
```javascript
// Load stock index for search
const index = await fetch('stock_index.json').then(r => r.json());

// Display with freshness indicator
stocks.forEach(stock => {
  const daysSince = dateDiff(stock.last_update, today);
  const indicator = daysSince === 0 ? '🟢' : daysSince <= 2 ? '🟡' : '🔴';
  displayStock(stock, indicator);
});

// Lazy load detail on click
async function showDetail(symbol) {
  const detail = await fetch(`stocks/${symbol}.json`).then(r => r.json());
  renderDetailView(detail);
}
```

**Integration Risk:** LOW  
- Backward compatible: `data.json` still exists with same schema
- Freshness tags are additive (frontend gracefully ignores if missing)
- Per-stock JSON files optional (fallback to `data.json` lookup)

---

### 5. Parquet Historical Store

**Current:**
- `master_canslim_signals.parquet` - time-series append
- `master_canslim_signals_fused.parquet` - TEJ-integrated

**New:**
- Keep appending with `date` column
- Merger reads latest date slice: `df[df.date == today]`

**Schema (Unchanged):**
```
date, stock_id, C, A, N, S, L, I, M, score, rs_rating, fund_change, ...
```

**Integration Risk:** NONE  
- Already designed for time-series
- Just filter by date in queries

---

## Suggested Build Order

### Phase 1: Core Orchestration (Est. 3-5 days)

**Goal:** Replace full-refresh with smart daily updates

**Deliverables:**
1. `DailyUpdateOrchestrator` class
   - `determine_update_scope()` method
   - State management integration
2. `CoreStockSelector` class
   - Base stocks list (hardcoded 2330, 0050, etc.)
   - Volume leaders (Top 100 from yesterday)
   - RS leaders (rs_rating > 80 from yesterday)
   - Signal stocks (read from `signals.json` if exists)
3. `BatchRotator` class
   - Modulo-3 rotation logic
   - Stock list splitting
4. `StateManager` class
   - JSON-based state persistence
   - Rotation index tracking
5. `daily_update.py` CLI script
   - Calls orchestrator
   - Calls existing `CanslimEngine` with scoped stock list
6. Update GitHub Actions workflow
   - Replace `export_canslim.py` with `daily_update.py`

**Testing:**
- Unit tests for selector logic
- Integration test: run 3 consecutive days, verify all stocks covered
- Verify `update_state.json` persists correctly

**Risks:**
- State file corruption → **Mitigation:** Validate schema on load, fallback to day % 3
- Core selector returns empty list → **Mitigation:** Always include base stocks

**Success Criteria:**
- Daily runs complete in <20 minutes
- All stocks covered within 3 days
- No full-market API bursts

---

### Phase 2: Publishing & Freshness (Est. 2-3 days)

**Goal:** Merge partial updates, export with freshness metadata

**Deliverables:**
1. `DataMerger` class
   - Load baseline from `data_base.json`
   - Load fresh from parquet
   - Merge and tag freshness
2. Enhanced `Publisher` class
   - `export_index()` → `stock_index.json`
   - `export_individual_stocks()` → `stocks/*.json` (core + signals only)
   - Maintain existing exports (`data.json`, `data_light.json`)
3. `publish_dashboard.py` CLI script
4. Update GitHub Actions to call publisher
5. Frontend changes (Vue.js):
   - Load `stock_index.json` for search
   - Display freshness indicators
   - Lazy load detail from `stocks/{symbol}.json`

**Testing:**
- Verify merged data has correct freshness tags
- Check `stock_index.json` includes all stocks
- Test frontend search and detail views

**Risks:**
- Baseline file size grows too large → **Mitigation:** Compress to `.json.gz`
- Per-stock files exceed repo limits → **Mitigation:** Only export core + recent signals (~500 files max)

**Success Criteria:**
- Dashboard displays freshness indicators
- Search works across full market
- Detail view loads lazily without errors

---

### Phase 3: Optimization (Est. 2-3 days - Optional)

**Goal:** Reduce API latency, improve reliability

**Deliverables:**
1. Batch API calls where supported
   - `FinMindProcessor.fetch_batch()`
   - `yfinance.download([...])` (already batch-capable)
2. Caching layer
   - ETF list cache (already exists)
   - Industry classification cache (already exists)
   - Price cache (`.raw_cache/*.parquet`) - extend to institutional data
3. Retry logic enhancement
   - Exponential backoff for rate limits
   - Partial success handling (continue on per-stock errors)
4. Monitoring
   - Log API call counts
   - Alert if batch exceeds time limit

**Testing:**
- Load test: simulate 1500 stock update
- Verify cache hit rates
- Confirm retry logic doesn't infinite loop

**Risks:**
- Cache invalidation bugs → **Mitigation:** TTL-based expiry (24 hours)
- Batch API changes breaking contract → **Mitigation:** Feature flag to disable batching

**Success Criteria:**
- Update time reduced by 20-30%
- API failure rate <5%
- Cache hit rate >60% for price/institution data

---

### Phase 4: Advanced Selection (Est. 3-4 days - Future)

**Goal:** Smart core selection based on alpha signals

**Deliverables:**
1. `AlphaScoreCalculator`
   - Combine volume rank, RS rating, signal strength
   - Weighted scoring: `alpha_score = 0.4*rs + 0.3*volume_rank + 0.3*signal_score`
2. Enhanced `CoreStockSelector`
   - Rank stocks by alpha score
   - Dynamic core size (200-500 based on signal count)
3. Industry rotation support
   - Ensure coverage across sectors
   - Avoid over-concentration in single industry
4. Watchlist integration
   - User-defined priority stocks (future feature)

**Testing:**
- Backtest selection strategy vs. fixed list
- Verify industry diversity
- Check alpha score distribution

**Success Criteria:**
- Core selection captures 90%+ of next-day signals
- Industry coverage maintained
- No single stock dominates alpha score

---

## Architectural Patterns to Follow

### 1. Single Responsibility Principle

**Each component does one thing:**
- CoreSelector → selects stocks (doesn't fetch data)
- UpdatePipeline → calculates CANSLIM (doesn't decide what to calculate)
- Publisher → exports data (doesn't merge or calculate)

**Anti-Pattern to Avoid:**
```python
# ❌ God class doing everything
class MasterUpdater:
    def select_and_update_and_publish():
        core = self.select()
        data = self.fetch_and_calculate()
        self.publish_to_json()
```

**Correct Pattern:**
```python
# ✅ Composed from specialists
orchestrator = DailyUpdateOrchestrator()
scope = orchestrator.determine_update_scope()  # Uses selector
pipeline = UpdatePipeline()
result = pipeline.run(scope)  # Uses engine
publisher = Publisher()
publisher.export(result)  # Uses merger
```

---

### 2. Data Immutability at Boundaries

**Rule:** Components receive data, return new data—don't mutate shared state.

**Example:**
```python
# ✅ Good: Pure function
def merge_updates(baseline: DataFrame, fresh: DataFrame) -> DataFrame:
    merged = baseline.copy()  # Don't mutate input
    merged.update(fresh)
    return merged

# ❌ Bad: Mutates input
def merge_updates(baseline: DataFrame, fresh: DataFrame):
    baseline.update(fresh)  # Side effect!
    return baseline
```

**Why:** Makes testing easier, prevents race conditions in future async updates.

---

### 3. Configuration Over Code

**Rule:** Strategy parameters in config files, not hardcoded.

**Example:**
```python
# ✅ Good: Configurable
config = load_config("update_config.json")
{
  "core_selection": {
    "base_stocks": ["2330", "2317", "0050"],
    "volume_top_n": 100,
    "rs_threshold": 80
  },
  "batch_rotation": {
    "daily_limit": 1000,
    "rotation_days": 3
  }
}
selector = CoreStockSelector(config.core_selection)

# ❌ Bad: Hardcoded
class CoreStockSelector:
    def select(self):
        return ["2330", "2317"] + get_volume_leaders(100)  # Magic numbers
```

**Why:** Allows A/B testing strategies without code changes.

---

### 4. Graceful Degradation

**Rule:** System works (with reduced quality) even when components fail.

**Example:**
```python
# CoreStockSelector
try:
    volume_leaders = fetch_volume_leaders()
except APIError:
    logger.warning("Volume API failed, using yesterday's list")
    volume_leaders = load_fallback("volume_cache.json")

core = base_stocks + volume_leaders + rs_leaders
return core if core else base_stocks  # Always return something
```

**Why:** Daily automation shouldn't fail completely due to one API hiccup.

---

### 5. Explicit State Management

**Rule:** State changes are logged and auditable.

**Example:**
```python
# StateManager
def update_rotation_state(self, index: int, date: datetime):
    old_state = self.load_state()
    new_state = {
        "rotation_index": index,
        "last_rotation_date": date.isoformat(),
        "transition_log": old_state.get("transition_log", []) + [
            {"from": old_state.get("rotation_index"), "to": index, "at": date.isoformat()}
        ]
    }
    self.save_state(new_state)
    logger.info(f"State transition: {old_state['rotation_index']} → {index}")
```

**Why:** Debugging rotation issues requires understanding state history.

---

## Anti-Patterns to Avoid

### Anti-Pattern 1: Premature Optimization

**What:** Implementing batch APIs, caching, async processing in Phase 1.

**Why Bad:** Adds complexity before validating core logic works.

**Instead:** Start simple (per-stock API calls), optimize in Phase 3 if needed.

---

### Anti-Pattern 2: Dual Data Sources

**What:** `data.json` and `data_base.json` diverge in schema or semantics.

**Why Bad:** Frontend doesn't know which to trust.

**Instead:** Single source of truth (`data_base.json`), derived views (`data.json` = top 1000 from base).

---

### Anti-Pattern 3: Stateless Rotation

**What:** Using only `datetime.now() % 3` without persisting offset.

**Why Bad:** Manual runs or CI failures break deterministic rotation.

**Instead:** Persist state in `update_state.json`, increment on successful run.

---

### Anti-Pattern 4: Silent Failures

**What:** API errors logged but orchestrator reports success.

**Why Bad:** Partial updates published without awareness of missing data.

**Instead:**
```python
result = pipeline.run(scope)
if result.failed_stocks:
    logger.error(f"Failed to update {len(result.failed_stocks)} stocks")
    # Option 1: Retry failed stocks
    # Option 2: Tag as stale in freshness metadata
    # Option 3: Fail entire run (conservative)
```

---

### Anti-Pattern 5: Frontend-Driven Logic

**What:** Vue.js dashboard calculates derived metrics (e.g., alpha scores).

**Why Bad:** Logic duplication, inconsistency across clients.

**Instead:** Pre-compute in Python, export as JSON field.

---

## Scalability Considerations

| Concern | At 2,000 Stocks (Current) | At 5,000 Stocks | At 10,000 Stocks |
|---------|---------------------------|-----------------|------------------|
| **API Calls** | 2,000 calls/day (scoped update) | 3 batches × 1,667 calls | 5 batches × 2,000 calls |
| **Update Time** | ~15 min | ~25 min | ~40 min (may need parallel workers) |
| **State File** | 10 KB | 20 KB | 40 KB (still manageable) |
| **data.json Size** | 1 MB | 2.5 MB | 5 MB (needs compression) |
| **stock_index.json** | 50 KB | 120 KB | 250 KB (acceptable) |
| **stocks/*.json Count** | 500 files | 1,000 files | 2,000 files (Git LFS consideration) |
| **GitHub Pages Build** | <1 min | <2 min | May timeout (need external hosting) |

**Mitigation Strategies:**

1. **For API Limits:**
   - Phase 3: Batch API calls
   - Use caching aggressively (`.raw_cache/`)
   - Implement request throttling (sleep between batches)

2. **For File Size:**
   - Serve `.json.gz` (already implemented for `data.json`)
   - Limit `stocks/*.json` to core + signals only (not all 10K)
   - Pagination: `stocks/page_1.json`, `stocks/page_2.json`

3. **For Build Time:**
   - GitHub Actions: Increase timeout to 60 min
   - Or: Split into multiple jobs (update data → publish → deploy)
   - Or: Self-hosted runner

4. **For Git Repo Size:**
   - Don't commit `.raw_cache/` (add to `.gitignore`)
   - Git LFS for large parquet files
   - Periodic squash/cleanup of old commits

---

## Brownfield Integration Risks

### Risk 1: State File Corruption

**Scenario:** Git conflict or manual edit breaks `update_state.json`.

**Impact:** Rotation index invalid, duplicate or missing batches.

**Mitigation:**
- JSON schema validation on load
- Fallback to `day % 3` if state invalid
- Commit hook to validate state file syntax

**Detection:** Unit test for state load/save round-trip.

---

### Risk 2: Parquet Schema Drift

**Scenario:** Existing `master_canslim_signals.parquet` has different columns than new updates.

**Impact:** Merge fails with KeyError.

**Mitigation:**
- Document required schema in code comments
- Add schema validation before merge
- Versioning: `master_canslim_signals_v2.parquet` if breaking change

**Detection:** Integration test loading historical parquet.

---

### Risk 3: GitHub Actions Timeout

**Scenario:** API slowness causes job to exceed 30-minute limit.

**Impact:** Incomplete update, no commit.

**Mitigation:**
- Set workflow `timeout-minutes: 60`
- Add checkpoint: commit partial updates every 500 stocks
- Fallback: Skip batch if running late, only update core

**Detection:** Monitor workflow run times, alert if >25 min.

---

### Risk 4: Frontend Compatibility

**Scenario:** Old frontend code expects `data.json` without `last_update` field.

**Impact:** Display errors or crashes.

**Mitigation:**
- Backward compatibility: `last_update` is optional, defaults to `null`
- Frontend checks: `if (stock.last_update) { showFreshness() }`
- Phased rollout: Deploy backend first, validate, then deploy frontend

**Detection:** Browser console error monitoring (if analytics exist).

---

### Risk 5: Core Selector Bias

**Scenario:** Core selection always picks same stocks (e.g., high-volume stocks never rotate out).

**Impact:** Some stocks perpetually stale.

**Mitigation:**
- Enforce core list size cap (max 500)
- Periodic "force refresh" day (e.g., every Sunday update all stocks)
- Monitor freshness distribution: alert if >10% stocks stale >5 days

**Detection:** Daily freshness report in logs.

---

## Testing Strategy

### Unit Tests

```python
# test_core_selector.py
def test_base_stocks_always_included():
    selector = CoreStockSelector()
    core = selector.select_core_stocks(MarketSnapshot())
    assert "2330" in core
    assert "0050" in core

def test_signal_stocks_prioritized():
    signals = ["1234", "5678"]
    selector = CoreStockSelector(signals=signals)
    core = selector.select_core_stocks(MarketSnapshot())
    assert "1234" in core and "5678" in core

# test_batch_rotator.py
def test_rotation_cycles_through_all_stocks():
    rotator = BatchRotator()
    all_stocks = [f"{i:04d}" for i in range(1, 2001)]
    batches = [rotator.get_today_batch(all_stocks, [], offset_day=i) for i in range(3)]
    all_batched = set().union(*batches)
    assert all_batched == set(all_stocks)  # Full coverage

# test_data_merger.py
def test_fresh_data_overwrites_baseline():
    baseline = pd.DataFrame({"stock_id": ["2330"], "score": [70], "last_update": ["2025-04-15"]})
    fresh = pd.DataFrame({"stock_id": ["2330"], "score": [85], "last_update": ["2025-04-18"]})
    merger = DataMerger()
    result = merger.merge(baseline, fresh)
    assert result.loc[result.stock_id == "2330", "score"].iloc[0] == 85
```

### Integration Tests

```python
# test_daily_update_e2e.py
def test_full_update_cycle():
    # Simulate 3 consecutive days
    for day in range(3):
        orchestrator = DailyUpdateOrchestrator(offset_day=day)
        scope = orchestrator.determine_update_scope()
        # Mock API calls
        result = MockUpdatePipeline().run(scope)
        assert len(result.updated_stocks) > 0
    
    # Verify all stocks covered
    state = StateManager().load_state()
    assert state["rotation_index"] == 0  # Cycled back

def test_state_persistence_across_runs():
    # Run 1
    orchestrator = DailyUpdateOrchestrator()
    orchestrator.run()
    state1 = StateManager().load_state()
    
    # Run 2 (same day)
    orchestrator2 = DailyUpdateOrchestrator()
    orchestrator2.run()
    state2 = StateManager().load_state()
    
    assert state1["rotation_index"] == state2["rotation_index"]  # No double increment
```

### Acceptance Tests

```bash
# test_github_actions.sh
# Run in CI environment
python3 daily_update.py
python3 publish_dashboard.py

# Verify outputs exist
test -f docs/data.json || exit 1
test -f docs/stock_index.json || exit 1
test -f .planning/state/update_state.json || exit 1

# Verify data quality
python3 -c "
import json
data = json.load(open('docs/data.json'))
assert len(data['stocks']) > 0, 'No stocks exported'
assert 'last_updated' in data, 'Missing timestamp'
print('✅ Acceptance tests passed')
"
```

---

## Decision Log

| Decision | Rationale | Trade-offs |
|----------|-----------|------------|
| **Use modulo-3 rotation** | Simplest deterministic schedule | Less flexible than priority queue; mitigated by core selection |
| **State in JSON file** | No DB dependency, Git-trackable | Not ACID-safe; mitigated by schema validation |
| **Core always includes signals** | Trading decisions need fresh signal data | May exceed core size cap on high-signal days; mitigated by cap enforcement |
| **Publish to static JSON** | Existing GitHub Pages integration | Large file sizes at scale; mitigated by compression and pagination |
| **Keep existing CANSLIM engine** | Proven calculation logic, minimal risk | Harder to optimize batch APIs; acceptable for Phase 1-2 |
| **Per-stock JSON files for core only** | Lazy loading for detail view | Not all stocks have detail file; mitigated by fallback to `data.json` |

---

## Open Questions for Future Phases

1. **Should we track per-stock update history?**
   - Pro: Enables "data quality" metrics (e.g., "updated 15/30 days")
   - Con: Increases state file size
   - **Recommendation:** Add in Phase 4 if needed for UI

2. **How to handle market holidays?**
   - Current: GitHub Actions runs on calendar days (may run on holidays)
   - Options: Skip if market closed, or run anyway (idempotent)
   - **Recommendation:** Check Taiwan market calendar API, skip if closed

3. **Should failed updates retry immediately or defer?**
   - Option A: Retry 3 times with backoff (delays completion)
   - Option B: Mark as stale, retry in next cycle (faster completion)
   - **Recommendation:** Option B for Phase 1, Option A for Phase 3

4. **What's the maximum acceptable staleness?**
   - Current assumption: 3 days for non-core stocks
   - Trade-off: Longer cycles reduce API pressure but increase staleness
   - **Recommendation:** Monitor user feedback on 3-day cycle before extending

---

## Success Metrics

### Phase 1 Success Criteria
- ✅ Daily updates complete in <20 minutes
- ✅ Core stocks updated every day (100% freshness)
- ✅ Full market covered within 3 days (>95% of stocks)
- ✅ No API rate limit errors
- ✅ State file persists correctly across runs

### Phase 2 Success Criteria
- ✅ Dashboard displays freshness indicators
- ✅ Search works across all stocks (not just top 1000)
- ✅ Detail view loads per-stock JSON correctly
- ✅ `stock_index.json` includes all stocks

### Phase 3 Success Criteria (Optional)
- ✅ Update time reduced by 20-30%
- ✅ API failure rate <5%
- ✅ Cache hit rate >60%

### Phase 4 Success Criteria (Future)
- ✅ Core selection captures 90%+ of next-day signals
- ✅ Industry coverage maintained (no single sector >30%)
- ✅ Alpha score correlation with trading success >0.7

---

## References

**Existing Codebase Patterns:**
- Current full-refresh: `export_canslim.py` (CanslimEngine loop)
- Batch update prototype: `batch_update_institutional.py` (modulo-3 rotation)
- State management: `incremental_workflow.py` (checks for state files)
- Publishing: `export_dashboard_data.py` (JSON export logic)

**External Dependencies:**
- GitHub Actions: Schedule triggers, workflow timeout limits
- FinMind API: Rate limits (600/min documented, actual may vary)
- TEJ API: Rate limits (undocumented, observed ~1000/hour)
- yfinance: No explicit rate limit, but throttles on burst requests

**Industry Patterns:**
- **Incremental ETL:** Merge fresh data with baseline snapshot (data warehousing)
- **Tiered Caching:** Hot/warm/cold data based on access frequency (CDNs)
- **Rotating Batch Jobs:** Common in daily analytics pipelines (Airflow, Luigi)

---

## Architecture Validation Checklist

- [x] **Does this fit existing pipeline?** Yes—reuses CanslimEngine, just controls input scope
- [x] **Can we roll back safely?** Yes—keep old `export_canslim.py` as fallback script
- [x] **Are state transitions auditable?** Yes—`update_state.json` with transition log
- [x] **Does it respect API limits?** Yes—scoped updates (1200 stocks/day vs. 2000+)
- [x] **Is frontend backward compatible?** Yes—`data.json` schema unchanged, freshness additive
- [x] **Can we test incrementally?** Yes—unit → integration → E2E → production
- [x] **What's the failure mode?** Graceful degradation (skip batch, use fallback data)
- [x] **How do we monitor health?** Logs + freshness distribution report + workflow run time

---

*Architecture research complete. Ready for roadmap phase structuring.*
