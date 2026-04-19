---
phase: 03-rotating-batch-orchestration
verified: 2026-04-19T00:00:00Z
status: passed
score: 7/7 must-haves verified
---

# Phase 3: Rotating Batch Orchestration Verification Report

**Phase Goal:** Maintainer can rotate non-core stocks through deterministic batches to achieve full market coverage within 3 days.  
**Status:** passed  
**Re-verification:** No - initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|---|---|---|
| 1 | Non-core stocks rotate through three deterministic groups | ✓ VERIFIED | `rotation_orchestrator.py` partitions `sorted(all_symbols - core_set)` into exactly 3 stable groups and derives a deterministic generation fingerprint |
| 2 | Rotation state survives reruns and rejects malformed payloads loudly | ✓ VERIFIED | `orchestration_state.py` seeds and atomically saves `.orchestration/rotation_state.json`, enforces the full schema, and `tests/test_rotation_state.py` covers malformed payload rejection |
| 3 | Interrupted runs resume only the remaining symbols from the frozen scheduled batch | ✓ VERIFIED | `write_in_progress(...)` persists the batch before processing and `build_daily_plan(...)` resumes `remaining_symbols` when `in_progress` exists |
| 4 | Retry queue items run before fresh rotation work without sacrificing scheduled-batch coverage | ✓ VERIFIED | `build_daily_plan(...)` reserves scheduled capacity first and only fills leftover budget with due retries; covered in `tests/test_rotation_orchestrator.py` |
| 5 | Cursor movement happens only after publish succeeds | ✓ VERIFIED | `export_canslim.py` calls `finalize_success(...)` only after final publish, while `finalize_failure(...)` queues failures without advancing `current_batch_index` |
| 6 | Requests, FinMind, TEJ, and yfinance all use the shared provider-policy contract | ✓ VERIFIED | `provider_policies.py`, `finmind_processor.py`, `tej_processor.py`, `yfinance_provider.py`, and `export_canslim.py` all route through the shared pacing/retry helpers |
| 7 | Workflow runs can restore and persist rotation state across runners and enforce the 20-minute runtime budget | ✓ VERIFIED | `.github/workflows/update_data.yml` and `.github/workflows/on_demand_update.yml` restore/upload `rotation_state.json`, and `.orchestration/runtime_budget.json` tracks `elapsed_seconds`, retry counters, and provider wait time |

**Score:** 7/7 truths verified

### Required Artifacts

| Artifact | Status | Details |
|---|---|---|
| `.orchestration/rotation_state.json` | ✓ VERIFIED | Checked-in seed state remains schema-valid and ready for workflow persistence |
| `orchestration_state.py` | ✓ VERIFIED | Implements strict schema validation, atomic persistence, and durable retry queue helpers |
| `rotation_orchestrator.py` | ✓ VERIFIED | Implements deterministic grouping, retry-first planning, resume seams, and finalize-success-only cursor advancement |
| `provider_policies.py` | ✓ VERIFIED | Defines explicit provider pacing/backoff contracts and preserves the 1000-symbol non-core daily budget |
| `export_canslim.py` | ✓ VERIFIED | Uses rotation-aware worklists, per-symbol freshness updates, and publish-boundary finalization |
| `finmind_processor.py` | ✓ VERIFIED | Routes FinMind calls through shared provider policy enforcement |
| `tej_processor.py` | ✓ VERIFIED | Routes TEJ calls through a shared policy wrapper |
| `yfinance_provider.py` | ✓ VERIFIED | Provides shared yfinance retry/pacing wrapper for export history calls |
| `.github/workflows/update_data.yml` | ✓ VERIFIED | Restores/uploads rotation state artifacts and enforces the runtime budget gate |
| `.github/workflows/on_demand_update.yml` | ✓ VERIFIED | Restores/uploads rotation state artifacts for on-demand reruns |
| `tests/test_rotation_state.py` | ✓ VERIFIED | Covers seed/save/reload durability and malformed-state rejection |
| `tests/test_rotation_orchestrator.py` | ✓ VERIFIED | Covers deterministic groups, generation churn, retry-first scheduling, resume, and finalize semantics |
| `tests/test_provider_policies.py` | ✓ VERIFIED | Covers requests, FinMind, TEJ, and yfinance policy wiring |
| `tests/test_primary_publish_path.py` | ✓ VERIFIED | Covers rotation-aware export ordering, resume behavior, and publish-boundary cursor advancement |

### Requirements Coverage

| Requirement | Status | Evidence |
|---|---|---|
| ORCH-02 | ✓ SATISFIED | Deterministic 3-way partitioning and rotation-aware export ordering are implemented and covered by orchestrator + publish-path tests |
| ORCH-03 | ✓ SATISFIED | File-backed orchestration state, retry queue persistence, freshness durability, and workflow restore/persist paths are implemented and validated |
| ORCH-04 | ✓ SATISFIED | Resume uses frozen `in_progress` state, failures queue durably, and cursor advancement is limited to successful finalization after publish |
| ORCH-05 | ✓ SATISFIED | Shared provider policies now govern requests, FinMind, TEJ, and yfinance, and the runtime budget gate enforces `elapsed_seconds <= 1200` |

### Flags

| File | Severity | Impact |
|---|---|---|
| `test_institutional_data.py` | Warning | Existing tests still return booleans instead of using assertions, which triggers pytest warnings but does not block Phase 3 behavior |

## Verdict

Phase 3 intent is achieved. The codebase now rotates non-core Taiwan stocks through deterministic 3-day batches, preserves resume/retry state durably across runs, routes provider calls through shared pacing/backoff contracts, and persists workflow checkpoints without breaking the Phase 1 publish safety contract.
