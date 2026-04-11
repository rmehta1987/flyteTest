# Milestone 19 Part B: Async Slurm Monitoring and Continuous Observability

Date: 2026-04-10
Status: Proposed

Related checklist milestone:
- `docs/realtime_refactor_checklist.md` Milestone 19 Part B

Implementation note:
- This slice separates continuous, asynchronous scheduler polling from the core caching and resumability logic in Milestone 19.
- Building an asyncio background loop mitigates the risk of blocking the main MCP server while Slurm queries (like `squeue` and `sacct`) run.
- It must gracefully handle file-lock contention and rate-limiting to avoid overwhelming the HPC scheduler.
- This milestone logically follows M19 (which introduces required granular stage states) but bounds the architectural shift of moving from synchronous to asynchronous polling.

## Current State

- Milestone 16 introduced Slurm lifecycle observability, but it relies on synchronous, on-demand polling.
- `capability_maturity.md` mentions async orchestration as a targeted future optimization for Slurm polling.
- There is no background watcher daemon; MCP requests must block to determine if jobs have transitioned.

## Target State

- A background asynchronous telemetry loop periodically batches checks against Slurm (`squeue`, `sacct`) without blocking the MCP server.
- The reconciler parses the active Slurm statuses and updates the local durable run records (`.runtime/runs/...`) when state transitions occur (e.g., to `COMPLETED`, `FAILED`).
- Proper file-locking mechanisms are used to prevent race conditions between the async updater and any synchronous MCP queries interacting with the run record.
- Rate limits are explicitly configured so the loop does not trigger scheduler bans or timeouts.

## Scope

In scope:

- Implement an `asyncio` background task or isolated watcher function inside the MCP server lifecycle.
- Add batched polling for all active user jobs rather than querying jobs sequentially.
- Implement robust shared-lock handling for updating durable filesystem run-records.
- Define configurable rate-limiting and backoff for Slurm CLI commands.
- Provide a mechanism to gracefully shut down the watcher when the MCP server exits.
- Add tests covering the async loop behavior, file-lock contention, and mock scheduler parsing.

Out of scope:

- Heavyweight message queues (e.g., Redis, RabbitMQ or Celery); keep it native `asyncio`.
- Altering the fundamental M19 resumability semantics or cache keys.
- Remote execution over non-Slurm orchestration systems.
- Emitting real-time desktop or web notifications (this handles the backend state transition only).

## Implementation Steps

1. Audit `src/flytetest/server.py` and `src/flytetest/spec_executor.py` to identify where an `asyncio` loop can be safely injected during server startup and shutdown.
2. Implement a batched Slurm parsing function capable of returning the state of multiple jobs in a single CLI call.
3. Introduce file locking (or atomic write logic) to the `.runtime/runs/...` metadata updates to prevent race conditions.
4. Build the asynchronous reconciliation loop, integrating configurable timers (e.g., poll every 30 seconds) and backoffs for `sacct` lag.
5. Provide tests simulating lock contention and verifying the batched Slurm parser.
6. Update `docs/capability_maturity.md` and the refactor checklist to mark continuous asynchronous monitoring as `Current`.

## Validation Steps

- Run `python3 -m py_compile` on touched Python files if code changes land.
- Run focused tests:
  - `python3 -m unittest tests.test_server` (specifically async loop lifecycle and teardown)
  - `python3 -m unittest tests.test_spec_executor` (specifically atomic run record updates)
- Run `git diff --check`.
- Start the server, mock a Slurm job transition, and ensure the run record updates automatically without a client prompting it.

## Blockers or Assumptions

- Assumes Python's `asyncio` can exist within the current server event loop without conflicting.
- Assumes the underlying shared filesystem (often NFS on HPCs) supports the locking mechanism chosen or atomicity guarantees.
- Assumes Slurm CLI commands will respond fast enough under normal load not to exhaust worker threads.
