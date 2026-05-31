# Option Skew Integration Spec (tw-trading-unified)

## 1. Objective

Integrate option market-derived signals (skew, tail risk, volatility regime) into the existing trading system as a **distribution perception layer**, without breaking current architecture principles.

---

## 2. System Role

This module is **NOT a signal generator**.

It is a:

> Market Distribution Estimator

It outputs **bias / risk structure**, not trade decisions.

---

## 3. Architecture Integration

### Current System

```
[P1] Raw Tick Layer
[P2] Canonical Bar Layer
[P3] Strategy Layer
```

### New System

```
[P1] Raw Tick Layer
[P1.5] Option Surface Engine   ← NEW
[P2] Canonical Bar Layer
[P3] Strategy Layer
```

---

## 4. Data Flow

### Input

#### 4.1 Option Data

* Call / Put prices (multi-strike)
* Bid / Ask (preferred)
* IV (optional)
* Volume / OI (optional)

#### 4.2 Futures Context

* Current futures price
* Session (day/night)
* Regime (existing system)

#### 4.3 Time Series

* Previous snapshot (for delta calculation)

---

### Output

#### 4.4 Skew Signal Object

```python
skew_signal = {
    "direction": "UP" | "DOWN" | "NEUTRAL",
    "confidence": float,   # 0 ~ 1

    "skew_level": float,
    "skew_change": float,

    "downside_risk": float,
    "upside_risk": float,
    "imbalance": float,

    "vol_regime": "EXPANDING" | "COMPRESSING"
}
```

---

## 5. Module Structure

```
core/derivatives/
├── option_snapshot.py
├── skew_calculator.py
├── surface_engine.py
└── skew_signal.py
```

---

## 6. Core Engine

### 6.1 OptionSurfaceEngine

```python
class OptionSurfaceEngine:
    def __init__(self):
        self.last_snapshot = None

    def update(self, option_quotes, futures_price):
        snapshot = build_snapshot(option_quotes, futures_price)
        signal = compute_skew(snapshot, self.last_snapshot)
        self.last_snapshot = snapshot
        return signal
```

---

## 7. Integration Rules (CRITICAL)

### 7.1 NO FETCH in Strategy Layer

`_strategy_tick()` must remain a pure consumer.

---

### 7.2 Inject via Shared State

#### In monitor / ingest layer:

```python
skew_signal = option_surface_engine.update(option_data, futures_price)
shared_state["skew_signal"] = skew_signal
```

---

#### In strategy layer:

```python
def _strategy_tick(ctx):
    skew = ctx.skew_signal
```

---

## 8. Strategy Integration Patterns

### 8.1 Filter

```python
if signal == "LONG" and skew["direction"] == "DOWN":
    return None
```

---

### 8.2 Position Sizing

```python
size = base_size

if skew["direction"] == "DOWN":
    size *= 1.5
```

---

### 8.3 Regime Override

```python
if skew["vol_regime"] == "EXPANDING":
    regime = "TREND"
```

---

## 9. Core Concept Shift

### Before

```
price → signal → trade
```

### After

```
distribution → bias → price signal → trade
```

---

## 10. Design Philosophy

* Price is **result**
* Skew is **expectation**
* Strategy should align with **expectation before price reacts**

---

## 11. Future Extensions

### 11.1 Term Structure

* Compare near vs far month skew

### 11.2 Dealer Positioning (Gamma)

* Infer market maker exposure

### 11.3 Cross-Asset Divergence

* Option moves first, futures lag

---

## 12. Summary

* This module acts as **market perception layer**
* It enhances, not replaces, existing strategy
* It should be used as:

  * Filter
  * Weighting factor
  * Regime modifier

---

## 13. Implementation Priority

| Priority | Task                     |
| -------- | ------------------------ |
| High     | Basic skew calculation   |
| High     | Shared state integration |
| Medium   | Tail risk modeling       |
| Medium   | Vol regime detection     |
| Low      | Term structure           |
| Low      | Dealer gamma             |

---

## 14. Key Principle

> Do not predict price.
> Observe how the market reprices future risk.

---

