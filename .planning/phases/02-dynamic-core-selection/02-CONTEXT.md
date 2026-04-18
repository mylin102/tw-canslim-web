# Phase 2: Dynamic Core Selection - Context

**Gathered:** 2026-04-19
**Status:** Ready for planning

<domain>
## Phase Boundary

Implement the daily core-stock selection layer that decides which names always receive priority updates. This phase defines the selection logic for the core universe only; batch rotation, persistent orchestration state, and freshness-aware publishing remain in later phases.

</domain>

<decisions>
## Implementation Decisions

### Core membership sources
- **D-01:** The daily core universe must be built from these source buckets: base symbols, ETFs, watchlist names, yesterday's signal names, top-volume leaders, RS leaders, and today's active signal names.

### Signal promotion source
- **D-02:** Same-day promotion into the core universe should trust signals already present in the fused parquet / `alpha_integration_module.py` path rather than introducing a second signal parser in this phase.

### Universe cap and tie-breaks
- **D-03:** Target a daily core universe of about 300 names.
- **D-04:** Always keep base symbols, ETFs, watchlist names, yesterday-signal names, and today's active signal names first; fill remaining slots by RS rank and volume rank.

### Drop-out behavior
- **D-05:** Yesterday's signal names get a one-day carryover window, then drop out unless they still qualify through another active bucket.

### the agent's Discretion
- Exact ranking formula between RS leaders and volume leaders once the fixed priority buckets are included.
- How to store and load the base list, ETF list, and watchlist configuration, as long as the selected source buckets remain intact.
- Internal helper/module boundaries for the selector implementation.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase scope and requirements
- `.planning/ROADMAP.md` §Phase 2: Dynamic Core Selection — phase goal, dependency on Phase 1, and success criteria for daily priority selection.
- `.planning/REQUIREMENTS.md` — ORCH-01 requirement definition and milestone-level scope boundaries.
- `.planning/PROJECT.md` — brownfield constraints, API-limit context, and upgrade goals from the project definition.

### Strategy source
- `update_strategy.md` §Layer 1 / Recommended plan — defines the strategy-driven update model, including core buckets such as base names, ETFs, watchlist, signal carryover, and top-volume names.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `export_canslim.py`: already has a hard-coded `priority` list and broad ticker scan flow that can be replaced or refactored into dynamic core selection.
- `alpha_integration_module.py`: already exposes the fused parquet signal surface chosen as the trusted source for same-day promotion.
- `export_dashboard_data.py`: already consumes fused parquet outputs and RS-related fields, which helps keep selector inputs aligned with current published data expectations.
- `core/logic.py`: already provides Mansfield RS calculations and related scoring primitives that can support RS-leader selection.

### Established Patterns
- Brownfield preference: build on existing CANSLIM engine and fused parquet outputs instead of introducing a separate orchestration stack.
- Python scripts use module-level logging, explicit helper functions, and file-based artifacts rather than database-backed state.
- Phase 1 established `publish_safety.py` as the required downstream publish contract, so Phase 2 should focus on selection logic rather than reworking publish behavior again.

### Integration Points
- `export_canslim.py` is the most direct place to replace the current static `priority` list with dynamic core-universe construction.
- `alpha_integration_module.py` and fused parquet files are the current reusable signal source for promotion decisions.
- Existing ticker metadata from `get_all_tw_tickers()` provides the starting universe to split into core and non-core names before later rotation work.

</code_context>

<specifics>
## Specific Ideas

- Keep important stocks always fresh while the broader market updates gradually under API limits.
- Reuse the existing fused parquet / alpha integration path for signal-driven promotion instead of inventing a new signal surface in this phase.
- Treat yesterday's signal names as sticky for one extra day so recent movers do not disappear immediately.

</specifics>

<deferred>
## Deferred Ideas

- Rotation group sizing and non-core batch handling belong to Phase 3.
- Freshness indicators, `stock_index.json`, and frontend-facing publish structure belong to Phase 4.

</deferred>

---

*Phase: 02-dynamic-core-selection*
*Context gathered: 2026-04-19*
