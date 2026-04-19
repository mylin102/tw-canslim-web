# Phase 4: Publishing & Freshness Awareness - Context

**Gathered:** 2026-04-19
**Status:** Ready for planning

<domain>
## Phase Boundary

Deliver the publish-layer outputs and frontend-visible freshness behavior for the strategy-driven update model. This phase owns explicit freshness metadata, full-universe search indexing, merged publish outputs that keep the dashboard working under the new daily-core-plus-rotation model, and a maintainer-facing update summary artifact. Core selection remains owned by Phase 2, while rotation state, retry queues, and provider-throttling mechanics remain owned by Phase 3.

</domain>

<decisions>
## Implementation Decisions

### Freshness semantics
- **D-01:** Freshness uses 3 levels: today, 1-2 days old, and 3+ days old.
- **D-02:** Each stock's freshness must be derived from that stock's own last successful update timestamp, not from a bundle-level `last_updated`.
- **D-03:** Freshness indicators must appear in search suggestions, stock detail views, and screener/list surfaces.
- **D-04:** Freshness should be shown as color/icon plus short text (for example `🟢 今日`, `🟡 2天前`, `🔴 逾3天`), not as icon-only or full raw timestamps everywhere.

### Full-universe search index
- **D-05:** Stocks that are not present in the main screener snapshot must still be searchable through the publish-ready index.
- **D-06:** When a non-snapshot stock is found through search, the UI should show basic stock information plus freshness, and clearly indicate when full CANSLIM detail is not available instead of pretending it is.
- **D-07:** `stock_index.json` must at least include `symbol`, `name`, `industry`, `freshness`, last successful update time, and whether the stock is present in the main snapshot.
- **D-08:** Full-universe search should support stock code and name substring matching by default.

### Merged publish outputs
- **D-09:** `data.json` should remain the main frontend entry point for compatibility, but its contents should become the merged output under the new publish model.
- **D-10:** The merged model should keep baseline coverage as the floor, while newer daily core / rotation / retry results overwrite older baseline values when fresher data exists.
- **D-11:** Stocks with stale freshness should still appear in the main screener if they are part of the merged output; freshness indicators should explain staleness instead of hiding those names.

### the agent's Discretion
- Exact output schema shape for `update_summary.json`, as long as it clearly communicates what refreshed, what failed, and what rotates next.
- Exact file generation boundaries between merged payload production, light/index payload generation, and frontend consumption helpers.
- Exact text copy, badge styling, and small UI wording choices for freshness labels, as long as the 3-level semantics remain intact.
- Exact fallback behavior when a searchable stock has partial detail fields beyond the required basic identity + freshness metadata.

</decisions>

<specifics>
## Specific Ideas

- Freshness should reflect the real per-stock update model from Phase 3, not a misleading bundle-wide timestamp.
- Search should become discoverable across the full Taiwan universe even when the main screener snapshot remains selective.
- The repo should keep one primary frontend data entry point (`data.json`) rather than forcing a broad frontend rewrite in this phase.
- Stale stocks are acceptable in the merged dataset as long as the UI makes staleness obvious.

</specifics>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase scope and requirements
- `.planning/ROADMAP.md` §Phase 4: Publishing & Freshness Awareness — phase goal, success criteria, and dependency on Phase 3.
- `.planning/REQUIREMENTS.md` — PUB-01, PUB-02, PUB-03, and PUB-04 definitions plus file-based deployment constraints.
- `.planning/PROJECT.md` — brownfield GitHub Pages architecture, compatibility constraints, and static-output deployment model.
- `.planning/STATE.md` — current milestone position and Phase 3 completion handoff.

### Strategy source
- `update_strategy.md` — layered update strategy defining daily core updates, rotating market coverage, and the need for publishable outputs that remain useful under partial freshness.

### Upstream phase contracts
- `.planning/phases/02-dynamic-core-selection/02-CONTEXT.md` — locked Phase 2 decisions defining the dynamic core universe and the intended core/non-core split.
- `.planning/phases/03-rotating-batch-orchestration/03-CONTEXT.md` — locked Phase 3 decisions defining per-stock freshness, retry-first behavior, and durable orchestration state.
- `.planning/phases/03-rotating-batch-orchestration/03-VERIFICATION.md` — verified truths about rotation state, per-stock freshness persistence, and workflow restore/persist behavior that Phase 4 must build on.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `export_canslim.py`: already owns the main publish path, now with Phase 3 per-stock freshness and rotation-aware worklists.
- `orchestration_state.py`: already persists per-stock freshness metadata and last successful update timestamps that Phase 4 can surface downstream.
- `merge_data.py`: existing proof-of-concept for merging baseline coverage into `data.json`, though it is too simple for the final Phase 4 contract.
- `export_dashboard_data.py`: existing publish helper for dashboard-oriented outputs through `publish_artifact_bundle(...)`.
- `docs/app.js`: current frontend reads `data.json`, builds search suggestions from `stockData.stocks`, and is the main compatibility surface for freshness/search changes.
- `docs/screener.js`: current screener/ranking module that Phase 4 will need to keep working with merged data.
- `docs/update_summary.json`: existing operator-facing summary artifact that can evolve into the Phase 4 summary contract.

### Established Patterns
- Brownfield preference remains in force: extend existing Python generators and static JSON outputs rather than introducing a backend service or database.
- Phase 1 established `publish_safety.py` as the required publish contract for artifact writes.
- Phase 3 established per-stock freshness and durable workflow state as the source of truth for freshness-aware publishing.
- Frontend currently assumes `data.json` is the primary payload and performs client-side search suggestion logic from that payload.

### Integration Points
- `export_canslim.py` is the natural place to emit or hand off the richer merged publish outputs after Phase 3 orchestration completes.
- `docs/app.js` and `docs/index.html` are the immediate consumers for freshness indicators and search behavior.
- A new `stock_index.json` generator will likely need to connect the merged publish layer to frontend search without requiring all stocks to have full screener detail.
- `update_data.yml` and related publish workflows already commit static artifacts and will need to include the finalized Phase 4 outputs.

</code_context>

<deferred>
## Deferred Ideas

- More advanced operator analytics or historical freshness trend tracking remain outside this phase and fit better in a later optimization/debugging phase.
- Richer search facets beyond code and name substring matching (for example industry-level search filters inside the global search box) are not required for this phase.
- Adaptive data-shape splitting or diff-oriented frontend payloads remain v2 optimization work.

</deferred>

---

*Phase: 04-publishing-freshness-awareness*
*Context gathered: 2026-04-19*
