# Milestone 18 Slurm Retry and Resubmission Policy

Date: 2026-04-08
Status: Complete

Related checklist milestone:
- `docs/realtime_refactor_checklist.md` Milestone 18

Implementation note:
- This slice should add Slurm-specific retry and resubmission behavior for
  failed jobs while preserving the frozen recipe boundary.
- It should use the durable run record and scheduler state to classify
  failures, not a generic remote orchestration layer.
- It should build on the already-landed submission, lifecycle reconciliation,
  cancellation, and authenticated-access boundary instead of reopening those
  earlier slices.
- Each retry attempt should remain explicit, inspectable, and linked to the
  original run.

## Current State

- Milestone 13 already established the first Slurm submission path plus the
  durable run record.
- Milestone 16 already added lifecycle reconciliation and cancellation from
  that durable record.
- Milestone 16 Part 2 already clarified the supported topology as an
  already-authenticated scheduler-capable environment and added explicit
  unsupported-environment diagnostics.
- The current roadmap now includes a structured retry policy for failed Slurm
  jobs.
- The project is still Slurm-only; retry handling should remain within that
  boundary.

## Target State

- Failed Slurm jobs are now classified as retryable or terminal based on
  scheduler state and exit information.
- A retry policy with an explicit maximum attempt limit now governs whether a
  job may be resubmitted.
- Retries now reuse the frozen `WorkflowSpec` and recorded execution profile
  instead of rebuilding intent or prompt state.
- The original run record stays intact while retry attempts are linked to it
  as explicit child attempts.
- Retry and resubmission can now be triggered through the execution layer or
  MCP without expanding into generic remote orchestration.

## Scope

In scope:

- Add a Slurm failure-classification model to the run-record layer.
- Define retryable versus terminal failures.
- Implement an explicit retry policy with a maximum attempt limit.
- Resubmit failed jobs using the frozen spec and recorded execution profile.
- Keep original and retry attempt history linked in the durable run record.
- Add tests for retry classification, resubmission, and attempt limits.

Out of scope:

- Generic remote orchestration.
- Broad backend retry strategies beyond Slurm.
- Changing how the initial submission path works.
- Database-backed retry state.

## Implementation Steps

1. Audit `src/flytetest/spec_executor.py`, `src/flytetest/server.py`,
   `src/flytetest/mcp_contract.py`, and the run-record code paths to identify
   the smallest retry surface.
2. Define a failure-classification model that uses scheduler state and exit
   information to determine retryability.
3. Add retry policy fields to the run record, including an explicit maximum
   attempt limit.
4. Implement resubmission using the frozen `WorkflowSpec` and recorded
   execution profile.
5. Link retry attempts back to the parent run record.
6. Add tests for retryable vs terminal failures, attempt limits, and stale
   record handling.
7. Update docs after the behavior lands.

## Validation Steps

- Run `python3 -m py_compile` on touched Python files if code changes land.
- Run focused tests:
  - `python3 -m unittest tests.test_spec_executor`
  - `python3 -m unittest tests.test_server`
  - `python3 -m unittest tests.test_specs`
- Run `git diff --check`.
- Expand coverage if the retry policy touches shared planner or MCP contracts.

## Blockers or Assumptions

- This milestone assumes scheduler state and exit details are enough to
  distinguish retryable from terminal failures.
- It assumes retries should remain Slurm-specific and not become a general
  remote execution policy.
- If a failure is not clearly retryable, the system should decline rather than
  guess.
