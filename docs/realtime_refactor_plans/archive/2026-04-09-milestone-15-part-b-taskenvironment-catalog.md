# Milestone 15 Part B: TaskEnvironment Catalog Refactor

Date: 2026-04-09
Status: Complete

Related checklist context:
- `docs/realtime_refactor_checklist.md` Milestone 15

Implementation note:
- This slice does not change the Milestone 15 planner/composition contract.
- It refactors the task-runtime layer so new task families can inherit shared
  `TaskEnvironment` defaults from a single declarative catalog.
- A couple of heavier families now carry explicit resource and description
  overrides so the catalog reflects real workload differences, not just names.
- Compatibility aliases remain in place for current imports and manifests, but
  newer task families should prefer the specific environment names in their own
  docs and manifest records.

## Current State

- `src/flytetest/config.py` previously declared each task environment directly
  with repeated `flyte.TaskEnvironment(...)` calls.
- The repository already used `@env.task` / `@..._env.task` consistently, but
  the environment definitions themselves were still repetitive.
- The refactor opportunity was to centralize shared task-environment defaults
  and make future task-family additions more declarative.
- `WORKFLOW_NAME` still exists as a legacy alias for the original RNA-seq
  baseline, but it should be treated as compatibility-only rather than as the
  model for newer milestone-specific task families.

## Target State

- A single helper constructs Flyte `TaskEnvironment` instances from a compact
  catalog entry.
- Shared defaults such as task-scoped env vars and a baseline resource policy
  are applied in one place.
- Heavy families can override the shared baseline with explicit resource and
  description settings when the workload already justifies it.
- The catalog is no longer purely uniform; it now reflects a small amount of
  real runtime differentiation between heavy and light families.
- Environment names remain available through compatibility aliases so current
  task modules and manifests continue to work unchanged.
- The broader refactor roadmap now includes the 18a / 18b / 18c utility
  cleanup lane before Milestone 15, so later planner work should assume those
  helper abstractions exist.

## Scope

In scope:

- Add a declarative task-environment catalog in `src/flytetest/config.py`.
- Centralize shared defaults for task-family environments.
- Add explicit per-family resource and description overrides for the heaviest
  current families.
- Preserve compatibility aliases such as `WORKFLOW_NAME` and the exported
  environment variables used by current task and workflow modules.
- Add tests that verify the catalog is populated and the aliases stay stable.
- Update user-facing docs to mention the shared task-defaults layer.

Out of scope:

- Changing the Milestone 15 composition planner contract.
- Pinning a single repository-wide container image.
- Removing current `@env.task` compatibility usage.

## Implementation Steps

1. Add a shared `TaskEnvironmentConfig`/catalog layer in
   `src/flytetest/config.py`.
2. Centralize shared env vars and resource defaults in one helper.
3. Add explicit overrides for the heaviest current task families so the
   catalog reflects real workload differences.
4. Rebind the existing environment exports from the catalog so current imports
   stay valid.
5. Add focused tests for the shared defaults, per-family overrides, and alias
   stability.
6. Update the README so the shared-default behavior is documented honestly.

## Validation Steps

- Run `python3 -m py_compile` on touched Python files.
- Run the focused config test module.
- Keep compatibility exports and existing task modules importable.

## Blockers or Assumptions

- This slice assumes the shared defaults remain intentionally modest so they do
  not force an early packaging decision.
- If a future family needs stronger defaults, the catalog can carry per-family
  overrides without changing the import surface.
- Any eventual removal of `WORKFLOW_NAME` should be treated as a separate
  compatibility migration, not as a side effect of this catalog refactor.
