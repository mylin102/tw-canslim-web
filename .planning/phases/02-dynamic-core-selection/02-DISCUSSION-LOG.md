# Phase 2: Dynamic Core Selection - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md - this log preserves the alternatives considered.

**Date:** 2026-04-19
**Phase:** 02-dynamic-core-selection
**Areas discussed:** Core membership sources, Signal promotion source, Universe cap and tie-breaks, Drop-out behavior, Volume ranking source

---

## Core membership sources

| Option | Description | Selected |
|--------|-------------|----------|
| Base symbols + ETFs + watchlist + yesterday's signal names + top-volume leaders + RS leaders + today's active signals | Full dynamic source set from roadmap plus strategy doc buckets | ✓ |
| Base symbols + ETFs + top-volume leaders + RS leaders + today's active signals | Excludes watchlist and yesterday-signal carryover | |
| Base symbols + top-volume leaders + RS leaders + today's active signals | Minimal source set closest to roadmap text only | |

**User's choice:** Base symbols + ETFs + watchlist + yesterday's signal names + top-volume leaders + RS leaders + today's active signals
**Notes:** Use the broader strategy-driven bucket set from `update_strategy.md`, not only the narrower roadmap phrasing.

---

## Signal promotion source

| Option | Description | Selected |
|--------|-------------|----------|
| Signals already present in the fused parquet / alpha integration path | Reuse current signal surface for same-day promotion | ✓ |
| Only explicit ORB and counter_vwap signals, even if that needs extra parsing | Restrict promotion to named strategies only | |
| A broader signal bundle if any strategy signal is active | Treat any active strategy signal as promotion-worthy | |

**User's choice:** Signals already present in the fused parquet / alpha integration path
**Notes:** Keep Phase 2 on top of existing reusable code instead of inventing a second signal engine first.

---

## Universe cap and tie-breaks

| Option | Description | Selected |
|--------|-------------|----------|
| Target about 300 names, keep fixed-priority buckets first, then fill remaining slots by RS and volume rank | Balanced cap aligned with roadmap range and API budget | ✓ |
| Target about 500 names, keep all qualifiers unless the list exceeds that hard cap | Higher breadth, looser API budget | |
| Use a strict 200-name cap with the most selective ranking possible | Maximum selectivity and budget protection | |

**User's choice:** Target about 300 names, keep all base/ETF/watchlist/yesterday-signal/today-signal names first, then fill remaining slots by RS and volume rank
**Notes:** Fixed-priority buckets stay in; ranking pressure applies only to the remaining capacity.

---

## Drop-out behavior

| Option | Description | Selected |
|--------|-------------|----------|
| Keep yesterday's signal names for one extra day, then drop them unless they still qualify | One-day cooling-off window | ✓ |
| Drop names immediately if they do not qualify on the current run | No stickiness | |
| Keep dynamic names for a multi-day cooling-off window | Longer persistence for recent movers | |

**User's choice:** Keep yesterday's signal names for one extra day, then drop them unless they still qualify
**Notes:** Recent movers should remain visible briefly, but not linger beyond one extra day without renewed qualification.

---

## Volume ranking source

| Option | Description | Selected |
|--------|-------------|----------|
| Extend the existing signal artifact once to persist a latest volume metric, then rank from artifacts | Artifact-driven and deterministic volume-leader selection | ✓ |
| Run a lightweight live prepass from the current financial-data fetch path each day | Use live fetches to derive volume leaders before selection | |
| Use a temporary proxy rank and refine true volume handling in a later phase | Delay exact volume implementation | |

**User's choice:** Extend the existing signal artifact once to persist a latest volume metric, then rank from artifacts
**Notes:** Phase 2 should keep selector inputs artifact-driven rather than adding a separate daily API prepass just to rank volume leaders.

---

## the agent's Discretion

- Exact scoring formula for RS and volume ordering once the fixed buckets are included.
- Selector helper/module structure.
- Config storage format for base symbols, ETFs, and watchlist inputs.

## Deferred Ideas

- Rotation group handling and state persistence - Phase 3
- Freshness metadata and publish/search output changes - Phase 4
