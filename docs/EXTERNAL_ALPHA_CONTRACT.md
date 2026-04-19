# 📘 External Alpha Data Contract

**Integration**: `tw-canslim-web` (Producer) ↔ `tw-trading-unified` (Consumer)  
**Status**: Formal Proposal for Confirmation  
**Version**: 1.0

---

## 1. Overview
This contract defines the data exchange format for Canslim-based alpha signals. `tw-canslim-web` acts as the **Daily Alpha Provider**, generating a list of "Leaders" that `tw-trading-unified` consumes to filter and scale stock trading positions.

---

## 2. Delivery Mechanism
- **Source Path**: `data/leaders.json` (in `tw-canslim-web` repository)
- **Access Method**: HTTP GET via GitHub Raw URL
- **Update Frequency**: Daily (Post-market or Pre-market)
- **Encoding**: UTF-8

---

## 3. Data Schema (JSON)

### 3.1 Example Payload
```json
{
  "schema_version": 1,
  "date": "2026-04-19",
  "generated_at": "2026-04-19T06:30:00+08:00",
  "universe": [
    {
      "symbol": "2330",
      "name": "台積電",
      "rs_rating": 92,
      "i_rating": 88,
      "breakout_score": 0.81,
      "volume_score": 0.73,
      "composite_score": 0.87,
      "industry_rank": 4,
      "tags": ["leader", "breakout_candidate"]
    }
  ]
}
```

### 3.2 Field Definitions

| Field | Type | Required | Description |
| :--- | :--- | :---: | :--- |
| `schema_version` | int | Yes | Current version is `1`. Increment on breaking changes. |
| `date` | str | Yes | Reference date for the data (YYYY-MM-DD). |
| `generated_at` | str | No | ISO 8601 timestamp of generation. |
| `universe` | list | Yes | List of stock objects in the high-alpha universe. |
| `symbol` | str | Yes | Taiwan stock symbol (e.g., "2330"). Suffixes like ".TW" are stripped by consumer. |
| `rs_rating` | int | Yes | Relative Strength rating (1-99). |
| `composite_score` | float | Yes | Normalized score (0.0 - 1.0) used for position scaling. |
| `tags` | list[str]| Yes | Classification. Presence of `"leader"` enables the Universe Filter. |

---

## 4. Consumer Implementation Rules (tw-trading-unified)
To ensure system stability, the following rules are applied on the consumer side:

1. **Asset Isolation**: Alpha signals **ONLY** affect `AssetType.STOCK`. Futures and Options are strictly excluded.
2. **Local Caching**: The system always loads from `cache/external_alpha/latest.json`.
3. **Fail-Safe Fetch**: Fetching from remote happens at startup or once daily. Failure to download **MUST NOT** block trading (falls back to stale cache).
4. **Symbol Normalization**: Consumer converts all incoming symbols to base strings (e.g., `"2330.TW"` -> `"2330"`) for matching.
5. **Soft Signal**:
    - If `filter_universe` is enabled: Entry is blocked if `symbol` is missing OR `tags` does not contain `"leader"`.
    - `composite_score` > 0.8: Position size multiplied by `position_multiplier_cap` (default 1.2x).
    - `composite_score` < 0.5: Position size reduced to 0.8x.

---

## 5. Evolution Policy
- **Non-breaking**: Adding new fields to stock objects or the root object.
- **Breaking**: Removing fields, changing field types, or changing the root structure.
- **Action**: Breaking changes require a `schema_version` increment and a corresponding update in `core/external_alpha_provider.py`.

---
**Approved by (tw-trading-unified)**: AI Agent  
**Date**: 2026-04-19
