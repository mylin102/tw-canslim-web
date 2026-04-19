# Phase 3: Rotating Batch Orchestration - Research

**Researched:** 2026-04-19
**Domain:** File-based Python orchestration for deterministic non-core market rotation
**Confidence:** MEDIUM

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
### Rotation advancement
- **D-01:** Advance to the next non-core batch only after the current batch finishes successfully; do not advance by calendar day alone.

### Rotation grouping
- **D-02:** Split the non-core universe into 3 deterministic groups using a stable sorted-symbol partition.
- **D-03:** Recompute those 3 groups deterministically whenever core/non-core membership changes.

### Failure handling
- **D-04:** Individual stock failures do not keep a batch open forever; once the scheduled batch run completes, the batch is considered complete and rotation may advance.
- **D-05:** Stocks that fail within a completed batch must be recorded in a retry queue instead of being dropped.

### Retry scheduling
- **D-06:** On each normal run, attempt queued retries before spending the remaining budget on that day's planned rotation batch.

### Daily budget
- **D-07:** Target 1000 non-core stocks per daily run by default, and stay within provider limits through throttling/backoff rather than lowering the default batch size up front.

### the agent's Discretion
- Exact state-file schema and file location, as long as it stays file-based and durable across GitHub Actions runs.
- Exact budget split between retry-queue work and fresh rotation work once queued retries are attempted first.
- Provider-specific throttling/backoff mechanics per source, as long as the default 1000-stock target remains the operating goal.
- Internal helper/module boundaries for orchestrator state loading, checkpointing, and batch assembly.

### Deferred Ideas (OUT OF SCOPE)
- Adaptive batch sizing based on live quota measurements remains a v2 optimization; Phase 3 should start with a fixed 1000-stock target plus throttling/backoff.
- Freshness indicators, merged publish outputs, `stock_index.json` behavior, and frontend-visible update summaries remain Phase 4 scope.
- Manual-only batch advancement and dedicated retry-only runs were considered but are not part of this phase's chosen behavior.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| ORCH-02 | Maintainer can rotate non-core stocks through deterministic batches so broad market coverage completes within a three-day cycle. [VERIFIED: REQUIREMENTS.md] | Use selector-produced `core_set`, derive `non_core_sorted`, persist `rotation_generation`, and build exactly 3 deterministic groups. [VERIFIED: codebase grep][ASSUMED] |
| ORCH-03 | Maintainer can persist orchestration state across runs, including rotation position, freshness, and failed-stock tracking. [VERIFIED: REQUIREMENTS.md] | Add a durable JSON state file with atomic replace, schema versioning, retry queue, per-symbol attempt metadata, and current batch cursor/checkpoint fields. [VERIFIED: codebase grep][ASSUMED] |
| ORCH-04 | Maintainer can resume a partial update run without rebuilding the entire market snapshot. [VERIFIED: REQUIREMENTS.md] | Reuse `validate_resume_stock_entry(...)` plus an `in_progress` checkpoint so reruns only process remaining symbols in the frozen batch plan. [VERIFIED: codebase grep][ASSUMED] |
| ORCH-05 | Maintainer can run the daily pipeline under provider limits using throttling, retry, and backoff behavior appropriate to each data source. [VERIFIED: REQUIREMENTS.md] | Centralize provider policy for FinMind / TEJ / yfinance / requests-based TWSE-TPEX calls; preserve 1000/day target and emit retry/backoff counters into state/summary seams. [VERIFIED: codebase grep][ASSUMED] |
</phase_requirements>

## Project Constraints (from copilot-instructions.md)

- Stay brownfield: extend the existing Python pipeline and file artifacts; do not introduce a database-backed orchestration service. [VERIFIED: copilot-instructions.md]
- Fit existing GitHub Actions + GitHub Pages deployment boundaries. [VERIFIED: copilot-instructions.md]
- Follow repo conventions: snake_case modules/functions, module-level `logging`, and pytest-based regression coverage. [VERIFIED: copilot-instructions.md]
- Existing scripts are direct Python entry points; no heavy orchestration framework is standard here. [VERIFIED: copilot-instructions.md]
- GSD workflow is required for repo edits; research/planning must preserve that workflow shape. [VERIFIED: copilot-instructions.md]

## Summary

Phase 3 should be implemented as a thin orchestration layer around the already-verified selector and publish-safety seams, not as a new scheduler or datastore. `export_canslim.py` already consumes `build_core_universe(...)`, validates resume entries, publishes through `publish_artifact_bundle(...)`, and tracks retry/failure stats; the missing capability is durable rotation state for the non-core tail, not a replacement export engine. [VERIFIED: codebase grep]

The current non-core behavior is still `selection.core_symbols + [t for t in all_t if t not in selection.core_set][:2000]`, so the same front slice of the non-core universe is eligible every run and no 3-day cursor exists yet. [VERIFIED: codebase grep] The existing prototype `batch_update_institutional.py` shows the right direction for a 3-way contiguous slice and retry metadata, but it is limited to one data surface and uses an `offset_day` parameter instead of success-based durable advancement. [VERIFIED: codebase grep]

**Primary recommendation:** Add one durable JSON orchestration state file plus a shared rotation helper that freezes the current batch plan, retries queued failures first within reserved capacity, and only advances the cursor after the scheduled batch publishes successfully. [VERIFIED: codebase grep][ASSUMED]

## Standard Stack

### Core
| Library / Module | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `core_selection.py` | repo module | Source of truth for `core_symbols` / `core_set` reused from Phase 2. [VERIFIED: codebase grep] | Phase 3 must subtract from this output instead of re-deriving priority logic. [VERIFIED: codebase grep] |
| `publish_safety.py` | repo module | Locked bundle publish, artifact validation, rollback, and resume-entry validation. [VERIFIED: codebase grep] | This preserves the Phase 1 publish-safety contract and already has passing concurrency/restore tests. [VERIFIED: codebase grep][VERIFIED: bash] |
| Python stdlib (`json`, `pathlib`, `dataclasses`, `os.replace`) | Python 3.11 runtime in Actions / 3.12.5 local. [VERIFIED: codebase grep][VERIFIED: bash] | Durable file state, schema-tagged checkpoints, deterministic partition metadata. [VERIFIED: codebase grep][ASSUMED] | Brownfield-aligned and avoids adding a database or orchestration framework. [VERIFIED: REQUIREMENTS.md][VERIFIED: copilot-instructions.md] |
| `pytest` | 9.0.2 local. [VERIFIED: bash] | Existing regression framework. [VERIFIED: requirements.txt][VERIFIED: bash] | Repo already uses pytest fixtures around publish safety and selector artifacts. [VERIFIED: codebase grep] |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `requests` | 2.32.5 local. [VERIFIED: bash] | Shared HTTP retry seam for TWSE/TPEx and any new requests-based provider wrapper. [VERIFIED: codebase grep] | Keep for explicit request/response handling and status-aware backoff. [VERIFIED: codebase grep] |
| `backoff` | 2.2.1, uploaded 2022-10-05. [VERIFIED: PyPI] | Optional decorator-based retry/backoff extraction. [CITED: https://github.com/litl/backoff] | Use if Phase 3 factors provider policies into a shared wrapper instead of open-coded `time.sleep(2 ** attempt)`. [VERIFIED: codebase grep][CITED: https://github.com/litl/backoff] |
| `requests-cache` | 1.3.1, uploaded 2026-03-04. [VERIFIED: PyPI] | Optional persistent cache for repeated GETs made through `requests`. [CITED: https://requests-cache.readthedocs.io/en/stable/] | Use only for idempotent GET-style provider calls; do not use it for state persistence. [CITED: https://requests-cache.readthedocs.io/en/stable/][ASSUMED] |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| JSON state file | SQLite/Postgres | Rejected because database-backed orchestration state is explicitly out of scope. [VERIFIED: REQUIREMENTS.md] |
| Shared provider policy helper | Ad hoc `sleep()` calls inside each provider path | Existing code already duplicates retry logic unevenly; shared policy is easier to verify at step boundaries. [VERIFIED: codebase grep][ASSUMED] |
| `backoff` | `ratelimit` 2.2.1 | `ratelimit` latest PyPI release is from 2018-12-17, so it looks materially staler than `backoff` and should not be the primary new control surface. [VERIFIED: PyPI] |

**Installation (only if adopting the optional helpers):**
```bash
pip install backoff requests-cache
```

**Version verification:** `backoff` 2.2.1 (2022-10-05), `requests-cache` 1.3.1 (2026-03-04), and `ratelimit` 2.2.1 (2018-12-17) were verified against PyPI during this session. [VERIFIED: PyPI]

## Architecture Patterns

### Recommended Project Structure
```text
export_canslim.py              # existing entrypoint keeps publish path
rotation_orchestrator.py       # new: batch assembly + retry-first scheduling
orchestration_state.py         # new: load/save/validate durable JSON state
publish_safety.py              # existing bundle-safe publish contract
tests/test_rotation_state.py   # new: state schema + cursor + checkpoint tests
tests/test_rotation_orchestrator.py  # new: partitioning / retries / resume tests
tests/test_provider_policies.py      # new: backoff / throttling tests
```

### Pattern 1: Generation-based deterministic rotation
**What:** Build `non_core_sorted = sorted(all_symbols - core_set)` and derive 3 stable groups from that ordered list. Persist a `rotation_generation` fingerprint so the code can tell when core/non-core membership changed. [VERIFIED: codebase grep][ASSUMED]
**When to use:** Every daily run before assembling retry + fresh work. [ASSUMED]
**Example:**
```python
# Source: pattern derived from core_selection.py + batch_update_institutional.py
non_core_sorted = sorted(symbol for symbol in all_symbols if symbol not in selection.core_set)
groups = [
    non_core_sorted[0::3],
    non_core_sorted[1::3],
    non_core_sorted[2::3],
]
rotation_generation = hash(tuple(non_core_sorted))
```
This exact round-robin partition shape is a recommendation, not an already-implemented repo contract. [ASSUMED]

### Pattern 2: Freeze the batch plan for resume
**What:** Before processing provider calls, persist an `in_progress` checkpoint containing the selected group id, generation id, ordered symbols, completed symbols, and remaining symbols. [ASSUMED]
**When to use:** At the boundary between “batch chosen” and “first provider call.” [ASSUMED]
**Why:** If the run crashes after partially updating `docs/data.json`, the next run can reload state, intersect with current eligibility, and finish the same batch instead of recomputing a different one. [VERIFIED: codebase grep][ASSUMED]

### Pattern 3: Retry-queue-first with reserved fresh capacity
**What:** Attempt due retry items first, but reserve enough capacity for the scheduled rotation group so ORCH-02 still completes a 3-day cycle. [VERIFIED: REQUIREMENTS.md][ASSUMED]
**When to use:** Daily normal runs. [VERIFIED: 03-CONTEXT.md]
**Recommended rule:** `rotation_capacity = len(current_group_remaining)` and `retry_capacity = max(0, daily_budget - rotation_capacity)`; execute retries first from `retry_capacity`, then spend the reserved capacity on the frozen current group. [ASSUMED]

### Pattern 4: Publish first, then finalize cursor
**What:** Keep the batch checkpoint open during processing; after final `publish_artifact_bundle(...)` succeeds, atomically rewrite state to mark the batch complete, enqueue failures, clear `in_progress`, and advance `current_batch_index`. [VERIFIED: codebase grep][ASSUMED]
**When to use:** At the boundary between “all planned symbols processed” and “run complete.” [ASSUMED]

### Anti-Patterns to Avoid
- **Calendar-driven cursor advancement:** The user explicitly rejected date-only movement. [VERIFIED: 03-CONTEXT.md]
- **Reusing the current `[:2000]` non-core tail:** That tail has no durable cursor and does not satisfy ORCH-02/03. [VERIFIED: codebase grep]
- **Logging failures without durable retry state:** `failed_tickers` in `update_summary.json` are useful, but Phase 3 needs a persisted retry queue that survives the next checkout. [VERIFIED: codebase grep][ASSUMED]
- **Advancing cursor before publish succeeds:** If publish fails after cursor movement, coverage gaps become invisible. [VERIFIED: codebase grep][ASSUMED]

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Multi-file publish safety | A custom sequence of raw `open()` / `write()` calls for docs artifacts | `publish_artifact_bundle(...)` + `restore_latest_bundle(...)` [VERIFIED: codebase grep] | Existing helper already locks with `fcntl`, writes staged temps, and keeps one latest manifest-backed snapshot. [VERIFIED: codebase grep] |
| Resume validation | `if symbol in existing_data: skip` | `validate_resume_stock_entry(...)` [VERIFIED: codebase grep] | Existing helper rejects incompatible schema/missing fields before resume skips work. [VERIFIED: codebase grep] |
| Rotation state persistence | External DB / queue service | One schema-versioned JSON state file with atomic replace. [VERIFIED: REQUIREMENTS.md][ASSUMED] | File-based durability is a locked constraint. [VERIFIED: REQUIREMENTS.md] |
| Provider throttling | Copy-pasted retry loops per provider | One provider policy table + shared wrapper. [VERIFIED: codebase grep][ASSUMED] | Current code retries `requests` paths but not FinMind/TEJ/yfinance consistently. [VERIFIED: codebase grep] |
| Scheduler | Airflow/Celery/cron-in-repo | Existing GitHub Actions workflows. [VERIFIED: codebase grep][VERIFIED: REQUIREMENTS.md] | Heavy orchestration framework adoption is explicitly out of scope. [VERIFIED: REQUIREMENTS.md] |

**Key insight:** The repo already has the hard safety primitives; Phase 3 should compose them into a deterministic state machine rather than invent new infrastructure. [VERIFIED: codebase grep]

## Common Pitfalls

### Pitfall 1: Universe churn reorders an unfinished batch
**What goes wrong:** Recomputing groups mid-resume can move symbols between groups and make the open batch non-deterministic. [ASSUMED]
**Why it happens:** Core membership is dynamic upstream, and D-03 requires groups to be recomputed when membership changes. [VERIFIED: 03-CONTEXT.md]
**How to avoid:** Persist both `rotation_generation` and the frozen `in_progress.symbols`; finish the open batch against its frozen list, then recompute future groups. [ASSUMED]
**Warning signs:** The same run reports a different “next batch” after a retry-only rerun. [ASSUMED]

### Pitfall 2: Retry queue starves fresh rotation
**What goes wrong:** A large retry queue can consume the full 1000-symbol budget and stop 3-day coverage. [VERIFIED: REQUIREMENTS.md][ASSUMED]
**Why it happens:** D-06 says retries go first, but it does not say retries may monopolize the entire budget forever. [VERIFIED: 03-CONTEXT.md]
**How to avoid:** Reserve enough capacity for the scheduled group and only let retries consume the leftover capacity. [ASSUMED]
**Warning signs:** `current_batch_index` never changes even though runs continue. [ASSUMED]

### Pitfall 3: Advancing the cursor on partial success
**What goes wrong:** If cursor movement is tied to “run started today” instead of “scheduled batch completed and published,” symbols can be skipped permanently. [VERIFIED: 03-CONTEXT.md][ASSUMED]
**Why it happens:** It is tempting to store only `last_run_date`. [ASSUMED]
**How to avoid:** Store `current_batch_index`, `in_progress`, and `last_completed_generation`; move the cursor only in the final state rewrite. [ASSUMED]
**Warning signs:** Missing coverage without corresponding entries in retry queue or summary. [ASSUMED]

### Pitfall 4: Provider throttling is inconsistent today
**What goes wrong:** `_fetch_with_retry()` handles only requests-based TWSE/TPEx fetches, while FinMind, TEJ, and yfinance paths still make direct calls. [VERIFIED: codebase grep]
**Why it happens:** Provider access is spread across `export_canslim.py`, `finmind_processor.py`, and `tej_processor.py`. [VERIFIED: codebase grep]
**How to avoid:** Add a provider policy wrapper or extract provider-specific call helpers before wiring rotation. [VERIFIED: codebase grep][ASSUMED]
**Warning signs:** Retry counters increase for TWSE/TPEx but not for the provider actually failing. [VERIFIED: codebase grep][ASSUMED]

### Pitfall 5: Local test commands fail without `PYTHONPATH=.`
**What goes wrong:** Pytest collection fails with `ModuleNotFoundError` for repo modules. [VERIFIED: bash]
**Why it happens:** There is no pytest config or package install step adding the repo root automatically. [VERIFIED: codebase grep][VERIFIED: bash]
**How to avoid:** Use `PYTHONPATH=. pytest ...` in all phase-level verification commands. [VERIFIED: bash]
**Warning signs:** Collection errors for `core_selection` or `publish_safety`. [VERIFIED: bash]

## Code Examples

Verified patterns from the current repo:

### Selector-first scan ordering
```python
# Source: export_canslim.py
selection = build_core_universe(
    all_symbols=all_t,
    config_path=os.path.join(SCRIPT_DIR, "core_selection_config.json"),
    fused_path=os.path.join(SCRIPT_DIR, "master_canslim_signals_fused.parquet"),
    master_path=os.path.join(SCRIPT_DIR, "master_canslim_signals.parquet"),
    baseline_path=os.path.join(OUTPUT_DIR, "data_base.json"),
)
scan_list = selection.core_symbols + [t for t in all_t if t not in selection.core_set][:2000]
```

### Resume-safe skip validation
```python
# Source: export_canslim.py + publish_safety.py
if t in self.output_data["stocks"]:
    stock_entry = self.output_data["stocks"][t]
    validate_resume_stock_entry(t, stock_entry, schema_version=SCHEMA_VERSION)
    continue
```

### Locked bundle publish
```python
# Source: publish_safety.py
with lock_file.open("a+", encoding="utf-8") as handle:
    fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
    ...
    os.replace(staged_path, artifact["target"])
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `core + first 2000 remaining` in one scan list. [VERIFIED: codebase grep] | Deterministic 3-group rotation with durable cursor/checkpoint. [ASSUMED] | Needed now for Phase 3. [VERIFIED: ROADMAP.md] | Enables true 3-day coverage instead of a repeated front slice. [VERIFIED: codebase grep][ASSUMED] |
| Ad hoc exponential sleep only inside `_fetch_with_retry()` for requests paths. [VERIFIED: codebase grep] | Shared provider policy for FinMind / TEJ / yfinance / requests-based APIs. [ASSUMED] | Needed now for ORCH-05. [VERIFIED: REQUIREMENTS.md] | Makes throttling/backoff observable and testable per provider. [ASSUMED] |
| Prototype `offset_day % 3` slicing in `batch_update_institutional.py`. [VERIFIED: codebase grep] | Success-based cursor advancement stored in durable state. [VERIFIED: 03-CONTEXT.md][ASSUMED] | Needed now for locked decision D-01. [VERIFIED: 03-CONTEXT.md] | Removes calendar drift. [VERIFIED: 03-CONTEXT.md] |

**Deprecated/outdated:**
- `ratelimit` as the primary new throttling dependency is not recommended because its latest PyPI release is from 2018-12-17. [VERIFIED: PyPI]

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | The best durable location is a non-published repo file (for example `.orchestration/rotation_state.json`) plus a workflow `git add` update. | Architecture Patterns | If the user wants public state under `docs/`, workflow/file-path tasks will differ. |
| A2 | An unfinished batch should be resumed from a frozen symbol list even if the selector generation changes mid-run. | Architecture Patterns / Common Pitfalls | If the user prefers immediate regrouping, resume semantics and test shape change. |
| A3 | The recommended budget rule is “reserve full current-group capacity, use only leftover capacity for retries, but execute retries first.” | Architecture Patterns | If the desired split is different, task sizing and starvation tests change. |
| A4 | A shared provider policy helper is preferable to open-coded retries across FinMind/TEJ/yfinance. | Standard Stack / Don’t Hand-Roll | If the user wants zero abstraction, implementation will stay more duplicated. |

## Open Questions (RESOLVED)

1. **Where should the durable orchestration state file live?**
   - **Resolution:** Store durable orchestration state in a non-published repo path at `.orchestration/rotation_state.json`, and explicitly include that fixed file in the scheduled workflow commit step. [RESOLVED: Phase 3 planning direction]
   - **Why:** This satisfies the file-based durability requirement without exposing internal orchestration state through `docs/`, and it aligns with the existing workflow pattern of committing selected artifact paths explicitly. [VERIFIED: REQUIREMENTS.md][VERIFIED: codebase grep]

2. **What are the exact provider quotas / preferred cooldowns for FinMind, TEJ, and Yahoo paths?**
   - **Resolution:** Phase 3 should encode one shared provider-policy table with explicit default attempts/backoff values for `finmind`, `tej`, `yfinance`, and requests-based TWSE/TPEx calls, then treat those values as the conservative operational defaults until measured quota data justifies tuning. [RESOLVED: 03-CONTEXT.md D-07 + research recommendation]
   - **Why:** The roadmap requires provider-aware throttling/backoff now, but quota calibration can remain an implementation-time validation/tuning activity instead of blocking planning. [VERIFIED: REQUIREMENTS.md][VERIFIED: ROADMAP.md]

3. **Should the existing incremental-save cadence (`every 50 stocks`) remain the publish checkpoint granularity?**
   - **Resolution:** Keep the current publish cadence unchanged in Phase 3 and add orchestration-state checkpoints around batch planning/finalization instead of changing the publish frequency. [RESOLVED: brownfield scope choice]
   - **Why:** This keeps Phase 1 publish behavior stable while still enabling Phase 3 resume semantics through the new state layer. [VERIFIED: codebase grep][VERIFIED: 03-CONTEXT.md]

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python | Main scripts / tests | ✓ [VERIFIED: bash] | 3.12.5 local; workflow uses 3.11. [VERIFIED: bash][VERIFIED: codebase grep] | — |
| pytest | Validation Architecture | ✓ [VERIFIED: bash] | 9.0.2 [VERIFIED: bash] | — |
| `requests` | Existing HTTP retry paths | ✓ [VERIFIED: bash] | 2.32.5 [VERIFIED: bash] | — |
| FinMind package | FinMind-backed provider calls | ✓ but below repo spec. [VERIFIED: bash][VERIFIED: requirements.txt] | 1.9.6 installed vs `>=1.9.7,<2` required. [VERIFIED: bash][VERIFIED: requirements.txt] | GitHub Actions installs from `requirements.txt`. [VERIFIED: codebase grep] |
| `tejapi` | TEJ provider path | ✓ [VERIFIED: bash] | 0.1.31 [VERIFIED: bash] | Existing code degrades when unavailable. [VERIFIED: codebase grep] |
| `backoff` | Optional shared retry helper | ✓ [VERIFIED: bash] | 2.2.1 [VERIFIED: bash] | Keep stdlib retry loop if not adopted. [VERIFIED: codebase grep] |
| `requests-cache` | Optional GET caching helper | ✗ [VERIFIED: bash] | — | Skip caching or install explicitly. [VERIFIED: bash] |

**Missing dependencies with no fallback:**
- None for planning. [VERIFIED: bash]

**Missing dependencies with fallback:**
- `requests-cache` is absent locally, but caching is optional for this phase. [VERIFIED: bash]
- Local FinMind is older than the repo requirement; use the workflow install step or upgrade local env before running full integration checks. [VERIFIED: bash][VERIFIED: requirements.txt]

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | `pytest` 9.0.2. [VERIFIED: bash] |
| Config file | none detected. [VERIFIED: bash] |
| Quick run command | `PYTHONPATH=. pytest -q tests/test_core_selection.py tests/test_primary_publish_path.py tests/test_operational_publish_path.py tests/test_publish_safety.py` [VERIFIED: bash] |
| Full suite command | `PYTHONPATH=. pytest -q` [VERIFIED: bash][ASSUMED] |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| ORCH-02 | Deterministic 3-way partitioning and generation changes. [VERIFIED: REQUIREMENTS.md][VERIFIED: 03-CONTEXT.md] | unit | `PYTHONPATH=. pytest -q tests/test_rotation_orchestrator.py -k "partition or generation"` [ASSUMED] | ❌ Wave 0 |
| ORCH-03 | Durable state file stores cursor, queue, freshness, and failures. [VERIFIED: REQUIREMENTS.md] | unit | `PYTHONPATH=. pytest -q tests/test_rotation_state.py -k "state or queue"` [ASSUMED] | ❌ Wave 0 |
| ORCH-04 | Partial rerun resumes remaining symbols only and reuses published data safely. [VERIFIED: REQUIREMENTS.md] | integration | `PYTHONPATH=. pytest -q tests/test_rotation_orchestrator.py -k resume tests/test_primary_publish_path.py::test_export_canslim_resume_rebuilds_incompatible_records_and_publishes_summary_bundle` [VERIFIED: codebase grep][ASSUMED] | ❌ Wave 0 |
| ORCH-05 | Provider-specific throttling/backoff and retry accounting. [VERIFIED: REQUIREMENTS.md] | unit/integration | `PYTHONPATH=. pytest -q tests/test_provider_policies.py tests/test_rotation_orchestrator.py -k retry` [ASSUMED] | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `PYTHONPATH=. pytest -q tests/test_rotation_state.py tests/test_rotation_orchestrator.py -q` once those files exist. [ASSUMED]
- **Per wave merge:** `PYTHONPATH=. pytest -q tests/test_core_selection.py tests/test_primary_publish_path.py tests/test_operational_publish_path.py tests/test_publish_safety.py tests/test_rotation_state.py tests/test_rotation_orchestrator.py tests/test_provider_policies.py` [ASSUMED]
- **Phase gate:** Full suite green before `/gsd-verify-work`. [VERIFIED: copilot-instructions.md][VERIFIED: .planning/config.json]

### Wave 0 Gaps
- [ ] `tests/test_rotation_state.py` — schema version, atomic save/load, cursor advancement, retry queue persistence. [ASSUMED]
- [ ] `tests/test_rotation_orchestrator.py` — deterministic groups, retry-first scheduling, generation churn, and resume behavior. [ASSUMED]
- [ ] `tests/test_provider_policies.py` — per-provider retry/backoff counters and due-time handling. [ASSUMED]
- [ ] A helper fixture for durable state temp paths plus synthetic selector outputs. [ASSUMED]
- [ ] Step-boundary verifier seams: explicit functions for `load_state`, `build_plan`, `write_in_progress`, `process_worklist`, `finalize_success`, and `finalize_failure`. [ASSUMED]

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no [VERIFIED: codebase grep] | none — local scripts / GitHub Actions job only. [VERIFIED: codebase grep] |
| V3 Session Management | no [VERIFIED: codebase grep] | none — no user session layer in this phase. [VERIFIED: codebase grep] |
| V4 Access Control | no [VERIFIED: codebase grep] | fixed repo paths and workflow permissions already constrained in workflows. [VERIFIED: codebase grep] |
| V5 Input Validation | yes [VERIFIED: codebase grep] | `validate_resume_stock_entry(...)`, selector symbol validation, and explicit state-schema validation. [VERIFIED: codebase grep][ASSUMED] |
| V6 Cryptography | no [VERIFIED: codebase grep] | none required; do not hand-roll crypto for state files. [VERIFIED: codebase grep] |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Artifact/state corruption from concurrent writes | Tampering | Keep docs publishes on `publish_artifact_bundle(...)` and use atomic replace for the new state file. [VERIFIED: codebase grep][ASSUMED] |
| Malformed resume or state payload skips work incorrectly | Tampering | Validate schema version and required fields before skipping or advancing. [VERIFIED: codebase grep][ASSUMED] |
| Retry storm against a degraded provider | Denial of Service | Per-provider max tries, exponential backoff, and persisted next-eligible timestamps. [VERIFIED: codebase grep][ASSUMED] |
| Path misuse in workflow commit/update steps | Tampering | Use fixed known paths, not user-controlled file targets. [VERIFIED: codebase grep][ASSUMED] |

## Sources

### Primary (HIGH confidence)
- `03-CONTEXT.md` — locked decisions, scope, and discretion. [VERIFIED: 03-CONTEXT.md]
- `.planning/REQUIREMENTS.md` — ORCH-02..05 and out-of-scope database/framework constraints. [VERIFIED: REQUIREMENTS.md]
- `.planning/ROADMAP.md` — Phase 3 goal/success criteria and sequencing. [VERIFIED: ROADMAP.md]
- `export_canslim.py` — current selector wiring, resume behavior, incremental publish cadence, and existing retry scope. [VERIFIED: codebase grep]
- `publish_safety.py` — lock, staged writes, validation, and rollback behavior. [VERIFIED: codebase grep]
- `batch_update_institutional.py` and `quick_auto_update_enhanced.py` — prototype 3-way slicing and failure-summary patterns. [VERIFIED: codebase grep]
- `.github/workflows/update_data.yml` and `.github/workflows/on_demand_update.yml` — current automation surface and publish concurrency contract. [VERIFIED: codebase grep]
- `tests/test_publish_safety.py`, `tests/test_primary_publish_path.py`, `tests/test_operational_publish_path.py` — verified seams and current regression shape. [VERIFIED: codebase grep]
- Local command results: env probe and pytest run (`29 passed, 2 skipped` with `PYTHONPATH=.`). [VERIFIED: bash]

### Secondary (MEDIUM confidence)
- PyPI metadata for `backoff`, `requests-cache`, and `ratelimit` — current versions and release dates. [VERIFIED: PyPI]
- Official `backoff` README — decorator-based retry/backoff semantics. [CITED: https://github.com/litl/backoff]
- Official `requests-cache` docs/README — persistent caching scope and `CachedSession` behavior. [CITED: https://requests-cache.readthedocs.io/en/stable/]

### Tertiary (LOW confidence)
- None.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - mostly repo-native modules and directly verified package/runtime versions. [VERIFIED: codebase grep][VERIFIED: bash]
- Architecture: MEDIUM - grounded in repo seams and locked decisions, but exact state schema/budget split still requires planner choice. [VERIFIED: codebase grep][ASSUMED]
- Pitfalls: HIGH - derived from current code gaps, locked decisions, and reproduced local test behavior. [VERIFIED: codebase grep][VERIFIED: bash]

**Research date:** 2026-04-19
**Valid until:** 2026-05-19 for codebase findings; re-check PyPI package metadata sooner if you decide to add optional dependencies. [VERIFIED: PyPI][ASSUMED]
