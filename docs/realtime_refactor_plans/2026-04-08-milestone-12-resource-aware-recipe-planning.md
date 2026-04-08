# Milestone 12 Resource-Aware Recipe Planning

Date: 2026-04-08
Status: Implemented

Related checklist milestone:
- `docs/realtime_refactor_checklist.md` Milestone 12

Implementation note:
- This slice should make resource requests and execution profiles first-class
  in the recipe-backed MCP flow without introducing Slurm submission yet.
- The goal is to freeze explicit CPU, memory, queue, walltime, and runtime
  image choices into saved recipes for the already supported runnable targets.
- Slurm job submission, scheduler monitoring, and cancellation remain out of
  scope for this milestone.

## Current State

- Milestones 9 through 11 already moved the MCP surface to recipe-backed
  execution, explicit input binding, and the EggNOG and AGAT expansions.
- `src/flytetest/specs.py` already defines `ResourceSpec`,
  `RuntimeImageSpec`, `ExecutionProfile`, and `BindingPlan.execution_profile`.
- `src/flytetest/registry.py` carries compatibility metadata with
  `execution_defaults`, supported execution profiles, and declarative local
  resource defaults for current workflow targets.
- `src/flytetest/server.py` and `src/flytetest/planning.py` already freeze
  manifest sources, explicit planner bindings, and runtime bindings into saved
  recipes; Milestone 12 extends that saved recipe boundary to resource and
  runtime-image policy.
- `docs/capability_maturity.md` now marks resource-aware execution planning as
  `Current` for the local recipe metadata layer while Slurm enforcement remains
  future work.

## Target State

- The planner can interpret explicit resource preferences from the prompt or
  caller input and resolve them into a concrete execution profile.
- Saved recipes preserve the selected profile plus any explicit CPU, memory,
  queue, walltime, and runtime-image bindings alongside the existing manifest
  and runtime bindings.
- Registry metadata can express which registered workflows or stages support
  which local execution profiles.
- MCP responses surface the selected execution profile and resource policy in a
  machine-readable way.
- Local execution records preserve the chosen profile and resource metadata in
  a way that can later feed Slurm work.
- No Slurm submission is added yet.

Implementation summary:
- `BindingPlan` now stores `resource_spec` and `runtime_image` alongside the
  selected `execution_profile`.
- `plan_typed_request`, `prepare_run_recipe`, and `prompt_and_run` accept
  explicit resource, profile, and runtime-image policy inputs while also
  parsing conservative prompt resource mentions.
- `LocalWorkflowSpecExecutor` propagates the selected policy into handler
  requests and execution results.
- Current workflow registry metadata exposes declarative local resource
  defaults for planning and review.

## Scope

In scope:

- Extend typed planning and recipe preparation so resource requests become
  explicit structured fields instead of ad hoc prompt text.
- Connect registry compatibility metadata to execution-profile selection for
  current runnable recipe targets.
- Persist execution profiles and resource bindings in saved artifacts and
  executor records.
- Add synthetic tests for resource-profile selection, artifact persistence, and
  local execution record propagation.
- Update docs and maturity snapshots to describe the resource layer honestly.

Out of scope:

- Slurm submission, scheduling, monitoring, or cancellation.
- Queue-aware cluster execution.
- Remote object storage or database-backed asset discovery.
- New biological workflow families or new runnable targets.

## Implementation Steps

1. Audit the current recipe contract in `src/flytetest/specs.py`,
   `src/flytetest/spec_artifacts.py`, `src/flytetest/planning.py`,
   `src/flytetest/server.py`, `src/flytetest/spec_executor.py`, and
   `src/flytetest/registry.py` to identify the smallest set of fields needed
   for explicit resource policy.
2. Add planner and MCP support for an explicit resource-request structure,
   likely built on `ResourceSpec` plus `ExecutionProfile`, so
   `prepare_run_recipe(...)` can freeze the choice before execution.
3. Extend registry compatibility metadata where needed so current supported
   targets can advertise local execution defaults and optional profile names
   without changing workflow signatures.
4. Persist the selected execution profile and resource request into saved
   recipe artifacts and local execution results.
5. Add tests for:
   - typed planning that selects or declines a resource profile explicitly
   - saved recipe artifacts that preserve the selected profile and resource spec
   - local executor propagation of execution profile metadata
   - structured declines when resource requests are incomplete or contradictory
6. Update `README.md`, `docs/mcp_showcase.md`, `docs/capability_maturity.md`,
   and the refactor checklist after behavior lands.

## Validation Steps

- Run `python3 -m py_compile` on touched Python files.
- Run focused tests:
  - `python3 -m unittest tests.test_specs`
  - `python3 -m unittest tests.test_planning`
  - `python3 -m unittest tests.test_server`
  - `python3 -m unittest tests.test_spec_executor`
  - `python3 -m unittest tests.test_registry`
- Run `git diff --check`.
- Expand coverage only if the resource-request plumbing touches shared planner
  or MCP contracts.

## Blockers or Assumptions

- This milestone assumes resource requests remain local-first and declarative,
  not scheduler-enforced yet.
- If a target lacks a meaningful execution profile, the planner should decline
  or fall back to an explicit local default rather than guessing.
- Slurm should not be introduced until resource policy is explicit enough to
  freeze into run records cleanly.
