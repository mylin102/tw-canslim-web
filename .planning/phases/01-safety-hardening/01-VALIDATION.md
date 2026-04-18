---
phase: 1
slug: safety-hardening
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-19
---

# Phase 1 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest + repo verification scripts |
| **Config file** | `pytest.ini` not detected — use existing pytest discovery |
| **Quick run command** | `PYTHONPATH=. pytest tests/test_logic_v2.py` |
| **Full suite command** | `PYTHONPATH=. pytest && python3 verify_local.py` |
| **Estimated runtime** | ~60-180 seconds |

---

## Sampling Rate

- **After every task commit:** Run `PYTHONPATH=. pytest tests/test_logic_v2.py`
- **After every plan wave:** Run `PYTHONPATH=. pytest && python3 verify_local.py`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 180 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 1-01-01 | 01 | 1 | SAFE-01 | T-1-01 | Shared writer prevents corrupt publish output during update writes | integration | `python3 verify_local.py` | ❌ W0 | ⬜ pending |
| 1-01-02 | 01 | 1 | SAFE-02 | T-1-02 | Active publish-path failures are logged and not silently swallowed | unit/integration | `PYTHONPATH=. pytest tests/test_logic_v2.py` | ❌ W0 | ⬜ pending |
| 1-01-03 | 02 | 2 | SAFE-03 | T-1-03 | Export contract includes versioned metadata and rejects invalid payloads before publish | unit | `PYTHONPATH=. pytest tests/test_logic_v2.py` | ❌ W0 | ⬜ pending |
| 1-01-04 | 02 | 2 | SAFE-04 | T-1-04 | Failed publish leaves last good snapshot recoverable through backup/restore path | integration | `python3 verify_local.py` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_publish_safety.py` — regression coverage for safe write + backup/restore behavior
- [ ] `tests/test_export_schema.py` — schema/version validation coverage for current JSON payload shape
- [ ] `tests/conftest.py` updates — fixtures/helpers for temporary publish files if needed

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Recovery procedure is understandable and usable by maintainer | SAFE-04 | Operator workflow quality is partly procedural | Run the documented rollback command on a staged invalid publish artifact and confirm the restored file is the expected last valid snapshot |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 180s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
