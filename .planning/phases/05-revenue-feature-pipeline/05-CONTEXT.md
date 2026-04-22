# Context: Phase 05 - Revenue Feature Pipeline

## 1. Goal
Implement the feature computation pipeline defined in `docs/VAN_FEATURE_pipiline.md` to calculate revenue-based factors, score, and derived flags for stocks, exporting the results to a standardized API format.

## 2. Requirements (from docs/VAN_FEATURE_pipiline.md)

### 2.1 Revenue Features
- `rev_yoy = (rev_now - rev_last_year) / rev_last_year`
- `rev_mom = (rev_now - rev_last_month) / rev_last_month`
- `rev_acc_1 = rev_yoy_now - rev_yoy_prev`
- `rev_acc_2 = rev_yoy_prev - rev_yoy_prev2`

### 2.2 Revenue Score
- Starts at 0
- `rev_yoy > 0.25`: +1
- `rev_yoy > 0.50`: +1
- `rev_mom > 0`: +1
- `rev_mom > 0.1`: +1
- `rev_acc_1 > 0`: +1
- `rev_acc_2 > 0`: +1
- Max score: 6

### 2.3 Derived Flags
- `rev_accelerating`: `rev_yoy_now > rev_yoy_prev > rev_yoy_prev2`
- `rev_strong`: `rev_yoy > 0.3 and rev_mom > 0.1`

### 2.4 Output Schema
#### `/api/stock_features.json`
```json
{
  "symbol": "2330",
  "rev_yoy": 0.35,
  "rev_mom": 0.08,
  "rev_acc_1": 0.05,
  "rev_acc_2": 0.03,
  "revenue_score": 5,
  "rev_accelerating": true,
  "updated_at": "2026-04-21"
}
```

#### `/api/ranking.json`
```json
{
  "symbol": "3017",
  "total_score": 87,
  "revenue_score": 5,
  "rs_score": 80,
  "volume_score": 70
}
```

## 3. Decisions

### D-01: Modular Revenue Analyzer
Create a dedicated `revenue_analyzer.py` module to handle feature computation. This module will be decoupled from the data providers (TEJ, FinMind) but can consume dataframes provided by them.

### D-02: Pipeline Integration
Integrate the revenue analyzer into a new `feature_pipeline.py` that can be run as part of the `update_data_direct.py` or `quick_auto_update_enhanced.py` workflow.

### D-03: Export Location
Create a root `api/` directory for the output JSON files, as specified in the pipeline document. This is distinct from the `docs/` folder used by the frontend to allow for server-side consumption if needed.

### D-04: Full Recompute
Since the calculation is relatively fast (simple math on 15 months of data), the pipeline will perform a full recompute of features for all stocks in the core universe/active symbols each time it runs.

## 4. Discovery Summary
- `TEJProcessor` already has `get_monthly_revenue` which provides the necessary data (`r16` column).
- At least 15 months of revenue data is required to calculate `rev_acc_2` (needs `rev_yoy_prev2`).

## 5. Constraints
- Must be deterministic.
- Must handle missing data (NaN) gracefully.
- Must produce standardized JSON output.
