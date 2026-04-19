---
phase: 04
slug: publishing-freshness-awareness
status: draft
nyquist_compliant: true
wave_0_complete: false
created: 2026-04-19
---

# Phase 04 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | `pytest` 9.0.2 |
| **Config file** | none detected |
| **Quick run command** | `PYTHONPATH=. pytest -q tests/test_export_schema.py tests/test_publish_safety.py tests/test_primary_publish_path.py` |
| **Full suite command** | `PYTHONPATH=. pytest -q` |
| **Estimated runtime** | ~30 seconds |

---

## Sampling Rate

- **After every task commit:** Run `PYTHONPATH=. pytest -q tests/test_primary_publish_path.py tests/test_export_schema.py`
- **After every plan wave:** Run `PYTHONPATH=. pytest -q tests/test_primary_publish_path.py tests/test_export_schema.py tests/test_publish_safety.py tests/test_rotation_orchestrator.py`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 04-01-01 | 01 | 1 | PUB-03 | T-04-01 | Merged `data.json` preserves baseline coverage while fresher run data overrides stale values deterministically | integration | `PYTHONPATH=. pytest -q tests/test_publish_merge.py` | ❌ W0 | ⬜ pending |
| 04-01-02 | 01 | 1 | PUB-01 | T-04-02 | Per-stock freshness metadata and 3-level labels are projected from Phase 3 state instead of bundle timestamps | unit/integration | `PYTHONPATH=. pytest -q tests/test_publish_freshness.py` | ❌ W0 | ⬜ pending |
| 04-02-01 | 02 | 2 | PUB-02 | T-04-03 | `stock_index.json` exposes full-universe search metadata and marks whether detail exists in the main snapshot | unit/integration | `PYTHONPATH=. pytest -q tests/test_stock_index.py` | ❌ W0 | ⬜ pending |
| 04-02-02 | 02 | 2 | PUB-01,PUB-02 | T-04-04 | Frontend-facing search/detail flows show freshness consistently and explicitly degrade when full CANSLIM detail is unavailable | integration | `PYTHONPATH=. pytest -q tests/test_primary_publish_path.py -k \"freshness or search or index\"` | ✅ existing | ⬜ pending |
| 04-03-01 | 03 | 3 | PUB-04 | T-04-05 | `update_summary.json` reports refreshed, failed, and next-rotation information without advancing rotation state before publish success | integration | `PYTHONPATH=. pytest -q tests/test_publish_summary_phase4.py tests/test_primary_publish_path.py -k summary` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_publish_merge.py` — merged payload precedence and compatibility stubs
- [ ] `tests/test_publish_freshness.py` — freshness projection and label stubs
- [ ] `tests/test_stock_index.py` — index generation and search metadata stubs
- [ ] `tests/test_publish_summary_phase4.py` — update summary contract stubs
- [ ] `tests/conftest.py` — shared fixtures for merged payloads / stock index / freshness state if existing fixtures are insufficient

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Dashboard UX communicates stale vs fresh stocks clearly in the live GitHub Pages UI | PUB-01, PUB-02 | No frontend browser test harness exists in the repo | Run the published dashboard, search for one in-snapshot stock and one index-only stock, confirm freshness badges and fallback messaging match the chosen Phase 4 behavior |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
