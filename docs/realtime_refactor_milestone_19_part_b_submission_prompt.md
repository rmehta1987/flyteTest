Use this prompt when handing the Milestone 19 Part B slice off to another
Codex session or when starting the next implementation pass.

```text
You are continuing the FLyteTest `realtime` architecture refactor under the rules in:

- /home/rmeht/Projects/flyteTest/AGENTS.md
- /home/rmeht/Projects/flyteTest/DESIGN.md
- /home/rmeht/Projects/flyteTest/docs/realtime_refactor_checklist.md
- /home/rmeht/Projects/flyteTest/docs/realtime_refactor_plans/2026-04-10-milestone-19-part-b-async-slurm-monitoring.md
- /home/rmeht/Projects/flyteTest/docs/realtime_refactor_plans/README.md
- /home/rmeht/Projects/flyteTest/README.md
- /home/rmeht/Projects/flyteTest/docs/capability_maturity.md

Read the relevant repo-local guides under `.codex/` for the area you touch,
especially:

- /home/rmeht/Projects/flyteTest/.codex/documentation.md
- /home/rmeht/Projects/flyteTest/.codex/testing.md
- /home/rmeht/Projects/flyteTest/.codex/workflows.md
- /home/rmeht/Projects/flyteTest/.codex/agent/python_specialist.md

Context:

- Milestone 19 should establish native stage-level caching, resumability, and dirty workspace cleanup.
- This Part B milestone focuses purely on separating the Slurm polling engine from synchronous, blocking requests into an independent asyncio loop.
- It is crucial to preserve the single-source-of-truth nature of the `.runtime/runs/` local state against race conditions.

Task:

1. Read `docs/realtime_refactor_plans/2026-04-10-milestone-19-part-b-async-slurm-monitoring.md`.
2. Investigate the current execution engine and server state in `spec_executor.py` and `server.py`.
3. Create a grouped Slurm parsing utility that can fetch statuses for all active jobs natively.
4. Implement atomic writes / file locking mechanisms for modifying durable run records.
5. Create and attach the background `asyncio` job to the main MCP server event loop.
6. Configure intelligent rate-limits to prevent HPC scheduler bans.
7. Add robust testing for your parsing, polling timeouts, and file locking.
8. Update docs (`capability_maturity.md`, checklist) so the new state is honest and reviewable.
9. Stop when blocked, when a compatibility guardrail would be at risk, or when a larger refactor is accidentally triggered.

Important constraints:

- Do NOT use generic job queues like Celery or Redis. Use native Python asyncio.
- Do NOT rewrite how the Slurm script executes jobs. Keep the footprint strictly to observability logging.
- Retain proper exception-handling within the async loop to prevent a single Slurm `sacct` timeout from fatally killing the MCP server.

Report back with:

- checklist item(s) completed
- files changed
- validation run results
- remaining blockers or assumptions
```
