# Milestone 15 Registry-Driven Dynamic Workflow Composition

Date: 2026-04-08
Status: Proposed

Related checklist milestone:
- `docs/realtime_refactor_checklist.md` Milestone 15

Implementation note:
- This slice should let users prompt by biological intent while the planner
  assembles only registry-compatible, typed, reviewable workflow compositions.
- It is currently scheduled after Milestone 17 generic asset adoption and
  Milestone 18 Slurm retry/resubmission so the repo can finish those enabling
  cleanup and recovery slices first. The current intended ordering is
  `17 -> 18 -> 15 -> 19`.
- It should stay bounded by explicit compatibility metadata, cycle detection,
  and structured declines.
- The generated plan must be frozen and reviewable before any executor runs it.
- This milestone is composition and approval only; execution-capable composed
  DAGs remain gated on Milestone 19 caching and resumability.

## Current State

- `src/flytetest/registry.py` already carries compatibility metadata that can
  describe stage inputs, outputs, and execution defaults.
- `src/flytetest/planning.py` can already produce typed prompt plans and saved
  `WorkflowSpec` previews for supported requests, but it still relies on the
  current request-shape heuristics rather than a generalized intent-based
  composition route.
- The system can already freeze plans into saved recipes and execute them
  locally or through the planned Slurm path, but it does not yet build
  multi-node DAGs from intent alone.
- The roadmap should expand composition only within registry-approved
  biological paths, not through open-ended workflow synthesis.

## Target State

- The planner accepts biological intent such as "generate a functional
  annotation workflow" and maps it to supported registry-constrained
  compositions when enough context is available.
- Registry compatibility metadata is used to traverse valid stage edges only.
- Multiple sequential `TaskSpec` nodes can be bundled into a single frozen
  `WorkflowSpec` with explicit stage boundaries and resolver-backed inputs.
- Composition failures return structured decline reasons when the graph is
  ambiguous, unsupported, cyclic, or too deep.
- A newly composed recipe is surfaced for explicit user approval, while actual
  composed DAG execution remains gated on Milestone 19.

## Scope

In scope:

- Add an intent-based planning route that can produce either a supported
  `WorkflowSpec` preview or a structured decline.
- Traverse registry compatibility metadata to build biologically valid
  multi-step compositions.
- Bundle sequential task nodes into frozen, reviewable workflow specs.
- Add cycle detection, depth limits, and clear decline reasons for unsupported
  paths.
- Require explicit approval for the composed recipe preview and keep
  execution gated until Milestone 19 lands.
- Add tests for bounded composition, decline behavior, and approval gating.
- Update docs so the planner behavior is described honestly.

Out of scope:

- Open-ended autonomous graph search.
- Executing unreviewed composed graphs.
- Database-backed or remote asset discovery as a prerequisite.
- New biological workflow families beyond the registered compatibility graph.

## Implementation Steps

1. Audit `src/flytetest/planning.py`, `src/flytetest/registry.py`,
   `src/flytetest/specs.py`, `src/flytetest/spec_artifacts.py`,
   `src/flytetest/server.py`, and the related tests to identify the smallest
   surface needed for intent-based composition.
2. Add a planner route that accepts biological intent and resolves it against
   registry compatibility metadata.
3. Implement bounded graph traversal over `RegistryEntry.compatibility` so the
   planner only considers biologically valid stage edges.
4. Assemble sequential task nodes into a frozen `WorkflowSpec` with explicit
   inputs, outputs, and stage boundaries.
5. Add cycle detection, maximum-depth checks, and structured declines for
   ambiguous or unsupported paths.
6. Ensure newly composed plans are surfaced for explicit user approval as a
   preview, with execution remaining gated until Milestone 19.
7. Add tests for composition success, decline conditions, and approval gating.
8. Update README, capability maturity notes, and checklist docs after the
   behavior lands.

## Validation Steps

- Run `python3 -m py_compile` on touched Python files if code changes land.
- Run focused tests:
  - `python3 -m unittest tests.test_planning`
  - `python3 -m unittest tests.test_registry`
  - `python3 -m unittest tests.test_server`
- Run `git diff --check`.
- Expand coverage if the composition work touches shared planner or spec
  contracts.

## Blockers or Assumptions

- This milestone assumes the registry compatibility graph is sufficiently
  expressive to describe valid biological stage composition.
- It assumes new compositions remain reviewable before execution and do not
  bypass the frozen recipe boundary.
- If the intent is ambiguous or the graph is too deep, the planner should
  decline instead of guessing.
