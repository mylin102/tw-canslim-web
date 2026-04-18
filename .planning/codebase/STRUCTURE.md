# Codebase Structure

**Analysis Date:** 2025-04-19

## Directory Layout

```
tw-canslim-web/
├── core/                           # Core calculation & order management
│   ├── logic.py                    # Pure CANSLIM factor functions
│   ├── data_adapter.py             # Data alignment & announcement lag
│   └── order_management/           # (Future) Order lifecycle management
│       ├── __init__.py             # Barrel export
│       ├── order.py                # Order class & enums
│       └── order_fill.py           # OrderFill class
├── tests/                          # Pytest test suite
│   ├── test_canslim.py             # CANSLIM logic unit tests
│   ├── test_finmind.py             # FinMind processor tests
│   ├── test_rs.py                  # Relative strength tests
│   ├── test_logic_v2.py            # Logic version 2 tests
│   └── test_institutional_logic.py # Institutional data tests
├── docs/                           # GitHub Pages deployment root
│   ├── index.html                  # Vue 3 dashboard (single-page app)
│   ├── app.js                      # Main Vue application
│   ├── screener.js                 # Stock filtering logic
│   ├── data.json                   # Current scoring snapshot (main data file)
│   ├── data.json.gz                # Compressed version (92% ratio)
│   └── update_summary.json         # Last update metadata
├── .github/                        # CI/CD configuration
│   └── workflows/                  # GitHub Actions automation
│       └── (implicit daily export jobs)
├── .planning/                      # GSD planning documents (orchestrator-managed)
│   └── codebase/                   # Architecture & code maps
│       ├── ARCHITECTURE.md
│       ├── STRUCTURE.md
│       ├── STACK.md
│       ├── INTEGRATIONS.md
│       ├── CONVENTIONS.md
│       ├── TESTING.md
│       └── CONCERNS.md
│
├── export_canslim.py               # PRIMARY ENTRY POINT - Main CANSLIM engine
├── serve_dashboard.py              # Dashboard HTTP server (dev only)
├── backtest.py                     # CANSLIM strategy backtest & analysis
├── compress_data.py                # JSON compression utility
├── export_dashboard_data.py        # Transform CANSLIM output for dashboard
├── alpha_integration_module.py     # Signal filtering for backtesting
├── finmind_processor.py            # FinMind API data processor
├── tej_processor.py                # TEJ API data processor
├── excel_processor.py              # Excel file data processor
├── institutional_analyzer.py       # Institutional sponsorship analysis
├── historical_generator_v2.py      # Historical data generation for backtesting
├── batch_update_institutional.py   # Batch institutional data updates
├── quick_auto_update.py            # Quick update workflow
├── quick_auto_update_enhanced.py   # Enhanced quick update
├── incremental_workflow.py         # Orchestrate update stages
├── quick_data_gen.py               # Fast data generation
├── fast_data_gen.py                # Alternative fast generation
├── update_single_stock.py          # Single-stock update utility
├── batch_strategy_analysis.py      # Multi-stock analysis
│
├── requirements.txt                # Python dependencies
├── README.md                       # Project documentation
├── RELEASE_NOTES.md                # Version history
├── REVIEW.md                       # Code review notes
└── POST_MORTEM_20260415.md         # Incident notes

(Test utilities, verification scripts, and temporary/cache files excluded from listing)
```

## Directory Purposes

**core/**
- Purpose: Isolated core logic without external dependencies
- Contains: Pure calculation functions, data adaptation logic, order lifecycle (stub)
- Key files: `logic.py` (CANSLIM factors), `data_adapter.py` (announcement lag handling), `order_management/` (unused)
- Dependency: Only pandas, numpy (no external APIs)
- Import pattern: `from core.logic import calculate_c_factor, calculate_mansfield_rs`

**tests/**
- Purpose: Pytest test suite
- Contains: Unit tests for all major components
- Key files: `test_canslim.py` (70+ cases), `test_finmind.py` (integration tests), `test_rs.py` (Mansfield RS tests)
- Dependency: pytest, test fixtures, sample data
- Run command: `pytest tests/` or `pytest tests/test_canslim.py::TestCanslimEngine`

**docs/**
- Purpose: GitHub Pages deployment directory (static web root)
- Contains: HTML/JS frontend and pre-computed data files
- Key files: `index.html` (SPA shell), `app.js` (Vue 3 logic), `data.json` (latest scores)
- Committed: ✅ Yes (part of deployment)
- Role: Consumed by browser; updated via `export_dashboard_data.py`

**.github/workflows/**
- Purpose: GitHub Actions CI/CD configuration
- Contains: Daily export jobs, data compression, deploy to Pages
- Committed: ✅ Yes (but YAML not explicitly listed in repo snapshot)
- Trigger: Scheduled daily 16:30 UTC+8, can also be manual

**.planning/codebase/**
- Purpose: Orchestrator-managed architecture documentation
- Contains: ARCHITECTURE.md, STRUCTURE.md, STACK.md, INTEGRATIONS.md, CONVENTIONS.md, TESTING.md, CONCERNS.md
- Committed: ✅ Yes (generated/updated by GSD commands)
- Created by: `/gsd-map-codebase` command

## Key File Locations

**Entry Points:**

| File | Purpose | Command | Audience |
|------|---------|---------|----------|
| `export_canslim.py` | Main CANSLIM engine | `python3 export_canslim.py` | Automation/Users |
| `backtest.py` | Strategy analysis | `python3 backtest.py` | Analysts |
| `serve_dashboard.py` | Dev dashboard server | `python3 serve_dashboard.py` | Dev/Local testing |
| `compress_data.py` | Compress JSON output | `python3 compress_data.py` | CI/CD |

**Core Logic:**

| File | Functionality | Primary Exports |
|------|--------------|-----------------|
| `core/logic.py` | CANSLIM factors, Mansfield RS, volatility | `calculate_c_factor()`, `calculate_mansfield_rs()`, `compute_canslim_score()` |
| `core/data_adapter.py` | EPS lag handling | `apply_announcement_lag()`, `resample_to_daily()` |

**Data Processors:**

| File | Source | Pattern |
|------|--------|---------|
| `finmind_processor.py` | FinMind API | Class `FinMindProcessor` with `fetch_institutional_investors()` |
| `tej_processor.py` | TEJ API | Class `TEJProcessor` with `fetch_eps()`, `fetch_financial_data()` |
| `excel_processor.py` | Local Excel files | Class `ExcelDataProcessor` with `load_health_check_data()`, `load_fund_holdings_data()` |

**Output/Export:**

| File | Output Format | Target | Updated By |
|------|---------------|--------|-----------|
| `docs/data.json` | JSON | Dashboard UI | `export_dashboard_data.py` |
| `docs/data.json.gz` | Gzip JSON | Dashboard UI (compressed) | `compress_data.py` |
| `master_canslim_signals.parquet` | Parquet | Backtesting | `export_canslim.py` |
| `master_canslim_signals_fused.parquet` | Parquet | Backtesting | `(fused after TEJ integration)` |

## Naming Conventions

**Files:**

- `export_*.py` — Data extraction and transformation (e.g., `export_canslim.py`, `export_dashboard_data.py`)
- `*_processor.py` — Data source adapters (e.g., `finmind_processor.py`, `excel_processor.py`)
- `*_analyzer.py` — Analysis utilities (e.g., `institutional_analyzer.py`)
- `*_generator.py` — Data generation/simulation (e.g., `historical_generator_v2.py`)
- `*_workflow.py` — Orchestration scripts (e.g., `incremental_workflow.py`)
- `test_*.py` — Test files (unit/integration tests)
- `quick_*.py` — Fast/lightweight variants (e.g., `quick_data_gen.py`)
- `batch_*.py` — Batch operations (e.g., `batch_update_institutional.py`)
- `*_v2.py`, `*_enhanced.py` — Newer/improved versions

**Directories:**

- `core/` — Core logic (minimal external dependencies)
- `tests/` — Test suite
- `docs/` — Static web root / deployment target
- `.github/` — GitHub configuration

**Python Conventions:**

- **Class names**: PascalCase (`CanslimEngine`, `FinMindProcessor`, `OrderStatus`)
- **Function names**: snake_case (`calculate_c_factor`, `fetch_institutional_investors`, `apply_announcement_lag`)
- **Constants**: UPPER_SNAKE_CASE (`C_QUARTERLY_GROWTH_THRESHOLD`, `TAIEX_SYMBOL`, `RS_LOOKBACK_DAYS`)
- **Module-level loggers**: `logger = logging.getLogger(__name__)` at top of file
- **Type hints**: Used throughout (e.g., `def calculate_c_factor(eps_series: pd.Series, threshold: float = 0.25) -> bool:`)

## Where to Add New Code

**New CANSLIM Factor:**
- Core function: Add to `core/logic.py` (e.g., `def calculate_x_factor(...) -> bool:`)
- Integration: Import in `export_canslim.py`, add to `CanslimEngine.run_analysis()` loop
- Weights: Update `compute_canslim_score()` weights dict
- Tests: Add test case to `tests/test_canslim.py`

**New Data Source (Processor):**
- Processor class: Create `new_source_processor.py` with `NewSourceProcessor` class
- Interface: Implement `fetch_*()` and optional `parse_*()` methods
- Integration: Instantiate in `CanslimEngine.__init__()`, call in data fetch phase
- Tests: Create `tests/test_new_source.py` with unit + integration tests

**New Analysis/Report:**
- Report function: Add to `backtest.py` as new method on `CANSLIMBacktester` class
- Or create new file: `new_analysis.py` if large (e.g., `batch_strategy_analysis.py`)
- Integration: Call from main entry point or via workflow script
- Output: Export to `docs/` or console depending on use case

**New Dashboard Feature:**
- Frontend: Add Vue component or function to `docs/app.js` (main logic) or `docs/screener.js` (filtering)
- Data dependency: If new field needed, add to `export_dashboard_data.py` before JSON generation
- Backend: If new calculation needed, add to `core/logic.py` and integrate into `CanslimEngine`
- Styling: Update CSS in `docs/index.html` or external CSS file (if exists)

**New Utility Function:**
- Shared across modules: Add to `core/logic.py` if calculation-heavy, or create `core/utils.py`
- Processor-specific: Add as method to relevant processor class
- Standalone script: Create `new_utility.py` if a CLI tool
- Tests: Add `tests/test_new_utility.py`

## Special Directories

**core/order_management/:**
- Purpose: Order lifecycle management (currently unused, stub for future trading integration)
- Committed: ✅ Yes (complete implementation)
- Generated: ❌ No
- Current state: Complete but not integrated into main CANSLIM flow
- Future: Will be consumed by trade execution layer

**docs/:**
- Purpose: GitHub Pages deployment root
- Generated: ✅ Partially (data files generated, HTML/JS hand-crafted)
- Committed: ✅ Yes (both static + generated data)
- Role: Web server root; updated by `export_dashboard_data.py` and `compress_data.py`

**tests/:**
- Purpose: Pytest test suite
- Generated: ❌ No (hand-written)
- Committed: ✅ Yes
- Run: `pytest tests/` or via CI/CD

**Cache files** (not in directory tree):
- `etf_cache.json` — ETF list cache (committed, refreshed manually)
- `industry_cache_minimal.json`, `industry_cache_simplified.json` — Industry classification caches
- `canslim_signals_2330.parquet`, `master_canslim_signals.parquet` — Cached scoring outputs (not typically committed)

---

*Structure analysis: 2025-04-19*
