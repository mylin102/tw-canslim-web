# Phase 2: Dynamic Core Selection - Research

**Researched:** 2026-04-18 [VERIFIED: system date]
**Domain:** Brownfield Python selector for daily core-stock priority ordering [VERIFIED: 02-CONTEXT.md; ROADMAP.md]
**Confidence:** MEDIUM [VERIFIED: codebase inspection; local artifact inspection; local test runs]

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** The daily core universe must be built from these source buckets: base symbols, ETFs, watchlist names, yesterday's signal names, top-volume leaders, RS leaders, and today's active signal names. [VERIFIED: 02-CONTEXT.md]
- **D-02:** Same-day promotion into the core universe should trust signals already present in the fused parquet / `alpha_integration_module.py` path rather than introducing a second signal parser in this phase. [VERIFIED: 02-CONTEXT.md]
- **D-03:** Target a daily core universe of about 300 names. [VERIFIED: 02-CONTEXT.md]
- **D-04:** Always keep base symbols, ETFs, watchlist names, yesterday-signal names, and today's active signal names first; fill remaining slots by RS rank and volume rank. [VERIFIED: 02-CONTEXT.md]
- **D-05:** Yesterday's signal names get a one-day carryover window, then drop out unless they still qualify through another active bucket. [VERIFIED: 02-CONTEXT.md]

### the agent's Discretion
- Exact ranking formula between RS leaders and volume leaders once the fixed priority buckets are included. [VERIFIED: 02-CONTEXT.md]
- How to store and load the base list, ETF list, and watchlist configuration, as long as the selected source buckets remain intact. [VERIFIED: 02-CONTEXT.md]
- Internal helper/module boundaries for the selector implementation. [VERIFIED: 02-CONTEXT.md]

### Deferred Ideas (OUT OF SCOPE)
- Rotation group sizing and non-core batch handling belong to Phase 3. [VERIFIED: 02-CONTEXT.md]
- Freshness indicators, `stock_index.json`, and frontend-facing publish structure belong to Phase 4. [VERIFIED: 02-CONTEXT.md]
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| ORCH-01 | Maintainer can generate a daily core stock universe from base symbols, volume leaders, RS leaders, and active signals. [VERIFIED: REQUIREMENTS.md] | Replace the inline `priority` list in `export_canslim.py` with a pure selector helper, source fixed buckets from checked-in JSON, source active/yesterday signals from fused parquet using AlphaFilter semantics, and fill the remainder from deterministic RS/volume ranking inputs. [VERIFIED: export_canslim.py:681-684; alpha_integration_module.py:18-63; local artifact inspection; ASSUMED] |
</phase_requirements>

## Project Constraints (from copilot-instructions.md)

- Stay brownfield and file-based; do not introduce a database-backed orchestration layer. [VERIFIED: copilot-instructions.md; PROJECT.md; REQUIREMENTS.md]
- Follow existing Python conventions: snake_case names, module-level logging, explicit helper functions, and type hints. [VERIFIED: copilot-instructions.md]
- Keep changes inside the existing Python/GitHub Actions pipeline and reuse existing modules where possible. [VERIFIED: copilot-instructions.md; PROJECT.md]
- Keep publish behavior on the shared publish-safety contract; Phase 2 should change selection logic, not bypass bundle-safe writers. [VERIFIED: 02-CONTEXT.md; export_canslim.py; tests/test_primary_publish_path.py]
- Use pytest-based validation and preserve deterministic tests. [VERIFIED: copilot-instructions.md; requirements.txt; local test runs]

## Summary

The lowest-risk Phase 2 implementation is to keep `export_canslim.py` as the entry point and replace only the two lines that build `priority`/`scan_list` with a dedicated selector helper that returns an ordered `core_symbols` list plus bucket metadata. The current behavior is a 7-symbol hard-coded list followed by the first 2,000 remaining tickers in sorted order, so the integration seam is already obvious and small. [VERIFIED: export_canslim.py:681-684]

Use the existing fused parquet path for signal-driven promotion, but validate it before trusting it. `AlphaFilter` already loads `master_canslim_signals_fused.parquet` and treats `score >= min_score` as the base approval rule with a default `min_score=75`, which is enough to define “today active signals” and “yesterday carryover” without inventing a second parser. [VERIFIED: alpha_integration_module.py:9-63] The local repo also shows a real freshness hazard: `master_canslim_signals_fused.parquet` currently tops out at `2025-04-10`, while `master_canslim_signals.parquet` reaches `2026-04-10`, so the selector must reject or refresh stale fused inputs before claiming same-day promotion. [VERIFIED: local parquet inspection on 2026-04-18]

The biggest planning risk is volume ranking. The published baseline artifact has useful RS data (`docs/data_base.json` contains 2,167 stocks with `canslim.mansfield_rs`), but it does not persist `financials.volume`, and the current master/fused parquet path does not persist absolute volume either. [VERIFIED: local artifact inspection; historical_generator.py:153-165; fuse_excel_data.py:47-56] Plan Phase 2 so RS ranking can be implemented immediately from existing artifacts, while volume ranking is satisfied either by extending the existing signal artifact schema to carry a latest-day volume metric or by an explicit, tested fallback prepass. [VERIFIED: codebase inspection; ASSUMED]

**Primary recommendation:** Add a pure `build_core_universe()` helper, back it with a checked-in JSON config for base/ETF/watchlist buckets, derive today/yesterday signals from fused parquet, and rank the remaining slots from cached RS plus a deliberately chosen volume source instead of keeping any new orchestration state. [VERIFIED: export_canslim.py; alpha_integration_module.py; docs/data_base.json; ASSUMED]

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python | 3.12.5 locally / 3.11 in Actions [VERIFIED: python3 --version; PROJECT.md] | Runs the existing pipeline and tests. [VERIFIED: PROJECT.md] | The repo is already a direct-script Python pipeline. [VERIFIED: PROJECT.md; export_canslim.py] |
| pandas | 2.3.3 locally [VERIFIED: local import version check] | Loads parquet inputs and performs date/rank/filter operations for selector inputs. [VERIFIED: alpha_integration_module.py; export_dashboard_data.py; fuse_excel_data.py] | Already used everywhere selector data lives. [VERIFIED: requirements.txt; codebase grep] |
| Existing selector seam in `export_canslim.py` | repo-local [VERIFIED: export_canslim.py] | Replaces the hard-coded priority list without changing publish plumbing. [VERIFIED: export_canslim.py:648-871] | This is the smallest brownfield integration point. [VERIFIED: 02-CONTEXT.md; export_canslim.py] |
| `alpha_integration_module.py` fused-parquet path | repo-local [VERIFIED: alpha_integration_module.py] | Defines the in-repo signal approval semantics for same-day promotion. [VERIFIED: alpha_integration_module.py:18-63] | Locked decision D-02 requires this path. [VERIFIED: 02-CONTEXT.md] |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pytest | 9.0.2 locally [VERIFIED: pytest --version] | Deterministic selector/unit/integration tests. [VERIFIED: requirements.txt; local test runs] | Use for pure selector tests and `export_canslim` integration tests. [VERIFIED: tests/test_primary_publish_path.py] |
| yfinance | 1.2.0 locally [VERIFIED: local import version check] | Existing path for live price/volume fetches if planner chooses a temporary volume prepass. [VERIFIED: export_canslim.py:394-412] | Use only if volume cannot be sourced from persisted artifacts yet. [VERIFIED: export_canslim.py; ASSUMED] |
| JSON config file (new) | repo-local [ASSUMED] | Stores curated base symbols, ETFs, and watchlist inputs. [ASSUMED] | Use because no existing watchlist/base-symbol source was found in the repo. [VERIFIED: repo search for `watchlist`/`base_symbols`] |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Pure selector helper imported by `export_canslim.py` [ASSUMED] | Inline more logic inside `CanslimEngine.run()` [VERIFIED: export_canslim.py] | Inline logic would make a large method larger and harder to test deterministically. [VERIFIED: export_canslim.py:648-871] |
| Checked-in JSON config for fixed buckets [ASSUMED] | Hard-code lists in Python again [VERIFIED: current `priority` list] | Hard-coding caused the current drift/problem and keeps watchlist changes coupled to code deploys. [VERIFIED: export_canslim.py:681-684; ROADMAP.md] |
| Derive carryover from previous fused-parquet trading day [ASSUMED] | Add a new state file in Phase 2 [VERIFIED: out-of-scope state is Phase 3] | A new state file bleeds into Phase 3 scope unnecessarily. [VERIFIED: REQUIREMENTS.md; ROADMAP.md] |

**Installation:** [VERIFIED: requirements.txt]
```bash
pip install -r requirements.txt
```

**Version verification:** No new package is required for Phase 2; the local environment already has `pandas 2.3.3`, `yfinance 1.2.0`, `pytest 9.0.2`, `requests 2.32.5`, and `numpy 1.26.4`. [VERIFIED: local import version check]

## Architecture Patterns

### Recommended Project Structure
```text
repo/
├── export_canslim.py              # Existing entry point; call selector here
├── core_selection.py              # New pure selection helper [ASSUMED]
├── core_selection_config.json     # New checked-in fixed-bucket config [ASSUMED]
└── tests/
    ├── test_core_selection.py     # Pure selector behavior tests [ASSUMED]
    └── test_primary_publish_path.py  # Export integration assertions (existing)
```

### Pattern 1: Pure selector helper with an explicit result object
**What:** Build a helper that accepts already-known inputs (all symbols, fused snapshot, baseline RS snapshot, config, target size) and returns ordered `core_symbols`, per-bucket membership, and debug counts. [ASSUMED]
**When to use:** Use it once at the top of `CanslimEngine.run()` before building `scan_list`. [VERIFIED: export_canslim.py:648-686]
**Why this fits:** `export_canslim.py` already has a clean seam where only `priority` and `scan_list` need replacement. [VERIFIED: export_canslim.py:681-684]
**Example:**
```python
# Recommended pattern; follows helper-first structure already used in export_canslim.py
selection = build_core_universe(
    all_symbols=sorted(self.ticker_info.keys()),
    fused_path=os.path.join(SCRIPT_DIR, "master_canslim_signals_fused.parquet"),
    baseline_path=os.path.join(OUTPUT_DIR, "data_base.json"),
    config_path=os.path.join(SCRIPT_DIR, "core_selection_config.json"),
    target_size=300,
)
scan_list = selection.core_symbols + [ticker for ticker in sorted(self.ticker_info) if ticker not in selection.core_set][:2000]
```
Source: recommended brownfield integration based on `export_canslim.py` scan-list seam. [VERIFIED: export_canslim.py:681-684; ASSUMED]

### Pattern 2: Carryover from prior trading-day signal snapshot, not a new state file
**What:** Read the latest and previous dates in fused parquet, compute “today active” and “yesterday active” from the same threshold function, and include yesterday’s names for exactly one day. [VERIFIED: alpha_integration_module.py:18-63; local parquet inspection]
**When to use:** Use for D-05 carryover because Phase 3 owns persistent orchestration state. [VERIFIED: REQUIREMENTS.md; ROADMAP.md]
**Example:**
```python
df = pd.read_parquet("master_canslim_signals_fused.parquet")
df["date"] = pd.to_datetime(df["date"])
dates = sorted(df["date"].dropna().unique())
latest_date = dates[-1]
previous_date = dates[-2]

today_active = set(df[(df["date"] == latest_date) & (df["score"].fillna(0) >= 75)]["stock_id"])
yesterday_active = set(df[(df["date"] == previous_date) & (df["score"].fillna(0) >= 75)]["stock_id"])
```
Source: threshold derived from `AlphaFilter(min_score=75)` semantics. [VERIFIED: alpha_integration_module.py:18-63]

### Pattern 3: Fixed buckets first, then deterministic RS/volume fill
**What:** Preserve fixed bucket order exactly, dedupe by first appearance, then rank the remainder with a stable sort key. [ASSUMED]
**When to use:** Use after base/ETF/watchlist/yesterday/today buckets are assembled. [VERIFIED: 02-CONTEXT.md]
**Recommended sort key:** `(-rs_metric, -volume_metric, symbol)` so the fill is deterministic and RS stays primary once fixed/signal buckets are already guaranteed. [ASSUMED]
**Evidence for RS source:** `docs/data_base.json` already has `canslim.mansfield_rs` for 2,167 stocks, with 356 symbols above 0 and 199 above 2, so RS can fill a ~300-name core immediately. [VERIFIED: local artifact inspection on 2026-04-18]

### Anti-Patterns to Avoid
- **Do not keep bucket definitions inside `export_canslim.py`:** that recreates the current hard-coded drift problem. [VERIFIED: export_canslim.py:681-684]
- **Do not add a new Phase-2 state store for carryover:** carryover can be derived from fused parquet dates, and persistent orchestration belongs to Phase 3. [VERIFIED: REQUIREMENTS.md; ROADMAP.md]
- **Do not trust stale fused parquet silently:** local artifacts already show fused data can lag raw signal data by a year. [VERIFIED: local parquet inspection on 2026-04-18]
- **Do not treat all cached ETFs as fixed-core members:** `etf_cache.json` contains 216 entries / 132 valid digit IDs, which would consume most of a 300-name budget by itself. [VERIFIED: etf_cache.json; local artifact inspection]

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Same-day signal parser | A second parser for ORB/counter-vwap-like promotion rules [VERIFIED: D-02] | `master_canslim_signals_fused.parquet` + `AlphaFilter` threshold semantics [VERIFIED: alpha_integration_module.py:18-63] | Locked decision D-02 already chooses this path. [VERIFIED: 02-CONTEXT.md] |
| Carryover state | A new state DB / state.json just for Phase 2 [VERIFIED: Phase 3 owns persistent state] | Previous trading-day rows from fused parquet [VERIFIED: local parquet inspection] | One-day carryover is derivable data, not new orchestration state. [VERIFIED: ROADMAP.md; REQUIREMENTS.md] |
| ETF discovery | Manual ETF scraping/list maintenance in code [VERIFIED: existing ETF cache] | `etf_cache.json` for metadata + curated ETF symbols in config [VERIFIED: export_canslim.py:88-103; etf_cache.json; ASSUMED] | The cache already supplies ETF metadata; only curated membership is missing. [VERIFIED: export_canslim.py; repo search] |
| Publish path changes | A custom writer for selector output [VERIFIED: Phase 1 established publish contract] | Keep existing `publish_artifact_bundle` path untouched [VERIFIED: export_canslim.py:217-235; tests/test_primary_publish_path.py] | Phase 2 should only change ordering/selection, not artifact safety. [VERIFIED: 02-CONTEXT.md] |

**Key insight:** The hard part is not “choose 300 symbols”; it is choosing them from stable, already-produced artifacts so Phase 2 does not accidentally grow into a new signal pipeline or Phase 3 state system. [VERIFIED: 02-CONTEXT.md; REQUIREMENTS.md; codebase inspection]

## Common Pitfalls

### Pitfall 1: Fused parquet freshness/schema drift
**What goes wrong:** Same-day promotion uses stale or incomplete fused data and silently misses recent signal names. [VERIFIED: export_dashboard_data.py expects fused fields; local parquet inspection]
**Why it happens:** Local artifacts show `master_canslim_signals_fused.parquet` is older than `master_canslim_signals.parquet`, and downstream code assumes fused columns like `rs_rating`, `fund_change`, and `smr_rating` exist. [VERIFIED: local parquet inspection; export_dashboard_data.py:44-116]
**How to avoid:** Validate file existence, required columns, and latest date before selecting signals; if stale, refresh through the existing fuse step or fail explicitly. [VERIFIED: fuse_excel_data.py:17-56; ASSUMED]
**Warning signs:** `latest_fused_date < latest_master_date`, missing required fused columns, or unexpectedly tiny active-signal counts. [VERIFIED: local parquet inspection]

### Pitfall 2: ETF bucket overwhelms the target universe
**What goes wrong:** Adding every ETF from cache leaves too little room for RS/volume leaders. [VERIFIED: etf_cache.json; local artifact inspection]
**Why it happens:** `etf_cache.json` currently lists 216 ETFs, with 132 numeric ticker IDs suitable for selection. [VERIFIED: etf_cache.json; local inspection]
**How to avoid:** Keep a curated `etf_symbols` list in config and use `etf_cache.json` only for metadata/validation. [ASSUMED]
**Warning signs:** Fixed buckets alone consume most of the 300 target before any RS/volume fill. [VERIFIED: D-03; etf_cache.json]

### Pitfall 3: “Newest Excel file” is not actually deterministic
**What goes wrong:** Regenerating fused data picks an unintended health-check workbook. [VERIFIED: excel_processor.py]
**Why it happens:** `ExcelDataProcessor._find_excel_files()` comments that it uses the newest health-check file, but the implementation just walks `os.listdir()` and keeps the last matching filename. [VERIFIED: excel_processor.py:25-39]
**How to avoid:** Either make file selection explicit before relying on regeneration, or keep Phase 2 selector read-only against already-produced fused parquet. [VERIFIED: excel_processor.py; ASSUMED]
**Warning signs:** Multiple `股票健診*.xlsm` files exist in repo root and the chosen workbook changes across environments. [VERIFIED: local file listing]

### Pitfall 4: Validation commands are not stable yet
**What goes wrong:** Planner assumes `pytest -q` is green, but the suite currently fails before selector work starts. [VERIFIED: local test runs]
**Why it happens:** `tests/test_institutional_logic.py` imports `calculate_i_factor`, which is not present in `core.logic`, and some test commands require `PYTHONPATH=.`. [VERIFIED: local test runs; core/logic.py; tests/test_institutional_logic.py]
**How to avoid:** Add targeted Phase 2 test commands now and treat full-suite repair as Wave 0 work if phase gate requires it. [VERIFIED: local test runs; ASSUMED]
**Warning signs:** `pytest -q` or `PYTHONPATH=. pytest -q` fails during collection before Phase 2 tests even run. [VERIFIED: local test runs]

## Code Examples

Verified patterns from codebase and recommended brownfield usage:

### Existing signal approval rule
```python
df_merged['is_canslim_approved'] = df_merged['score'].fillna(0) >= min_score
```
Source: `alpha_integration_module.py` active-signal threshold behavior. [VERIFIED: alpha_integration_module.py:42]

### Existing integration seam to replace
```python
priority = ["1101", "2330", "3565", "6770", "2303", "8069", "6805"]
all_t = sorted(list(self.ticker_info.keys()))
scan_list = priority + [t for t in all_t if t not in priority][:2000]
```
Source: current hard-coded priority logic in `export_canslim.py`. [VERIFIED: export_canslim.py:682-684]

### Recommended selector ordering skeleton
```python
ordered_fixed = dedupe_preserve_order(
    config.base_symbols
    + config.etf_symbols
    + config.watchlist_symbols
    + yesterday_signals
    + today_signals
)

remaining_slots = max(0, target_size - len(ordered_fixed))
ranked_fill = sorted(
    candidate_pool,
    key=lambda item: (-item.rs_metric, -item.volume_metric, item.symbol),
)
core_symbols = ordered_fixed + [item.symbol for item in ranked_fill[:remaining_slots]]
```
Source: recommended deterministic implementation for D-03/D-04. [ASSUMED]

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Static 7-symbol `priority` list plus alphabetical tail in `export_canslim.py` [VERIFIED: export_canslim.py:682-684] | Dynamic selector built from fixed buckets, fused-parquet signals, and ranked fill [ASSUMED] | Phase 2 plan target [VERIFIED: ROADMAP.md] | Removes manual list drift and makes priority updates data-driven. [VERIFIED: ROADMAP.md; ASSUMED] |
| Manual priority maintenance [VERIFIED: export_canslim.py] | Checked-in fixed-bucket config file [ASSUMED] | Phase 2 [VERIFIED: ROADMAP.md] | Lets planner separate list curation from code changes. [ASSUMED] |
| Implicit carryover via whatever remained in the old list [VERIFIED: absence of current logic in export_canslim.py] | Explicit one-day carryover from previous fused signal date [ASSUMED] | Phase 2 [VERIFIED: 02-CONTEXT.md] | Satisfies D-05 without introducing Phase 3 state. [VERIFIED: 02-CONTEXT.md; ASSUMED] |

**Deprecated/outdated:**
- Hard-coded `priority` inside `export_canslim.py` is the old mechanism to replace. [VERIFIED: export_canslim.py:682-684]

## Open Questions

1. **What exact source should drive volume ranking?**
   - What we know: `docs/data_base.json` has RS but no persisted `financials`, and current master/fused parquet artifacts do not expose absolute volume columns. [VERIFIED: local artifact inspection; historical_generator.py:153-165; fuse_excel_data.py:47-56]
   - What's unclear: whether planner should extend the existing signal artifact schema with `volume`/`volume_rank`, or accept a live yfinance prepass. [VERIFIED: export_canslim.py:394-412; ASSUMED]
   - Recommendation: prefer extending the existing master/fused parquet path so volume ranking stays file-based and deterministic. [ASSUMED]

2. **Should same-day promotion fail closed when fused parquet is stale?**
   - What we know: local fused data is one year behind raw master data. [VERIFIED: local parquet inspection]
   - What's unclear: whether the production workflow always regenerates fused parquet before `export_canslim.py`. [VERIFIED: update_data.yml does not reference fused generation]
   - Recommendation: planner should add an explicit freshness guard and either refresh fused data or stop promotion with an operator-visible error. [VERIFIED: update_data.yml; ASSUMED]

3. **What should seed the first checked-in base/ETF/watchlist config?**
   - What we know: there is no existing watchlist/base-symbol source in the repo, and the current inline list has only seven symbols. [VERIFIED: repo search; export_canslim.py:682]
   - What's unclear: which user-curated names beyond the roadmap examples must always stay in core. [VERIFIED: ROADMAP.md]
   - Recommendation: seed from the current 7-symbol list plus roadmap examples like `0050`, then let the user edit the config file. [VERIFIED: export_canslim.py; ROADMAP.md; ASSUMED]

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python | Selector code and pytest runs [VERIFIED: project stack] | ✓ [VERIFIED: local command] | 3.12.5 local / 3.11 Actions [VERIFIED: python3 --version; PROJECT.md] | — |
| pytest | Deterministic selector validation [VERIFIED: requirements.txt] | ✓ [VERIFIED: local command] | 9.0.2 [VERIFIED: pytest --version] | — |
| `master_canslim_signals_fused.parquet` | Today/yesterday signal buckets [VERIFIED: D-02] | ✓ [VERIFIED: local file check] | latest row date `2025-04-10` [VERIFIED: local parquet inspection] | Refresh via existing fuse step if stale. [VERIFIED: fuse_excel_data.py; ASSUMED] |
| `master_canslim_signals.parquet` | Upstream comparison / possible fused refresh [VERIFIED: codebase] | ✓ [VERIFIED: local file check] | latest row date `2026-04-10` [VERIFIED: local parquet inspection] | — |
| `docs/data_base.json` | Cached RS fill input [VERIFIED: local artifact inspection] | ✓ [VERIFIED: local file check] | last_updated `2026-04-17 09:58:34` [VERIFIED: local artifact inspection] | If absent, rank from parquet `L_rank` when available. [VERIFIED: historical_generator.py; ASSUMED] |
| `etf_cache.json` | ETF metadata/validation [VERIFIED: export_canslim.py] | ✓ [VERIFIED: local file check] | last_updated `2026-04-15 08:51:22` [VERIFIED: etf_cache.json] | None needed for metadata; curated ETF membership still needs config. [VERIFIED: etf_cache.json; ASSUMED] |

**Missing dependencies with no fallback:**
- None at the tool/runtime level. [VERIFIED: local environment checks]

**Missing dependencies with fallback:**
- A curated fixed-bucket config file does not exist yet; create one in-repo rather than hard-coding lists again. [VERIFIED: repo search; ASSUMED]
- The fused parquet is present but stale; refresh it before trusting same-day promotion. [VERIFIED: local parquet inspection]

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.0.2 [VERIFIED: pytest --version] |
| Config file | none detected [VERIFIED: local file listing] |
| Quick run command | `PYTHONPATH=. pytest -q tests/test_core_selection.py tests/test_primary_publish_path.py` [ASSUMED] |
| Full suite command | `PYTHONPATH=. pytest -q` [VERIFIED: local test runs] |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| ORCH-01 | Fixed buckets are always included, deduped, and preserve order. [VERIFIED: 02-CONTEXT.md] | unit | `PYTHONPATH=. pytest -q tests/test_core_selection.py -k fixed_buckets` [ASSUMED] | ❌ Wave 0 |
| ORCH-01 | Today signals and one-day carryover are derived from latest/previous fused parquet dates. [VERIFIED: alpha_integration_module.py; 02-CONTEXT.md] | unit | `PYTHONPATH=. pytest -q tests/test_core_selection.py -k signals` [ASSUMED] | ❌ Wave 0 |
| ORCH-01 | `export_canslim` uses selector output instead of inline `priority`. [VERIFIED: export_canslim.py] | integration | `PYTHONPATH=. pytest -q tests/test_primary_publish_path.py -k export_canslim` [VERIFIED: local test run pattern] | ✅ |
| ORCH-01 | Core universe caps near 300 and fills deterministically by RS/volume ordering. [VERIFIED: 02-CONTEXT.md] | unit | `PYTHONPATH=. pytest -q tests/test_core_selection.py -k ranking` [ASSUMED] | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `PYTHONPATH=. pytest -q tests/test_core_selection.py tests/test_primary_publish_path.py` [ASSUMED]
- **Per wave merge:** `PYTHONPATH=. pytest -q tests/test_canslim.py tests/test_core_selection.py tests/test_primary_publish_path.py tests/test_export_schema.py` [ASSUMED]
- **Phase gate:** `PYTHONPATH=. pytest -q` after repairing current suite collection failure. [VERIFIED: local test runs]

### Wave 0 Gaps
- [ ] `tests/test_core_selection.py` — pure selector behavior is not covered yet. [VERIFIED: tests directory listing]
- [ ] A fixture/helper for synthetic fused-parquet and baseline JSON inputs — current fixtures only cover publish bundles, not selector inputs. [VERIFIED: tests/conftest.py]
- [ ] Repair `tests/test_institutional_logic.py` or otherwise unblock full-suite collection; it imports `calculate_i_factor`, which does not exist in `core.logic`. [VERIFIED: local test runs; tests/test_institutional_logic.py; core/logic.py]
- [ ] Normalize test invocation with `PYTHONPATH=.` or add package/test configuration, because some tests import repo modules as top-level packages. [VERIFIED: local test runs]

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no [VERIFIED: phase scope in ROADMAP.md] | — |
| V3 Session Management | no [VERIFIED: phase scope in ROADMAP.md] | — |
| V4 Access Control | no [VERIFIED: phase scope in ROADMAP.md] | — |
| V5 Input Validation | yes [VERIFIED: selector will read JSON/parquet/file inputs] | Validate config schema, ticker format, required parquet columns, and latest-date freshness before selection. [VERIFIED: codebase file inputs; ASSUMED] |
| V6 Cryptography | no [VERIFIED: phase scope in ROADMAP.md] | — |

### Known Threat Patterns for this phase

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Stale or malformed parquet drives wrong priority decisions. [VERIFIED: local parquet inspection] | Tampering | Fail fast on missing columns/date freshness and log the refusal. [VERIFIED: codebase logging pattern; ASSUMED] |
| Malformed JSON config or non-digit symbols pollute the core list. [VERIFIED: config will be file-based; repo uses digit tickers] | Tampering | Validate symbol format and reject invalid entries before ranking. [VERIFIED: update_single_stock.py:194-196; ASSUMED] |
| Unbounded fixed buckets exceed API budget. [VERIFIED: D-03 target ~300; ETF cache size] | Denial of Service | Cap target size, record overflow counts, and keep curated ETF/watchlist lists small. [VERIFIED: 02-CONTEXT.md; etf_cache.json; ASSUMED] |

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | The new fixed-bucket source should be a checked-in `core_selection_config.json` file. | Standard Stack / Architecture Patterns | Planner may choose a different storage location or format. |
| A2 | Remaining slots should sort by `(-rs_metric, -volume_metric, symbol)` after fixed buckets. | Architecture Patterns / Code Examples | Different ranking math changes which names make the core cut near the boundary. |
| A3 | The best volume solution is to extend the existing master/fused parquet path with a volume metric rather than using a live prepass forever. | Summary / Open Questions | Planner may spend extra effort on artifact changes or choose a live-fetch compromise instead. |
| A4 | If fused parquet is stale, Phase 2 should refresh it or fail closed rather than silently falling back to a different signal parser. | Common Pitfalls / Open Questions | Planner may need a looser operator experience if refresh is not always available. |

## Sources

### Primary (HIGH confidence)
- `/.planning/phases/02-dynamic-core-selection/02-CONTEXT.md` — locked decisions, scope boundary, and canonical brownfield integration points. [VERIFIED: file read]
- `/.planning/REQUIREMENTS.md` and `/.planning/ROADMAP.md` — ORCH-01 definition, phase boundaries, and sequencing constraints. [VERIFIED: file reads]
- `/export_canslim.py` — current hard-coded priority list, scan-list seam, yfinance volume path, and publish integration. [VERIFIED: file read]
- `/alpha_integration_module.py` — fused-parquet loading and active-signal threshold semantics. [VERIFIED: file read]
- `/fuse_excel_data.py`, `/historical_generator.py`, `/historical_generator_v2.py` — existing signal artifact production path and current schema shape. [VERIFIED: file reads]
- `/docs/data_base.json`, `/etf_cache.json`, local parquet inspection commands — actual local artifact availability, freshness, RS coverage, and ETF counts. [VERIFIED: local inspection commands on 2026-04-18]
- `/tests/test_primary_publish_path.py`, `/tests/test_export_schema.py`, `/tests/conftest.py`, and local pytest runs — current validation seams and baseline test health. [VERIFIED: file reads; local test runs]

### Secondary (MEDIUM confidence)
- None. [VERIFIED: no external docs/source used]

### Tertiary (LOW confidence)
- None. [VERIFIED: no web-only findings used]

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new stack is needed; findings are from repo files and local environment checks. [VERIFIED: requirements.txt; local version checks]
- Architecture: MEDIUM — the integration seam is clear, but the exact volume-ranking source still needs a planning decision. [VERIFIED: export_canslim.py; local artifact inspection]
- Pitfalls: HIGH — the stale fused parquet, oversized ETF cache, and test-suite gaps were reproduced locally. [VERIFIED: local parquet inspection; etf_cache.json; local test runs]

**Research date:** 2026-04-18 [VERIFIED: system date]
**Valid until:** 2026-05-18 for codebase-specific findings, or earlier if parquet-generation scripts/workflows change. [ASSUMED]
