---
status: investigating
trigger: "The retry queue in `.orchestration/rotation_state.json` shows multiple failures with `AttributeError: 'CanslimEngine' object has no attribute 'inst_cache'`."
created: 2026-04-22T00:00:00Z
updated: 2026-04-22T00:00:00Z
---

## Current Focus

hypothesis: `CanslimEngine` in `export_canslim.py` is missing `inst_cache` initialization in `__init__`.
test: Read `export_canslim.py` to check `__init__` and usages.
expecting: `inst_cache` is used but not initialized in `__init__`.
next_action: Read `export_canslim.py` and `.orchestration/rotation_state.json`.

## Symptoms

expected: `CanslimEngine` should have `inst_cache` initialized and used safely.
actual: `AttributeError: 'CanslimEngine' object has no attribute 'inst_cache'`.
errors: `AttributeError: 'CanslimEngine' object has no attribute 'inst_cache'`
reproduction: Run `python3 export_canslim.py --symbols 1734`.
started: Recently reported by user via retry queue.

## Eliminated

## Evidence

## Resolution

root_cause: 
fix: 
verification: 
files_changed: []
