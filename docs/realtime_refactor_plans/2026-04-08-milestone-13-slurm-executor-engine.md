# Milestone 13 HPC Slurm Executor Engine

Date: 2026-04-08
Status: Proposed

Related checklist milestone:
- `docs/realtime_refactor_checklist.md` Milestone 13

Implementation note:
- This slice should turn frozen recipe artifacts plus explicit execution
  profiles into deterministic Slurm submission artifacts and durable run
  records.
- It should not reintroduce prompt-text-driven resource inference or depend on
  in-memory MCP state for job tracking.
- Scheduler monitoring and cancellation can follow once submission and
  filesystem records are proven stable.

## Current State

- Milestone 12 is the resource-aware planning slice and should be complete
  before this work starts.
- `src/flytetest/specs.py` already defines `ResourceSpec`,
  `RuntimeImageSpec`, and `ExecutionProfile`.
- `src/flytetest/spec_artifacts.py` and `src/flytetest/spec_executor.py` can
  already persist and replay frozen recipes for the local execution path.
- `src/flytetest/server.py` currently exposes the recipe-backed MCP surface but
  does not yet submit work through Slurm.
- The docs and maturity snapshot still describe Slurm/HPC execution as future
  work rather than as an implemented executor path.

## Target State

- A new `SlurmWorkflowSpecExecutor` sibling can execute frozen recipes through
  an explicit Slurm submission path.
- The executor renders a deterministic Bash / Slurm script from the frozen
  `WorkflowSpec`, resolved bindings, and selected `ExecutionProfile`.
- Submission uses `subprocess.run(["sbatch", script_path], capture_output=True,
  text=True, check=True)` or an equivalent explicit wrapper that preserves the
  same behavior.
- The emitted Slurm job ID is captured immediately and written into a
  run-scoped filesystem record.
- The run record stores the job ID, recipe ID, script path, stdout path,
  stderr path, selected execution profile, and any other scheduler metadata
  needed for later observation.
- MCP exposes a `run_slurm_recipe` entrypoint while keeping local recipe
  execution intact.

## Scope

In scope:

- Add a Slurm executor class alongside the local saved-spec executor.
- Render deterministic Slurm scripts from frozen recipe data and explicit
  runtime bindings.
- Dispatch the rendered script with `sbatch` and persist the resulting job ID.
- Persist a run-scoped filesystem record for each accepted submission.
- Add MCP/server plumbing for `run_slurm_recipe`.
- Add tests for deterministic script rendering, submission parsing, record
  persistence, and MCP wiring.
- Update docs and checklist entries so the Slurm execution path is described
  honestly.

Out of scope:

- Scheduler polling, `squeue` / `sacct` monitoring, or cancellation.
- Queue discovery or cluster policy inference.
- Database-backed or remote-object-backed run state.
- New biological workflow families or broader workflow composition changes.

## Implementation Steps

1. Audit the current recipe contract in `src/flytetest/specs.py`,
   `src/flytetest/spec_artifacts.py`, `src/flytetest/spec_executor.py`,
   `src/flytetest/server.py`, `src/flytetest/mcp_contract.py`, and
   `src/flytetest/registry.py` to identify the smallest run-record and
   execution-profile fields needed for Slurm submission.
2. Add a deterministic Slurm script renderer that consumes a frozen
   `WorkflowSpec`, its resolved bindings, and the selected `ExecutionProfile`.
3. Introduce `SlurmWorkflowSpecExecutor` as a sibling to the local executor,
   keeping the local execution path unchanged.
4. Implement `sbatch` submission via `subprocess.run(...)`, parse the emitted
   job ID, and persist a run-scoped record immediately after submission.
5. Expose `run_slurm_recipe` through the MCP server and contract metadata.
6. Add synthetic tests for script determinism, `sbatch` parsing, record
   persistence, and MCP/tool wiring.
7. Update README, MCP showcase docs, capability maturity notes, and the
   checklist once the behavior lands.

## Validation Steps

- Run `python3 -m py_compile` on touched Python files if code changes land.
- Run focused tests:
  - `python3 -m unittest tests.test_spec_executor`
  - `python3 -m unittest tests.test_server`
  - `python3 -m unittest tests.test_specs`
- Optional cluster smoke test:
  - `python3 -m unittest tests.test_spec_executor_slurm_smoke`
  - This test is skipped unless `sbatch` is available and only checks that a
    minimal submission succeeds with the explicit `rcc-staff` account and
    `broadwl` partition policy.
- Run `git diff --check`.
- Expand coverage if the implementation touches shared planner or MCP
  contracts.

## Blockers or Assumptions

- This milestone assumes `sbatch` is available on the target system and its
  output format can be parsed reliably enough to capture the job ID.
- The run record should be written atomically and treated as the durable
  source of truth for later monitoring or cancellation work.
- If the selected execution profile is missing or contradictory, the executor
  should fail explicitly rather than guessing at cluster defaults.
- Monitoring and cancellation are expected to be later milestones, not hidden
  inside this submission slice.
