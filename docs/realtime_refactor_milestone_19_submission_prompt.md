Use this prompt when handing the Milestone 19 caching and resumability slice
off to another Codex session or when starting the next implementation pass.

```text
You are continuing the FLyteTest `realtime` architecture refactor under the rules in:

- /home/rmeht/Projects/flyteTest/AGENTS.md
- /home/rmeht/Projects/flyteTest/DESIGN.md
- /home/rmeht/Projects/flyteTest/docs/realtime_refactor_checklist.md
- /home/rmeht/Projects/flyteTest/docs/realtime_refactor_plans/2026-04-08-milestone-19-caching-resumability.md
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

- Milestones 13, 16, and 18 should already have established the Slurm run
  record, lifecycle reconciliation, and retry policy.
- The next step is to make repeated or interrupted runs resumable from the
  frozen recipe and explicit run record.
- Keep the behavior explicit and inspectable.
- Milestone 19 is the prerequisite that makes execution-capable composed DAGs
  safe to expose after Milestone 15 has defined the composition preview.

Task:

1. Read `docs/realtime_refactor_plans/2026-04-08-milestone-19-caching-resumability.md`.
2. Investigate the current implementation state in `spec_executor.py`,
   `spec_artifacts.py`, `server.py`, and the relevant tests.
3. Define cache keys from frozen specs, resolved inputs, and runtime bindings
   or execution profile data.
4. Persist stage completion state in run records.
5. Implement resume behavior that skips completed stages and reruns only
   missing or invalidated work.
6. Add tests for cache hits, cache misses, and interrupted-run recovery.
7. Update docs and the checklist so the new state is honest, reviewable, and
   aligned with the milestone plan.
8. If you materially revise the detailed milestone plan, save the revision
   under `docs/realtime_refactor_plans/` and archive superseded versions under
   `docs/realtime_refactor_plans/archive/`.
9. Stop when blocked, when a compatibility guardrail would be at risk, or
   when the next step would require a larger risky batch that should be split.

Important constraints:

- Keep caching and resumability explicit and reproducible.
- Do not hide stage completion state in memory.
- Resume only from the frozen recipe and recorded bindings.
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
