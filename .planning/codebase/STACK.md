# Technology Stack

**Analysis Date:** 2025-04-18

## Languages

**Primary:**
- Python 3.12.5 - Data processing, analysis engine, API integration, and backend scripts

**Secondary:**
- JavaScript (ES6+) - Frontend UI, real-time interactivity
- HTML/CSS - Frontend presentation layer

## Runtime

**Environment:**
- Python 3.12.5 (production: Python 3.11 via GitHub Actions)

**Package Manager:**
- pip (Python)
- npm/CDN for JavaScript (frontend dependencies loaded via CDN)
- Lockfile: `requirements.txt` (no `requirements.lock` file)

## Frameworks

**Core:**
- pandas - Data manipulation and analysis for stock data processing
- yfinance - Historical stock price and market data retrieval
- FinMind (>=1.9.7, <2) - Taiwan stock institutional investor data

**Testing:**
- pytest - Unit and integration testing framework

**Build/Dev:**
- No build tool; scripts run directly as Python modules

**Frontend:**
- Vue 3.3.4 - Reactive UI framework (CDN: `https://cdnjs.cloudflare.com/ajax/libs/vue/3.3.4/`)
- Tailwind CSS - Utility-first CSS framework (CDN: `https://cdn.tailwindcss.com`)
- Chart.js - Data visualization (CDN: `https://cdn.jsdelivr.net/npm/chart.js`)
- Font Awesome 6.0.0 - Icon library (CDN: `https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/`)

## Key Dependencies

**Critical:**
- **pandas** - Core data processing for CANSLIM analysis
- **yfinance** - Stock price and market data via Yahoo Finance
- **requests** - HTTP client for API calls to TWSE, TPEx, and FinMind
- **FinMind** (>=1.9.7, <2) - Institutional investor trading data
- **openpyxl** - Excel file reading/writing for historical analysis data
- **beautifulsoup4** - HTML parsing for TWSE/TPEx web scraping fallback

**Infrastructure:**
- **tejapi** (>=0.1.31, <0.2) - Taiwan Economic Journal (TEJ) API client for advanced financial data (optional, gracefully handles absence)

## Configuration

**Environment:**
- `.env` file present - Contains `TEJ_API_KEY` for optional TEJ API access
- Environment variables checked: `TEJ_API_KEY` (falls back to `.env` if not set)
- No configuration schema validation detected; graceful degradation when APIs unavailable

**Build:**
- No build pipeline; Python scripts executed directly
- Output directory: `docs/` (GitHub Pages deployment directory)
- CI/CD via GitHub Actions: `.github/workflows/update_data.yml` and `.github/workflows/on_demand_update.yml`

## Platform Requirements

**Development:**
- Python 3.11+ (3.12.5 tested)
- pip with access to PyPI
- Internet connection for API calls (FinMind, TEJ, TWSE, TPEx, Yahoo Finance)
- 100MB+ disk space for parquet data files and JSON caches

**Production:**
- **Deployment target:** GitHub Pages (static site with pre-generated JSON data)
- **Scheduled execution:** GitHub Actions runners (ubuntu-latest)
- **Data storage:** Git repository for version control of generated data files
- **Execution schedule:** Daily at 18:00 Taiwan time (UTC+8) = 10:00 UTC, Monday-Friday

## Data Formats

**Input:**
- CSV - TWSE/TPEx ticker lists and financial data
- Excel (`.xlsm`) - Historical analysis and scoring data
- Parquet - Pre-cached signal data for fast retrieval

**Output:**
- JSON - Primary distribution format for web frontend
- JSON.GZ - Compressed data files (92% compression ratio for GitHub Pages optimization)
- Parquet - Internal caching and historical analysis

## Performance Characteristics

- **Data coverage:** 1,500+ Taiwan stocks and ETFs
- **Update frequency:** Daily (post-market 18:00 Taiwan time)
- **Compression:** Data files compressed from ~1MB to ~29KB (97.1% reduction)
- **No database:** All data is in-memory or file-based (no persistent database)

---

*Stack analysis: 2025-04-18*
