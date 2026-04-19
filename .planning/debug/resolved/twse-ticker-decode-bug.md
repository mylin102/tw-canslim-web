---
status: resolved
trigger: "Investigate issue: twse-ticker-decode-bug"
created: 2026-04-19T00:00:00Z
updated: 2026-04-20T02:22:00Z
---

## Current Focus

hypothesis: confirmed — export_canslim was mis-decoding official TWSE/TPEx CSVs through response.text; parsing raw bytes with utf-8-sig resolves the broken headers
test: archived
expecting: resolved session record with verified real-run evidence
next_action: none

## Symptoms

expected: correct data from TWSE; official TWSE/TPEx ticker CSVs should load with proper Chinese column names and populate the full ticker universe.
actual: ticker CSV in export_canslim.py is decoded incorrectly, so the TWSE/TPEx list does not load correctly.
errors: likely log lines include `Failed to fetch TWSE tickers: '公司代號'` and/or `Failed to fetch TPEx tickers: '公司代號'`. Manual investigation in main context confirmed HTTP 200 responses, content-type text/csv, requests chooses ISO-8859-1 for response.text, and the payload bytes are actually UTF-8 with BOM. Parsing via response.text produced mojibake column names; parsing response.content via BytesIO with utf-8-sig produced the correct columns including `公司代號`.
reproduction: run `python3 export_canslim.py` in the repo root. A smaller reproduction is the current `get_all_tw_tickers()` path in export_canslim.py.
started: issue has happened before; not brand new.

## Eliminated

## Evidence

- timestamp: 2026-04-20T02:17:00Z
  checked: real `PYTHONPATH=. python3 export_canslim.py` execution
  found: live workflow logs showed successful ticker-list fetches (`Fetched 1075 TWSE tickers`, `Fetched 1956 total tickers`) and no `Failed to fetch TWSE/TPEx tickers` or `公司代號` errors during the decode-sensitive step
  implication: the original decode bug does not reproduce in the real export workflow entry point

- timestamp: 2026-04-20T02:20:00Z
  checked: repository outputs/log search after the validation run
  found: `rg` found no matches for `公司代號`, `Failed to fetch TWSE tickers`, or `Failed to fetch TPEx tickers` under `debug_log.txt`, `docs`, or `.orchestration`
  implication: the validation run left no recorded evidence of the prior ticker decode failure signature

- timestamp: 2026-04-19T00:04:00Z
  checked: .planning/debug/knowledge-base.md
  found: knowledge base file does not exist
  implication: no prior known-pattern entry is available for this bug

- timestamp: 2026-04-19T00:04:30Z
  checked: export_canslim.py get_all_tw_tickers/fetch_csv
  found: fetch_csv returns pd.read_csv(StringIO(response.text), encoding="utf-8") after requests.get
  implication: parsing depends on requests' inferred response.text charset instead of the CSV bytes, matching the reported mojibake failure mode

- timestamp: 2026-04-19T00:07:30Z
  checked: live TWSE/TPEx CSV reproduction against current parsing logic
  found: both endpoints return HTTP 200 with content-type text/csv and requests encoding ISO-8859-1; parsing via StringIO(response.text) yields mojibake headers and KeyError on 公司代號, while parsing BytesIO(response.content) with utf-8-sig yields correct Chinese headers
  implication: the root failure is directly reproduced and the bytes + utf-8-sig remedy is supported by observation

- timestamp: 2026-04-19T00:09:30Z
  checked: repository search for similar response.text/StringIO CSV parsing
  found: the exact StringIO(response.text) CSV pattern appears in export_canslim.py only; other references to response.text are unrelated logging/HTML use
  implication: a surgical fix in export_canslim.py is sufficient for the reported bug surface

- timestamp: 2026-04-19T00:17:30Z
  checked: targeted pytest run without PYTHONPATH adjustment
  found: tests failed with ModuleNotFoundError for export_canslim before executing assertions
  implication: the failure is due to local test invocation/import setup rather than the ticker decoding change itself; validation should be rerun with the repository root on PYTHONPATH

- timestamp: 2026-04-19T00:17:45Z
  checked: live get_all_tw_tickers verification after patch
  found: get_all_tw_tickers loaded 2173 entries and returned valid examples for 1101, 2330, and 1240 without 公司代號 errors
  implication: the runtime path used by export_canslim now successfully decodes the official TWSE/TPEx CSVs

- timestamp: 2026-04-19T00:19:30Z
  checked: targeted pytest run with PYTHONPATH=. for export_canslim provider-policy tests
  found: the shared-policy test and the new BOM-prefixed UTF-8 ticker decode regression test both passed
  implication: the code change fixes the regression while preserving the existing provider-policy call path

- timestamp: 2026-04-19T00:21:30Z
  checked: adjacent export_canslim publish-path pytest
  found: tests/test_primary_publish_path.py::test_export_canslim_primary_bundle_contains_stock_index_json passed with PYTHONPATH=.
  implication: the ticker-loader fix did not break a nearby export_canslim publish workflow

## Resolution

root_cause: export_canslim fetches official ticker CSVs via response.text and StringIO; requests infers ISO-8859-1 for these text/csv responses, so the UTF-8 BOM payload is mis-decoded before pandas parses it, producing mojibake headers instead of 公司代號/公司簡稱
fix: switched ticker CSV parsing in export_canslim.py from StringIO(response.text) to BytesIO(response.content) with utf-8-sig, and added a regression test that simulates BOM-prefixed UTF-8 CSV bodies with mojibake response.text
verification: live get_all_tw_tickers verification loaded 2173 entries with valid TWSE/TPEx examples; targeted pytest regression for BOM-prefixed UTF-8 CSV decoding passed; adjacent export_canslim publish-path test passed; real `python3 export_canslim.py` execution fetched TWSE/TPEx ticker lists without the prior 公司代號 decode errors
files_changed: [export_canslim.py, tests/test_provider_policies.py]
