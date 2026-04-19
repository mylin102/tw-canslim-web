# Phase 3: Rotating Batch Orchestration - Context

**Gathered:** 2026-04-19
**Status:** Ready for planning

<domain>
## Phase Boundary

Build the non-core rotation system that updates the rest of the Taiwan market in deterministic 3-day batches. This phase owns batch partitioning, persistent orchestration state, resume behavior, retry handling, and provider-aware throttling/backoff for the daily run. Dynamic core selection remains upstream from Phase 2, and freshness-aware publish/search outputs remain in Phase 4.

</domain>

<decisions>
## Implementation Decisions

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

</decisions>

<specifics>
## Specific Ideas

- No date-based drift: rotation should move only when a batch really completed.
- Keep the grouping easy to reason about for operators by using a deterministic sorted-symbol split instead of opaque hashing.
- Retry failures early on the next run so problematic names do not age out behind fresh rotation work.
- Reuse the Phase 2 core/non-core split and keep Phase 1 publish-safety behavior intact rather than inventing a separate orchestrator stack.

</specifics>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase scope and requirements
- `.planning/ROADMAP.md` §Phase 3: Rotating Batch Orchestration — phase goal, success criteria, and dependency on Phase 2.
- `.planning/REQUIREMENTS.md` — ORCH-02, ORCH-03, ORCH-04, and ORCH-05 definitions plus out-of-scope file-based-state constraint.
- `.planning/PROJECT.md` — brownfield architecture constraints, API-limit context, and GitHub Pages/file-based deployment boundaries.
- `.planning/STATE.md` — current milestone position and Phase 3 handoff notes.

### Strategy source
- `update_strategy.md` §Layer 2 / 推薦方案（正式） — 3-group rotation intent and daily core + rotating batch model.

### Upstream phase contracts
- `.planning/phases/02-dynamic-core-selection/02-CONTEXT.md` — locked Phase 2 decisions defining the core/non-core boundary that Phase 3 must reuse.
- `.planning/phases/02-dynamic-core-selection/02-VERIFICATION.md` — verified truths about the selector and explicit note that Phase 3 owns rotation/state behavior.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `core_selection.py`: already produces the Phase 2 core set that Phase 3 can subtract from the full ticker universe to derive the non-core pool.
- `export_canslim.py`: already wires the selector into `scan_list`, has resume-safe stock-entry validation, and includes retry/failure accounting plus bundle-safe incremental publishes.
- `batch_update_institutional.py`: already demonstrates modulo-3 batch concepts, `offset_day`, `daily_limit`, failed-ticker tracking, and summary payload structure.
- `quick_auto_update_enhanced.py`: already shows the repo's operator-facing retry/failure summary pattern.
- `publish_safety.py`: remains the required contract for any published artifacts touched during orchestration.

### Established Patterns
- Brownfield preference: extend existing Python scripts and file artifacts instead of adding a database-backed orchestration service.
- Operational scripts use module-level logging, explicit helper functions, and summary artifacts to expose retry/failure outcomes.
- Phase 1 established loud failure behavior and bundle-safe publishing; Phase 3 should build on those guarantees instead of bypassing them.
- Phase 2 established that selector decisions come from checked-in config plus persisted artifacts; Phase 3 should preserve that determinism for non-core partitioning too.

### Integration Points
- `export_canslim.py` is the main place where selector output can be transformed into `core_symbols + rotation/retry work` instead of `core_symbols + first 2000 remaining`.
- Existing GitHub Actions scheduling in `.github/workflows/update_data.yml` is the automation surface Phase 3 will need to align with.
- The repo currently has no durable orchestration state store beyond committed files, so Phase 3 must introduce state in a way that survives crashes and subsequent workflow runs without requiring a database.

</code_context>

<deferred>
## Deferred Ideas

- Adaptive batch sizing based on live quota measurements remains a v2 optimization; Phase 3 should start with a fixed 1000-stock target plus throttling/backoff.
- Freshness indicators, merged publish outputs, `stock_index.json` behavior, and frontend-visible update summaries remain Phase 4 scope.
- Manual-only batch advancement and dedicated retry-only runs were considered but are not part of this phase's chosen behavior.

</deferred>

---

*Phase: 03-rotating-batch-orchestration*
*Context gathered: 2026-04-19*
