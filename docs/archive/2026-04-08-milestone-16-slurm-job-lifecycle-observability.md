# Milestone 16 Slurm Job Lifecycle and Observability

Date: 2026-04-08
Status: Complete

Related checklist milestone:
- `docs/realtime_refactor_checklist.md` Milestone 16

Implementation note:
- This slice should reconcile submitted Slurm jobs with durable filesystem
  run records and scheduler state.
- It should build on the submission boundary from Milestone 13 rather than
  changing how jobs are submitted.
- The filesystem record should stay the durable source of truth while the
  scheduler provides live state.

## Current State

- Milestone 13 is intended to create the first `sbatch`-driven submission path
  and run record.
- The current local executor and recipe-backed MCP surface do not yet expose
  Slurm job lifecycle state, scheduler polling, or cancellation.
- The roadmap still shows Slurm/HPC execution integration as future work, and
  the execution path does not yet reconcile live scheduler state with saved
  run records.

## Target State

- Submitted Slurm jobs can be reloaded from a durable filesystem-backed run
  record after MCP restarts.
- The executor or associated service can poll `squeue`, `scontrol show job`,
  and `sacct` to reconcile pending, running, completed, failed, and cancelled
  jobs.
- Run records store stdout and stderr paths, final scheduler state, and exit
  information so the execution history is inspectable later.
- MCP can surface job status and cancellation operations without losing the
  submission path or the durable run record.

## Scope

In scope:

- Add a Slurm run-record loader and status model.
- Reconcile live scheduler state with durable filesystem records.
- Capture stdout, stderr, exit code, and final state in the run record.
- Add MCP status and cancellation support for submitted Slurm jobs.
- Add tests for scheduler polling, cancellation, and stale or missing record
  handling.
- Update docs so the lifecycle boundary is described honestly.

Out of scope:

- Reworking the submission mechanism itself.
- Database-backed or remote-object-backed job state.
- Broad remote execution architecture beyond Slurm lifecycle handling.
- New biological workflow families or planner composition changes.

## Implementation Steps

1. Audit `src/flytetest/spec_executor.py`, `src/flytetest/server.py`,
   `src/flytetest/mcp_contract.py`, `src/flytetest/spec_artifacts.py`, and the
   relevant tests to identify the smallest lifecycle surface needed.
2. Define a run-status model and loader for persisted Slurm run records under
   `.runtime/runs/`.
3. Implement scheduler reconciliation using `squeue`, `scontrol show job`, and
   `sacct` to map live job state back into the run record.
4. Persist stdout and stderr paths, exit code, and final scheduler state when a
   job reaches a terminal state.
5. Expose MCP operations for job status and cancellation while preserving the
   submission path from Milestone 13.
6. Add tests for live-state reconciliation, cancellation, and missing or stale
   record handling.
7. Update README, MCP showcase docs, and the capability maturity snapshot
   after the behavior lands.

## Validation Steps

- Run `python3 -m py_compile` on touched Python files if code changes land.
- Run focused tests:
  - `python3 -m unittest tests.test_spec_executor`
  - `python3 -m unittest tests.test_server`
  - `python3 -m unittest tests.test_specs`
- Run `git diff --check`.
- Expand coverage if the lifecycle plumbing touches shared planner or MCP
  contracts.

## Blockers or Assumptions

- This milestone assumes the scheduler is reachable enough to query live job
  state after submission.
- It assumes terminal job details can be reconciled from scheduler commands
  and the durable run record without guessing.
- If the job record is missing or stale, the system should decline or report
  that explicitly rather than inventing state.
