Historical note: Milestone 16 landed on 2026-04-08 with filesystem-backed Slurm
run-record loading, scheduler reconciliation through `squeue`,
`scontrol show job`, and `sacct`, plus MCP `monitor_slurm_job` and
`cancel_slurm_job` operations.

Use this prompt only when reviewing or repairing the Milestone 16 Slurm
lifecycle slice. For new work, start from the next unchecked milestone in
`docs/realtime_refactor_checklist.md`.

```text
You are continuing the FLyteTest `realtime` architecture refactor under the rules in:

- /home/rmeht/Projects/flyteTest/AGENTS.md
- /home/rmeht/Projects/flyteTest/DESIGN.md
- /home/rmeht/Projects/flyteTest/docs/realtime_refactor_checklist.md
- /home/rmeht/Projects/flyteTest/docs/realtime_refactor_plans/2026-04-08-milestone-16-slurm-job-lifecycle-observability.md
- /home/rmeht/Projects/flyteTest/docs/realtime_refactor_plans/README.md
- /home/rmeht/Projects/flyteTest/README.md
- /home/rmeht/Projects/flyteTest/docs/capability_maturity.md

Read the relevant repo-local guides under `.codex/` for the area you touch,
especially:

- /home/rmeht/Projects/flyteTest/.codex/documentation.md
- /home/rmeht/Projects/flyteTest/.codex/testing.md
- /home/rmeht/Projects/flyteTest/.codex/tasks.md
- /home/rmeht/Projects/flyteTest/.codex/workflows.md

If you were assigned a specialist role, also read the matching guide under
`.codex/agent/`.

Context:

- Milestone 13 should already have introduced the first `sbatch`-driven
  submission path and durable run records.
- The next step is to reconcile those submitted runs with live scheduler
  state and expose lifecycle operations.
- The filesystem record is the durable source of truth; the scheduler is the
  source of live state.
- Do not rework the submission path in this slice unless a bug in submission
  itself blocks lifecycle handling.

Task:

1. Read `docs/realtime_refactor_plans/2026-04-08-milestone-16-slurm-job-lifecycle-observability.md`.
2. Investigate the current implementation state in `spec_executor.py`,
   `server.py`, `mcp_contract.py`, `spec_artifacts.py`, and the relevant
   tests.
3. Add a filesystem-backed Slurm run-record loader and status model.
4. Reconcile live scheduler state using `squeue`, `scontrol show job`, and
   `sacct` for pending, running, completed, failed, and cancelled jobs.
5. Persist stdout and stderr paths, exit code, and final scheduler state in
   the durable run record.
6. Expose MCP operations for job status and cancellation while preserving the
   submission path.
7. Add tests for scheduler reconciliation, cancellation, and stale or missing
   record handling.
8. Update docs and the checklist so the new state is honest, reviewable, and
   aligned with the milestone plan.
9. If you materially revise the detailed milestone plan, save the revision
   under `docs/realtime_refactor_plans/` and archive superseded versions under
   `docs/realtime_refactor_plans/archive/`.
10. Stop when blocked, when a compatibility guardrail would be at risk, or
    when the next step would require a larger risky batch that should be split.

Important constraints:

- Treat the filesystem run record as authoritative for durable history.
- Do not guess at job state if scheduler data is missing or stale.
- Do not break the submission path while adding lifecycle plumbing.
- Keep README, DESIGN, checklist docs, registry metadata, planner behavior,
  MCP contract, and tests aligned.

Report back with:

- checklist item(s) completed
- files changed
- validation run
- current checklist status
- new or archived plan documents created
- remaining blockers or assumptions
```
