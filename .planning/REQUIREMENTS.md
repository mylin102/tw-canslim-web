# Requirements: tw-canslim-web

**Defined:** 2026-04-18
**Core Value:** Keep the most actionable Taiwan stocks reliably fresh for trading decisions without losing broad market coverage.

## v1 Requirements

### Safety & Reliability

- [ ] **SAFE-01**: Maintainer can run the update workflow without concurrent writers corrupting published JSON artifacts.
- [ ] **SAFE-02**: Maintainer can see explicit update failures and retry outcomes instead of silent API/data suppression.
- [ ] **SAFE-03**: Maintainer can evolve exported stock schemas safely using versioned metadata and validation checks.
- [ ] **SAFE-04**: Maintainer can publish updates atomically and recover to the last good snapshot when a run fails validation.

### Orchestration

- [ ] **ORCH-01**: Maintainer can generate a daily core stock universe from base symbols, volume leaders, RS leaders, and active signals.
- [ ] **ORCH-02**: Maintainer can rotate non-core stocks through deterministic batches so broad market coverage completes within a three-day cycle.
- [ ] **ORCH-03**: Maintainer can persist orchestration state across runs, including rotation position, freshness, and failed-stock tracking.
- [ ] **ORCH-04**: Maintainer can resume a partial update run without rebuilding the entire market snapshot.
- [ ] **ORCH-05**: Maintainer can run the daily pipeline under provider limits using throttling, retry, and backoff behavior appropriate to each data source.

### Publishing & UX

- [ ] **PUB-01**: Dashboard user can see freshness metadata for each stock and understand when data is stale.
- [ ] **PUB-02**: Dashboard user can search the full stock universe through a publish-ready index even when a stock is not present in the main screener snapshot.
- [ ] **PUB-03**: Dashboard user can load stock and screener data from outputs produced by the merged baseline-plus-incremental update model.
- [ ] **PUB-04**: Maintainer can publish an update summary artifact that shows what refreshed, what failed, and what rotates next.

## v2 Requirements

### Optimization

- **OPTI-01**: Maintainer can adapt batch size dynamically based on observed quota usage and response quality.
- **OPTI-02**: Dashboard can consume diff-oriented update artifacts to reduce reload costs.
- **OPTI-03**: Maintainer can track historical freshness trends for debugging and tuning.

### Advanced Selection

- **SELE-01**: Maintainer can rank core candidates with an alpha-style weighted score beyond the first-pass signal/volume/RS rules.
- **SELE-02**: Maintainer can bias rotation or priority by industry strength and diversity constraints.
- **SELE-03**: Maintainer can inject personal watchlist preferences into the dynamic priority queue.

## Out of Scope

| Feature | Reason |
|---------|--------|
| Real-time websocket or push updates | Static GitHub Pages deployment does not support a live server model and it is not required for this upgrade |
| Full-market every-run refresh | Conflicts directly with API-limit and reliability constraints |
| Database-backed orchestration state | Adds operational complexity beyond the repo's current file-based deployment model |
| Heavy orchestration framework adoption | Existing GitHub Actions plus Python scripts are sufficient and lower-risk for this brownfield upgrade |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| SAFE-01 | Phase TBD | Pending |
| SAFE-02 | Phase TBD | Pending |
| SAFE-03 | Phase TBD | Pending |
| SAFE-04 | Phase TBD | Pending |
| ORCH-01 | Phase TBD | Pending |
| ORCH-02 | Phase TBD | Pending |
| ORCH-03 | Phase TBD | Pending |
| ORCH-04 | Phase TBD | Pending |
| ORCH-05 | Phase TBD | Pending |
| PUB-01 | Phase TBD | Pending |
| PUB-02 | Phase TBD | Pending |
| PUB-03 | Phase TBD | Pending |
| PUB-04 | Phase TBD | Pending |

**Coverage:**
- v1 requirements: 13 total
- Mapped to phases: 0
- Unmapped: 13 ⚠️

---
*Requirements defined: 2026-04-18*
*Last updated: 2026-04-18 after initial definition*
