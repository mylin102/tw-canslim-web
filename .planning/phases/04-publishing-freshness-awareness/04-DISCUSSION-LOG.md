# Phase 4 Discussion Log

**Date:** 2026-04-19
**Phase:** 04 - Publishing & Freshness Awareness

## Decisions captured

1. Freshness uses 3 levels: today, 1-2 days old, and 3+ days old.
2. Freshness is based on each stock's own last successful update time.
3. Freshness appears in search suggestions, stock detail views, and screener/list surfaces.
4. Freshness is shown as color/icon plus short text.
5. Full-universe search must return stocks outside the main snapshot.
6. Non-snapshot search hits show basic info plus freshness and clearly indicate when full CANSLIM detail is unavailable.
7. `stock_index.json` must include symbol, name, industry, freshness, last successful update time, and snapshot membership.
8. Search matching covers stock code and name substring matching.
9. `data.json` remains the main frontend entry point but becomes the merged output.
10. Baseline coverage remains the floor; fresher core/rotation/retry data overwrites older baseline values.
11. Stale stocks remain visible in the main screener with explicit freshness indicators instead of being hidden.

## Areas left to agent discretion

- Exact `update_summary.json` shape and field set
- Exact merged-output generation boundaries
- Exact label wording / visual styling
- Exact partial-detail fallback behavior beyond the required basic search result metadata

---

*Ready for planning*
