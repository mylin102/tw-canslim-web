---
phase: 04-publishing-freshness-awareness
status: complete
created: 2026-04-19
confidence: medium-high
---

# Phase 04 — Research

## Summary

Phase 4 should stay brownfield: reuse the Phase 3 publish path and per-stock freshness state, then add a single publish-projection step that emits all Phase 4 artifacts together. The cleanest approach is to build merged outputs from the current run, the baseline artifact, and `.orchestration/rotation_state.json`, then publish `data.json`, `stock_index.json`, and `update_summary.json` in one bundle.

The main planning risk is contract drift between backend artifacts and the current frontend, because `docs/app.js` still only searches and renders from `data.json`. Phase 4 therefore needs explicit tasks for merged-output precedence, search-index generation, frontend search rewiring, and summary timing that does not violate Phase 3's finalize-after-publish rule.

## Locked Decisions to Honor

- Freshness uses 3 levels: today, 1-2 days old, and 3+ days old.
- Freshness derives from each stock's own last successful update time.
- Freshness appears in search suggestions, stock detail views, and screener/list surfaces.
- `data.json` remains the main frontend entry point.
- Full-universe search uses a dedicated `stock_index.json`.
- Search index must support code and name substring matching.
- Non-snapshot stocks must still be discoverable, but missing full CANSLIM detail must be shown explicitly rather than faked.

## Existing Assets

### Backend / publish seams
- `export_canslim.py` already owns the main publish flow, update summary building, and Phase 3 rotation-aware export path.
- `orchestration_state.py` already persists per-stock `last_succeeded_at` freshness information.
- `publish_safety.py` already provides the required bundle-level publish contract.
- `rotation_orchestrator.py` can provide deterministic "what rotates next" preview logic without mutating live state early.
- `merge_data.py` is only a simple prototype; it is not enough for the final merged-output contract.

### Frontend seams
- `docs/app.js` is the active dashboard/search UI and currently fetches only `data.json`.
- `docs/index.html` loads `app.js`; `docs/screener.js` exists but is not the active integration point.

### Workflow seams
- `.github/workflows/update_data.yml` already references `create_stock_index.py`, but that script does not currently exist.
- Scheduled workflow currently does not commit `docs/update_summary.json`; on-demand and scheduled workflows will need aligned Phase 4 artifact handling.

## Recommended Architecture

### 1. Publish projection layer
Add a projection step in or adjacent to `export_canslim.py` that:
1. loads current-run stock data
2. loads baseline coverage from `docs/data_base.json`
3. loads per-stock freshness from `.orchestration/rotation_state.json`
4. produces all frontend/operator artifacts from the same snapshot

This avoids drift between merged data, search index, and summary output.

### 2. Freshness as a derived projection
Do not invent a new freshness store. Use Phase 3 freshness state as the source of truth and project:
- raw timestamp (e.g. `last_succeeded_at`)
- derived freshness level
- derived freshness label

### 3. Dedicated `stock_index.json`
Generate a lightweight index for full-universe search with:
- `symbol`
- `name`
- `industry`
- `freshness`
- last successful update time
- whether the stock is present in the main snapshot

Frontend search should use the index first, then hydrate richer detail from `data.json` when available.

### 4. Summary preview without early cursor advance
`update_summary.json` should preview what rotates next without changing persisted state before publish succeeds. Use deterministic planner/group information to preview the next batch rather than mutating the cursor early.

## Concrete Integration Points

- `export_canslim.py` — merged payload assembly, summary generation, final publish bundle
- `docs/app.js` — search suggestions, full-universe search fallback, freshness badge rendering
- `docs/index.html` — any template changes required for freshness badges or index-backed search fallback
- `.github/workflows/update_data.yml`
- `.github/workflows/on_demand_update.yml`

## Common Pitfalls

1. Using bundle-level `last_updated` as stock freshness instead of per-stock success time
2. Publishing `stock_index.json` or `update_summary.json` outside the shared publish bundle
3. Advancing Phase 3 rotation state before publish succeeds just to make summary output easier
4. Adding `stock_index.json` without rewiring `docs/app.js` to actually read it
5. Planning against `docs/screener.js` instead of the active `docs/app.js` path

## Validation Architecture

Phase 4 needs new Wave 0 tests for:
- freshness projection and labeling
- merged-output precedence and compatibility
- stock-index generation
- update-summary contract
- frontend-facing publish-path integration

Existing publish, rotation, and primary publish-path tests are strong enough to extend rather than replace.

## Validation Architecture

### Test Infrastructure
- Framework: `pytest` 9.0.2
- Quick run baseline: `PYTHONPATH=. pytest -q tests/test_export_schema.py tests/test_publish_safety.py tests/test_primary_publish_path.py`
- Full suite: `PYTHONPATH=. pytest -q`

### Phase-specific gaps
- `tests/test_publish_freshness.py` — freshness field projection and 3-level labels
- `tests/test_stock_index.py` — full-universe index generation and membership flags
- `tests/test_publish_merge.py` — merged `data.json` precedence and compatibility
- `tests/test_publish_summary_phase4.py` — refreshed/failed/next-rotation summary contract

## Open Questions (RESOLVED)

- Keep `data.json` as the frontend's primary entrypoint rather than forcing a multi-payload rewrite.
- Treat `stock_index.json` as a separate search payload, not a replacement for merged `data.json`.
- Keep stale stocks visible in the main screener with explicit freshness labels.

## Sources

- `.planning/phases/04-publishing-freshness-awareness/04-CONTEXT.md`
- `.planning/REQUIREMENTS.md`
- `.planning/STATE.md`
- `export_canslim.py`
- `orchestration_state.py`
- `rotation_orchestrator.py`
- `publish_safety.py`
- `docs/app.js`
- `docs/index.html`
- `.github/workflows/update_data.yml`
- `.github/workflows/on_demand_update.yml`
