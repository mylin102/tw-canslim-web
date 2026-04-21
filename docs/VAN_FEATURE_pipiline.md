# tw-canslim-web Feature Pipeline Spec

## 0. Purpose

Define feature computation pipeline for:
- revenue factors
- CANSLIM-like ranking
- cross-sectional stock scoring

This layer produces standardized features for downstream systems.

---

## 1. Responsibilities

tw-canslim-web is responsible for:

- Data ingestion (monthly revenue, price, volume)
- Feature engineering
- Cross-sectional ranking
- Static API / JSON output

It MUST NOT:
- contain trading logic
- contain order / execution logic
- depend on intraday data

---

## 2. Data Sources

### Required

- Monthly revenue (TWSE / MOPS)
- Daily OHLCV
- Market cap / shares

---

## 3. Feature Definitions

### 3.1 Revenue Features

```python
rev_yoy = (rev_now - rev_last_year) / rev_last_year
rev_mom = (rev_now - rev_last_month) / rev_last_month
rev_acc_1 = rev_yoy_now - rev_yoy_prev
rev_acc_2 = rev_yoy_prev - rev_yoy_prev2

# tw-canslim-web Feature Pipeline Spec

## 0. Purpose

Define feature computation pipeline for:
- revenue factors
- CANSLIM-like ranking
- cross-sectional stock scoring

This layer produces standardized features for downstream systems.

---

## 1. Responsibilities

tw-canslim-web is responsible for:

- Data ingestion (monthly revenue, price, volume)
- Feature engineering
- Cross-sectional ranking
- Static API / JSON output

It MUST NOT:
- contain trading logic
- contain order / execution logic
- depend on intraday data

---

## 2. Data Sources

### Required

- Monthly revenue (TWSE / MOPS)
- Daily OHLCV
- Market cap / shares

---

## 3. Feature Definitions

### 3.1 Revenue Features

```python
rev_yoy = (rev_now - rev_last_year) / rev_last_year
rev_mom = (rev_now - rev_last_month) / rev_last_month
rev_acc_1 = rev_yoy_now - rev_yoy_prev
rev_acc_2 = rev_yoy_prev - rev_yoy_prev2

3.2 Revenue Score
score = 0

if rev_yoy > 0.25: score += 1
if rev_yoy > 0.50: score += 1

if rev_mom > 0: score += 1
if rev_mom > 0.1: score += 1

if rev_acc_1 > 0: score += 1
if rev_acc_2 > 0: score += 1

3.3 Derived Flags
rev_accelerating = (
    rev_yoy_now > rev_yoy_prev > rev_yoy_prev2
)

rev_strong = (
    rev_yoy > 0.3 and rev_mom > 0.1
)

3.4 Optional Features
RS Rating
Breakout strength (daily timeframe)
Volume spike ratio
Institutional accumulation

4. Output Schema
stock_features.json
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

ranking.json
{
  "symbol": "3017",
  "total_score": 87,
  "revenue_score": 5,
  "rs_score": 80,
  "volume_score": 70
}

5. Pipeline Design
Batch Update
Frequency: Daily
Monthly revenue update: on release
Full recompute allowed

5. Pipeline Design
Batch Update
Frequency: Daily
Monthly revenue update: on release
Full recompute allowed

Processing Flow
Raw Data
→ Clean
→ Feature Engineering
→ Scoring
→ Ranking
→ JSON Export

6. Storage
/api/stock_features.json
/api/ranking.json

7. Versioning
Add:
"feature_version": "v1.0"

8. Constraints
Must be deterministic
Must not depend on intraday state
Must be reproducible

9. Future Extensions
ML-based scoring
sector-relative ranking
anomaly detection
