<!-- GSD:project-start source:PROJECT.md -->
## Project

**tw-canslim-web**

`tw-canslim-web` is a brownfield Taiwan stock analysis repo that runs a Python-based CANSLIM data pipeline and publishes precomputed dashboard data to GitHub Pages. The next upgrade is to evolve the current full-update workflow into a strategy-driven update system that keeps core trading candidates fresh every day while rotating the rest of the market under API and rate-limit constraints.

**Core Value:** Keep the most actionable Taiwan stocks reliably fresh for trading decisions without losing broad market coverage.

### Constraints

- **Tech stack**: Python pipeline + static GitHub Pages outputs — the repo already depends on file-based exports rather than a database-backed service
- **External APIs**: FinMind, TEJ, Yahoo Finance, and related sources can rate-limit or degrade — update design must reduce bursty broad refresh behavior
- **Deployment**: Scheduled execution runs through GitHub Actions — the new flow must fit existing automation and artifact publishing patterns
- **Compatibility**: Existing dashboard/search experiences should keep working or evolve in a controlled way — output changes need explicit wiring to frontend consumers
<!-- GSD:project-end -->

<!-- GSD:stack-start source:codebase/STACK.md -->
## Technology Stack

## Languages
- Python 3.12.5 - Data processing, analysis engine, API integration, and backend scripts
- JavaScript (ES6+) - Frontend UI, real-time interactivity
- HTML/CSS - Frontend presentation layer
## Runtime
- Python 3.12.5 (production: Python 3.11 via GitHub Actions)
- pip (Python)
- npm/CDN for JavaScript (frontend dependencies loaded via CDN)
- Lockfile: `requirements.txt` (no `requirements.lock` file)
## Frameworks
- pandas - Data manipulation and analysis for stock data processing
- yfinance - Historical stock price and market data retrieval
- FinMind (>=1.9.7, <2) - Taiwan stock institutional investor data
- pytest - Unit and integration testing framework
- No build tool; scripts run directly as Python modules
- Vue 3.3.4 - Reactive UI framework (CDN: `https://cdnjs.cloudflare.com/ajax/libs/vue/3.3.4/`)
- Tailwind CSS - Utility-first CSS framework (CDN: `https://cdn.tailwindcss.com`)
- Chart.js - Data visualization (CDN: `https://cdn.jsdelivr.net/npm/chart.js`)
- Font Awesome 6.0.0 - Icon library (CDN: `https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/`)
## Key Dependencies
- **pandas** - Core data processing for CANSLIM analysis
- **yfinance** - Stock price and market data via Yahoo Finance
- **requests** - HTTP client for API calls to TWSE, TPEx, and FinMind
- **FinMind** (>=1.9.7, <2) - Institutional investor trading data
- **openpyxl** - Excel file reading/writing for historical analysis data
- **beautifulsoup4** - HTML parsing for TWSE/TPEx web scraping fallback
- **tejapi** (>=0.1.31, <0.2) - Taiwan Economic Journal (TEJ) API client for advanced financial data (optional, gracefully handles absence)
## Configuration
- `.env` file present - Contains `TEJ_API_KEY` for optional TEJ API access
- Environment variables checked: `TEJ_API_KEY` (falls back to `.env` if not set)
- No configuration schema validation detected; graceful degradation when APIs unavailable
- No build pipeline; Python scripts executed directly
- Output directory: `docs/` (GitHub Pages deployment directory)
- CI/CD via GitHub Actions: `.github/workflows/update_data.yml` and `.github/workflows/on_demand_update.yml`
## Platform Requirements
- Python 3.11+ (3.12.5 tested)
- pip with access to PyPI
- Internet connection for API calls (FinMind, TEJ, TWSE, TPEx, Yahoo Finance)
- 100MB+ disk space for parquet data files and JSON caches
- **Deployment target:** GitHub Pages (static site with pre-generated JSON data)
- **Scheduled execution:** GitHub Actions runners (ubuntu-latest)
- **Data storage:** Git repository for version control of generated data files
- **Execution schedule:** Daily at 18:00 Taiwan time (UTC+8) = 10:00 UTC, Monday-Friday
## Data Formats
- CSV - TWSE/TPEx ticker lists and financial data
- Excel (`.xlsm`) - Historical analysis and scoring data
- Parquet - Pre-cached signal data for fast retrieval
- JSON - Primary distribution format for web frontend
- JSON.GZ - Compressed data files (92% compression ratio for GitHub Pages optimization)
- Parquet - Internal caching and historical analysis
## Performance Characteristics
- **Data coverage:** 1,500+ Taiwan stocks and ETFs
- **Update frequency:** Daily (post-market 18:00 Taiwan time)
- **Compression:** Data files compressed from ~1MB to ~29KB (97.1% reduction)
- **No database:** All data is in-memory or file-based (no persistent database)
<!-- GSD:stack-end -->

<!-- GSD:conventions-start source:CONVENTIONS.md -->
## Conventions

## Naming Patterns
- Snake case: `export_canslim.py`, `finmind_processor.py`, `tej_processor.py`
- Module files use verb_noun pattern: `excel_processor.py`, `institutional_analyzer.py`
- Test files use pattern: `test_*.py` (e.g., `test_canslim.py`, `test_finmind.py`)
- Verification/batch scripts use verb_noun: `verify_local.py`, `batch_strategy_analysis.py`
- Underscore separates logical sections: `quick_auto_update.py`, `export_dashboard_data.py`
- PascalCase with descriptive names
- Examples: `CanslimEngine`, `FinMindProcessor`, `ExcelDataProcessor`, `TEJProcessor`, `Order`, `OrderStatus`
- Class names reflect their primary responsibility (processor, engine, manager)
- Snake case universally
- Action verbs for functions: `calculate_c_factor()`, `fetch_institutional_data()`, `check_n_factor()`
- Boolean functions use `check_` or `calculate_` prefix: `check_i_institutional()`, `calculate_a_factor()`
- Helper methods use verb_noun: `_safe_int()`, `_load_etf_cache()`, `_fetch_with_retry()`
- Private methods prefixed with underscore: `_find_excel_files()`, `_load_excel_data()`
- Snake case throughout: `total_shares`, `current_eps`, `market_hist`, `target_tickers`
- Constants in UPPER_CASE: `C_QUARTERLY_GROWTH_THRESHOLD = 0.25`, `TAIEX_SYMBOL = "^TWII"`
- Loop variables descriptive: `for t in target_tickers:` not `for t in tickers:` or `for i, row in df.iterrows():`
- Boolean flags descriptive: `is_etf`, `available`, `initialized` rather than simple `is_a`
- Type hints used extensively: `pd.Series`, `pd.DataFrame`, `Dict[str, Dict]`, `Optional[pd.DataFrame]`
- Examples from codebase:
## Code Style
- No enforced formatter (no Black, Ruff, or autopep8 config found)
- Follows PEP 8 conventions (4-space indentation)
- Line breaks used strategically to group related operations
- Example from `core/logic.py` lines 22-30: Empty line after imports, logic grouped by operation
- No linting configuration file found
- Code follows Python conventions implicitly
- Error handling uses try/except blocks (see Exception Handling section)
- Standard library imports first (os, sys, json, logging, etc.)
- Third-party imports second (pandas, yfinance, requests, openpyxl)
- Local imports last (from export_canslim import, from core.logic import)
- Example from `export_canslim.py` lines 1-14:
## Error Handling
- Try/except blocks used extensively for API calls and file I/O
- Generic `except Exception as e:` for broad error catching
- Specific exceptions like `requests.RequestException` when possible
- Graceful degradation: Return `None` or empty dict/list on failure
- Examples from `export_canslim.py`:
- Custom retry mechanism with exponential backoff (see `_fetch_with_retry()` in `export_canslim.py`)
- Max retries parameter (default 3)
- Sleep between retries using `time.sleep()`
- Example from lines 196-211:
## Logging
- Logger initialized per module: `logger = logging.getLogger(__name__)`
- Centralized config in main modules using `logging.basicConfig()`
- Levels used: `DEBUG`, `INFO`, `WARNING`, `ERROR`
- 577 logger calls across codebase indicate heavy logging usage
- Informational: `logger.info(f"Fetching institutional data for {stock_id} ({start_date} to {end_date})")`
- Warnings: `logger.warning("FinMind package is not installed; FinMind-backed data fetches are disabled")`
- Errors: `logger.error(f"Failed to fetch TWSE tickers: {e}")`
- Format includes timestamps and levels: `'%(asctime)s - %(levelname)s - %(message)s'`
## Comments
- Algorithm explanations: "Turnaround: Negative/Zero to Positive" (in `calculate_c_factor()`)
- Non-obvious business logic: "Taiwan stock chips are in 'shares' (1 lot = 1000 shares)"
- Data structure assumptions: "Note: To avoid seasonality, compare with the same quarter of last year"
- Workarounds for anomalies: "Self-Correction: If MRIS is extremely negative but price is at short-term high, it's likely a data split anomaly"
- Triple-quoted strings for all functions and classes
- Example from `finmind_processor.py` lines 51-67:
## Function Design
- Pure functions preferred (e.g., `calculate_c_factor()` at 20 lines)
- Methods can be longer (up to 50+ lines) but remain focused on single responsibility
- Explicit parameters preferred (no *args/**kwargs abuse)
- Default parameters used for thresholds: `threshold: float = 0.25`
- Optional parameters typed with `Optional[]`: `roe: Optional[float] = None`
- Longer parameter lists formatted with one per line
- Boolean for validation functions: `calculate_c_factor()` returns `bool`
- Numeric for calculations: `calculate_accumulation_strength()` returns `float`
- DataFrame/Dict for data processing: `fetch_institutional_investors()` returns `Optional[pd.DataFrame]`
- `None` used for missing/failed operations rather than raising exceptions in API processors
## Module Design
- Classes and functions exported as needed, no explicit `__all__` used
- Functions are module-level (not forced into classes unnecessarily)
- Processor classes (FinMindProcessor, TEJProcessor, ExcelDataProcessor) are stateful and instantiated
- Pure functions in `core/logic.py` are stateless
- No barrel files (`__init__.py`) with re-exports observed
- Core module has minimal init files
- `core/order_management/__init__.py` exists but checked to be sparse
- Core algorithmic functions in `core/logic.py` (stateless, pure)
- Data processors as separate modules: `finmind_processor.py`, `tej_processor.py`, `excel_processor.py`
- Main orchestration in `export_canslim.py` (CanslimEngine class)
- Order management in `core/order_management/` (Order, OrderStatus enums)
## Data Handling Conventions
- Consistent column naming with underscores: `foreign_net`, `trust_net`, `dealer_net`
- Date columns as strings initially, converted to `pd.to_datetime()` when needed
- Indices used meaningfully: `set_index(['stock_id', 'date'])` for resampling
- Missing data handled explicitly with `dropna()`, `fillna()`, or forward fill `.ffill()`
- APIs may return `None` or empty DataFrames
- Callers check for validity: `if df is None or len(df) == 0:`
- Fallback mechanisms built in (e.g., Excel backup for TEJ data in `verify_local.py`)
- Configuration constants at module level
- Thresholds grouped: C_QUARTERLY_GROWTH_THRESHOLD, A_ANNUAL_CAGR_THRESHOLD, etc.
- Example from `export_canslim.py` lines 39-45:
<!-- GSD:conventions-end -->

<!-- GSD:architecture-start source:ARCHITECTURE.md -->
## Architecture

## Pattern Overview
- **Layered processing**: Data ingestion → Calculation → Scoring → Visualization
- **Multi-source fusion**: FinMind API, TEJ API, yfinance, and Excel data streams converge
- **Separated concerns**: Processors for each data source, core logic isolated in `/core/`
- **Workflow orchestration**: Incremental update workflows chain multiple stages
- **Export-driven UI**: Generates JSON once, serves statically via GitHub Pages
## Layers
- Purpose: Fetch data from multiple external sources
- Location: `finmind_processor.py`, `tej_processor.py`, `excel_processor.py`, `institutional_analyzer.py`
- Contains: API clients, data fetchers, transformations
- Depends on: External APIs (FinMind, TEJ, yfinance), local Excel files
- Used by: CanslimEngine, HistoricalGeneratorV2
- Purpose: Pure CANSLIM factor calculations and financial metrics
- Location: `core/logic.py`, `core/data_adapter.py`
- Contains: Factor checkers (C, A, N, S, L, I, M), Mansfield RS, volatility grids, scoring functions
- Depends on: pandas, numpy (no external APIs)
- Used by: export_canslim.py, backtest.py, HistoricalGeneratorV2
- Purpose: Orchestrate data ingestion + scoring for all stocks
- Location: `export_canslim.py` (CanslimEngine class)
- Contains: Ticker management, Excel integration, scoring orchestration, JSON export
- Depends on: All data processors + core logic
- Used by: Main export workflow, backtest
- Purpose: Trade lifecycle management (stub for future trading)
- Location: `core/order_management/`
- Contains: Order, OrderFill, OrderManager, OrderStatus enums
- Depends on: datetime, uuid (no external APIs)
- Used by: Not currently integrated into main flow
- Purpose: Transform scored data for dashboard and analytics
- Location: `export_dashboard_data.py`, `backtest.py`, `compress_data.py`, `alpha_integration_module.py`
- Contains: JSON export, backtest reporting, compression utilities, signal filtering
- Depends on: Core engine output, scored parquet files
- Used by: CI/CD workflows, dashboard
- Purpose: Serve pre-computed data via web interface
- Location: `docs/index.html`, `docs/app.js`, `docs/screener.js`, `serve_dashboard.py`
- Contains: Vue 3 frontend, static dashboard server
- Depends on: Exported JSON data (`docs/data.json`)
- Used by: End users (browser access)
## Data Flow
- **Transient**: Calculated scores exist only during `export_canslim.py` run
- **Persistent**: Final output stored as `docs/data.json` (JSON) and parquet files
- **Historical**: `master_canslim_signals.parquet` and `master_canslim_signals_fused.parquet` track time-series
- **Cached**: ETF list (`etf_cache.json`), industry data cached to reduce API calls
## Key Abstractions
- Purpose: Coordinates all data sources and applies CANSLIM logic to all Taiwan stocks
- Examples: `export_canslim.py` (class instantiation and orchestration)
- Pattern: Facade pattern - hides complexity of multiple processors behind single interface
- Key methods: `_load_excel_data()`, `run_analysis()`, `save_to_json()`
- Purpose: Generic interface for fetching and transforming data from specific sources
- Examples: `FinMindProcessor`, `TEJProcessor`, `ExcelDataProcessor`
- Pattern: Strategy pattern - each processor implements own fetch/transform logic
- Key methods: `fetch_*()`, `parse_*()`, `map_*()`
- Purpose: Pure functions computing individual CANSLIM factors
- Examples: `calculate_c_factor()`, `calculate_l_factor()`, `calculate_mansfield_rs()`
- Pattern: Functional composition - chain factor checks to build overall score
- Key contract: Input (Series/DataFrame) → Output (bool or float)
- Purpose: Represents order lifecycle for potential live trading integration
- Examples: `core/order_management/order.py`, `order_fill.py`
- Pattern: State machine - tracks status transitions (PENDING → SUBMITTED → FILLED/CANCELLED)
- Key enums: `OrderStatus`, `OrderType`, `OrderSide`
## Entry Points
- Location: `export_canslim.py`
- Triggers: `python3 export_canslim.py` (manual) or GitHub Actions schedule (daily 16:30)
- Responsibilities: 
- Error handling: Logs warnings per stock, continues processing
- Location: `serve_dashboard.py`
- Triggers: `python3 serve_dashboard.py`
- Responsibilities: Start HTTP server on port 8000 serving `docs/` directory
- Error handling: Checks if `docs/` exists, displays error if missing
- Location: `backtest.py`
- Triggers: `python3 backtest.py` with data.json as input
- Responsibilities: Generate backtest statistics (score distribution, metric pass rates)
- Error handling: Validates JSON structure, skips malformed records
- Location: `.github/workflows/` (implicit from README)
- Triggers: Daily 16:30 UTC+8
- Responsibilities: Execute export_canslim.py, compress_data.py, push to Pages
- Location: `tests/test_canslim.py`, `tests/test_finmind.py`, etc.
- Triggers: `pytest` or CI/CD
- Responsibilities: Unit test factors, integration test data processors
## Error Handling
## Cross-Cutting Concerns
- Framework: Python stdlib `logging`
- Pattern: Create module-level logger with format `'%(asctime)s - %(levelname)s - %(message)s'`
- Used in: Every major module for info/warning/error events
- Configuration: `basicConfig(level=logging.INFO)` in entry points
- Pattern: Type hints + guard clauses (e.g., `if len(eps_series) < 5: return False`)
- Location: Factor calculation functions use minimum data length checks
- Example: `calculate_c_factor()` requires 5+ quarters; returns False if insufficient
- Pattern: Each processor applies own transformations (e.g., name mapping, date parsing)
- Example: `FinMindProcessor.map_investor_name()` converts English → Chinese labels
- Location: Happens in fetch/parse stage before data merged
- Pattern: All dates treated as UTC-unaware (implicit UTC+8 Taiwan time)
- Location: `TEJProcessor.ApiConfig.ignoretz = True`
- Assumption: All input dates from Taiwan market APIs already UTC+8
<!-- GSD:architecture-end -->

<!-- GSD:skills-start source:skills/ -->
## Project Skills

No project skills found. Add skills to any of: `.github/skills/`, `.agents/skills/`, `.cursor/skills/`, or `.github/skills/` with a `SKILL.md` index file.
<!-- GSD:skills-end -->

<!-- GSD:workflow-start source:GSD defaults -->
## GSD Workflow Enforcement

Before using Edit, Write, or other file-changing tools, start work through a GSD command so planning artifacts and execution context stay in sync.

Use these entry points:
- `/gsd-quick` for small fixes, doc updates, and ad-hoc tasks
- `/gsd-debug` for investigation and bug fixing
- `/gsd-execute-phase` for planned phase work

Do not make direct repo edits outside a GSD workflow unless the user explicitly asks to bypass it.
<!-- GSD:workflow-end -->



<!-- GSD:profile-start -->
## Developer Profile

> Profile not yet configured. Run `/gsd-profile-user` to generate your developer profile.
> This section is managed by `generate-claude-profile` -- do not edit manually.
<!-- GSD:profile-end -->
