# Phase 3: Rotating Batch Orchestration - Discussion Log

**Date:** 2026-04-19
**Status:** Completed

## Phase Boundary

Build the non-core rotation system with deterministic 3-day batches, persistent state, resume behavior, failed-stock tracking, and provider-aware throttling/backoff. Do not pull freshness-aware publishing or search/index work into this phase.

## Prior Context Carried Forward

- Phase 1 established `publish_safety.py` as the publish contract and loud-failure behavior for supported publish paths.
- Phase 2 established the dynamic core selector and explicitly left rotation/state behavior for Phase 3.
- Project constraints still require a brownfield, file-based orchestration approach that works inside GitHub Actions rather than a database-backed service.

## Questions and Decisions

### 1. Rotation advancement trigger
**Question:** When should the orchestrator advance to the next non-core batch?

**Options considered:**
1. Advance only after the current batch finishes successfully
2. Advance once per scheduled run/day, even if the batch was partial
3. Advance on manual operator command only

**Decision:** Advance only after the current batch finishes successfully.

**Why this matters:** This avoids date-based drift and makes crash-safe resume meaningful.

### 2. Meaning of batch completion when some stocks fail
**Question:** If a scheduled batch finishes but some individual stocks fail, how should the batch be treated?

**Options considered:**
1. Mark the batch complete, carry failed stocks in a retry queue, and advance rotation
2. Keep the batch open and retry the same batch on the next run until every stock succeeds
3. Advance rotation and only log failed stocks without automatic retry

**Decision:** Mark the batch complete, carry failed stocks in a retry queue, and advance rotation.

**Why this matters:** This prevents a few unstable symbols from stalling whole-market coverage while still preserving accountability for retries.

### 3. Deterministic group construction
**Question:** How should the non-core universe be split into 3 groups?

**Options considered:**
1. Stable sorted-symbol partition into 3 fixed groups, recomputed deterministically when membership changes
2. Rolling window slice of the current non-core list each run
3. Hash-based assignment so each symbol always maps to the same group

**Decision:** Use a stable sorted-symbol partition into 3 fixed groups, then recompute deterministically when core/non-core membership changes.

**Why this matters:** This keeps the rotation easy to inspect and predictable for operators while remaining deterministic as the Phase 2 selector changes membership.

### 4. Retry queue priority
**Question:** How should queued retry stocks be scheduled relative to the day's normal batch?

**Options considered:**
1. Try queued retries first, then use the remaining budget for the planned batch
2. Run the planned batch first, then spend leftover budget on retries
3. Dedicate separate runs to retries and keep daily rotation runs clean

**Decision:** Try queued retries first, then use the remaining budget for the planned batch.

**Why this matters:** This gives failed names the fastest path back to freshness without requiring a separate operator workflow.

### 5. Default daily non-core budget
**Question:** What default non-core batch size should the phase target?

**Options considered:**
1. 1000 stocks/day, with throttling/backoff managing the budget
2. 700 stocks/day for a more conservative default
3. 500 stocks/day for maximum safety

**Decision:** Target 1000 non-core stocks/day by default, and manage limits through throttling/backoff.

**Why this matters:** This preserves the 3-day coverage goal from the strategy unless real provider behavior proves a smaller cap is necessary later.

## Deferred / Out of Scope

- Adaptive batch sizing based on measured quota consumption
- Freshness indicators and publish/search artifact changes
- Manual-only cursor advancement
- Dedicated retry-only runs

## Outcome

Phase 3 now has enough product decisions to plan around:
- success-based cursor advancement
- deterministic 3-way non-core partitioning
- retry-queue-first scheduling
- fixed 1000/day operating target with throttling/backoff

---

*Phase: 03-rotating-batch-orchestration*
*Discussion completed: 2026-04-19*
