# Milestone 19 Caching and Resumability

Date: 2026-04-08
Status: Proposed

Related checklist milestone:
- `docs/realtime_refactor_checklist.md` Milestone 19

Implementation note:
- This slice should let interrupted work continue from frozen recipes and
  explicit run records without recomputing already completed stages.
- It should stay explicit and inspectable, not hidden behind mutable local
  process state.
- Cache and resume rules should be compatible with both local saved-spec
  execution and the Slurm path established earlier.
- This milestone is the prerequisite that makes execution-capable composed
  DAGs safe to expose after Milestone 15 has defined the composition preview.

## Current State

- The repo already has frozen `WorkflowSpec` and `BindingPlan` artifacts plus
  durable local result bundles.
- Milestones 13, 16, and 18 are expected to establish Slurm submission,
  lifecycle reconciliation, and retry semantics.
- There is not yet an explicit cache-key or resumability model for stage
  completion.

## Target State

- Cache keys are derived from the frozen `WorkflowSpec`, resolved inputs, and
  relevant runtime bindings or execution profile data.
- Stage completion state is persisted in run records.
- Resuming a run reuses completed stages and only reruns missing or invalidated
  work.
- Cache hits and misses are visible and testable rather than implicit.
- Local saved-spec execution and Slurm-backed execution can both honor the
  same replayable resume rules.
- Once this lands, execution-capable composed DAGs can be exposed safely for
  the Milestone 15 composition path.

## Scope

In scope:

- Define cache keys for frozen specs and resolved inputs.
- Persist stage completion state in durable run records.
- Implement resume behavior for interrupted runs.
- Re-execute only missing or invalidated stages.
- Add tests for cache hits, cache misses, and interrupted-run recovery.

Out of scope:

- Database-backed cache state.
- Non-Slurm remote orchestration.
- Hidden implicit retries without a frozen recipe.
- Any change that breaks replay of existing manifests.

## Implementation Steps

1. Audit `src/flytetest/spec_executor.py`, `src/flytetest/spec_artifacts.py`,
   `src/flytetest/server.py`, and the run-record structures to identify where
   stage completion and cache metadata should live.
2. Define cache keys from frozen spec identity, resolved inputs, and runtime
   bindings or execution profile data.
3. Persist stage completion state in run records so interrupted work can be
   resumed explicitly.
4. Implement resume behavior that skips completed stages and reruns only
   missing or invalidated work.
5. Add tests for cache hits, cache misses, and interrupted-run recovery.
6. Update docs and roadmap notes after the behavior lands.

## Validation Steps

- Run `python3 -m py_compile` on touched Python files if code changes land.
- Run focused tests:
  - `python3 -m unittest tests.test_spec_executor`
  - `python3 -m unittest tests.test_server`
  - `python3 -m unittest tests.test_specs`
- Run `git diff --check`.
- Expand coverage if the caching work touches shared planner or run-record
  contracts.

## Blockers or Assumptions

- This milestone assumes the run record can store enough stage-completion
  detail to make resume deterministic.
- It assumes cache reuse must be explicit and reproducible, not heuristic.
- If the frozen recipe or resolved inputs differ, the system should treat the
  run as a cache miss rather than guessing.
