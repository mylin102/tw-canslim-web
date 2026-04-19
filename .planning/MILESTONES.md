# Milestones

## v1.0 Strategy-Driven Update Pipeline Upgrade (Shipped: 2026-04-19)

**Phases completed:** 4 phases, 12 plans, 25 tasks

**Key accomplishments:**

- Artifact-aware bundle publishing with repo-level locking, manifest-backed rollback, and regression scaffolds for later writer migrations
- Bundle-safe CANSLIM and dashboard exports with record-level resume validation, failure summaries, and loud publish errors
- Bundle-safe quick, batch, verification, and on-demand publish flows with deterministic rollback and serialized GitHub Actions publish surfaces
- Validated selector contracts with checked-in core buckets, fused-parquet signal carryover rules, and pytest fixtures for future export wiring.
- Artifact-backed core selection now promotes trusted fused signals, RS leaders, and top-volume leaders from persisted parquet data without any live prepass.
- Artifact-backed core selection now drives CANSLIM export scan order while Phase 1 bundle publishing and failure summaries remain intact
- Atomic JSON rotation-state persistence plus explicit provider retry/throttle contracts for later batch orchestration wiring
- Deterministic three-way non-core rotation with frozen-batch resume seams, due-retry prioritization, and success-only cursor advancement
- Retry-first rotation exports now share provider pacing, persist crash-survivable state, and validate daily runtime budget inside the GitHub Actions pipeline
- Freshness-aware publish projection now emits merged screener data, a full-universe stock index, and rotation-safe operator summaries from Phase 3 state.
- Vue dashboard now searches the full published stock index, shows freshness badges across requested surfaces, and clearly marks non-snapshot stocks as limited-detail results.
- Shared Phase 4 publish-bundle reuse for single-stock updates plus workflow commits that keep stock_index.json and update_summary.json durable in CI.

---
