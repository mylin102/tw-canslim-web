---
phase: 02-dynamic-core-selection
verified: 2026-04-19T00:00:00Z
status: passed
score: 9/9 must-haves verified
---

# Phase 2: Dynamic Core Selection Verification Report

**Phase Goal:** Maintainer can automatically prioritize daily updates for stocks with active trading signals and market strength.  
**Status:** passed  
**Re-verification:** No - initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|---|---|---|
| 1 | The daily core universe includes the required source buckets | ✓ VERIFIED | `core_selection.py` assembles base, ETF, watchlist, yesterday-signal, today-signal, RS-leader, and top-volume-leader buckets in fixed order |
| 2 | Same-day promotion uses fused parquet semantics instead of a second parser | ✓ VERIFIED | `core_selection.py` derives signals from fused parquet with `score >= 75`, matching `alpha_integration_module.py` |
| 3 | RS leaders use persisted `rs_rating >= 80` on the intended 0-100 scale | ✓ VERIFIED | `core_selection.py` uses persisted `rs_rating` for explicit RS-leader membership |
| 4 | Top-volume leaders use persisted `volume_rank` | ✓ VERIFIED | `historical_generator.py` persists `latest_volume`/`volume_rank`; `fuse_excel_data.py` carries them forward; `core_selection.py` uses `volume_rank` for top-100 volume leaders |
| 5 | Overflow behavior preserves required buckets up to 500 and fails loudly above that | ✓ VERIFIED | `core_selection.py` expands beyond 300 when required buckets exceed default target and raises `ValueError` above 500 |
| 6 | `export_canslim.py` uses the selector instead of a static priority list | ✓ VERIFIED | `export_canslim.py` now calls `build_core_universe(...)` and removes the inline `priority` seam |
| 7 | No Phase 3 rotation/state or Phase 4 publish/freshness scope bleed was introduced | ✓ VERIFIED | Phase 2 changes stay limited to selector config, artifact persistence, selector logic, and export scan-order wiring |
| 8 | Regression coverage exists for selector logic and export wiring | ✓ VERIFIED | `tests/test_core_selection.py`, `tests/test_primary_publish_path.py`, and `tests/test_institutional_logic.py` validate Phase 2 behavior |
| 9 | Targeted verification commands pass | ✓ VERIFIED | `25 passed, 2 skipped` on the targeted Phase 2 suite |

**Score:** 9/9 truths verified

### Required Artifacts

| Artifact | Status | Details |
|---|---|---|
| `core_selection.py` | ✓ VERIFIED | Implements config loading, fused/master input validation, required buckets, overflow handling, and ranked fill |
| `core_selection_config.json` | ✓ VERIFIED | Stores checked-in base, ETF, watchlist, and target-size configuration |
| `historical_generator.py` | ✓ VERIFIED | Persists `latest_volume` and `volume_rank` |
| `fuse_excel_data.py` | ✓ VERIFIED | Carries volume fields into fused parquet |
| `export_canslim.py` | ✓ VERIFIED | Uses selector-driven scan ordering while preserving Phase 1 publish behavior |
| `tests/test_core_selection.py` | ✓ VERIFIED | Covers buckets, freshness checks, overflow, and artifact-driven ranking |
| `tests/test_primary_publish_path.py` | ✓ VERIFIED | Covers selector-driven export ordering and loud failure behavior |

### Requirements Coverage

| Requirement | Status | Evidence |
|---|---|---|
| ORCH-01 | ✓ SATISFIED | Selector buckets, explicit signal semantics, persisted RS/volume leaders, overflow handling, and export wiring all validated |

### Flags

| File | Severity | Impact |
|---|---|---|
| `core_selection_config.json` | Warning | `watchlist_symbols` is currently empty; the mechanism is implemented, but the curated contents still need operator review |

## Verdict

Phase 2 intent is achieved. The codebase now generates a dynamic daily core stock universe from the required buckets, uses artifact-backed signal and volume data, and wires that selector into the main export path without breaking Phase 1 publish safety.
