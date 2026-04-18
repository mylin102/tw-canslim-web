# Domain Pitfalls: Incremental Update Migration

**Domain:** Taiwan stock analysis pipeline (brownfield)
**Migration:** Batch full-update → Priority-driven incremental updates
**Researched:** 2025-05-24
**Overall confidence:** HIGH (based on codebase analysis + brownfield migration patterns)

---

## Executive Summary

Moving from "update everything" to "update core stocks daily + rotate the rest" seems simple but exposes fundamental architectural debt in data pipelines. This codebase faces amplified risk because:

1. **Multiple writers with no coordination** — 6+ scripts write to `data.json` without locks
2. **Silent API failures hidden by bare exceptions** — Rate limits cause zero-value data, not errors
3. **No staleness metadata** — Frontend can't distinguish fresh vs. 3-day-old data
4. **Resume logic assumes field stability** — Adding new fields breaks partial updates
5. **GitHub Actions overwrites local fixes** — Automation uses outdated logic forks

The core anti-pattern: **treating incremental updates as "just run the batch script on fewer stocks"** instead of redesigning for partial freshness, staleness tracking, and coordinated writes.

---

## Critical Pitfalls

### Pitfall 1: Priority List Becomes Stale Static Config

**What goes wrong:**
Core stock selection list defined once (e.g., top 100 by market cap) and hardcoded. Two months later, market shifts: new IPO gets hot, priority list still updates the original 100 stocks. User manually searches for the hot stock → sees 5-day-old data despite "daily updates running."

**Why it happens:**
- Initial implementation uses simple static list: `CORE_STOCKS = ["2330", "2317", ...]`
- No signal-driven selection (yesterday's breakout stocks not auto-added to core)
- No volume-based rotation (today's most-traded stocks not prioritized)
- "Set it and forget it" mentality — works initially, degrades silently over weeks

**Consequences:**
- Trading opportunities missed (signal stocks stale)
- User trust erodes ("daily updates" but I see old data)
- Manual workarounds proliferate (local runs, one-off updates)

**Prevention:**
- **Dynamic core selection from 4 sources** (update_strategy.md specifies this):
  1. Fixed base (ETFs, mega-caps) ← only 20-30 stocks
  2. Volume leaders (yesterday's top 100 by turnover)
  3. RS leaders (RS > 80)
  4. **Signal stocks** (ORB breakout, counter_vwap alerts) ← highest priority
- Core list regenerated EVERY RUN from live market data
- Log core selection changes: "2024-05-24: Added 3563 to core (volume spike), Removed 6531 (fell out of top 100)"
- Add `core_selection_metadata.json` with reasons and timestamps

**Detection warning signs:**
- User complaints: "Why is [hot stock] showing old data?"
- Core list size creeps upward (never removes stocks)
- Core list unchanged for >7 days despite market volatility
- Signal stocks not appearing in `data.json` until rotation catches them

**Which phase should address:**
- **Phase 1 (Core Infrastructure)**: Establish dynamic selection function
- **Phase 2 (Integration)**: Connect signals → core selection
- **Validation**: Daily audit log comparing core list day-over-day

---

### Pitfall 2: No Staleness Metadata → User Sees Inconsistent Freshness

**What goes wrong:**
Dashboard shows 1,000 stocks. Stock A updated today, Stock B updated 3 days ago. No visual indicator. User filters for "high RS stocks" → mix of fresh and stale data. Decides to buy Stock B based on stale 3-day-old RS score that has since dropped.

**Why it happens:**
- Output JSON has no `last_updated` timestamp per stock
- Rotating batch updates leave some stocks unrefreshed for 2-3 days (by design)
- Frontend assumes all data equally fresh
- No staleness indicator in UI
- Search/filter treats all stocks identically regardless of age

**Consequences:**
- **Trading decisions on stale data** — critical for intraday/swing trading
- User can't trust dashboard: "Is this today's data or last week's?"
- Support burden: constant questions about "why different dates?"
- Legal/compliance risk if data staleness not disclosed

**Prevention:**
1. **Add timestamps to every stock record:**
   ```json
   {
     "symbol": "2330",
     "name": "台積電",
     "last_updated": "2025-05-24T06:30:00Z",
     "data_age_days": 0,
     "canslim": { ... }
   }
   ```

2. **Add `stock_index.json` with staleness metadata** (update_strategy.md specifies this):
   ```json
   {
     "symbol": "2330",
     "name": "台積電", 
     "last_update": "2025-05-24",
     "in_core": true,
     "in_snapshot": true
   }
   ```

3. **Frontend staleness indicators**:
   - 🟢 Today (0-1 days old)
   - 🟡 Recent (1-2 days old)  
   - 🔴 Stale (3+ days old)
   - Gray out stale stocks in ranking tables
   - Filter controls: "Show only fresh data (today)"

4. **Add staleness warnings to detail views:**
   - "⚠️ Data last updated 3 days ago — not in daily core rotation"
   - "This stock will refresh in ~2 days (batch rotation schedule)"

**Detection warning signs:**
- No `last_updated` field in data exports
- Frontend renders all stocks identically
- User queries: "When was this updated?"
- Random stocks have inconsistent data ages when spot-checked

**Which phase should address:**
- **Phase 1**: Add timestamp infrastructure to data generation
- **Phase 2**: Implement frontend staleness indicators
- **Phase 3**: Add staleness-aware filtering and search

**Existing code evidence:**
Current `data.json` structure lacks per-stock timestamps. `POST_MORTEM_20260415.md` shows users couldn't tell when data diverged. `docs/update_summary.json` exists but not integrated into frontend.

---

### Pitfall 3: Output Format Fragmentation → Frontend Breaks Silently

**What goes wrong:**
Phase 1 generates `data.json` with 200 core stocks (full fields). Phase 2 adds rotating stocks as lightweight entries (missing `institutional`, `grid_strategy` fields). Frontend expects all stocks to have same fields → null pointer errors on rotated stocks. Page crashes when user searches rotated stock.

**Why it happens:**
- Incremental update produces different output formats for different stock tiers:
  - Core stocks: full detail (all fields populated)
  - Rotated stocks: basic only (price, RS, volume)
  - Snapshot (1000 stocks): medium detail
- No schema versioning or field presence contracts
- Resume logic merges heterogeneous data without validation
- Frontend assumes field presence: `stock.canslim.institutional.foreign_net` crashes if undefined

**Consequences:**
- **White screen crashes** (already documented in POST_MORTEM: searching 0050 crashes page)
- Data tables render partially (some columns blank)
- Silent calculation failures (tried to sum undefined institutional data)
- User perception: "The website is broken after the update"

**Prevention:**
1. **Define explicit output schemas per stock tier:**
   ```typescript
   // Core stock schema (all fields required)
   interface CoreStock {
     symbol: string
     last_updated: string
     canslim: {
       c_factor: boolean
       a_factor: boolean
       rs_score: number
       institutional: InstitutionalData  // required
       grid_strategy: GridData           // required
     }
   }
   
   // Rotated stock schema (subset)
   interface RotatedStock {
     symbol: string
     last_updated: string
     canslim: {
       rs_score: number
       // institutional, grid_strategy are optional
     }
   }
   ```

2. **Populate all fields with defaults for rotated stocks:**
   ```python
   # Don't emit undefined fields
   # Instead, use explicit nulls or default values
   stock_data = {
       "institutional": None,  # explicit None, not missing
       "grid_strategy": {"status": "not_calculated"},
   }
   ```

3. **Frontend defensive rendering:**
   ```javascript
   // Current (crashes):
   stock.canslim.institutional.foreign_net.toLocaleString()
   
   // Fixed (safe):
   (stock.canslim?.institutional?.foreign_net || 0).toLocaleString()
   ```

4. **Add schema version to output:**
   ```json
   {
     "schema_version": "2025_05_24_v2",
     "stocks": { ... }
   }
   ```

5. **Validation before merge:**
   ```python
   def validate_stock_data(stock_data, tier):
       required_fields = SCHEMA_REQUIREMENTS[tier]
       for field in required_fields:
           if field not in stock_data:
               raise SchemaError(f"Missing {field} for {tier}")
   ```

**Detection warning signs:**
- Frontend errors: `Cannot read property 'X' of undefined`
- Some stocks render, others don't
- Different data.json files have different field sets
- Resume corrupts data by merging incompatible schemas

**Which phase should address:**
- **Phase 1**: Define schemas, add validation
- **Phase 2**: Implement defensive frontend rendering
- **Testing**: Add schema validation tests before any data export

**Existing code evidence:**
`POST_MORTEM_20260415.md` documents: "搜尋 0050 或部分 ETF 時，網頁變成一片空白" due to calling `.toLocaleString()` on undefined. `CONCERNS.md` lists: "Frontend Type Errors on Null/Undefined Fields."

---

### Pitfall 4: Race Conditions Between Multiple Update Scripts

**What goes wrong:**
1. GitHub Actions runs daily update (writes `data.json`)
2. User triggers manual update for single stock (modifies `data.json` in place)
3. Daily update resumes from checkpoint, reads partially modified file
4. Final output is corrupted mix: some stocks from step 1, some from step 2, some missing

**Why it happens:**
- 6 scripts write to same `data.json`: `export_canslim.py`, `fast_data_gen.py`, `update_single_stock.py`, `quick_auto_update.py`, `verify_local.py`, `fuse_data_json.py`
- No file locking mechanism
- No atomic writes (direct write to `data.json`, not write-temp-then-rename)
- GitHub Actions and local runs can execute simultaneously
- Resume logic reads file mid-write from concurrent process

**Consequences:**
- **Data loss**: newer updates overwritten by older resumed runs
- **Corruption**: malformed JSON from partial writes
- **Silent failures**: corrupt file treated as empty, full regeneration starts (loses all progress)
- **User confusion**: "I updated Stock A locally, but it reverted after Actions ran"

**Prevention:**
1. **Implement file locking:**
   ```python
   import fcntl
   
   class DataFileLock:
       def __init__(self, path):
           self.path = path
           self.lock_file = f"{path}.lock"
       
       def __enter__(self):
           self.lock_fd = open(self.lock_file, 'w')
           try:
               fcntl.flock(self.lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
           except IOError:
               raise RuntimeError(f"Data file locked by another process")
           return self
       
       def __exit__(self, *args):
           fcntl.flock(self.lock_fd, fcntl.LOCK_UN)
           self.lock_fd.close()
   
   # Usage:
   with DataFileLock('docs/data.json'):
       # Read, modify, write
   ```

2. **Atomic writes with temp files:**
   ```python
   import os
   import tempfile
   
   def atomic_write_json(path, data):
       # Write to temp file first
       fd, temp_path = tempfile.mkstemp(
           dir=os.path.dirname(path),
           prefix='.tmp_data_',
           suffix='.json'
       )
       
       with os.fdopen(fd, 'w') as f:
           json.dump(data, f, ensure_ascii=False, indent=2)
       
       # Atomic rename (overwrites destination)
       os.replace(temp_path, path)
   ```

3. **Coordination metadata:**
   ```json
   // .data.lock metadata
   {
     "locked_by": "export_canslim.py",
     "pid": 12345,
     "started_at": "2025-05-24T06:00:00Z",
     "timeout_at": "2025-05-24T07:00:00Z"
   }
   ```

4. **GitHub Actions coordination:**
   ```yaml
   # Add concurrency control
   concurrency:
     group: data-update
     cancel-in-progress: false  # Don't cancel, queue instead
   ```

5. **Detect lock timeouts:**
   ```python
   # If lock older than 1 hour, assume crash and force-unlock
   if lock_age > timedelta(hours=1):
       logger.warning("Stale lock detected, forcing unlock")
       os.remove(lock_file)
   ```

**Detection warning signs:**
- Corrupt JSON files (86 bytes, documented in CONCERNS.md)
- Random data reversions
- `data.json` occasionally has mismatched stock counts
- Logs show overlapping execution times
- File modification timestamps show multiple writes within seconds

**Which phase should address:**
- **Phase 1 (CRITICAL)**: Add file locking before any incremental work
- **Phase 1**: Implement atomic writes
- **Phase 2**: Add GitHub Actions concurrency controls

**Existing code evidence:**
`CONCERNS.md` documents: "No coordination between scripts that write to data.json... No file locking, no atomic writes." `POST_MORTEM_20260415.md`: "GitHub Actions 覆蓋：自動化腳本使用了舊邏輯產生資料，覆蓋了本地修正後的正確資料."

---

### Pitfall 5: API Rate Limits Trigger Silent Cascading Failures

**What goes wrong:**
Update runs for 200 core stocks. Stock 50 triggers FinMind rate limit (5,000/month quota exhausted). Exception caught with bare `except: pass`. Remaining 150 stocks get zero institutional data. CANSLIM I-factor becomes False for all. All scores drop 20 points. User sees "all strong stocks suddenly became weak."

**Why it happens:**
- 28 instances of bare `except:` that swallow all errors (CONCERNS.md audit)
- API failures return zero/null instead of raising errors:
  ```python
  try:
      institutional_data = fetch_institutional(stock)
  except:
      return 0  # BUG: Silently returns wrong data
  ```
- No quota tracking for external APIs (FinMind, TEJ, TWSE)
- No circuit breaker pattern (keeps calling failed API)
- No fallback data source
- Priority updates amplify problem (core stocks call APIs more frequently)

**Consequences:**
- **Data quality degradation invisible** — scores silently become inaccurate
- **Cascading failures** — one API down affects all downstream calculations
- **Quota exhaustion** — priority updates consume quota faster, breaking rotation
- **Debugging nightmare** — no error logs, must reverse-engineer from zero values
- **User distrust** — "Yesterday's strong stocks all dropped today, makes no sense"

**Prevention:**
1. **Replace all bare exceptions:**
   ```python
   # Bad (current):
   except:
       return 0
   
   # Good:
   except requests.HTTPError as e:
       if e.response.status_code == 429:  # Rate limit
           logger.error(f"Rate limit hit for {stock}: {e}")
           raise RateLimitError(f"API quota exhausted")
       else:
           logger.error(f"API error for {stock}: {e}")
           raise
   except Exception as e:
       logger.error(f"Unexpected error for {stock}: {e}")
       raise
   ```

2. **Implement quota tracking:**
   ```python
   class APIQuotaManager:
       def __init__(self):
           self.quotas = {
               'finmind': {'limit': 5000, 'used': 0, 'reset': '2025-06-01'},
               'tej': {'limit': 5000, 'used': 0, 'reset': '2025-06-01'},
           }
       
       def check_quota(self, api):
           if self.quotas[api]['used'] >= self.quotas[api]['limit']:
               raise QuotaExceededError(f"{api} quota exhausted")
       
       def record_call(self, api):
           self.quotas[api]['used'] += 1
   ```

3. **Circuit breaker pattern:**
   ```python
   class CircuitBreaker:
       def __init__(self, failure_threshold=5):
           self.failure_count = 0
           self.threshold = failure_threshold
           self.state = 'closed'  # closed, open, half-open
       
       def call(self, func):
           if self.state == 'open':
               raise CircuitOpenError("API circuit breaker open")
           
           try:
               result = func()
               self.failure_count = 0  # Reset on success
               return result
           except Exception as e:
               self.failure_count += 1
               if self.failure_count >= self.threshold:
                   self.state = 'open'
                   logger.error("Circuit breaker opened due to failures")
               raise
   ```

4. **Fallback data sources:**
   ```python
   def fetch_institutional_data(stock):
       # Try primary source
       try:
           return finmind.fetch(stock)
       except RateLimitError:
           logger.warning(f"FinMind rate limited, using cache")
           # Fall back to yesterday's cached data
           return cache.get_latest(stock)
       except APIError:
           # Fall back to TWSE direct
           return twse_fallback.fetch(stock)
   ```

5. **Fail-fast with clear errors:**
   ```python
   # Don't silently degrade
   # Fail the entire run with clear error message
   if api_quota_exceeded:
       raise QuotaError(
           f"FinMind quota exhausted ({used}/{limit}). "
           f"Resets on {reset_date}. "
           f"Cannot complete core stock updates."
       )
   ```

**Detection warning signs:**
- Sudden unexplained drops in scores across many stocks
- Zero values in institutional data fields
- API error logs missing (silence despite failures)
- Quota exhausted but script continues
- Daily updates complete but with degraded data quality

**Which phase should address:**
- **Phase 1 (CRITICAL)**: Remove bare exceptions, add logging
- **Phase 1**: Implement quota tracking
- **Phase 2**: Add circuit breakers and fallback data
- **Phase 3**: Build quota dashboard and alerts

**Existing code evidence:**
`CONCERNS.md` documents: "28 instances of bare `except:` clauses... API failures silently ignored... RS scores = 0 when market data fails." Multiple files with `except: pass` pattern.

---

### Pitfall 6: Resume Logic Breaks Schema Evolution

**What goes wrong:**
Day 1: Generate `data.json` with 500 stocks (schema v1, no `volatility_grid` field).
Day 2: Add `volatility_grid` to code, resume from checkpoint. Script sees 500 stocks exist, skips them. Outputs mix: 500 stocks without `volatility_grid`, 500 new stocks with it. Frontend breaks on inconsistent schemas.

**Why it happens:**
- Resume checks: `if ticker in existing_data['stocks']: continue`
- No schema version checking
- No field-level validation (are all expected fields present?)
- Resume assumes existing data is compatible with current code
- No migration path for schema changes

**Consequences:**
- **Permanent schema fragmentation** — data.json has inconsistent field sets
- **Feature rollout blocked** — new fields never populate for resumed stocks
- **Forced full regeneration** — only way to fix is wipe and rebuild (hours)
- **Silent frontend failures** — trying to read missing fields

**Prevention:**
1. **Add schema versioning:**
   ```json
   {
     "schema_version": "2025_05_24_v2",
     "required_fields": ["canslim.rs_score", "canslim.volatility_grid"],
     "stocks": { ... }
   }
   ```

2. **Resume with schema validation:**
   ```python
   CURRENT_SCHEMA_VERSION = "2025_05_24_v2"
   REQUIRED_FIELDS = ["canslim.rs_score", "canslim.volatility_grid"]
   
   def can_resume_stock(stock_data):
       # Check schema version
       if data.get("schema_version") != CURRENT_SCHEMA_VERSION:
           logger.info("Schema version mismatch, forcing full refresh")
           return False
       
       # Check required fields
       for field_path in REQUIRED_FIELDS:
           if not has_nested_field(stock_data, field_path):
               logger.info(f"Missing field {field_path}, forcing refresh")
               return False
       
       return True
   ```

3. **Migration scripts for schema changes:**
   ```python
   def migrate_schema_v1_to_v2(data):
       """Add volatility_grid field to existing stocks"""
       for symbol, stock in data['stocks'].items():
           if 'volatility_grid' not in stock['canslim']:
               # Add default value instead of leaving missing
               stock['canslim']['volatility_grid'] = {
                   'status': 'pending_calculation',
                   'last_calculated': None
               }
       data['schema_version'] = 'v2'
       return data
   ```

4. **CLI flag for force refresh:**
   ```python
   parser.add_argument('--force-refresh', action='store_true',
                       help='Ignore existing data, regenerate all')
   
   if args.force_refresh:
       logger.info("Force refresh enabled, skipping resume")
       resume_enabled = False
   ```

5. **Resume safety checks:**
   ```python
   # Check data age — if >7 days old, don't resume
   last_update = datetime.fromisoformat(data['metadata']['last_update'])
   if datetime.now() - last_update > timedelta(days=7):
       logger.warning("Data too old for resume, forcing full refresh")
       return False
   ```

**Detection warning signs:**
- Same stock has different field sets across multiple runs
- New features don't appear in dashboard despite code deployment
- Need manual full regeneration after every schema change
- Frontend console shows missing field errors for some stocks

**Which phase should address:**
- **Phase 1**: Add schema versioning
- **Phase 2**: Implement field validation in resume logic
- **Phase 3**: Build migration framework for schema evolution

**Existing code evidence:**
`CONCERNS.md` documents: "Resume checks if ticker exists but doesn't validate that all fields are present... New fields added (Mansfield RS, grid_strategy, volatility_grid) are missing from old data.json."

---

### Pitfall 7: Rotating Batch Scheduling Becomes Coordination Nightmare

**What goes wrong:**
Design: Rotate 1,500 stocks across 3 groups (500 each), updating one group per day.
Reality: Day 1 updates Group A. Day 2 crashes mid-run (API failure). Day 3 should update Group C but resume logic continues Day 2's Group B. Group C never updates, gets 3+ days stale. User doesn't see rotation coverage degradation.

**Why it happens:**
- No persistent state for rotation schedule
- Crash/restart loses track of which group is "next"
- Resume logic assumes same run, not next scheduled run
- No validation that all groups get updated within rotation period
- Rotation groups not deterministic (random selection)

**Consequences:**
- **Uneven coverage** — some stocks updated daily by accident, others ignored for weeks
- **Rotation drift** — schedule drifts from 3-day cycle to 5-day, then 7-day
- **Coverage gaps invisible** — no monitoring of which stocks haven't updated
- **Priority creep** — core list expands to compensate for broken rotation

**Prevention:**
1. **Persistent rotation state:**
   ```json
   // rotation_state.json
   {
     "rotation_cycle_days": 3,
     "groups": {
       "A": ["0050", "1101", ...],  // 500 stocks
       "B": ["2330", "2317", ...],
       "C": ["3008", "5880", ...]
     },
     "schedule": [
       {"date": "2025-05-24", "group": "A", "status": "completed"},
       {"date": "2025-05-25", "group": "B", "status": "in_progress"},
       {"date": "2025-05-26", "group": "C", "status": "pending"}
     ],
     "last_full_coverage": "2025-05-24"
   }
   ```

2. **Deterministic group assignment:**
   ```python
   def assign_rotation_group(symbol):
       # Hash-based assignment (stable across runs)
       group_id = hash(symbol) % NUM_GROUPS
       return f"Group_{group_id}"
   
   # All stocks always in same group, no drift
   ```

3. **Schedule validation:**
   ```python
   def validate_rotation_coverage():
       state = load_rotation_state()
       
       # Check: all stocks updated within cycle period?
       for symbol in all_symbols:
           last_update = get_last_update(symbol)
           if datetime.now() - last_update > timedelta(days=ROTATION_CYCLE):
               logger.error(f"{symbol} not updated in {ROTATION_CYCLE} days")
               return False
       
       # Check: each group updated within cycle?
       for group_name, stocks in state['groups'].items():
           last_group_update = max(get_last_update(s) for s in stocks)
           if datetime.now() - last_group_update > timedelta(days=ROTATION_CYCLE):
               logger.error(f"{group_name} missed rotation cycle")
               return False
       
       return True
   ```

4. **Crash recovery:**
   ```python
   def get_next_scheduled_group():
       state = load_rotation_state()
       today = datetime.now().date()
       
       # Find today's scheduled group
       for schedule_entry in state['schedule']:
           if schedule_entry['date'] == today:
               if schedule_entry['status'] == 'completed':
                   logger.info("Today's group already completed")
                   return None
               return schedule_entry['group']
       
       # If not found, determine next group in cycle
       last_completed = find_last_completed_group(state)
       return get_next_group_in_cycle(last_completed)
   ```

5. **Coverage monitoring:**
   ```python
   def generate_coverage_report():
       report = {
           'total_stocks': len(all_symbols),
           'updated_today': 0,
           'updated_1_day': 0,
           'updated_2_days': 0,
           'stale_3plus_days': 0,
           'never_updated': 0
       }
       
       for symbol in all_symbols:
           age = get_data_age(symbol)
           if age == 0: report['updated_today'] += 1
           elif age == 1: report['updated_1_day'] += 1
           elif age == 2: report['updated_2_days'] += 1
           elif age >= 3: report['stale_3plus_days'] += 1
           if age is None: report['never_updated'] += 1
       
       # Alert if coverage degraded
       if report['stale_3plus_days'] > 0.1 * report['total_stocks']:
           raise CoverageError("More than 10% of stocks stale")
       
       return report
   ```

**Detection warning signs:**
- Some stocks never updated despite rotation "running daily"
- Rotation cycle drifts from 3 days to 5+ days
- After crash, rotation schedule becomes unpredictable
- No way to answer "when will stock X update next?"
- Coverage gaps discovered only through user complaints

**Which phase should address:**
- **Phase 2**: Implement rotation state persistence
- **Phase 2**: Build schedule validation and coverage monitoring
- **Phase 3**: Add rotation status to dashboard (show next update time)

---

### Pitfall 8: No Rollback Strategy When Updates Corrupt Data

**What goes wrong:**
New incremental update logic deployed. First run generates corrupted `data.json` (schema mismatch). Gets committed to GitHub Pages. Website breaks. Old working `data.json` is gone (overwritten). No way to rollback. Hours-long full regeneration required to fix.

**Why it happens:**
- No backup before update runs
- Git commits overwrite previous version
- No validation before publishing
- No health checks that fail deployment
- No quick rollback mechanism

**Consequences:**
- **Extended outages** — website broken until full regeneration completes
- **Data loss risk** — no way to recover previous good state
- **User impact** — trading decisions blocked during outage
- **Emergency pressure** — forced to rush fixes instead of methodical debugging

**Prevention:**
1. **Pre-update backup:**
   ```python
   def backup_before_update():
       timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
       backup_path = f"docs/backups/data_{timestamp}.json"
       
       # Keep last 7 backups only
       cleanup_old_backups(keep=7)
       
       shutil.copy('docs/data.json', backup_path)
       logger.info(f"Backup created: {backup_path}")
       return backup_path
   ```

2. **Validation before commit:**
   ```python
   def validate_before_publish(data_path):
       # 1. Valid JSON syntax
       with open(data_path) as f:
           data = json.load(f)
       
       # 2. Minimum stock count
       if len(data.get('stocks', {})) < 100:
           raise ValidationError(f"Too few stocks: {len(data['stocks'])}")
       
       # 3. Schema compliance
       validate_schema(data)
       
       # 4. Required fields present
       sample_stock = list(data['stocks'].values())[0]
       required = ['symbol', 'canslim', 'last_updated']
       for field in required:
           if field not in sample_stock:
               raise ValidationError(f"Missing field: {field}")
       
       # 5. Data freshness
       latest_update = max(s['last_updated'] for s in data['stocks'].values())
       if datetime.now() - parse_datetime(latest_update) > timedelta(days=2):
           raise ValidationError("Data too stale to publish")
       
       logger.info("Validation passed")
       return True
   ```

3. **GitHub Actions validation gate:**
   ```yaml
   - name: Validate data before commit
     run: |
       python3 validate_data.py docs/data.json
       if [ $? -ne 0 ]; then
         echo "Validation failed, aborting deployment"
         exit 1
       fi
   ```

4. **Rollback script:**
   ```python
   def rollback_to_backup(backup_name=None):
       if backup_name is None:
           # Use most recent backup
           backups = sorted(glob('docs/backups/data_*.json'))
           if not backups:
               raise Error("No backups available")
           backup_name = backups[-1]
       
       logger.info(f"Rolling back to {backup_name}")
       shutil.copy(backup_name, 'docs/data.json')
       
       # Commit rollback
       os.system('git add docs/data.json')
       os.system(f'git commit -m "Rollback to {backup_name}"')
       os.system('git push')
   ```

5. **Health check endpoint:**
   ```python
   # Add to static site
   // docs/health.json (regenerated with every update)
   {
     "status": "healthy",
     "last_update": "2025-05-24T06:30:00Z",
     "stock_count": 1500,
     "schema_version": "v2",
     "validation_passed": true
   }
   
   # Monitor script checks this endpoint
   # Alerts if health.json stale or status != "healthy"
   ```

**Detection warning signs:**
- No backup files in repository
- Deployment fails but no way to revert
- Manual emergency fixes required frequently
- No validation step in deployment pipeline

**Which phase should address:**
- **Phase 1**: Add backup before every update
- **Phase 2**: Implement validation gate
- **Phase 3**: Build automated rollback mechanism

**Existing code evidence:**
`CONCERNS.md` documents: "Backup created but no verification that backup is valid JSON... Multiple partial/corrupted backups in docs/ (data_rescue.json = 86 bytes)." Current backup strategy exists but doesn't prevent corrupt data publication.

---

## Moderate Pitfalls

### Pitfall 9: Incremental Calculation Drift

**What goes wrong:**
Batch mode: recalculate RS from scratch (2 years of data) every run.
Incremental mode: update RS by appending today's data to yesterday's calculation.
After 30 days, incremental RS diverges from batch RS due to accumulated rounding errors, missing data points, or calculation logic changes.

**Why it happens:**
- Incremental calculations rely on previous state
- No periodic full recalculation to correct drift
- Floating-point rounding accumulates
- Missing data handled differently in incremental vs. batch
- No validation comparing incremental vs. batch results

**Prevention:**
- Run full batch recalculation weekly (even with incremental updates)
- Compare incremental vs. batch: if delta > threshold, flag for investigation
- Log calculation inputs to debug drift
- Use Decimal for money calculations (not float)
- Add `last_full_recalc` timestamp to track drift risk

**Which phase should address:** Phase 2 (calculation migration)

---

### Pitfall 10: Core List Size Creep

**What goes wrong:**
Week 1: Core list has 200 stocks (reasonable).
Week 4: Core list has 450 stocks (signal stocks keep getting added, never removed).
Week 8: Core list has 800 stocks (defeats the purpose of "core").

**Why it happens:**
- Add logic: "If signal triggered, add to core"
- No remove logic: "If no signal for 7 days, remove from core"
- Core list grows monotonically
- No size cap enforcement

**Prevention:**
- Hard cap: `MAX_CORE_SIZE = 500`
- Remove stocks that drop out of criteria (not just add)
- Age out signal stocks after 7 days of inactivity
- Monitor core size: alert if >400 stocks
- Weekly review: prune stocks no longer meeting criteria

**Which phase should address:** Phase 2 (core selection refinement)

---

### Pitfall 11: Update Time Budget Exceeded

**What goes wrong:**
Design: "Update 200 core stocks daily, should take 30 minutes."
Reality: One stock hangs (API timeout), delays entire run. After 200 stocks, 2 hours elapsed. GitHub Actions timeout (3 hours) at risk.

**Why it happens:**
- No per-stock timeout
- Sequential processing (no parallelization)
- No early-abort on time budget
- One slow stock blocks all others

**Prevention:**
- Per-stock timeout: `timeout=30` seconds
- Parallel processing: `ThreadPoolExecutor` with 10 workers
- Time budget tracking: abort if >80% of allotted time used
- Skip/defer problem stocks: log and continue
- Fail-fast on repeated timeouts (circuit breaker)

**Which phase should address:** Phase 2 (orchestration optimization)

---

### Pitfall 12: Inconsistent Priority Between Core Selection and Frontend Display

**What goes wrong:**
Backend: Prioritizes volume + RS + signals for core updates.
Frontend: Sorts by market cap (default).
User sees: Small-cap breakout stock (in core, updated today) buried on page 10. Large-cap stock (not in core, 3 days old) on page 1.

**Why it happens:**
- Backend and frontend use different priority definitions
- No shared priority scoring
- Frontend sort doesn't consider data freshness
- Users don't understand what "core" means

**Prevention:**
- Shared priority score used by backend AND frontend
- Frontend default sort: priority score (not market cap)
- Add "Updated today" badge on fresh stocks
- Default filter: "Show top 100 by priority + freshness"
- Explain priority criteria in UI

**Which phase should address:** Phase 3 (frontend integration)

---

## Minor Pitfalls

### Pitfall 13: Test Coverage Doesn't Cover Incremental Paths

**What goes wrong:**
Tests validate batch mode (full regeneration). Incremental mode has no tests. Resume logic breaks in production.

**Prevention:**
- Add tests for resume logic
- Test partial updates
- Test schema migration
- Test concurrent writes
- Integration tests for full workflow

**Which phase should address:** Phase 1 (testing infrastructure)

---

### Pitfall 14: No Monitoring/Observability for Update Process

**What goes wrong:**
Update runs daily. No visibility into what happened. Failures silent. User reports break first signal.

**Prevention:**
- Log every run: stocks updated, API calls, errors, duration
- Dashboard: show last run status, coverage %, staleness distribution
- Alerts: email/Slack on failure, quota warnings, coverage degradation
- Metrics: API quota usage, update duration trends, error rates

**Which phase should address:** Phase 3 (operations/monitoring)

---

### Pitfall 15: Documentation Drift from Implementation

**What goes wrong:**
`update_strategy.md` describes "3-day rotation cycle." Implementation uses 5-day. README says "all stocks updated daily." No one updates docs.

**Prevention:**
- Auto-generate docs from configuration
- Add "last verified" date to strategy docs
- Link code to docs (comments with doc references)
- Require doc update in PR checklist
- Periodic audit: does implementation match spec?

**Which phase should address:** Phase 3 (documentation)

---

## Phase-Specific Warnings

| Phase Topic | Likely Pitfall | Mitigation |
|-------------|---------------|------------|
| **Phase 1: Core Selection** | Static core list, no dynamic selection | Implement 4-source dynamic selection (signals, volume, RS, base) |
| **Phase 1: File I/O** | Race conditions, no locking | Add file locks and atomic writes BEFORE any incremental work |
| **Phase 1: Error Handling** | Bare exceptions hide API failures | Remove all bare `except:`, add logging and quota tracking |
| **Phase 2: Rotation** | Schedule drift, uneven coverage | Persistent rotation state, coverage validation |
| **Phase 2: Schema Evolution** | Resume breaks with new fields | Schema versioning, field validation, migration scripts |
| **Phase 2: Calculation** | Incremental drift from batch truth | Weekly full recalc, validation against batch mode |
| **Phase 3: Frontend** | No staleness indicators | Add timestamps, freshness badges, staleness filters |
| **Phase 3: Publication** | No rollback on corruption | Pre-publish validation, backup, rollback script |
| **Phase 3: Operations** | Silent failures invisible | Monitoring, alerts, coverage dashboard |

---

## Emphasis: Critical Risks

### API Limit Risks
- **Current quota burn rate unknown** — No tracking of FinMind (5K/mo), TEJ (5K/mo), TWSE limits
- **Priority updates amplify consumption** — 200 stocks × 3 institutions × 20 days = 12K calls (exceeds monthly quota in one run)
- **Circuit breakers missing** — Will keep calling failed API until quota exhausted
- **Mitigation**: Implement quota manager (Phase 1), cache aggressively, fallback to yesterday's data

### Stale Data UX Risks
- **Users can't trust data** — No way to tell if seeing today's or last week's data
- **Trading decision risk** — Stale RS/price data leads to bad entries
- **Legal exposure** — If user loses money due to stale data without warning
- **Mitigation**: Per-stock timestamps (Phase 1), staleness indicators (Phase 2), filters (Phase 3)

### Brownfield Migration Risks
- **6 scripts modify same file** — Coordination nightmare, data corruption risk
- **No schema versioning** — Can't evolve data format safely
- **Resume logic brittle** — Assumes data structure stable
- **POST_MORTEM lessons ignored** — Same issues (logic duplication, bare exceptions) not yet fixed
- **Mitigation**: File locking (Phase 1), schema versioning (Phase 1), centralize logic (Phase 1)

### Publication Risks
- **No validation gate** — Corrupt data published directly to GitHub Pages
- **No rollback mechanism** — If bad data published, hours to fix
- **GitHub Actions overwrites** — Automation can revert manual fixes
- **Silent failures** — Actions complete "successfully" with degraded data
- **Mitigation**: Validation before commit (Phase 2), backups (Phase 1), health checks (Phase 3)

---

## Quality Gate: Pre-Phase Checklist

**Before starting Phase 1:**
- [ ] All 28 bare `except:` catalogued with replacement plan
- [ ] File locking proof-of-concept tested
- [ ] Schema versioning design reviewed
- [ ] API quota limits researched and documented
- [ ] Existing resume logic audited for schema assumptions

**Before starting Phase 2:**
- [ ] Phase 1 file locking deployed and tested
- [ ] Schema versioning implemented
- [ ] Rotation state persistence designed
- [ ] Coverage validation logic specified

**Before starting Phase 3:**
- [ ] Staleness metadata in all outputs
- [ ] Frontend rendering handles missing fields
- [ ] Validation gate tested
- [ ] Rollback procedure documented and tested

---

## Sources

**HIGH Confidence:**
- `.planning/PROJECT.md` — Project requirements and constraints
- `.planning/codebase/CONCERNS.md` — Existing technical debt catalog (25KB, comprehensive audit)
- `update_strategy.md` — Specified rotation and priority strategy
- `POST_MORTEM_20260415.md` — Production incidents (logic regression, white screen, data corruption)
- Codebase inspection: `quick_auto_update.py`, `incremental_workflow.py`, multiple update scripts
- File listing: 6+ scripts writing to `data.json`, no coordination visible

**MEDIUM Confidence:**
- Common brownfield migration patterns (training data)
- API rate limiting patterns (training data)
- Data pipeline best practices (training data)

**Domain-specific evidence:**
- 28 bare exceptions catalogued in CONCERNS.md
- Multiple data corruption incidents in POST_MORTEM
- Existing staleness issues ("when was this updated?" user confusion)
- File lock absence confirmed by code inspection
- Schema drift already occurring (volatility_grid, mansfield_rs field additions)

---

**Last updated:** 2025-05-24
**Researcher confidence:** HIGH
**Primary risk areas:** File coordination, API quota, staleness UX, schema evolution
