Use this prompt when handing the Milestone 18 Slurm retry slice off to another
Codex session or when starting the next implementation pass.

```text
You are continuing the FLyteTest `realtime` architecture refactor under the rules in:

- /home/rmeht/Projects/flyteTest/AGENTS.md
- /home/rmeht/Projects/flyteTest/DESIGN.md
- /home/rmeht/Projects/flyteTest/docs/realtime_refactor_checklist.md
- /home/rmeht/Projects/flyteTest/docs/realtime_refactor_plans/2026-04-08-milestone-18-slurm-retry-resubmission-policy.md
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

- Milestone 13 should already have introduced Slurm submission and durable run
  records.
- Milestone 16 should already have introduced scheduler reconciliation and
  cancellation.
- The next step is to add Slurm-specific retry and resubmission policy for
  failed jobs.
- Keep the scope frozen-recipe driven and Slurm-specific.

Task:

1. Read `docs/realtime_refactor_plans/2026-04-08-milestone-18-slurm-retry-resubmission-policy.md`.
2. Investigate the current implementation state in `spec_executor.py`,
   `server.py`, `mcp_contract.py`, and the relevant tests.
3. Define a Slurm failure-classification model in the run-record layer.
4. Distinguish retryable from terminal failures using scheduler state and exit
   information.
5. Add a retry policy with an explicit maximum attempt limit.
6. Resubmit failed jobs by reusing the frozen `WorkflowSpec` and recorded
   execution profile.
7. Preserve the original run record while linking retry attempts back to the
   parent job.
8. Add tests for retry classification, resubmission behavior, attempt limits,
   and stale-record handling.
9. Update docs and the checklist so the new state is honest, reviewable, and
   aligned with the milestone plan.
10. If you materially revise the detailed milestone plan, save the revision
    under `docs/realtime_refactor_plans/` and archive superseded versions under
    `docs/realtime_refactor_plans/archive/`.
11. Stop when blocked, when a compatibility guardrail would be at risk, or
    when the next step would require a larger risky batch that should be split.

Important constraints:

- Keep retries Slurm-specific.
- Do not broaden the project into generic remote orchestration.
- Retry only from the frozen recipe and recorded execution profile.
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
