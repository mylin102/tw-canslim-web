# Phase 1: Safety Hardening - Research

**Researched:** 2026-04-18 [VERIFIED: system date]  
**Domain:** File-safe artifact publishing, failure visibility, schema evolution, rollback, and validation for a Python file-based data pipeline [VERIFIED: ROADMAP.md:31-43][VERIFIED: REQUIREMENTS.md:10-13]  
**Confidence:** HIGH [VERIFIED: codebase inspection + Python/GitHub docs]

## User Constraints

- No phase-specific `01-CONTEXT.md` exists, so there are no locked discuss-phase decisions to copy verbatim. [VERIFIED: gsd init output + phase context file check]
- This phase must address `SAFE-01`, `SAFE-02`, `SAFE-03`, and `SAFE-04`. [VERIFIED: REQUIREMENTS.md:10-13][VERIFIED: ROADMAP.md:31-43]
- Planning should focus on write targets, lock strategy, exception-removal scope, schema-versioning options, rollback approach, validation/test approach, and sequencing risks. [VERIFIED: user prompt]

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| SAFE-01 | Maintainer can run the update workflow without concurrent writers corrupting published JSON artifacts. [VERIFIED: REQUIREMENTS.md:10] | Shared publish lock, workflow concurrency group, atomic write/replace, and canonical write targets. [VERIFIED: export_canslim.py:663-744][VERIFIED: quick_auto_update.py:115-176][VERIFIED: quick_auto_update_enhanced.py:217-232][VERIFIED: verify_local.py:98-104][CITED: https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/control-workflow-concurrency][CITED: https://docs.python.org/3/library/os.html#os.replace] |
| SAFE-02 | Maintainer can see explicit update failures and retry outcomes instead of silent API/data suppression. [VERIFIED: REQUIREMENTS.md:11] | Bare-exception audit, exception classification, `logger.exception`, and failure summary counters. [VERIFIED: repo-wide bare except grep][VERIFIED: export_canslim.py:189-194][VERIFIED: quick_data_gen.py:99-110][VERIFIED: tej_processor.py:45-52][VERIFIED: python3 logging.Logger.exception docstring] |
| SAFE-03 | Maintainer can evolve exported stock schemas safely using versioned metadata and validation checks. [VERIFIED: REQUIREMENTS.md:12] | Schema envelope, resume validator, compatibility policy, and artifact manifest. [VERIFIED: export_canslim.py:557-565][VERIFIED: docs/data.json schema probe][VERIFIED: CONCERNS.md:312-347] |
| SAFE-04 | Maintainer can publish updates atomically and recover to the last good snapshot when a run fails validation. [VERIFIED: REQUIREMENTS.md:13] | Stage-validate-promote workflow, last-good snapshot directory, rollback command/script, and validation gates before commit. [VERIFIED: export_canslim.py:727-744][VERIFIED: backup artifact inventory][CITED: https://docs.python.org/3/library/os.html#os.replace] |
</phase_requirements>

## Summary

Phase 1 should treat safety hardening as a publish-system rewrite, not a small bug-fix sweep. The repo currently has multiple direct writers for `docs/data.json` and `docs/data_base.json`, including `export_canslim.py`, `quick_data_gen.py`, `quick_auto_update.py`, `quick_auto_update_enhanced.py`, `verify_local.py`, `fast_data_gen.py`, and `update_single_stock.py`. [VERIFIED: export_canslim.py:23,663-744][VERIFIED: quick_data_gen.py:281-285][VERIFIED: quick_auto_update.py:22-176][VERIFIED: quick_auto_update_enhanced.py:31-306][VERIFIED: verify_local.py:98-104][VERIFIED: fast_data_gen.py:295-302][VERIFIED: update_single_stock.py:171-201] The current publish path still includes in-place overwrites, ad hoc temp-file usage, and no shared locking across scripts. [VERIFIED: export_canslim.py:663-744][VERIFIED: quick_auto_update.py:115-176][VERIFIED: quick_auto_update_enhanced.py:217-232]

Failure visibility is also incomplete. A fresh repo-wide grep finds 13 remaining bare `except:` clauses, while the planning docs still reference a prior 28-item audit, so the planner should assume a safety sweep is still required and also reconcile the stale count during implementation. [VERIFIED: repo-wide bare except grep][VERIFIED: STATE.md:64-76][VERIFIED: CONCERNS.md:31-55] Current tests do not cover publish safety, and full `pytest --collect-only` already fails because `tests/test_institutional_logic.py` imports a missing `calculate_i_factor`. [VERIFIED: tests/test_institutional_logic.py:9-70][VERIFIED: pytest --collect-only output]

The safest plan is: first centralize all artifact writes behind one shared writer module using `fcntl` locks plus same-directory temp files and `os.replace`; second, remove silent exception paths and emit structured failure summaries; third, add schema metadata plus schema-aware resume checks; fourth, add a validated last-good snapshot and rollback path; finally, wire GitHub Actions workflow concurrency so remote runs cannot overlap local or issue-driven publish runs. [VERIFIED: python3 fcntl docstrings][CITED: https://docs.python.org/3/library/os.html#os.replace][CITED: https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/control-workflow-concurrency]

**Primary recommendation:** Make `data_base.json` the only canonical mutable snapshot, route every publish through one lock-protected atomic writer, and treat `data.json`, `data_light.json`, `data.json.gz`, and `update_summary.json` as derived artifacts built and promoted under the same publish transaction. [VERIFIED: fast_data_gen.py:295-302][VERIFIED: create_medium_data.py:10-63][VERIFIED: create_light_data.py:11-42][VERIFIED: compress_data.py:17-41]

## Project Constraints (from copilot-instructions.md)

- Keep the existing Python pipeline + static GitHub Pages output model; do not plan a database-backed orchestration state or a service rewrite. [VERIFIED: copilot-instructions.md:10-16]
- Fit the implementation into the current GitHub Actions automation model. [VERIFIED: copilot-instructions.md:13-15]
- Preserve compatibility with existing dashboard/search consumers unless output changes are explicitly wired through. [VERIFIED: copilot-instructions.md:15][VERIFIED: docs/app.js references in CONCERNS.md:146-167]
- Follow current Python conventions: snake_case naming, stdlib/third-party/local import order, module-level logging, docstrings, and type hints where practical. [VERIFIED: CONVENTIONS.md:7-68][VERIFIED: CONVENTIONS.md:106-170]
- Do not plan direct repo edits outside the GSD workflow. [VERIFIED: copilot-instructions.md:279-290]

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python stdlib `fcntl` | Python 3.11+ runtime; available in local Python 3.12.5 [VERIFIED: update_data.yml:23-32][VERIFIED: `python3 --version`] | Advisory shared/exclusive file locking for Unix runners and local macOS. [VERIFIED: python3 fcntl.lockf/flock docstrings] | No new dependency, matches Darwin + `ubuntu-latest`, and supports non-blocking lock acquisition semantics. [VERIFIED: `python3` fcntl docstrings][VERIFIED: update_data.yml:14-32] |
| Python stdlib `tempfile` + `os.replace` | Python 3.11+ runtime; available in local Python 3.12.5 [VERIFIED: update_data.yml:23-32][VERIFIED: `python3 --version`] | Same-directory temp staging and atomic file replacement. [VERIFIED: python3 tempfile.NamedTemporaryFile docstring][CITED: https://docs.python.org/3/library/os.html#os.replace] | `os.replace` explicitly overwrites destination and Python docs state a successful rename is atomic on POSIX filesystems. [CITED: https://docs.python.org/3/library/os.html#os.replace] |
| Python stdlib `logging` | Python 3.11+ runtime [VERIFIED: update_data.yml:23-32] | Structured error, warning, retry, and rollback logging. [VERIFIED: CONVENTIONS.md:106-121] | `Logger.exception` includes exception information without inventing custom traceback plumbing. [VERIFIED: python3 logging.Logger.exception docstring] |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `pytest` | 9.0.2 installed locally; 9.0.3 current on PyPI as of 2026-04-07 [VERIFIED: `pytest --version`][VERIFIED: PyPI JSON for pytest] | Unit/integration validation for locks, schema guards, resume behavior, and rollback. [VERIFIED: requirements.txt:4][VERIFIED: tests directory listing] | Use for all Phase 1 safety gates and regressions. [VERIFIED: POST_MORTEM_20260415.md:39-44] |
| Python stdlib `gzip` | Python 3.11+ runtime [VERIFIED: compress_data.py:1-41][VERIFIED: update_data.yml:23-32] | Regenerate `docs/data.json.gz` from the validated `data.json`. [VERIFIED: compress_data.py:17-41] | Use after `data.json` passes validation and before the final publish marker is written. [VERIFIED: compress_data.py:17-41][ASSUMED] |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `fcntl` advisory locks [VERIFIED: python3 fcntl docstrings] | `portalocker` or `filelock` [ASSUMED] | Extra dependency is unnecessary for Darwin + GitHub Actions Ubuntu; stdlib is lower-risk here. [VERIFIED: update_data.yml:14-32][ASSUMED] |
| Project-specific schema validator + version policy [VERIFIED: docs/data.json schema probe][VERIFIED: CONCERNS.md:312-347] | `jsonschema` 4.26.0 [VERIFIED: PyPI JSON for jsonschema] | `jsonschema` is stronger for broad contracts, but Phase 1 only needs one controlled artifact family and can stay dependency-light if validation remains narrow. [VERIFIED: copilot-instructions.md:10-16][ASSUMED] |
| Workflow `concurrency` plus file locks [CITED: https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/control-workflow-concurrency] | File locks only [ASSUMED] | Workflow concurrency prevents remote overlap; file locks still protect local/manual runs and multi-script access on the same filesystem. [VERIFIED: on_demand_update.yml:1-54][VERIFIED: update_data.yml:1-90] |

**Installation:** No new dependency is required for the recommended Phase 1 core path. [VERIFIED: python stdlib usage]

## Architecture Patterns

### Recommended Project Structure
```text
core/
├── artifact_io.py      # lock, stage, validate, replace, snapshot, rollback
├── artifact_schema.py  # schema version, required-field checks, manifest helpers
└── failure_policy.py   # exception classification, retry/result recording

tests/
├── test_artifact_io.py
├── test_schema_guard.py
└── test_rollback.py
```

This fits the repo's existing pattern of keeping reusable logic in `core/` while entry-point scripts stay thin. [VERIFIED: ARCHITECTURE.md:178-239][VERIFIED: CONVENTIONS.md:171-189]

### Write Targets to Plan Around

| Target | Current Role | Current Writers | Planning Decision |
|--------|--------------|-----------------|------------------|
| `docs/data_base.json` | Full snapshot source. [VERIFIED: fast_data_gen.py:295-302][VERIFIED: create_medium_data.py:11-19] | `fast_data_gen.py`, `update_single_stock.py`. [VERIFIED: fast_data_gen.py:295-302][VERIFIED: update_single_stock.py:171-201] | Make this the canonical mutable dataset. [VERIFIED: current derivation chain] |
| `docs/data.json` | Main published subset consumed by dashboard. [VERIFIED: export_canslim.py:23][VERIFIED: quick_auto_update.py:22-116] | `export_canslim.py`, `quick_data_gen.py`, `quick_auto_update.py`, `quick_auto_update_enhanced.py`, `verify_local.py`, derived from `create_medium_data.py`. [VERIFIED: export_canslim.py:663-744][VERIFIED: quick_data_gen.py:281-285][VERIFIED: quick_auto_update.py:115-116][VERIFIED: quick_auto_update_enhanced.py:217-232][VERIFIED: verify_local.py:98-104][VERIFIED: create_medium_data.py:47-49] | Stop direct writes; generate only through shared publish helper. [VERIFIED: current fragmentation] |
| `docs/data_light.json` | Lightweight derivative. [VERIFIED: create_light_data.py:11-42][VERIFIED: quick_auto_update.py:120-145] | `create_light_data.py`, `quick_auto_update.py`, `quick_auto_update_enhanced.py`. [VERIFIED: create_light_data.py:35-37][VERIFIED: quick_auto_update.py:143-144][VERIFIED: quick_auto_update_enhanced.py:269-270] | Derive from canonical snapshot under same lock. [VERIFIED: artifact dependency chain] |
| `docs/data.json.gz` | Compressed derivative. [VERIFIED: compress_data.py:17-41] | `compress_data.py` and workflows commit it. [VERIFIED: compress_data.py:17-41][VERIFIED: update_data.yml:81-82][VERIFIED: on_demand_update.yml:44] | Regenerate after validated `data.json`; publish with same run ID. [VERIFIED: current pipeline][ASSUMED] |
| `docs/update_summary.json` | Run summary artifact. [VERIFIED: quick_auto_update.py:156-183][VERIFIED: quick_auto_update_enhanced.py:280-313] | `quick_auto_update.py`, `quick_auto_update_enhanced.py`. [VERIFIED: quick_auto_update.py:175-176][VERIFIED: quick_auto_update_enhanced.py:305-306] | Promote as a required safety artifact with failure counts and rollback pointer. [VERIFIED: SAFE-02/04 goals][ASSUMED] |

### Pattern 1: Single Publish Transaction
**What:** All scripts call one helper that acquires an exclusive lock, writes staged files in the target directory, validates them, then promotes them with `os.replace`. [VERIFIED: python3 fcntl docstrings][CITED: https://docs.python.org/3/library/os.html#os.replace]

**When to use:** Every write touching `docs/data_base.json`, `docs/data.json`, `docs/data_light.json`, `docs/data.json.gz`, or `docs/update_summary.json`. [VERIFIED: current write inventory]

**Recommended lock strategy:** Use one repo-wide publish lock such as `docs/.publish.lock` for the whole artifact bundle, not one lock per file, because current scripts read-modify-write multiple related files. [VERIFIED: quick_auto_update.py:19-176][VERIFIED: quick_auto_update_enhanced.py:25-313][VERIFIED: create_medium_data.py:10-63][VERIFIED: create_light_data.py:11-42]

**Example:**
```python
# Source: Python stdlib docs for fcntl/tempfile/os.replace
from __future__ import annotations

import fcntl
import json
import os
import tempfile
from contextlib import contextmanager
from pathlib import Path


@contextmanager
def publish_lock(lock_path: Path):
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with open(lock_path, "a+", encoding="utf-8") as lock_file:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


def atomic_json_write(target: Path, payload: dict) -> None:
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        dir=target.parent,
        delete=False,
    ) as tmp:
        json.dump(payload, tmp, ensure_ascii=False, indent=2)
        tmp.flush()
        os.fsync(tmp.fileno())
        tmp_name = tmp.name
    os.replace(tmp_name, target)
```

### Pattern 2: Schema Envelope + Resume Validator
**What:** Put schema metadata at the top level and validate stock records before resume skips them. [VERIFIED: export_canslim.py:557-565][VERIFIED: docs/data.json schema probe]

**When to use:** Any script that resumes from prior output or merges incremental updates. [VERIFIED: export_canslim.py:531-565][VERIFIED: CONCERNS.md:312-330]

**Recommended option:** Use semantic schema versions (`1.0`, `1.1`, `2.0`) with this policy: additive fields bump minor; breaking shape changes bump major; resume is allowed only when major matches and required-field validation passes. [ASSUMED]

**Schema options to plan explicitly:**

| Option | Pros | Cons | Recommendation |
|--------|------|------|----------------|
| Integer version only | Simple. [ASSUMED] | Any field addition usually forces full rebuild or unsafe skip logic. [VERIFIED: CONCERNS.md:317-330] | Not recommended. [VERIFIED: resume risk] |
| Semver-like string + required-field validator | Handles additive fields safely and keeps skip logic explicit. [ASSUMED] | Slightly more code. [ASSUMED] | **Recommended.** [ASSUMED] |
| Content-hash manifest of required paths | Very precise. [ASSUMED] | Higher complexity than Phase 1 needs. [ASSUMED] | Defer unless resume logic becomes much more dynamic. [ASSUMED] |

**Recommended envelope:**
```json
{
  "schema_version": "1.0",
  "artifact_kind": "data_base",
  "run_id": "2026-04-18T12:00:00Z",
  "generated_at": "2026-04-18T12:00:00Z",
  "stocks": {}
}
```

### Pattern 3: Last-Good Snapshot Promotion
**What:** Keep a validated copy of the most recent good artifact bundle outside `docs/`, then promote new artifacts only after validation succeeds. [VERIFIED: backup artifact inventory][VERIFIED: POST_MORTEM_20260415.md:54-56]

**When to use:** Every scheduled or on-demand publish. [VERIFIED: update_data.yml:34-89][VERIFIED: on_demand_update.yml:36-46]

**Recommended rollback layout:** `backups/last_good/{data_base.json,data.json,data_light.json,data.json.gz,update_summary.json,manifest.json}`. [ASSUMED]

### Anti-Patterns to Avoid

- **Locking only `data.json`:** Current scripts also update `data_base.json`, `data_light.json`, `data.json.gz`, and `update_summary.json`, so a single-file lock still allows bundle inconsistency. [VERIFIED: fast_data_gen.py:295-302][VERIFIED: quick_auto_update.py:115-176][VERIFIED: quick_auto_update_enhanced.py:217-306]
- **In-place `json.dump` to live artifacts:** Existing in-place writes can leave partial or corrupt files if serialization fails mid-write. [VERIFIED: export_canslim.py:663-744][VERIFIED: POST_MORTEM_20260415.md:29-34]
- **Resume by ticker existence only:** `export_canslim.py` already had to special-case `grid_strategy` because existence checks were too weak. [VERIFIED: export_canslim.py:557-565]
- **Using workflow scheduling alone as the lock:** GitHub workflow concurrency prevents overlapping runs in Actions, but not local/manual scripts on the same checkout. [CITED: https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/control-workflow-concurrency][VERIFIED: local direct-run scripts]

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Cross-script mutual exclusion | Ad hoc `.lock` file existence checks with polling only. [ASSUMED] | `fcntl.flock`/`lockf` around a real lock file. [VERIFIED: python3 fcntl docstrings] | The stdlib already exposes exclusive/shared locking and non-blocking behavior. [VERIFIED: python3 fcntl docstrings] |
| Atomic publish | Direct overwrite or append-to-live-file flows. [VERIFIED: export_canslim.py:663-744][VERIFIED: quick_auto_update.py:115-176] | Same-directory temp write + `os.replace`. [CITED: https://docs.python.org/3/library/os.html#os.replace][VERIFIED: python3 tempfile.NamedTemporaryFile docstring] | This is the standard safe pattern for replacing files on POSIX. [CITED: https://docs.python.org/3/library/os.html#os.replace] |
| Exception reporting | `except: pass` or `except: return default`. [VERIFIED: repo-wide bare except grep] | Specific exception types plus `logger.exception` for unexpected failures. [VERIFIED: python3 logging.Logger.exception docstring] | Silent fallback is exactly what Phase 1 is trying to remove. [VERIFIED: SAFE-02][VERIFIED: CONCERNS.md:31-55] |
| Resume compatibility | “Ticker exists, skip it.” [VERIFIED: export_canslim.py:557-565][VERIFIED: CONCERNS.md:317-330] | Version-aware validator with required-field checks. [VERIFIED: docs/data.json schema probe][ASSUMED] | Presence-only resume causes partial schema drift. [VERIFIED: CONCERNS.md:317-330] |

**Key insight:** Phase 1 should not invent a new orchestration framework; it should centralize existing file I/O rules so every current entry point can share them. [VERIFIED: copilot-instructions.md:10-16][VERIFIED: ROADMAP.md:153-161]

## Common Pitfalls

### Pitfall 1: Fixing the workflow but not the scripts
**What goes wrong:** Adding GitHub Actions concurrency without changing local/manual writers still leaves corruption windows. [CITED: https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/control-workflow-concurrency][VERIFIED: local writer inventory]  
**Why it happens:** Current writes happen from normal Python scripts, not only scheduled workflows. [VERIFIED: export_canslim.py, quick_data_gen.py, quick_auto_update.py, quick_auto_update_enhanced.py, verify_local.py, update_single_stock.py]  
**How to avoid:** Make every writer import the same publish helper before changing workflow YAML. [VERIFIED: current fragmentation]  
**Warning signs:** Phase 1 PR changes `.github/workflows/*.yml` but leaves direct `open(..., 'w')` calls in writer scripts. [VERIFIED: current write inventory]

### Pitfall 2: Replacing bare exceptions with broad `except Exception` and no surfaced outcome
**What goes wrong:** Logs improve, but the run still “succeeds” with hidden data loss. [VERIFIED: CONCERNS.md:45-54][VERIFIED: POST_MORTEM_20260415.md:29-34]  
**Why it happens:** Failure counts are not accumulated into a publish decision. [VERIFIED: quick_auto_update.py:150-183][VERIFIED: export_canslim.py:666-668]  
**How to avoid:** Track per-run counts for retries, soft failures, fatal failures, and skipped stocks; fail publish when thresholds are crossed. [ASSUMED]  
**Warning signs:** `logger.error(...)` exists, but `update_summary.json` or exit codes never reflect the failures. [VERIFIED: current scripts]

### Pitfall 3: Adding `schema_version` but not validating stock completeness
**What goes wrong:** New fields still go missing on resumed stocks because the version matches while the record shape does not. [VERIFIED: CONCERNS.md:317-330]  
**Why it happens:** Resume safety is about field presence, not just top-level version labels. [VERIFIED: export_canslim.py:557-565][VERIFIED: docs/data.json schema probe]  
**How to avoid:** Validate required stock paths for the current schema before skipping. [ASSUMED]  
**Warning signs:** Dashboard fields appear for newly computed stocks but stay absent for resumed ones. [VERIFIED: CONCERNS.md:327-330]

### Pitfall 4: Keeping backups that were never validated
**What goes wrong:** Rollback restores an already-bad file, as seen by tiny rescue artifacts already in `docs/`. [VERIFIED: backup artifact inventory]  
**Why it happens:** Current backup creation copies the prior file without validating it and stores multiple rescue artifacts with no manifest. [VERIFIED: export_canslim.py:727-735][VERIFIED: backup artifact inventory]  
**How to avoid:** Validate snapshot JSON, schema, and minimum stock counts before declaring it `last_good`. [ASSUMED]  
**Warning signs:** Backup directories contain 86-byte or similarly tiny JSON files. [VERIFIED: backup artifact inventory]

## Code Examples

Verified patterns from official or local authoritative sources:

### Lock + atomic replace
```python
# Source: Python stdlib docs/help for fcntl.flock, tempfile.NamedTemporaryFile, os.replace
with publish_lock(Path("docs/.publish.lock")):
    atomic_json_write(Path("docs/data_base.json"), data_base_payload)
    atomic_json_write(Path("docs/data.json"), data_payload)
    atomic_json_write(Path("docs/data_light.json"), light_payload)
```

### Explicit unexpected-failure logging
```python
# Source: python3 logging.Logger.exception docstring
try:
    response = requests.get(url, timeout=15)
    response.raise_for_status()
except requests.RequestException:
    logger.exception("Institutional fetch failed for %s", ticker)
    failure_counts["institutional_fetch"] += 1
    return None
```

### Schema-aware resume guard
```python
# Source: current export resume logic + Phase 1 recommendation
REQUIRED_CANSLIM_KEYS = {"score", "mansfield_rs", "grid_strategy"}

def can_resume(stock_entry: dict, schema_version: str) -> bool:
    if stock_entry.get("_schema_version") != schema_version:
        return False
    canslim = stock_entry.get("canslim", {})
    return REQUIRED_CANSLIM_KEYS.issubset(canslim.keys())
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| In-place overwrite of live JSON. [VERIFIED: export_canslim.py:663-744][VERIFIED: quick_auto_update.py:115-176] | Stage + validate + `os.replace`. [CITED: https://docs.python.org/3/library/os.html#os.replace] | Long-standing Python/POSIX guidance. [CITED: https://docs.python.org/3/library/os.html#os.replace] | Prevents partial live-file corruption. [CITED: https://docs.python.org/3/library/os.html#os.replace] |
| Silent `except:` fallback. [VERIFIED: repo-wide bare except grep] | Specific exceptions + logged traceback. [VERIFIED: python3 logging.Logger.exception docstring] | Long-standing stdlib capability. [VERIFIED: python3 logging.Logger.exception docstring] | Makes retry and publish decisions observable. [VERIFIED: SAFE-02] |
| Resume by ticker presence. [VERIFIED: CONCERNS.md:317-330] | Resume by schema compatibility + required fields. [ASSUMED] | Current best practice for file-based snapshots. [ASSUMED] | Allows additive schema evolution without half-updated records. [ASSUMED] |

**Deprecated/outdated:**
- `os.rename(temp_file, 'docs/data.json')` as the primary promotion API is outdated here; prefer `os.replace` for explicit destination overwrite behavior. [VERIFIED: quick_auto_update_enhanced.py:232][CITED: https://docs.python.org/3/library/os.html#os.replace]
- Timestamped `.bak` copies without validation or manifest are inadequate as a rollback system. [VERIFIED: export_canslim.py:727-735][VERIFIED: backup artifact inventory]

## Open Questions

1. **Should Phase 1 support every legacy writer, or deprecate some immediately?**
   - What we know: At least six entry points still write publish artifacts directly, and several duplicate scoring logic. [VERIFIED: current write inventory][VERIFIED: CONCERNS.md:7-30]
   - What's unclear: Whether maintainers still rely on `quick_data_gen.py`, `quick_auto_update.py`, and `verify_local.py` as first-class tools. [ASSUMED]
   - Recommendation: Decide this in Wave 0; if a script is kept, it must use the shared writer; if not, explicitly deprecate it. [ASSUMED]

2. **Should rollback restore only docs artifacts, or also the canonical base snapshot?**
   - What we know: `data_base.json` is already the upstream for `data.json`/`data_light.json` in the newer path. [VERIFIED: fast_data_gen.py:295-302][VERIFIED: create_medium_data.py:10-63][VERIFIED: create_light_data.py:11-42]
   - What's unclear: Whether a rollback should restore `data_base.json` directly or regenerate derivatives from the saved base snapshot. [ASSUMED]
   - Recommendation: Save and restore the full bundle in Phase 1, then simplify later if the canonical path is stabilized. [ASSUMED]

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3 | All Phase 1 tooling and scripts. [VERIFIED: repo codebase] | ✓ [VERIFIED: `python3 --version`] | 3.12.5 local; workflow uses 3.11. [VERIFIED: `python3 --version`][VERIFIED: update_data.yml:23-32] | — |
| pytest | Validation architecture. [VERIFIED: requirements.txt:4] | ✓ [VERIFIED: `pytest --version`] | 9.0.2 local. [VERIFIED: `pytest --version`] | `python3 -m pytest` if PATH differs. [ASSUMED] |
| GitHub Actions workflow concurrency | Remote overlap protection. [VERIFIED: workflows exist] | Configurable, not currently enabled. [VERIFIED: update_data.yml:1-90][VERIFIED: on_demand_update.yml:1-54] | — | File locks still protect same-checkout runs. [ASSUMED] |

**Missing dependencies with no fallback:**
- None for planning and local validation. [VERIFIED: environment probes]

**Missing dependencies with fallback:**
- Workflow-level concurrency is missing today, but same-checkout file locks still provide local safety once implemented. [VERIFIED: current workflow YAML][ASSUMED]

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.0.2 installed locally; dependency declared in `requirements.txt`. [VERIFIED: `pytest --version`][VERIFIED: requirements.txt:4] |
| Config file | none detected. [VERIFIED: test config file probe] |
| Quick run command | `PYTHONPATH=. pytest tests/test_logic_v2.py -q` [VERIFIED: POST_MORTEM_20260415.md:39-44][VERIFIED: tests/test_logic_v2.py] |
| Full suite command | `PYTHONPATH=. pytest -q` currently fails during collection because `tests/test_institutional_logic.py` imports a missing symbol. [VERIFIED: pytest --collect-only output][VERIFIED: tests/test_institutional_logic.py:9-70] |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| SAFE-01 | Concurrent writers do not corrupt artifacts. [VERIFIED: REQUIREMENTS.md:10] | unit + integration | `PYTHONPATH=. pytest tests/test_artifact_io.py -q` | ❌ Wave 0 |
| SAFE-02 | API/data failures are logged and summarized. [VERIFIED: REQUIREMENTS.md:11] | unit | `PYTHONPATH=. pytest tests/test_failure_policy.py -q` | ❌ Wave 0 |
| SAFE-03 | Resume logic rejects incompatible or incomplete schema states. [VERIFIED: REQUIREMENTS.md:12] | unit | `PYTHONPATH=. pytest tests/test_schema_guard.py -q` | ❌ Wave 0 |
| SAFE-04 | Publish can rollback to last good snapshot. [VERIFIED: REQUIREMENTS.md:13] | integration | `PYTHONPATH=. pytest tests/test_rollback.py -q` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `PYTHONPATH=. pytest tests/test_logic_v2.py -q` plus the new Phase 1 safety tests touched by the change. [VERIFIED: POST_MORTEM_20260415.md:39-44][ASSUMED]
- **Per wave merge:** `PYTHONPATH=. pytest -q` after fixing current collection errors. [VERIFIED: pytest --collect-only output][ASSUMED]
- **Phase gate:** `PYTHONPATH=. pytest -q && python3 verify_local.py` once `verify_local.py` also uses the shared writer. [VERIFIED: POST_MORTEM_20260415.md:39-56][ASSUMED]

### Wave 0 Gaps
- [ ] `tests/test_artifact_io.py` — lock acquisition, timeout, same-directory atomic replace, partial-write prevention. [ASSUMED]
- [ ] `tests/test_failure_policy.py` — logged exception coverage and publish-fail thresholds. [ASSUMED]
- [ ] `tests/test_schema_guard.py` — schema version compatibility and required-field validation. [ASSUMED]
- [ ] `tests/test_rollback.py` — snapshot restore and manifest verification. [ASSUMED]
- [ ] Fix or quarantine `tests/test_institutional_logic.py` because it currently breaks collection. [VERIFIED: pytest --collect-only output][VERIFIED: tests/test_institutional_logic.py:9-70]

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no — Phase 1 is file/process safety, not user auth. [VERIFIED: REQUIREMENTS.md:10-13] | — |
| V3 Session Management | no — no session layer is introduced. [VERIFIED: repo architecture] | — |
| V4 Access Control | no — scope is local scripts and workflow coordination. [VERIFIED: Phase 1 goal] | — |
| V5 Input Validation | yes — ticker input, JSON structure, and schema validation all matter. [VERIFIED: update_single_stock.py:88-92][VERIFIED: docs/data.json schema probe] | Regex ticker validation plus explicit schema validation. [VERIFIED: update_single_stock.py:88-92][ASSUMED] |
| V6 Cryptography | yes — integrity checks can use `hashlib.sha256`; do not invent custom checksums. [ASSUMED] | Python stdlib `hashlib`. [ASSUMED] |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Concurrent file overwrite corrupts JSON. [VERIFIED: POST_MORTEM_20260415.md:29-34][VERIFIED: current write inventory] | Tampering / DoS | Exclusive publish lock + atomic replace + validation before promotion. [VERIFIED: python3 fcntl docstrings][CITED: https://docs.python.org/3/library/os.html#os.replace] |
| Silent fallback hides provider failure and publishes degraded data. [VERIFIED: CONCERNS.md:31-55] | Repudiation / Integrity | Specific exception logging, retry accounting, and publish-fail thresholds. [VERIFIED: python3 logging.Logger.exception docstring][ASSUMED] |
| Unvalidated issue-title ticker input reaches on-demand update path. [VERIFIED: on_demand_update.yml:28-38][VERIFIED: update_single_stock.py:88-92] | Input validation / Tampering | Keep regex validation in `update_single_stock.py` and reject unexpected ticker formats early. [VERIFIED: update_single_stock.py:88-92] |

## Sources

### Primary (HIGH confidence)
- `REQUIREMENTS.md` — Phase 1 requirement definitions. [VERIFIED: .planning/REQUIREMENTS.md]
- `ROADMAP.md` — Phase 1 goal, success criteria, and sequencing. [VERIFIED: .planning/ROADMAP.md]
- `STATE.md` — active TODOs and known issues for Phase 1. [VERIFIED: .planning/STATE.md]
- `CONCERNS.md` — technical debt, resume/schema risks, and file coordination issues. [VERIFIED: .planning/codebase/CONCERNS.md]
- `POST_MORTEM_20260415.md` — real corruption, serialization, and validation failures. [VERIFIED: POST_MORTEM_20260415.md]
- `export_canslim.py`, `fast_data_gen.py`, `quick_data_gen.py`, `quick_auto_update.py`, `quick_auto_update_enhanced.py`, `update_single_stock.py`, `verify_local.py` — current write paths and failure handling. [VERIFIED: code file inspection]
- Python stdlib docs/help for `fcntl`, `tempfile.NamedTemporaryFile`, `logging.Logger.exception`, and `os.replace`. [VERIFIED: python3 docstrings][CITED: https://docs.python.org/3/library/os.html#os.replace]
- GitHub Actions concurrency docs. [CITED: https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/control-workflow-concurrency]

### Secondary (MEDIUM confidence)
- PyPI JSON metadata for `pytest` and `jsonschema` version verification. [VERIFIED: PyPI JSON queries]

### Tertiary (LOW confidence)
- None.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `data.json.gz` should be regenerated before the final publish marker is written. [ASSUMED] | Standard Stack / Write Targets | Could cause minor artifact ordering rework. |
| A2 | Semantic schema versions (`major.minor`) are the best fit for Phase 1 resume compatibility. [ASSUMED] | Architecture Patterns | Could change validator design or force a simpler integer version. |
| A3 | `backups/last_good/` outside `docs/` is the best rollback storage location. [ASSUMED] | Architecture Patterns | Could require a different backup path if deployment or git policies differ. |
| A4 | Publish failure thresholds should be enforced via per-run failure counters. [ASSUMED] | Common Pitfalls / Security Domain | Could affect exit-code policy and summary format. |

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — recommendations rely mostly on Python stdlib and repo-observed workflow patterns. [VERIFIED: codebase + stdlib docs]
- Architecture: HIGH — write targets and race conditions are directly observable in the current repo. [VERIFIED: current write inventory]
- Pitfalls: HIGH — backed by real post-mortem incidents, stale backups, missing schema metadata, and current bare-except sites. [VERIFIED: POST_MORTEM_20260415.md][VERIFIED: backup artifact inventory][VERIFIED: docs/data.json schema probe][VERIFIED: repo-wide bare except grep]

**Research date:** 2026-04-18 [VERIFIED: system date]  
**Valid until:** 2026-05-18 for repo-specific observations; re-check external docs if implementation starts later. [ASSUMED]
