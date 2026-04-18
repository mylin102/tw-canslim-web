# tw-canslim-web

## What This Is

`tw-canslim-web` is a brownfield Taiwan stock analysis repo that runs a Python-based CANSLIM data pipeline and publishes precomputed dashboard data to GitHub Pages. The next upgrade is to evolve the current full-update workflow into a strategy-driven update system that keeps core trading candidates fresh every day while rotating the rest of the market under API and rate-limit constraints.

## Core Value

Keep the most actionable Taiwan stocks reliably fresh for trading decisions without losing broad market coverage.

## Requirements

### Validated

- ✓ Repo can ingest multi-source market data and generate CANSLIM-style stock analysis outputs — existing
- ✓ Repo can publish static dashboard data to GitHub Pages from generated JSON artifacts — existing
- ✓ Repo already supports scheduled and on-demand update workflows driven by scripts and GitHub Actions — existing

### Active

- [ ] Upgrade the update pipeline to follow `update_strategy.md` with daily core-stock updates plus rotating batch coverage for the rest of the market
- [ ] Make the update flow resilient to API and rate-limit constraints instead of depending on broad full-market freshness
- [ ] Serve static outputs that support dashboard, search, and stock detail flows under the new update model

### Out of Scope

- Real-time full-market updates for every stock on every run — incompatible with current API limits and reliability goals
- Immediate live-trading execution integration — current work is focused on data freshness and publishable outputs first

## Context

This is a brownfield codebase with an existing Python data pipeline, CANSLIM scoring logic, and a static frontend served from `docs/`. The current architecture already supports multi-source data ingestion, scoring, JSON export, and GitHub Actions-based updates. The main problem driving this work is that API and rate-limit constraints make a broad full-update strategy unreliable, so the repo needs a more deliberate update model that prioritizes daily freshness for core stocks and batch rotation for the rest of the market. The primary users are the repo owner's own trading workflow and anyone consuming the published dashboard.

## Constraints

- **Tech stack**: Python pipeline + static GitHub Pages outputs — the repo already depends on file-based exports rather than a database-backed service
- **External APIs**: FinMind, TEJ, Yahoo Finance, and related sources can rate-limit or degrade — update design must reduce bursty broad refresh behavior
- **Deployment**: Scheduled execution runs through GitHub Actions — the new flow must fit existing automation and artifact publishing patterns
- **Compatibility**: Existing dashboard/search experiences should keep working or evolve in a controlled way — output changes need explicit wiring to frontend consumers

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Treat this as a brownfield pipeline upgrade, not a greenfield redesign | The repo already has working ingestion, scoring, and publishing flows that should be reused | — Pending |
| Prioritize automated update orchestration first | The main user pain is unreliable freshness under API constraints, not lack of analytics features | — Pending |
| Define done as daily core updates plus rotating batch coverage with reliable published outputs | This is the observable behavior the strategy doc is trying to introduce | — Pending |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? -> Move to Out of Scope with reason
2. Requirements validated? -> Move to Validated with phase reference
3. New requirements emerged? -> Add to Active
4. Decisions to log? -> Add to Key Decisions
5. "What This Is" still accurate? -> Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check -> still the right priority?
3. Audit Out of Scope -> reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-04-18 after initialization*
