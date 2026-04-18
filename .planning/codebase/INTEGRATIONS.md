# External Integrations

**Analysis Date:** 2025-04-18

## APIs & External Services

**Stock Data Providers:**
- **yfinance** - Historical stock prices and market data
  - SDK/Client: yfinance (imported as `yf`)
  - No API key required
  - Used in: `export_canslim.py`, `historical_generator_v2.py`, `test_api_detailed.py`
  - Fallback provider when FinMind/TEJ unavailable

- **FinMind** - Taiwan stock institutional investor trading data
  - SDK/Client: FinMind DataLoader (`from FinMind.data import DataLoader`)
  - Auth: No explicit API key (free tier via web)
  - Used in: `finmind_processor.py`, `export_canslim.py`, multiple batch scripts
  - Critical for "I" (Institutional) factor in CANSLIM scoring
  - Location: `finmind_processor.py` (wrapper class)

- **TEJ (Taiwan Economic Journal)** - Premium financial data
  - SDK/Client: tejapi (>=0.1.31, <0.2)
  - Auth: `TEJ_API_KEY` environment variable (set in `.env`)
  - Used in: `tej_processor.py`, `export_canslim.py`
  - Optional/gracefully disabled if API key missing
  - Provides: Daily prices (TRAIL/TAPRCD, TWN/APRCD), quarterly EPS, revenue, margins

**Taiwan Stock Exchange (TWSE) APIs:**
- **TWSE Ticker List** - Stock metadata
  - Endpoint: `https://mopsfin.twse.com.tw/opendata/t187ap03_L.csv`
  - Format: CSV
  - Used in: `export_canslim.py`, line 60
  - Provides: Stock codes, names, market type

- **TPEx (Gre Tai Securities Market) Ticker List** - OTC stock metadata
  - Endpoint: `https://mopsfin.twse.com.tw/opendata/t187ap03_O.csv`
  - Format: CSV
  - Used in: `export_canslim.py`, line 71

- **TWSE Institutional Investors Data** - Three major investor categories
  - Endpoint: `https://www.twse.com.tw/rwd/zh/fund/T86`
  - Used in: `export_canslim.py`, line 33
  - Provides: Foreign investors, investment trusts, dealers (分類)

- **TPEx Institutional Investors Data**
  - Endpoint: `https://www.tpex.org.tw/web/stock/aftertrading/fund_twse/fund_twse_result.php`
  - Used in: `export_canslim.py`, line 34

- **TWSE Financial Data (MOPS)**
  - Endpoint: `https://mops.twse.com.tw/mops/web/ajax_t163sb04`
  - Used in: `export_canslim.py`, line 37
  - Provides: Quarterly financials (EPS, revenue, margins)

- **ETF List Sync**
  - Endpoint: `https://www.twse.com.tw/rwd/zh/ETF/list?response=json`
  - Used in: `sync_etf_list.py`
  - Maintains: `etf_cache.json`

**Web Scraping:**
- **BeautifulSoup4** - HTML parsing for TWSE fallback data
  - Used when API endpoints unavailable
  - Location: `export_canslim.py`, line ~900s (financial data extraction)

## Data Storage

**Databases:**
- **None** - No persistent database (SQLite, PostgreSQL, MongoDB, etc.)
- All data processed in-memory via pandas DataFrames

**File Storage:**
- **Local filesystem only**
  - Output directory: `docs/` (GitHub Pages serving directory)
  - Cache files: `etf_cache.json`, `industry_cache_minimal.json`, `industry_cache_simplified.json`
  - Historical data: `*.parquet` files (Parquet format for efficient column storage)

**Primary Output Files:**
- `data.json` - Complete CANSLIM analysis for all stocks (~1MB)
- `data.json.gz` - Compressed version for GitHub Pages (~29KB)
- `data_base.json` - Base financial data
- `data_light.json` - Lightweight version for fast loading
- `signals.json` - Trading signals from incremental updates
- `ranking.json` - RS (Relative Strength) ranking
- `stock_index.json` - Stock ticker index for search

**Caching:**
- File-based caching only (in-memory during script execution)
- JSON cache files: `etf_cache.json`, `industry_cache_*.json`
- Parquet cache: `master_canslim_signals.parquet`, `master_canslim_signals_fused.parquet`
- Cache invalidation: Manual or script-based (no TTL-based expiry)

## Authentication & Identity

**Auth Provider:**
- **None** - No user authentication system
- **TEJ API Key:** Optional environment variable `TEJ_API_KEY`
  - Source: `.env` file (checked first), then environment
  - Fallback: TEJProcessor disables gracefully if key missing
  - Location: `tej_processor.py`, lines 42-62

**API Rate Limiting:**
- Not explicitly handled in codebase; assumes API providers handle limits
- Retry logic: Basic exponential backoff for HTTP requests
  - Location: `export_canslim.py`, `_fetch_with_retry()` method (3 retries, 15-second timeout)

## Monitoring & Observability

**Error Tracking:**
- None detected (no Sentry, DataDog, or error aggregation service)

**Logs:**
- **Logging framework:** Python `logging` module
- **Configuration:** `basicConfig()` in entry scripts
- **Log level:** INFO (detailed operation logs)
- **Output:** Console/stdout (no persistent log files)
- **Example files:**
  - `export_canslim.py`: Lines 26-30 (basicConfig setup)
  - `batch_update_institutional.py`: StreamHandler configuration
  - Multiple files use `logger.info()`, `logger.warning()`, `logger.error()`

**Debug Logs:**
- `debug_log.txt` file present (manual capture)
- No structured logging or centralized aggregation

## CI/CD & Deployment

**Hosting:**
- **GitHub Pages** - Static site hosting at `https://mylin102.github.io/tw-canslim-web/`
- **Git repository:** mylin102/tw-canslim-web

**CI Pipeline:**
- **GitHub Actions** (via `.github/workflows/`)

**Workflow 1: Daily Incremental Update**
- File: `.github/workflows/update_data.yml`
- Schedule: `0 10 * * 1-5` (UTC 10:00 = Taiwan 18:00, Monday-Friday)
- Trigger: Scheduled daily post-market update
- Steps:
  1. Checkout repository
  2. Setup Python 3.11 with pip caching
  3. Install dependencies from `requirements.txt`
  4. Execute `export_canslim.py` (full CANSLIM analysis)
  5. Execute `incremental_workflow.py` (incremental calculations)
  6. Execute `create_stock_index.py` (stock ticker indexing)
  7. Validate JSON files (signals.json, ranking.json)
  8. Commit and push updates to main branch
- Output files updated: `data.json`, `data_light.json`, `signals.json`, `ranking.json`, `stock_index.json`
- Timeout: 30 minutes

**Workflow 2: On-Demand Update**
- File: `.github/workflows/on_demand_update.yml`
- Trigger: Manual via GitHub UI (`workflow_dispatch`)
- Purpose: Force immediate data refresh outside schedule

**Deployment Details:**
- All generated JSON files committed to repository
- GitHub Pages reads from `docs/` directory (marked with `.nojekyll` to disable Jekyll processing)
- No separate CI for staging/testing; updates go directly to production

## Environment Configuration

**Required env vars:**
- `TEJ_API_KEY` - (Optional) TEJ API authentication key
  - If not provided, TEJ data fetching disabled (graceful fallback)
  - Location: Checked in `.env` file or via `os.environ.get()`

**Optional env vars:**
- `GITHUB_TOKEN` - (Optional) For GitHub Actions automatic commits

**Secrets location:**
- `.env` file (present in repository, standard pattern for development)
- GitHub Actions: No explicit secret configuration detected in workflow files

## Webhooks & Callbacks

**Incoming:**
- None detected

**Outgoing:**
- **GitHub commit/push** - Results of scheduled workflows push to repository (automatic)

## Update Flow & Data Processing

**Daily Automated Pipeline:**

1. **Data Acquisition** (export_canslim.py)
   - Fetch ticker lists from TWSE/TPEx APIs
   - Fetch institutional investor data (FinMind or web scrape)
   - Fetch historical prices (yfinance or TEJ)
   - Fetch quarterly financials (TWSE MOPS or TEJ)
   - Calculate CANSLIM scores (C, A, N, S, L, I, M factors)

2. **Incremental Updates** (incremental_workflow.py)
   - Process day-over-day changes in institutional holdings
   - Update RS (Relative Strength) rankings
   - Recalculate accumulation signals

3. **Indexing** (create_stock_index.py)
   - Build search index for stock ticker lookup

4. **Compression** (compress_data.py)
   - Compress JSON to `.json.gz` for bandwidth optimization
   - 92-97% compression ratio achieved

5. **Deployment**
   - All files committed and pushed to GitHub
   - GitHub Pages auto-rebuilds from `docs/` directory

## Data Refresh Strategy

- **Full refresh:** Daily post-market (18:00 Taiwan time)
- **Frequency:** 1x daily, Monday-Friday (no weekend/holiday automation)
- **Manual refresh:** Available via GitHub Actions on-demand workflow

---

*Integration audit: 2025-04-18*
