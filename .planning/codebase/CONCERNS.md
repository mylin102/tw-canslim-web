# Codebase Concerns

**Analysis Date:** 2025-05-24

## Tech Debt

### Data Pipeline Duplication & Inconsistency

**Issue:** Multiple data generation scripts with hardcoded/duplicated logic instead of centralizing in `core/logic.py`.

**Files:** 
- `export_canslim.py` (749 lines)
- `fast_data_gen.py` (305 lines)
- `quick_data_gen.py` (299 lines)
- `historical_generator_v2.py` (325 lines)
- `quick_auto_update.py` (230 lines)
- `quick_auto_update_enhanced.py` (408 lines)

**Impact:** 
- CANSLIM scoring logic implemented in multiple places leads to inconsistent results (documented in POST_MORTEM_20260415.md: "族群清單顯示 ETF 50 分，但詳情顯示 100 分")
- When `core/logic.py` is updated, changes must be manually propagated to all scripts
- GitHub Actions may use outdated logic and overwrite local corrections
- High risk of regression on each data generation run

**Fix approach:** 
1. Establish `core/logic.py` as the single source of truth for all CANSLIM calculations
2. All scripts must call functions from `core/logic.py`, not reimplement them
3. Remove inline calculation logic from `export_canslim.py:476`, `fast_data_gen.py` institutional fetch, `quick_data_gen.py`
4. Add validation layer that enforces this in pre-commit hooks

### Bare Exception Handling

**Issue:** 28 instances of bare `except:` clauses that silence all errors, making debugging impossible.

**Files:** 
- `fast_data_gen.py:44, 67, 69` (bare except swallowing CSV parse errors)
- `tej_processor.py:51, 86, 383, 423, 453` (API failures silently ignored)
- `export_canslim.py:193, 330, 353`
- `update_single_stock.py:47, 70, 72, 109, 120`
- `historical_generator_v2.py:66, 93, 169`
- `verify_local.py:29`

**Pattern Example:** `except: pass` and `except: return 0` lose actual error context.

**Impact:** 
- Failed API calls (TWSE, TEJ, yfinance) produce zero values silently instead of alerting
- RS scores = 0 when market data fails (masks the real problem)
- Debugging production issues requires manual tracing

**Fix approach:** 
1. Replace all `except:` with specific exception types (`requests.RequestException`, `KeyError`, `pd.errors.ParserError`)
2. Log all exceptions at minimum: `logger.error(f"Failed: {e}")`
3. Distinguish between recoverable (log + continue) vs. fatal (re-raise) failures
4. Add linting rule to forbid bare except

### Fragile Institutional Data Integration

**Issue:** Multiple ways to fetch institutional data, no centralized caching or fallback strategy.

**Files:** 
- `finmind_processor.py:157-180` (FinMind API calls)
- `export_canslim.py:212-270` (TWSE/TPEx REST API)
- `fast_data_gen.py:56-70` (another TWSE implementation)
- `quick_data_gen.py:52-100` (yet another variant)

**Current behavior:**
- FinMind processor hits rate limits (no backoff)
- TWSE/TPEx REST endpoints require date formatting tricks (ROC calendar for TPEx)
- No centralized cache means repeated calls for same date/stock
- Some implementations skip ".replace(',', '')" for parsing, causing silent failures

**Impact:**
- Institutional strength scores can be missing (0.0) on ETFs (POST_MORTEM: "ETF 缺失的淨買超張數")
- Two-tier data quality between scripts that call vs. scripts that skip institutional data
- Rate limiting causes GitHub Actions failures silently

**Fix approach:**
1. Create `core/institutional_data.py` with single `fetch_institutional_data(ticker, date_range)` function
2. Implement file-based cache (daily snapshot in `data/cache/institutional_2025_05_24.json`)
3. Add backoff retry for API failures: exponential backoff + max 3 retries
4. All scripts must use only the cached data for >7 days old, real-time only for last 3 trading days

---

## Known Bugs

### TEJ Financial Data YoY Calculation Broken (CRITICAL)

**Symptoms:** 
- C factor (quarterly EPS growth) always returns False for non-turnaround stocks
- A factor (annual EPS growth) always fails because calculation needs 8 quarters but only 4 are fetched
- All growth calculations fallback to Excel data

**Files:** `tej_processor.py:214, 255-257, 346`

**Trigger:** Any stock with valid TEJ quarterly financials will have C/A factors incorrectly computed.

**Root cause (from REVIEW.md CR-01):**
```python
# tej_processor.py line ~255
unique_dates = sorted(data['mdate'].unique(), reverse=True)[:4]  # BUG: Should be [:8]
```

For C factor calculation, the code compares `eps_list[0]` with `eps_list[3]` (4 quarters ago), but YoY should compare with `eps_list[4]` (exactly 1 year = 4 quarters ago). Current 4-quarter limit makes 5-quarter comparison impossible.

**Workaround:** Stocks rely on Excel-based EPS data instead; reduces scoring accuracy.

**Fix:** 
```python
unique_dates = sorted(data['mdate'].unique(), reverse=True)[:8]  # At least 8 quarters
# In calculate_canslim_c_and_a:
if len(eps_list) >= 5:
    current_q_eps = eps_list[0]
    same_q_last_year_eps = eps_list[4]
```

### Mansfield RS Always Zero (CRITICAL)

**Symptoms:** 
- All stocks show `mansfield_rs: 0.0` in data.json
- Relative Strength (L) factor always False
- Market momentum analysis unavailable

**Files:** `export_canslim.py:507, 647`

**Trigger:** Any run of `export_canslim.py` will produce all-zero MRIS values.

**Root cause (from REVIEW.md CR-02):**
```python
# export_canslim.py line 507
TAIEX_SYMBOL = "^TWII"
market_hist = self.get_price_history(TAIEX_SYMBOL.replace("^", ""), ...)  # BUG
# Becomes: get_price_history("TWII", ...) → then adds ".TW" → "TWII.TW" is not a valid symbol
```

Yahoo Finance doesn't recognize `TWII.TW` as the TAIEX index. The symbol must remain `^TWII`.

**Workaround:** None. L factor (Relative Strength) is always False, reducing CANSLIM scores by 20 points.

**Fix:**
```python
# Remove the .replace("^", "")
market_hist = self.get_price_history(TAIEX_SYMBOL, period="2y")
```

### Frontend Type Errors on Null/Undefined Fields

**Symptoms:** 
- Page goes blank when searching for certain ETFs (e.g., 0050)
- Error in browser console: `Cannot read property 'toLocaleString' of undefined`
- Some stocks display incomplete data

**Files:** `docs/app.js` (Vue template rendering)

**Trigger:** ETFs or stocks with missing financial fields (e.g., no `inst_strength_5d` or `dividend_yield`).

**Root cause:** 
- Vue templates call methods on potentially undefined values: `stock.canslim.dividend_yield.toFixed(2)` when field is missing
- Data structure assumes all stocks have identical financial fields, but ETFs are heterogeneous

**Workaround:** Manually refresh page or filter out problematic stocks.

**Fix:** 
- Use defensive operators in all templates: `(stock.canslim.dividend_yield || 0).toFixed(2)`
- Add v-if guards: `v-if="stock.canslim && stock.canslim.dividend_yield"`
- Standardize output data to always include all expected fields with null/0 as fallback

### Data Serialization Crashes on Pandas Timestamp

**Symptoms:** 
- `data.json` contains 86 bytes (essentially empty) after running export
- Or script crashes silently during json.dump

**Files:** `export_canslim.py:737-744`, `fast_data_gen.py:289-297`, `update_single_stock.py:186-193`

**Trigger:** When TEJ processor returns `Timestamp` objects or `numpy.bool_` types instead of native Python types.

**Root cause:** 
- `json.dump()` cannot serialize pandas Timestamp or numpy types directly
- The custom `json_serial` function handles Timestamp but not `numpy.bool_` or `numpy.int64`
- If unhandled type is encountered, dump silently fails or produces corrupt output

**Current mitigation:** `json_serial` function handles `datetime` and `pd.Timestamp` only.

**Workaround:** Manual JSON encoding with `.astype()` conversions before dump.

**Fix:**
```python
def json_serial(obj):
    if isinstance(obj, (datetime, pd.Timestamp)):
        return obj.strftime('%Y-%m-%d')
    if isinstance(obj, (np.integer, np.floating)):
        return obj.item()  # Convert numpy types to Python native
    if isinstance(obj, (np.bool_)):
        return bool(obj)
    raise TypeError(f"Type {type(obj)} not serializable")
```

---

## Security Considerations

### No Input Validation on Stock Ticker Symbols

**Risk:** Stock ticker symbols are passed directly to yfinance and URL parameters without validation.

**Files:** `export_canslim.py:276-277`, `fast_data_gen.py:39-43`

**Current mitigation:** None. Direct string interpolation: `f"{ticker}{suffix}"`

**Recommendation:**
1. Validate ticker format: `^[0-9]{4}$` for TWSE/TPEx
2. Add allowlist of known ETF prefixes (00, 1, 2)
3. Sanitize URL parameters with `urllib.parse.quote()`
4. Reject any ticker with special characters

### API Credentials Not Clearly Separated

**Risk:** TEJAPI key stored in `.env` but multiple scripts import/use it without clear credential handling.

**Files:** 
- `tej_processor.py` (initializes with `os.environ.get("TEJAPI_KEY")`)
- `.env` file (present but contents hidden)

**Current mitigation:** Credentials in `.env` file, not committed.

**Recommendation:**
1. Centralize credential usage in single module (`core/credentials.py`)
2. Add explicit checks: `if not TEJAPI_KEY: raise ValueError("Missing TEJAPI_KEY")`
3. Log credential usage (without printing values): `logger.info("TEJ API initialized")`
4. Add `.env` to `.gitignore` validation in CI/CD

---

## Performance Bottlenecks

### Sequential yfinance Downloads Trigger Rate Limiting

**Problem:** Script processes 1,500+ stocks and downloads each one individually with `yf.Ticker(symbol).history()`.

**Files:** `export_canslim.py:545-668` (loops over all tickers sequentially)

**Cause:** 
- Each `yf.Ticker(...)` makes a separate HTTP request
- No batching, no caching, no request throttling
- Yahoo Finance rate limit: ~2000 requests per hour (~1 per 2 seconds)
- Processing 1,500 stocks sequentially = ~1 hour minimum

**Current impact:**
- GitHub Actions timeout (default 360 minutes but job can fail)
- Blocks CI/CD pipeline for others
- If a single stock fails, entire job restarts

**Improvement path:**
1. Use `yf.download(list_of_tickers, ...)` for batch downloads (10 stocks/batch)
2. Cache historical data in `data/cache/prices_2025_05_24.parquet`
3. Only download if price data >7 days old
4. Add exponential backoff: wait 5s between batches
5. Implement circuit breaker: if >10% fail in batch, stop and alert

### No Caching Layer for Institutional Data

**Problem:** Same institutional data fetched multiple times per run and on every run.

**Files:** 
- `finmind_processor.py:157-180` (called per stock)
- `export_canslim.py:600-607` (called again in loop)
- Multiple scripts do independent full scans

**Cause:** 
- No persistent cache of TWSE/TPEx institutional data
- Every stock lookup = fresh API call (or cached per-session only)
- Multiple scripts (export, fast_gen, quick_update) each fetch full institutional history

**Current impact:**
- GitHub Actions uses full quota on TWSE/TPEx APIs daily
- TEJ API rate limited → fallback to zero values
- Repeated work: 1,500 stocks × 3 concurrent scripts = 4,500 redundant calls

**Improvement path:**
1. Create daily snapshot cache: `data/institutional/inst_2025_05_24.json`
2. Load from cache if <24hrs old, else fetch
3. Dedup institutional data fetch across scripts with file lock
4. Archive historical snapshots for trend analysis

---

## Fragile Areas

### `core/logic.py` - Assumption of Data Completeness

**Files:** `core/logic.py`

**Why fragile:** 
- Functions assume required columns exist in DataFrames
- No defensive checks for NaN/missing values before mathematical operations
- Line 32-50 (`calculate_accumulation_strength`): assumes `foreign_net`, `trust_net`, `dealer_net` columns exist
- Line 52-55 (`calculate_rs_score`): divides Series values without checking for zero/NaN
- Line 102-126 (`calculate_mansfield_rs`): complex logic with self-correction but no logging of fallback decisions

**Safe modification:**
1. Add defensive column checks at function start
2. Log warnings when fallback logic is triggered
3. Add unit tests for edge cases (empty DF, all NaN, zero denominator)
4. Validate input types explicitly with type hints

**Test coverage gaps:**
- No tests for what happens when institutional data is missing (chip_df empty)
- No tests for yfinance returning mismatched indices (stock vs. market data length)
- No tests for Timestamp/numpy type serialization

### Data Pipeline Resume Logic - Incomplete Field Updates

**Files:** `export_canslim.py:520`, `fast_data_gen.py:83-100`

**Why fragile:** 
- Resume checks if ticker exists in `data.json` but doesn't validate that all fields are present
- New fields added (Mansfield RS, grid_strategy, volatility_grid) are missing from old data.json
- If resume happens with partial data, user sees stale scores

**Safe modification:**
1. Add version field to data.json: `{"version": "2025_05_24", "stocks": {...}}`
2. Skip resume if version mismatch detected
3. Check for presence of critical fields: if `"mansfield_rs" not in stock["canslim"]`, skip resume
4. Add CLI flag: `--force-refresh` to bypass resume entirely

**Example vulnerability:** 
- Run 1 generates data with 100 stocks (old version, no mansfield_rs)
- Run 2 tries resume with `if t in output_data["stocks"]: continue`
- Result: 100 stocks missing new field, not regenerated

### JSON Backup/Versioning - No Integrity Check

**Files:** `export_canslim.py:728-735`, `docs/data*.json` (7 different versions)

**Why fragile:** 
- Backup created but no verification that backup is valid JSON
- If export crashes mid-write, backup is from previous run (stale)
- Multiple partial/corrupted backups in docs/ (data_rescue.json = 86 bytes, data_fix.json = 492 bytes)
- No mechanism to restore from backup on corruption detected

**Safe modification:**
1. Verify backup before resume: `json.load(backup_file)` to validate syntax
2. Implement backup rotation (keep only last 3 versions)
3. Add checksum: `{"version": "...", "stocks": {...}, "checksum": "sha256:..."}`
4. Before using data.json, validate it with schema

---

## Scaling Limits

### Single JSON File Serves All Data

**Current capacity:** ~1,500 stocks × ~2KB per stock = ~3MB uncompressed, ~300KB gzip

**Limit:** 
- Browser loading: 300KB gzip still requires parsing 3MB JSON in JavaScript
- Memory: storing 1,500 stocks in memory = ~300MB for Vue component
- Search/filter: O(n) scan through array for every keystroke
- Adding 500 more stocks = 20% size increase, browser gets sluggish

**Scaling path:**
1. Split by industry or market cap tier: `data_large_cap.json`, `data_etf.json`
2. Implement pagination in API: `/api/stocks?page=1&limit=100`
3. Implement server-side search/filter instead of client-side
4. Use SQLite or IndexedDB for client-side persistence

### API Rate Limiting Not Managed

**Current state:** 
- FinMind: 5,000 requests/month (shared across all users)
- TEJ: 5,000 requests/month (shared)
- TWSE/TPEx: no official limit but gets blocked after ~10,000/day
- Yahoo Finance: ~2000/hour

**Limit reached when:** 
- Multiple concurrent GitHub Actions runs (one per scheduled time)
- Manual runs during testing + scheduled run = overlapping quota

**Scaling path:**
1. Implement request quota management: central counter in GitHub Actions
2. Add request deduplication: if same stock in queue >1x, dedupe
3. Prioritize: focus on top 20 stocks first, then expand
4. Cache aggressively: >7 days old = skip unless explicitly requested
5. Add graceful degradation: if API down, use cached data + alert

---

## Fragile Workflows

### Data Consistency Across Multiple Scripts

**Issue:** No coordination between scripts that write to `data.json`.

**Files:** 
- `export_canslim.py` (main writer)
- `fast_data_gen.py` (alternate generator)
- `update_single_stock.py` (incremental updater)
- `verify_local.py` (rebuilds high-fidelity subset)
- `quick_auto_update.py` (quick partial update)

**Scenario:** 
1. GitHub Actions runs `export_canslim.py` → generates data.json (1,500 stocks)
2. Manual user runs `update_single_stock.py 2330` → modifies data.json in place
3. GitHub Actions runs again, resumes from checkpoint → overwrites user's changes

**Risk:** 
- Data loss if multiple scripts access same file simultaneously
- No file locking, no atomic writes
- Resume logic may use stale partial data

**Fix approach:**
1. Establish single writer per run: add file lock (`.data.lock`)
2. All readers must check lock and wait (max 5 min timeout)
3. All writers must atomic move: write to `.data.json.tmp`, then `os.rename()`
4. Add metadata: `{"locked_by": "export_canslim.py", "locked_at": "2025-05-24T10:00:00Z"}`

### GitHub Actions CI/CD - Silent Failures

**Files:** `.github/workflows/update_data.yml`, `.github/workflows/on_demand_update.yml`

**Current behavior:** 
- If export fails mid-run, old data stays on GitHub Pages
- No notification of failure (webhook silence)
- Resume logic masks the problem (resumes from checkpoint, seems to succeed)
- User sees stale data but no indication of age

**Risk:** 
- Data becomes stale without user knowledge
- If API is down (TWSE, TEJ, yfinance), stale data serves for days
- Post-mortem revealed failures only after manual audit

**Fix approach:**
1. Add explicit check: if output stocks < 100, fail job and alert
2. Log expected stock count: `expected: 1500, actual: 1200` → fail if gap >10%
3. Add Slack/email notification on failure
4. Include data freshness timestamp in response: `last_generated: 2025-05-24T10:30Z`
5. Add health check endpoint that fails if data >24hrs old

---

## Test Coverage Gaps

### Core Logic Missing Edge Case Tests

**Untested area:** Error scenarios and boundary conditions in `core/logic.py`

**Files:** `core/logic.py` (221 lines) with `tests/test_*.py` (849 lines total, but spread across 5 files)

**What's not tested:**
- Empty Series passed to `calculate_c_factor`, `calculate_a_factor` → should return False gracefully
- All NaN values in price history → should return 0 for MRIS, not crash
- Division by zero in `calculate_rs_score` when market_returns[i] = 0
- Timestamp serialization with various numpy dtypes
- ETF-specific scoring logic (`compute_canslim_score_etf`) has no dedicated tests
- Grid strategy calculation (`calculate_volatility_grid`) not tested at all

**Risk:** Production data generation can crash or produce invalid scores silently.

**Priority:** High - These failures go undetected because exceptions are caught and swallowed (bare except).

### Integration Tests Between Modules Missing

**Untested workflows:**
- Full pipeline: Excel data → logic functions → JSON serialization → frontend rendering
- Cross-module interaction: When TEJ returns valid data but Excel has different score → which takes precedence?
- Resume functionality: Does resume with partial data pass validation?
- Data migration: What if new field added to output schema? Do old data.json files still render?

**Risk:** Bugs in integration discovered only in production (like POST_MORTEM incidents).

### Frontend Rendering Tests Missing

**Untested area:** `docs/app.js` Vue template rendering, especially for ETFs and edge cases

**Specific gaps:**
- What happens if `stock.canslim.inst_strength_5d` is undefined? (causes white screen)
- Grid strategy visualization when grid data is null?
- Search filter on stocks with missing fields?
- Very large numbers in financials (>999 trillion TWD)?

**Risk:** Users experience crashes that backend tests don't catch.

---

## Dependencies at Risk

### TEJ API Integration - Unstable

**Risk:** TEJ API is new integration with inconsistent data quality.

**Files:** `tej_processor.py` (482 lines, heavily used)

**Current issues:**
- Quarterly financials limited to 4 records (should be 8+) — blocks A/C factor calculation
- No fallback if TEJ unavailable — silently produces wrong scores
- Multiple exception handlers silently ignore failures: `except: pass`
- API might rate-limit or go offline without graceful degradation

**Migration plan:**
1. Add fallback to MOPS (Taiwan stock exchange) free API for EPS data
2. Implement feature flag: `USE_TEJ = False` if API fails >2x
3. Add health check: `tej_processor.is_initialized()` before use
4. Document TEJ dependency: what data it provides, what happens if missing

### yfinance - Unstable for Taiwan Stocks

**Risk:** yfinance is community-maintained, Taiwan stock support is secondary.

**Current issues:**
- Symbol format inconsistency (`.TW` vs `.TWO` vs ticker only)
- Price split handling buggy (produces anomalies in RS calculation, MRIS self-corrects but loses accuracy)
- Batch downloads sometimes return mismatched indices
- Rate limiting without backoff

**Impact:** 
- Mansfield RS currently always 0 due to symbol parsing bug (CR-02)
- Price anomalies masked by fallback logic instead of fixed

**Migration plan:**
1. Add Yahoo Finance health check: daily validation that key symbols work
2. If yfinance fails, use local market data (TEJ, TAIEX historical)
3. Keep local cache of price history (last 2 years) as fallback
4. Monitor for new yfinance issues: track symbol failures per run

### FinMind - Rate Limited and Unreliable

**Risk:** FinMind API used for institutional data but no SLA, subject to throttling.

**Current behavior:**
- No retry logic (bare except swallows errors)
- No backoff on rate limit (HTTP 429)
- Shared quota across all users (5,000 req/month)

**Impact:** 
- Institutional strength scores can become 0.0 silently
- GitHub Actions job may fail if concurrent runs exhaust quota

**Migration plan:**
1. Implement retry with exponential backoff for FinMind
2. Add request dedup: if same ticker requested >1x, use cache
3. If FinMind down, fallback to TWSE REST API (slower but reliable)
4. Add SLA monitoring: alert if >5% of FinMind requests fail

---

## Missing Critical Features

### Atomic Data Writes & Transactions

**Problem:** Multi-step data generation has no rollback on partial failure.

**Scenario:** 
- Export generates 1,000 stocks successfully
- Crashes on stock 1,001
- Partial data.json is saved; not usable for frontend

**Blocks:** Cannot safely interrupt/resume without risk of corruption.

### Data Validation Schema

**Problem:** No schema validation. Frontend receives malformed data silently crashes.

**Example:** If a stock is missing `canslim.score` field, frontend crashes.

**Solution:** JSON Schema validation before write:
- Define schema: `data.schema.json` with required fields
- Validate on write: `jsonschema.validate(data, schema)` before dump
- Validate on read (frontend): check all expected fields exist

### Monitoring & Alerting

**Problem:** No observability. Data generation succeeds but produces invalid output.

**Example:** If all MRIS values are 0, no alert is raised.

**Missing:**
- Sanity checks: if avg CANSLIM score < 20, alert
- Data freshness: alert if data >24hrs old
- API health: track which APIs are failing
- Performance metrics: track generation time, stocks processed/sec

### API Versioning

**Problem:** Data structure changes break old clients.

**Risk:** If new field added, old frontend breaks. If field removed, resume logic breaks.

**Solution:** 
1. Add version to data.json: `{"version": "v2.1", ...}`
2. Add migration layer: if version mismatch, convert old→new
3. Deprecate old fields gradually, don't remove suddenly

---

## Additional Concerns

### Code Duplication - Function Definitions Across Scripts

**Issue:** Same function defined in multiple files instead of centralized in core modules.

**Examples:**
- `fetch_inst_all()` defined in both `export_canslim.py`, `fast_data_gen.py`, `quick_data_gen.py`
- `fetch_twse_inst()` defined separately in `export_canslim.py`, `fast_data_gen.py`, `quick_data_gen.py`, `historical_generator_v2.py`
- `fetch_tpex_inst()` defined in 4 different scripts
- `calculate_mansfield_rs()` only in logic.py but similar logic partially duplicated in export

**Impact:**
- Bug fixes must be applied to 3+ locations
- Inconsistent implementations (one handles commas in numbers, another doesn't)
- Tests must be written multiple times

**Fix:** Move all institutional/price fetch to `core/institutional_data.py` and `core/market_data.py`.

### Logging - Inconsistent and Hard to Debug

**Issue:** Mixed logging approaches with no consistent log level strategy.

**Files:** 
- `export_canslim.py:29` - INFO level for everything
- `quick_auto_update_enhanced.py:16` - DEBUG level
- Many bare `except: pass` with no logging at all

**Impact:** 
- Production errors invisible until they accumulate
- No audit trail of what data was fetched vs. what failed
- Debugging requires adding print() statements manually

**Fix:** 
1. Centralize logging config in `core/logging_config.py`
2. Use consistent log levels: ERROR (fatal), WARNING (recoverable), INFO (checkpoints), DEBUG (detailed)
3. Log entry/exit of major functions with args (not secrets)
4. Add structured logging: JSON format for machine parsing

### Data Loss Risk - Multiple Backup Files Accumulating

**Issue:** 7 data files in docs/ directory, no clear retention policy.

**Files in docs/:**
- `data.json` (1.0M, current)
- `data_remote.json` (1.7M, unclear purpose)
- `data_base.json` (1.4M, unclear purpose)
- `data_light.json` (303K, lightened version)
- `data_fix.json` (12K, partial)
- `data_rescue.json` (86B, empty/corrupt)
- `data_20260415_*.json.bak` (multiple timestamped backups)

**Risk:** 
- Which is the source of truth?
- If corrupted, which backup to restore?
- Disk usage grows indefinitely with backups
- Frontend might serve wrong version accidentally

**Fix:** 
1. Establish single authoritative file: `data.json`
2. Keep only last 3 timestamped backups: `data.backup.2.json`, `data.backup.1.json`, (current as-is)
3. Delete special-purpose files or rename to indicate read-only purpose: `data_light.json` → `data.lightweight.snapshot.json`
4. Add cleanup script that removes backups >7 days old
5. Document purpose of each file in README

---

*Concerns audit: 2025-05-24*
*Severity: 4 Critical, 3 High, 5 Medium, 6 Low*
