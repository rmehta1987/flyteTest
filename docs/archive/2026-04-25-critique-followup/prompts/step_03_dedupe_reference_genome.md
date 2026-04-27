# Step 03 — Collapse duplicate `ReferenceGenome`

## Goal

Have exactly one `class ReferenceGenome` in the codebase.

## Current state

- `src/flytetest/planner_types.py:42` —
  `class ReferenceGenome(PlannerSerializable)`. Used by planner code paths
  and asset round-trip (it has the serialization mixin).
- `src/flytetest/types/assets.py:49` — `class ReferenceGenome` (plain
  dataclass, no mixin). Different shape.

## Decision rule

Keep the `planner_types.py` version. The serialization mixin is required for
the manifest round-trip; the `types/assets.py` version diverged without
clear motivation and breaks at the asset boundary.

## How

1. `rg -n 'from flytetest.types.assets import .*ReferenceGenome|from flytetest\.types\.assets import' src/flytetest tests`
   to enumerate every import site of the `assets.py` version.
2. For each site, switch to
   `from flytetest.planner_types import ReferenceGenome`.
3. Verify field compatibility — if the two definitions differ in fields,
   stop and report rather than silently mapping fields.
4. Delete the `class ReferenceGenome` block from `src/flytetest/types/assets.py`.
5. Run the full suite: `PYTHONPATH=src python3 -m pytest tests/ -q`.

## Acceptance

- `rg '^class ReferenceGenome' src/flytetest/` returns one match
  (`planner_types.py:42`).
- All 887 tests pass.

## If the two definitions diverge in fields

Stop. Document the divergence in a one-paragraph comment on the checklist
and ask before merging. The cost of silently aligning two slightly-different
biology types is higher than living with the duplicate.

## Commit

`critique-followup: dedupe ReferenceGenome (consolidate on planner_types)`
