# GSD Debug Knowledge Base

Resolved debug sessions. Used by `gsd-debugger` to surface known-pattern hypotheses at the start of new investigations.

---

## twse-ticker-decode-bug — TWSE/TPEx ticker CSVs were mis-decoded in export_canslim
- **Date:** 2026-04-20
- **Error patterns:** 公司代號, Failed to fetch TWSE tickers, Failed to fetch TPEx tickers, ticker CSV, decode, mojibake, UTF-8 BOM, response.text
- **Root cause:** export_canslim fetches official ticker CSVs via response.text and StringIO; requests infers ISO-8859-1 for these text/csv responses, so the UTF-8 BOM payload is mis-decoded before pandas parses it, producing mojibake headers instead of 公司代號/公司簡稱
- **Fix:** switched ticker CSV parsing in export_canslim.py from StringIO(response.text) to BytesIO(response.content) with utf-8-sig, and added a regression test that simulates BOM-prefixed UTF-8 CSV bodies with mojibake response.text
- **Files changed:** export_canslim.py, tests/test_provider_policies.py
---
