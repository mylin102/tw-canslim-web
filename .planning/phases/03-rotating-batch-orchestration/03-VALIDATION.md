---
phase: 03
slug: rotating-batch-orchestration
status: draft
nyquist_compliant: true
wave_0_complete: false
created: 2026-04-19
---

# Phase 03 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | `pytest` 9.0.2 |
| **Config file** | none detected |
| **Quick run command** | `PYTHONPATH=. pytest -q tests/test_core_selection.py tests/test_primary_publish_path.py tests/test_operational_publish_path.py tests/test_publish_safety.py` |
| **Full suite command** | `PYTHONPATH=. pytest -q` |
| **Estimated runtime** | ~30 seconds |

---

## Sampling Rate

- **After every task commit:** Run `PYTHONPATH=. pytest -q tests/test_rotation_state.py tests/test_rotation_orchestrator.py`
- **After every plan wave:** Run `PYTHONPATH=. pytest -q tests/test_core_selection.py tests/test_primary_publish_path.py tests/test_operational_publish_path.py tests/test_publish_safety.py tests/test_rotation_state.py tests/test_rotation_orchestrator.py tests/test_provider_policies.py`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 03-01-01 | 01 | 1 | ORCH-02 | T-03-01 | Deterministic 3-way partitioning stays stable and generation changes are explicit | unit | `PYTHONPATH=. pytest -q tests/test_rotation_orchestrator.py -k "partition or generation"` | ❌ W0 | ⬜ pending |
| 03-01-02 | 01 | 1 | ORCH-03 | T-03-02 | State writes are atomic, schema-validated, and persist cursor/queue metadata safely | unit | `PYTHONPATH=. pytest -q tests/test_rotation_state.py -k "state or queue"` | ❌ W0 | ⬜ pending |
| 03-02-01 | 02 | 2 | ORCH-04 | T-03-03 | Resume completes only remaining symbols from the frozen batch plan | integration | `PYTHONPATH=. pytest -q tests/test_rotation_orchestrator.py -k resume tests/test_primary_publish_path.py::test_export_canslim_resume_rebuilds_incompatible_records_and_publishes_summary_bundle` | ❌ W0 | ⬜ pending |
| 03-02-02 | 02 | 2 | ORCH-05 | T-03-04 | Provider retry/backoff policy is enforced and retry timing is persisted instead of storming providers | unit/integration | `PYTHONPATH=. pytest -q tests/test_provider_policies.py tests/test_rotation_orchestrator.py -k retry` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_rotation_state.py` — stubs for state schema, atomic save/load, cursor advancement, freshness, and retry queue persistence
- [ ] `tests/test_rotation_orchestrator.py` — stubs for deterministic groups, retry-first scheduling, generation churn, and resume behavior
- [ ] `tests/test_provider_policies.py` — stubs for provider-specific retry/backoff counters and due-time handling
- [ ] `tests/conftest.py` — shared fixtures for durable state temp paths and synthetic selector outputs

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Daily pipeline remains under real provider quotas with the chosen default batch size | ORCH-05 | Real provider behavior and quota enforcement cannot be proven fully in unit tests | Run the scheduled workflow or equivalent dry run, inspect retry/backoff counters and elapsed runtime, confirm the run stays within the target operating window |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
