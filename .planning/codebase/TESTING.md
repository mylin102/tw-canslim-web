# Testing Patterns

**Analysis Date:** 2025-04-16

## Test Framework

**Runner:**
- pytest [installed from requirements.txt]
- Config: `.pytest_cache/` directory exists (no pytest.ini found, uses defaults)

**Assertion Library:**
- Built-in `assert` statements (pytest style)
- unittest.TestCase assertions when using unittest (`self.assertTrue()`, `self.assertEqual()`)

**Run Commands:**
```bash
pytest tests/                          # Run all tests in tests/ directory
pytest tests/test_canslim.py           # Run specific test file
pytest -v                              # Verbose output
pytest --tb=short                      # Show short traceback
pytest tests/test_canslim.py::TestCanslimEngine::test_safe_int_with_normal_input  # Run specific test
```

## Test File Organization

**Location:**
- Primary tests in `/tests/` directory (co-located in dedicated directory)
- Root-level verification scripts also present: `test_institutional_data.py`, `test_api_detailed.py`, `verify_local.py`
- Some scripts use `.py` naming but are not formal test suites (more like verification scripts)

**Naming:**
- Formal tests: `test_*.py` pattern (e.g., `test_canslim.py`)
- Verification/validation scripts: May use different patterns

**Structure:**
```
tests/
├── test_canslim.py          # 162 lines - Engine and helper methods
├── test_finmind.py          # 230 lines - FinMind processor tests (TDD approach)
├── test_institutional_logic.py  # 73 lines - Institutional factor logic
├── test_logic_v2.py         # 78 lines - Core CANSLIM factor calculations
├── test_rs.py               # 85 lines - Relative Strength calculations
└── [test files total: 628 lines]
```

## Test Structure

**Suite Organization - Pytest Style:**
```python
class TestCanslimEngine:
    """Test suite for CANSLIM engine."""
    
    @pytest.fixture
    def engine(self):
        """Create a CanslimEngine instance."""
        return CanslimEngine()
    
    def test_safe_int_with_normal_input(self, engine):
        """Test _safe_int with normal integer input."""
        assert engine._safe_int("1000") == 1000
        assert engine._safe_int("1,234") == 1234
```

**Suite Organization - Unittest Style:**
```python
class TestInstitutionalLogic(unittest.TestCase):
    def setUp(self):
        # Create sample data
        self.sample_df = pd.DataFrame({
            'date': ['20260401', '20260402', '20260403'],
            'foreign_net': [100, 200, -50],
        })
        self.total_shares = 10000000
    
    def test_accumulation_strength_calculation(self):
        strength = calculate_accumulation_strength(self.sample_df, self.total_shares, days=5)
        self.assertAlmostEqual(strength, 0.098)
```

**Patterns:**

1. **Setup Pattern (pytest):** Use `@pytest.fixture` for shared resources
   - Example: Engine initialization fixture reused across multiple tests
   - Fixtures parametrized when testing multiple cases

2. **Setup Pattern (unittest):** Use `setUp()` method for test initialization
   - All test data created fresh for each test (isolation)
   - Teardown handled implicitly

3. **Assertion Pattern:** Direct assertions with descriptive test names
   - Test name describes what is being tested: `test_safe_int_with_normal_input`
   - One or more assertions per test based on logical grouping

## Mocking

**Framework:** `unittest.mock` (from standard library)

**Patterns:**
```python
from unittest.mock import Mock, patch

def test_fetch_institutional_investors(self, mock_institutional_data):
    """Test fetching institutional investors data."""
    with patch('finmind_processor.DataLoader') as mock_loader:
        mock_loader.return_value.taiwan_stock_institutional_investors.return_value = mock_institutional_data
        
        processor = FinMindProcessor()
        result = processor.fetch_institutional_investors(
            stock_id="2330",
            start_date="2026-04-07",
            end_date="2026-04-08"
        )
        
        assert result is not None
        assert len(result) > 0
```

**Actual Mock Usage** (from `test_finmind.py` lines 36-56):
- `patch()` context manager used to replace external dependencies
- Mock returns configured via `.return_value`
- Tested to ensure processor handles mocked API responses

**What to Mock:**
- External API calls (FinMind DataLoader, TEJ API)
- File I/O operations
- Date/time operations (if needed)

**What NOT to Mock:**
- Pure calculation functions (`calculate_c_factor()`, `calculate_a_factor()`)
- DataFrame operations (test with real DataFrames)
- Core logic in `core/logic.py` (integration tested instead)

## Fixtures and Factories

**Test Data:**

Example from `test_finmind.py` lines 15-26:
```python
@pytest.fixture
def mock_institutional_data(self):
    """Mock institutional investors data response."""
    import pandas as pd
    return pd.DataFrame({
        'date': ['2026-04-07', '2026-04-07', '2026-04-07',
                 '2026-04-08', '2026-04-08', '2026-04-08'],
        'stock_id': ['2330'] * 6,
        'buy': [0, 59000, 13401937, 0, 1252000, 34485923],
        'name': ['Foreign_Dealer_Self', 'Dealer_self', 'Foreign_Investor',
                 'Foreign_Dealer_Self', 'Dealer_self', 'Foreign_Investor'],
        'sell': [0, 95136, 7521487, 0, 158000, 16092438]
    })
```

Example from `test_institutional_logic.py` lines 12-28:
```python
def setUp(self):
    self.sample_df = pd.DataFrame({
        'date': ['20260401', '20260402', '20260403', '20260404', '20260405'],
        'foreign_net': [100, 200, -50, 300, 150],
        'trust_net': [50, 50, 50, 50, 50],
        'dealer_net': [10, -20, 30, -10, 20]
    })
    self.total_shares = 10000000
```

**Location:**
- Fixtures defined in test files directly
- No separate factory or fixture file
- Parametrized data for testing multiple scenarios

## Coverage

**Requirements:** Not enforced (no pytest.ini with minversion or coverage plugin)

**View Coverage:**
```bash
pytest --cov=core tests/                    # Generate coverage report
pytest --cov=core --cov-report=html tests/  # HTML coverage report
# No actual command executed in codebase
```

## Test Types

**Unit Tests:**
- **Scope:** Pure functions and isolated methods
- **Approach:** Test single function with various inputs
- **Example:** `test_calculate_c_factor()` in `test_logic_v2.py` tests growth calculation with 3 cases
  ```python
  def test_calculate_c_factor():
      # Case 1: Normal growth >= 25%
      eps = pd.Series([1.0, 1.1, 1.2, 1.3, 2.0])
      assert calculate_c_factor(eps) == True
      
      # Case 2: Growth < 25%
      eps = pd.Series([1.0, 1.1, 1.2, 1.3, 1.1])
      assert calculate_c_factor(eps) == False
      
      # Case 3: Turnaround (Negative to Positive)
      eps = pd.Series([-0.5, 0.1, 0.2, 0.3, 0.5])
      assert calculate_c_factor(eps) == True
  ```

**Integration Tests:**
- **Scope:** Multiple components working together
- **Approach:** Test processor classes with mocked external APIs
- **Example:** `test_fetch_institutional_investors()` combines FinMind processor with mocked DataLoader
- **Note:** TDD approach mentioned in test file: "Tests FinMind API integration BEFORE implementation"

**E2E Tests:**
- **Framework:** Not used
- **Verification Scripts:** Instead, root-level scripts serve as E2E validation:
  - `verify_local.py` - Tests full pipeline for core symbols
  - `test_institutional_data.py` - Direct API testing with real endpoints
  - `test_api_detailed.py` - Detailed API response validation
  - `verify_update.py` - Tests data update workflow

## Common Patterns

**Async Testing:**
- Not used (synchronous API calls only)
- Time delays handled with `time.sleep()` in retry logic

**Error Testing:**
```python
def test_check_c_quarterly_growth_zero_eps(self, engine):
    """Test C metric: zero or negative EPS should fail."""
    assert engine.check_c_quarterly_growth(0, 4.0) == False
    assert engine.check_c_quarterly_growth(5.0, 0) == False
    assert engine.check_c_quarterly_growth(-1.0, 4.0) == False
```

**Edge Case Testing:**
- Empty DataFrames: `if chip_df.empty or total_shares <= 0: return 0.0`
- NA/NaN values: `if pd.isna(curr) or pd.isna(last_year): return False`
- Insufficient data: `if len(eps_series) < 5: return False`

**Data Validation Tests:**
```python
def test_accumulation_strength_calculation(self):
    # Verify calculation: 5 days accumulation: 980 lots * 1000 / 10,000,000 = 0.098
    strength = calculate_accumulation_strength(self.sample_df, self.total_shares, days=5)
    self.assertAlmostEqual(strength, 0.098)
```

## Verification Scripts

These are not traditional tests but serve validation purposes:

**`test_institutional_data.py`** (root level):
- Tests FinMind API directly
- Logs complete response structure
- Validates data shape and columns
- Uses `requests` library directly for API testing

**`test_api_detailed.py`** (root level):
- Likely tests multiple API endpoints in detail
- Comprehensive response validation

**`verify_local.py`** (root level):
- Full pipeline verification for core symbols: "2330", "2317", "2454", etc.
- Rebuilds high-fidelity data for target tickers
- Tests fallback mechanisms (Excel, Fund holdings)
- Validates CANSLIM score calculation end-to-end
- Output written to documentation with timestamps

**`verify_update.py`** (root level):
- Tests data update workflow
- Ensures incremental updates preserve data integrity

## Test Organization Strategy

**Separation:**
- Formal unit/integration tests: `tests/` directory
- Verification scripts: Root level for ad-hoc validation
- This allows:
  - `pytest tests/` for CI/CD pipelines
  - Manual verification scripts for complex workflows

**Coverage Notes:**
- Core logic (`core/logic.py`): Well-tested via `test_logic_v2.py`
- Processor classes: Mocked tests in `test_finmind.py`
- Institutional factor: Covered in `test_institutional_logic.py`
- Engine methods: Covered in `test_canslim.py`
- Relative Strength: Dedicated `test_rs.py`

---

*Testing analysis: 2025-04-16*
