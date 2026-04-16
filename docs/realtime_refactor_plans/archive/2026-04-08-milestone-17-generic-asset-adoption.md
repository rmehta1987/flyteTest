# Milestone 17 Generic Asset Adoption and Legacy Alias Retention

Date: 2026-04-08
Status: Complete

Related checklist milestone:
- `docs/realtime_refactor_checklist.md` Milestone 17

Implementation note:
- This slice should move the internal asset surface toward the generic biology
  names introduced in Milestone 14 while keeping the legacy aliases available
  for replay and compatibility.
- It should prefer the generic names in planner adapters, resolver outputs,
  and local workflow-produced manifests without rewriting historical records.
- The milestone should be a migration phase, not a compatibility break.

## Current State

- Milestone 14 is the compatibility-preserving alias and provenance slice, so
  the generic asset names and legacy names can both load today.
- Planner adapters, resolver behavior, and local workflow outputs still carry a
  mix of vendor-specific and generic concepts where the migration has not yet
  been completed.
- Historical run records and manifests must remain replayable, so the generic
  adoption work has to be additive and careful.

## Target State

- Planner adapters emit the generic biology-facing asset names by default when
  the semantic meaning is already known.
- Local workflow outputs and manifest-producing helpers prefer the generic
  asset vocabulary while keeping legacy aliases available.
- Resolver and replay paths continue to accept historical asset names without
  rewriting manifests.
- Tests cover both legacy alias loading and generic-name round-tripping so the
  migration stays compatibility-safe.

## Scope

In scope:

- Update planner adapters to prefer generic asset names in new outputs.
- Update local workflow outputs and manifest-producing helpers to use the
  generic asset types.
- Keep legacy aliases available so older manifests and callers still work.
- Add tests that prove both legacy and generic forms load and round-trip.
- Update docs so the migration is described honestly.

Out of scope:

- Removing legacy aliases.
- Rewriting old manifests.
- Introducing new biological workflow families.
- Changing the underlying compatibility model from Milestone 14.

## Implementation Steps

1. Audit `src/flytetest/planner_adapters.py`, `src/flytetest/resolver.py`,
   `src/flytetest/types/assets.py`, `src/flytetest/tasks/`, and
   `src/flytetest/workflows/` to identify where legacy asset names still leak
   into new outputs.
2. Update planner adapters so they emit generic asset classes by default while
   retaining legacy aliases for compatibility.
3. Update local workflow outputs and manifest-producing helpers to construct
   the generic names where the semantic type is already known.
4. Keep resolver and replay paths able to accept historical names without any
   manifest rewrite step.
5. Add tests for generic-name round-tripping and legacy alias replay.
6. Update README, capability maturity notes, and the checklist when the
   migration lands.

## Validation Steps

- Run `python3 -m py_compile` on touched Python files if code changes land.
- Run focused tests:
  - `python3 -m unittest tests.test_planner_adapters`
  - `python3 -m unittest tests.test_resolver`
  - `python3 -m unittest tests.test_spec_executor`
- Run `git diff --check`.
- Expand coverage if the migration touches shared planner or manifest
  contracts.

## Blockers or Assumptions

- This milestone assumes the generic names from Milestone 14 are already
  available and loader-compatible.
- It assumes historical manifests must remain replayable throughout the
  migration.
- If a legacy alias is still required for a caller, it should remain available
  until that caller is deliberately migrated.
