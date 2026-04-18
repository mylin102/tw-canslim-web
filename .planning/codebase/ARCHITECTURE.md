# Architecture

**Analysis Date:** 2025-04-19

## Pattern Overview

**Overall:** Modular multi-stage data pipeline with specialized processors feeding into a CANSLIM scoring engine, exposed via a dashboard interface.

**Key Characteristics:**
- **Layered processing**: Data ingestion → Calculation → Scoring → Visualization
- **Multi-source fusion**: FinMind API, TEJ API, yfinance, and Excel data streams converge
- **Separated concerns**: Processors for each data source, core logic isolated in `/core/`
- **Workflow orchestration**: Incremental update workflows chain multiple stages
- **Export-driven UI**: Generates JSON once, serves statically via GitHub Pages

## Layers

**Data Acquisition Layer:**
- Purpose: Fetch data from multiple external sources
- Location: `finmind_processor.py`, `tej_processor.py`, `excel_processor.py`, `institutional_analyzer.py`
- Contains: API clients, data fetchers, transformations
- Depends on: External APIs (FinMind, TEJ, yfinance), local Excel files
- Used by: CanslimEngine, HistoricalGeneratorV2

**Core Calculation Layer:**
- Purpose: Pure CANSLIM factor calculations and financial metrics
- Location: `core/logic.py`, `core/data_adapter.py`
- Contains: Factor checkers (C, A, N, S, L, I, M), Mansfield RS, volatility grids, scoring functions
- Depends on: pandas, numpy (no external APIs)
- Used by: export_canslim.py, backtest.py, HistoricalGeneratorV2

**CANSLIM Engine Layer:**
- Purpose: Orchestrate data ingestion + scoring for all stocks
- Location: `export_canslim.py` (CanslimEngine class)
- Contains: Ticker management, Excel integration, scoring orchestration, JSON export
- Depends on: All data processors + core logic
- Used by: Main export workflow, backtest

**Order Management Layer:**
- Purpose: Trade lifecycle management (stub for future trading)
- Location: `core/order_management/`
- Contains: Order, OrderFill, OrderManager, OrderStatus enums
- Depends on: datetime, uuid (no external APIs)
- Used by: Not currently integrated into main flow

**Data Export & Analysis Layer:**
- Purpose: Transform scored data for dashboard and analytics
- Location: `export_dashboard_data.py`, `backtest.py`, `compress_data.py`, `alpha_integration_module.py`
- Contains: JSON export, backtest reporting, compression utilities, signal filtering
- Depends on: Core engine output, scored parquet files
- Used by: CI/CD workflows, dashboard

**Presentation Layer:**
- Purpose: Serve pre-computed data via web interface
- Location: `docs/index.html`, `docs/app.js`, `docs/screener.js`, `serve_dashboard.py`
- Contains: Vue 3 frontend, static dashboard server
- Depends on: Exported JSON data (`docs/data.json`)
- Used by: End users (browser access)

## Data Flow

**Daily CANSLIM Update Flow:**

1. **Trigger**: CI/CD (GitHub Actions) or manual `export_canslim.py`
2. **Fetch Phase**:
   - `CanslimEngine._load_excel_data()` loads health check ratings, fund holdings, industry data
   - `FinMindProcessor.fetch_institutional_investors()` fetches 3 days of law person data
   - `yfinance` retrieves price and market data via `backtest.get_market_return_6m()`
3. **Calculate Phase**:
   - For each stock, compute all 7 CANSLIM factors (C, A, N, S, L, I, M) using `core/logic.py`
   - Calculate Mansfield RS via `calculate_mansfield_rs()`, volatility grids via `calculate_volatility_grid()`
   - Apply institutional sponsorship strength via `calculate_accumulation_strength()`
4. **Score Phase**:
   - Call `compute_canslim_score()` (stocks) or `compute_canslim_score_etf()` (ETFs)
   - Generate weighted 0-100 score based on factor weights (C:20, A:20, L:20, N:10, S:10, I:10, M:10)
5. **Export Phase**:
   - `CanslimEngine.save_to_json()` writes `docs/data.json`
   - `compress_data.py` generates `docs/data.json.gz` (92% compression)
6. **Serve Phase**:
   - Dashboard loads `data.json` via Vue 3
   - User queries filter/display top stocks or search by ticker

**Backtest Flow:**

1. Load scored data from parquet: `CANSLIMBacktester(data_file)`
2. Filter stocks by score threshold: `get_top_stocks(min_score=80)`
3. Analyze institutional buying patterns: `get_stocks_with_institutional_buying()`
4. Generate report: `generate_backtest_report()` (score distribution, metric pass rates)

**State Management:**

- **Transient**: Calculated scores exist only during `export_canslim.py` run
- **Persistent**: Final output stored as `docs/data.json` (JSON) and parquet files
- **Historical**: `master_canslim_signals.parquet` and `master_canslim_signals_fused.parquet` track time-series
- **Cached**: ETF list (`etf_cache.json`), industry data cached to reduce API calls

## Key Abstractions

**CanslimEngine:**
- Purpose: Coordinates all data sources and applies CANSLIM logic to all Taiwan stocks
- Examples: `export_canslim.py` (class instantiation and orchestration)
- Pattern: Facade pattern - hides complexity of multiple processors behind single interface
- Key methods: `_load_excel_data()`, `run_analysis()`, `save_to_json()`

**DataProcessor:**
- Purpose: Generic interface for fetching and transforming data from specific sources
- Examples: `FinMindProcessor`, `TEJProcessor`, `ExcelDataProcessor`
- Pattern: Strategy pattern - each processor implements own fetch/transform logic
- Key methods: `fetch_*()`, `parse_*()`, `map_*()`

**Factor Calculator Functions:**
- Purpose: Pure functions computing individual CANSLIM factors
- Examples: `calculate_c_factor()`, `calculate_l_factor()`, `calculate_mansfield_rs()`
- Pattern: Functional composition - chain factor checks to build overall score
- Key contract: Input (Series/DataFrame) → Output (bool or float)

**OrderEntity (Unused):**
- Purpose: Represents order lifecycle for potential live trading integration
- Examples: `core/order_management/order.py`, `order_fill.py`
- Pattern: State machine - tracks status transitions (PENDING → SUBMITTED → FILLED/CANCELLED)
- Key enums: `OrderStatus`, `OrderType`, `OrderSide`

## Entry Points

**export_canslim.py (Primary CLI):**
- Location: `export_canslim.py`
- Triggers: `python3 export_canslim.py` (manual) or GitHub Actions schedule (daily 16:30)
- Responsibilities: 
  - Initialize CanslimEngine with all data sources
  - Loop over all Taiwan stocks
  - Calculate CANSLIM scores
  - Export JSON to `docs/data.json`
- Error handling: Logs warnings per stock, continues processing

**serve_dashboard.py (Dashboard Server):**
- Location: `serve_dashboard.py`
- Triggers: `python3 serve_dashboard.py`
- Responsibilities: Start HTTP server on port 8000 serving `docs/` directory
- Error handling: Checks if `docs/` exists, displays error if missing

**backtest.py (Analysis CLI):**
- Location: `backtest.py`
- Triggers: `python3 backtest.py` with data.json as input
- Responsibilities: Generate backtest statistics (score distribution, metric pass rates)
- Error handling: Validates JSON structure, skips malformed records

**GitHub Actions (CI/CD):**
- Location: `.github/workflows/` (implicit from README)
- Triggers: Daily 16:30 UTC+8
- Responsibilities: Execute export_canslim.py, compress_data.py, push to Pages

**Test Suite:**
- Location: `tests/test_canslim.py`, `tests/test_finmind.py`, etc.
- Triggers: `pytest` or CI/CD
- Responsibilities: Unit test factors, integration test data processors

## Error Handling

**Strategy:** Graceful degradation with logging

**Patterns:**

1. **Per-Stock Tolerance**: If one stock's data fetch fails, log warning and skip, continue with others
   - Location: `CanslimEngine` loop in `export_canslim.py`
   - Example: Missing EPS data → return default False for factor C

2. **API Retry Logic**: Retry failed HTTP requests up to 3 times with exponential backoff
   - Location: `FinMindProcessor._fetch_with_retry()`, `TEJProcessor`
   - Configuration: `max_retries=3` parameter

3. **Null Coalescing**: Use sentinel values when data unavailable
   - Example: `calculate_mansfield_rs(...) → 0.0` if prices None
   - Example: `score = min(score, 100)` to cap at max

4. **Type Safety**: Use `Optional[]` annotations throughout
   - Example: `fetch_eps_data(...) -> Optional[pd.DataFrame]`
   - Checked before use: `if df is not None:`

## Cross-Cutting Concerns

**Logging:**
- Framework: Python stdlib `logging`
- Pattern: Create module-level logger with format `'%(asctime)s - %(levelname)s - %(message)s'`
- Used in: Every major module for info/warning/error events
- Configuration: `basicConfig(level=logging.INFO)` in entry points

**Validation:**
- Pattern: Type hints + guard clauses (e.g., `if len(eps_series) < 5: return False`)
- Location: Factor calculation functions use minimum data length checks
- Example: `calculate_c_factor()` requires 5+ quarters; returns False if insufficient

**Data Normalization:**
- Pattern: Each processor applies own transformations (e.g., name mapping, date parsing)
- Example: `FinMindProcessor.map_investor_name()` converts English → Chinese labels
- Location: Happens in fetch/parse stage before data merged

**Timezone Handling:**
- Pattern: All dates treated as UTC-unaware (implicit UTC+8 Taiwan time)
- Location: `TEJProcessor.ApiConfig.ignoretz = True`
- Assumption: All input dates from Taiwan market APIs already UTC+8

---

*Architecture analysis: 2025-04-19*
