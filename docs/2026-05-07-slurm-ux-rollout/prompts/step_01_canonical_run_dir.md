# Step 01 — Canonical run dir + recipe-id hash + SCIENTIST_GUIDE fix

## Context

flyteTest currently splits a single submission's artifacts across two directories:
- `.runtime/specs/<recipe_id>.json` — the frozen recipe
- `.runtime/runs/<recipe_id>/slurm_run_record.json` — submission/lifecycle record + Slurm stdout/stderr files

Investigating a failure means `cd`-ing between the two. This step collapses the split: specs move into the run dir, `.runtime/specs/` goes away. While we're touching `spec_artifacts.py`, we also fix two related issues:
- **Recipe-id truncation collisions** when long workflow names get chopped to ~30 chars (e.g., `select_germline_short_variant_discovery` and `select_germline_short_variant_recalibration` both truncate to `select_germline_short_variant_`). Add a hash suffix when truncation kicks in.
- **`SCIENTIST_GUIDE.md` Step 6 docs bug** — line ~168 calls `run_slurm_recipe(recipe_id=..., partition=..., account=...)` but the actual signature is `(artifact_path, shared_fs_roots)`. Copying the example raises `TypeError`.

## Files to read before editing

- `src/flytetest/spec_artifacts.py` — current spec write/read (recipe_id format: `<YYYYMMDDThhmmss.mmm>Z-<target_name>`)
- `src/flytetest/spec_executor.py` — spec reads, `_submit_saved_artifact`
- `src/flytetest/planning.py` — any spec-path resolution
- `src/flytetest/server.py` — `validate_run_recipe`, `run_local_recipe`, `run_slurm_recipe`
- `SCIENTIST_GUIDE.md` lines ~155-180 (Step 6 of the "first run end-to-end" walkthrough)
- `CLAUDE.md` and `AGENTS.md` for any `.runtime/specs/` mentions

## Files to create / edit

| Action | File |
|---|---|
| Edit | `src/flytetest/spec_artifacts.py` |
| Edit | `src/flytetest/spec_executor.py` |
| Edit | `src/flytetest/planning.py` |
| Edit | `src/flytetest/server.py` |
| Create | `scripts/migrate_specs_to_runs.py` |
| Edit | tests asserting on `.runtime/specs/` paths |
| Edit | `SCIENTIST_GUIDE.md` |
| Edit | `CLAUDE.md`, `AGENTS.md` |
| Edit | `CHANGELOG.md` |

## Implementation instructions

### `src/flytetest/spec_artifacts.py`

**Spec location change:**

Current behavior writes the frozen recipe to `.runtime/specs/<recipe_id>.json`. Change so it writes to `.runtime/runs/<recipe_id>/spec.json`. The function that creates the run dir should also create it at *spec freeze time* — not just at submit time — so `prepare_run_recipe` and `run_workflow(dry_run=True)` populate the canonical location.

Update the matching reader (`_load_artifact` or equivalent) to look at the new location.

**Recipe-id hash suffix:**

The current `recipe_id` format is `<YYYYMMDDThhmmss.mmm>Z-<target_name>`. Add conditional truncation:

```python
import hashlib

_TARGET_NAME_BUDGET = 25  # chars before suffix
_HASH_DIGEST_BYTES = 2    # 4 hex chars after blake2b

def _truncate_target_name(target_name: str) -> str:
    """Return a directory-safe form of `target_name`.

    For names that fit under the budget, returned as-is.
    For longer names, truncate and append a 4-hex-char blake2b hash so two
    workflows with the same prefix don't collide on disk.
    """
    if len(target_name) <= _TARGET_NAME_BUDGET + 5:  # +5 = `-XXXX` suffix room
        return target_name
    digest = hashlib.blake2b(target_name.encode("utf-8"), digest_size=_HASH_DIGEST_BYTES).hexdigest()
    return f"{target_name[:_TARGET_NAME_BUDGET]}-{digest}"
```

Then where the `recipe_id` is assembled, replace the raw `target_name` with the truncated form. Examples:

- `prepare_reference` (short) → `prepare_reference` (unchanged)
- `select_germline_short_variant_discovery` → `select_germline_short_var-a3f7`
- `select_germline_short_variant_recalibration` → `select_germline_short_var-b1c9`

### `src/flytetest/spec_executor.py`

Update every reader of the old `.runtime/specs/<recipe_id>.json` path to point at `.runtime/runs/<recipe_id>/spec.json`. Most likely affected:

- `_submit_saved_artifact` (~line 2127)
- `_load_artifact` or whatever resolves the artifact path
- `_run_id_for_artifact` (~line 1577) — verify `.resolve()` still works post-rename

### `src/flytetest/planning.py`

Search for `.runtime/specs/` and `.specs/` references; update.

### `src/flytetest/server.py`

`validate_run_recipe`, `run_local_recipe`, `run_slurm_recipe` all read frozen spec paths. Update their resolution.

### `scripts/migrate_specs_to_runs.py`

One-shot migration of pre-existing spec files. Idempotent — safe to re-run.

```python
#!/usr/bin/env python3
"""Migrate .runtime/specs/<recipe_id>.json into .runtime/runs/<recipe_id>/spec.json.

After this script runs successfully, .runtime/specs/ is removed.
"""
from __future__ import annotations
import sys
from pathlib import Path

def main() -> int:
    root = Path(".runtime")
    specs_dir = root / "specs"
    runs_dir = root / "runs"
    if not specs_dir.exists():
        print(f"{specs_dir} does not exist; nothing to migrate.")
        return 0

    runs_dir.mkdir(parents=True, exist_ok=True)
    moved = 0
    for spec_file in specs_dir.glob("*.json"):
        recipe_id = spec_file.stem
        run_dir = runs_dir / recipe_id
        run_dir.mkdir(parents=True, exist_ok=True)
        target = run_dir / "spec.json"
        if target.exists():
            print(f"Skipping {spec_file.name}: {target} already exists")
            continue
        spec_file.rename(target)
        moved += 1
        print(f"Moved {spec_file} → {target}")

    if not any(specs_dir.iterdir()):
        specs_dir.rmdir()
        print(f"Removed empty {specs_dir}")

    print(f"Migration complete: {moved} spec(s) moved.")
    return 0

if __name__ == "__main__":
    sys.exit(main())
```

### Tests

Search for `.runtime/specs/` in `tests/` and update assertions. Most fixtures probably use `tmp_path` and don't hit this directly, but any integration test that checks where the spec ended up will need updating.

### `SCIENTIST_GUIDE.md` (line ~168)

Replace:

```
6. `run_slurm_recipe(recipe_id=..., partition=..., account=...)`

   Submits the frozen recipe via `sbatch`. Returns the run record path
   and the assigned `job_id`. Note: `partition` and `account` must come
   from you — the server will not invent them.
```

with:

```
6. `run_slurm_recipe(artifact_path=...)`

   Submits the frozen recipe via `sbatch`. Returns the run record path
   and the assigned `job_id`. The `partition` and `account` you provided
   in `resource_request` at Step 4 (recipe freeze) are baked into the
   recipe and used here automatically — no need to pass them again at
   submission time.
```

### `CLAUDE.md` and `AGENTS.md`

`rg '\.runtime/specs/'` to find all references and update to `.runtime/runs/<recipe_id>/spec.json`.

### `CHANGELOG.md`

Add a dated entry under `## Unreleased`.

## Acceptance criteria

- `python -m py_compile src/flytetest/spec_artifacts.py` exits 0
- After running `python scripts/migrate_specs_to_runs.py` on a project with prior specs, `.runtime/specs/` is gone and every spec is reachable at `.runtime/runs/<recipe_id>/spec.json`
- Fresh `prepare_run_recipe` / `run_workflow(dry_run=True)` writes to the new location
- Long workflow names (`select_germline_short_variant_discovery`) produce recipe IDs ending in `-<hash4>`; short names (`prepare_reference`) are unchanged
- `python -m pytest tests/` passes (or shows only expected, fixed-in-this-step failures)
- `SCIENTIST_GUIDE.md` Step 6 example runs without `TypeError`

## CHANGELOG entry template

```
## Unreleased

### Slurm UX rollout — Phase 0 step 01 (2026-05-07)

- [x] 2026-05-07 `spec_artifacts.py`: spec write/read paths moved from `.runtime/specs/<recipe_id>.json` to `.runtime/runs/<recipe_id>/spec.json`. Run dir created at freeze time so prepare/dry-run populate the canonical location. Eliminates the spec/run directory split.
- [x] 2026-05-07 `spec_artifacts.py`: recipe-id truncation now appends `-<hash4>` (blake2b 2-byte digest) when `target_name` exceeds 25 chars; short names unchanged. Resolves visual collisions for similarly-prefixed long workflow names.
- [x] 2026-05-07 `spec_executor.py`, `planning.py`, `server.py`: spec readers updated to new location.
- [x] 2026-05-07 `scripts/migrate_specs_to_runs.py`: one-shot migration of pre-existing spec files; idempotent.
- [x] 2026-05-07 `SCIENTIST_GUIDE.md`: Step 6 example fixed (was `run_slurm_recipe(recipe_id=..., partition=..., account=...)`, now `run_slurm_recipe(artifact_path=...)`).
- [x] 2026-05-07 `CLAUDE.md`, `AGENTS.md`: `.runtime/specs/` mentions updated.
```
