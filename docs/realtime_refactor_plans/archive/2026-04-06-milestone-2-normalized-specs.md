# Milestone 2 Normalized Specs

Date: 2026-04-06

Related checklist milestone:
- `docs/realtime_refactor_checklist.md` Milestone 2

## Current State

- The repo now has planner-facing biology dataclasses in
  `src/flytetest/planner_types.py`, but it does not yet have a normalized spec
  layer for planning-time and replay-time metadata.
- The current registry remains the machine-readable source for runnable task and
  workflow metadata, and the current MCP showcase planner should stay unchanged
  in this milestone.

## Target State

- A stable spec module exists under `src/flytetest/` with:
  `TaskSpec`, `WorkflowSpec`, `BindingPlan`, `ExecutionProfile`,
  `ResourceSpec`, `RuntimeImageSpec`, and `GeneratedEntityRecord`.
- The spec layer is explicitly planning-time and metadata-time only.
- `TaskSpec`, `WorkflowSpec`, and `BindingPlan` serialize and round-trip
  cleanly.
- `WorkflowSpec` can represent:
  - a direct registered-workflow selection
  - a composition built from registered stages
  - a saved generated workflow artifact

## Implementation Steps

1. Add a normalized spec module with serialization helpers and small supporting
   node/edge/input field dataclasses where needed.
2. Keep the module additive and separate from the current executor, registry,
   and narrow MCP showcase behavior.
3. Add synthetic tests for:
   - spec serialization round-trips
   - a registered workflow example
   - a registered-stage composition example
   - a saved generated workflow example
4. Update README and the realtime checklist to describe the new layer honestly.

## Validation Steps

- Run focused unit tests for the new spec module plus the existing compatibility
  suites.
- Run `py_compile` on the touched Python and test files.

## Blockers Or Assumptions

- This slice intentionally does not define resolver behavior yet.
- The new spec layer should not be wired into execution or registry mutation in
  this milestone; it is a contract and serialization layer only.
