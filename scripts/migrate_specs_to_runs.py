#!/usr/bin/env python3
"""Migrate ``.runtime/specs/<recipe_id>.json`` into ``.runtime/runs/<recipe_id>/spec.json``.

One-shot migration for the Slurm UX rollout Phase 0 step 01 canonical run-dir
layout.  After this script runs successfully, ``.runtime/specs/`` is removed
when empty.  Idempotent — safe to re-run; existing canonical-layout specs are
left in place and conflicts are reported rather than overwritten.

Usage::

    python scripts/migrate_specs_to_runs.py [project_root]

When *project_root* is omitted the migration runs against ``.runtime/`` under
the current working directory.
"""

from __future__ import annotations

import sys
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    args = list(argv if argv is not None else sys.argv[1:])
    project_root = Path(args[0]) if args else Path.cwd()
    runtime_root = project_root / ".runtime"
    specs_dir = runtime_root / "specs"
    runs_dir = runtime_root / "runs"

    if not specs_dir.exists():
        print(f"{specs_dir} does not exist; nothing to migrate.")
        return 0

    runs_dir.mkdir(parents=True, exist_ok=True)
    moved = 0
    skipped = 0
    for spec_file in sorted(specs_dir.glob("*.json")):
        recipe_id = spec_file.stem
        run_dir = runs_dir / recipe_id
        target = run_dir / "spec.json"
        if target.exists():
            print(f"Skipping {spec_file.name}: {target} already exists")
            skipped += 1
            continue
        run_dir.mkdir(parents=True, exist_ok=True)
        spec_file.rename(target)
        moved += 1
        print(f"Moved {spec_file} -> {target}")

    leftover = list(specs_dir.iterdir()) if specs_dir.exists() else []
    if not leftover:
        specs_dir.rmdir()
        print(f"Removed empty {specs_dir}")
    else:
        names = ", ".join(p.name for p in leftover)
        print(f"Leaving {specs_dir} in place; non-spec entries remain: {names}")

    print(f"Migration complete: {moved} spec(s) moved, {skipped} skipped.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
