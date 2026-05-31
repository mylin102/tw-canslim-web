# CB (Convertible Bond) Data Source Reference

## TPEX OpenAPI（最穩定）

平台: https://www.tpex.org.tw/openapi/

| Endpoint | Description |
|----------|-------------|
| `GET /bond_ISSBD6_data` | 國內轉(交)換債發行資料（發行日期、到期日、擔保情況） |
| `GET /bond_CB_daily_quotes` | 可轉債成交行情（每日成交價、量、收盤價） |

## TPEX XHR API（最即時）

Base URL: `https://www.tpex.org.tw/www/zh-tw/bond/cbDayQry`

Parameters:
- `l=zh-tw` — language
- `d=113/05/20` — date in ROC calendar (YYYY-1911/MM/DD)
- `response=json` — output format

API Pattern: `API_PATTERN = "/www/{LANG}/{ACTION}"`

Known working: `https://www.tpex.org.tw/www/zh-tw/bond/cbDayQry` returns `stat=ok` with fields but `rows=0` — query parameters need more investigation.

## Pipeline Pitfalls

1. **ROC calendar conversion**: Always convert `113/05/20` → `2024-05-20` (ISO 8601)
2. **CB code → stock mapping**: CB code = 4-digit stock code + 1-2 digits suffix (e.g. 23301 = TSMC)
3. **Conversion price adjustments**: Changes on ex-dividend dates; need periodic refresh

## Third-party Alternatives

| Provider | Quality | Cost |
|----------|---------|------|
| FinMind (`TaiwanStockConvertibleBondDaily`) | Cleaned, ISO dates | Backer/sponsor only |
| TEJ API | High accuracy | Paid |

## Recommended v1 Path

Phase 1 → TPEX OpenAPI `/bond_CB_daily_quotes` (official = stable)
Phase 2 → CB-to-stock mapping + equity_lead
Phase 3 → Conversion premium calculation
