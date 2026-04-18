---
phase: 02
slug: dynamic-core-selection
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-19
---

# Phase 02 - Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.x |
| **Config file** | none |
| **Quick run command** | `PYTHONPATH=. pytest -q tests/test_core_selection.py tests/test_primary_publish_path.py` |
| **Full suite command** | `PYTHONPATH=. pytest -q` |
| **Estimated runtime** | ~10 seconds for quick run once selector tests exist |

---

## Sampling Rate

- **After every task commit:** Run `PYTHONPATH=. pytest -q tests/test_core_selection.py tests/test_primary_publish_path.py`
- **After every plan wave:** Run `PYTHONPATH=. pytest -q tests/test_canslim.py tests/test_core_selection.py tests/test_primary_publish_path.py tests/test_export_schema.py`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 02-01-01 | 01 | 1 | ORCH-01 | T-02-01 | Fixed buckets are always included, deduped, and preserve order | unit | `PYTHONPATH=. pytest -q tests/test_core_selection.py -k fixed_buckets` | ❌ W0 | ⬜ pending |
| 02-01-02 | 01 | 1 | ORCH-01 | T-02-02 | Today signals and one-day carryover are derived from latest and previous fused-parquet dates | unit | `PYTHONPATH=. pytest -q tests/test_core_selection.py -k signals` | ❌ W0 | ⬜ pending |
| 02-01-03 | 01 | 1 | ORCH-01 | T-02-03 | Selector enforces target-size cap and deterministic RS/volume fill ordering | unit | `PYTHONPATH=. pytest -q tests/test_core_selection.py -k ranking` | ❌ W0 | ⬜ pending |
| 02-02-01 | 02 | 2 | ORCH-01 | T-02-04 | `export_canslim.py` uses selector output instead of inline priority list | integration | `PYTHONPATH=. pytest -q tests/test_primary_publish_path.py -k export_canslim` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_core_selection.py` - pure selector behavior coverage for fixed buckets, signal carryover, cap enforcement, and deterministic ranking
- [ ] synthetic fused-parquet and baseline JSON fixtures for selector inputs
- [ ] repair `tests/test_institutional_logic.py` collection failure or explicitly isolate Phase 2 targeted commands from that breakage
- [ ] normalize Phase 2 test invocation with `PYTHONPATH=.`

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Curated base, ETF, and watchlist contents remain sensible for the user's actual trading universe | ORCH-01 | The repo can validate shape and ordering, but not whether the curated list matches real operator intent | Review the checked-in config file and confirm the seed symbols are the intended starting buckets |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all missing references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
