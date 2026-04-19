# tw-canslim-web

## What This Is

`tw-canslim-web` is a brownfield Taiwan stock analysis repo that runs a Python CANSLIM pipeline and publishes precomputed dashboard artifacts to GitHub Pages. v1.0 shipped a strategy-driven update system that keeps a dynamic core stock universe fresh every day, rotates the rest of the market on a deterministic 3-day cycle, and publishes bundle-safe data, search, and summary artifacts.

## Core Value

Keep the most actionable Taiwan stocks reliably fresh for trading decisions without losing broad market coverage.

## Current State

- **Shipped version:** v1.0 Strategy-Driven Update Pipeline Upgrade (2026-04-19)
- **Operational shape:** dynamic core selection + deterministic 3-day rotation + bundle-safe publish/rollback
- **Published surfaces:** `docs/data.json`, `docs/stock_index.json`, `docs/update_summary.json`, and related workflow state artifacts
- **Current planning state:** no active next milestone yet; roadmap and requirements are archived under `.planning/milestones/`

## Requirements

### Validated

- ✓ Repo can ingest multi-source market data and generate CANSLIM-style stock analysis outputs — existing
- ✓ Repo can publish static dashboard data to GitHub Pages from generated JSON artifacts — existing
- ✓ Repo already supports scheduled and on-demand update workflows driven by scripts and GitHub Actions — existing
- ✓ Strategy-driven updates now keep daily core stocks fresh while rotating the rest of the market across a deterministic 3-day cycle — v1.0
- ✓ Publish workflows now validate and promote related dashboard artifacts as one bundle-safe transaction with rollback support — v1.0
- ✓ Dashboard search and freshness UI now consume the full-universe stock index and explicit update-summary artifacts — v1.0

### Active

- [ ] Define the next milestone scope from the archived optimization and advanced-selection requirements
- [ ] Decide whether the next milestone should focus first on adaptive batching, diff-oriented artifacts, or smarter selection/ranking

### Out of Scope

- Real-time full-market updates for every stock on every run — incompatible with current API limits and reliability goals
- Immediate live-trading execution integration — current work is focused on data freshness and publishable outputs first

## Context

The codebase now has a shipped orchestration layer on top of the existing CANSLIM pipeline. It uses persisted selector/orchestration artifacts, bundle-safe publish helpers, and GitHub Actions automation to keep the dashboard outputs coherent under API and rate-limit constraints. The primary remaining planning need is choosing which optimization and selection improvements become the next milestone.

## Constraints

- **Tech stack:** Python pipeline + static GitHub Pages outputs with file-based state and publish artifacts
- **External APIs:** FinMind, TEJ, Yahoo Finance, and related sources can rate-limit or degrade
- **Deployment:** Scheduled and on-demand execution runs through GitHub Actions and repo commits
- **Compatibility:** Existing dashboard/search experiences should continue to evolve through explicit publish-contract changes

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Treat this as a brownfield pipeline upgrade, not a greenfield redesign | The repo already had working ingestion, scoring, and publishing flows worth reusing | ✓ Shipped in v1.0 |
| Prioritize automated update orchestration first | The main user pain was unreliable freshness under API constraints | ✓ Shipped in v1.0 |
| Define done as daily core updates plus rotating batch coverage with reliable published outputs | This was the observable behavior required by `update_strategy.md` | ✓ Shipped in v1.0 |
| Use one shared publish lock and manifest-backed rollback path for supported writers | Related artifacts must not drift apart across scheduled/on-demand/operational paths | ✓ Shipped in v1.0 |

## Next Milestone Goals

- Choose the highest-value v2 requirement cluster from the archived backlog
- Preserve the shipped publish-bundle and workflow contracts while extending behavior
- Keep milestone scope explicit before adding new phases to the roadmap

---
*Last updated: 2026-04-19 after v1.0 milestone completion*
