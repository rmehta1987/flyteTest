Use this prompt when handing the Milestone 21 ad hoc task execution slice off
to another Codex session or when starting the next implementation pass.

```text
You are continuing the FLyteTest `realtime` architecture refactor under the rules in:

- /home/rmeht/Projects/flyteTest/AGENTS.md
- /home/rmeht/Projects/flyteTest/DESIGN.md
- /home/rmeht/Projects/flyteTest/docs/realtime_refactor_checklist.md
- /home/rmeht/Projects/flyteTest/docs/realtime_refactor_plans/2026-04-10-milestone-21-ad-hoc-task-execution-surface.md
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

- The repo already has a recipe-first workflow execution surface.
- The current MCP/server task runner exposes only one explicit ad hoc task:
  `exonerate_align_chunk`.
- The next step is to define a bounded broader task surface for ad hoc
  experimentation without weakening saved recipe provenance for workflows.

Task:

1. Read `docs/realtime_refactor_plans/2026-04-10-milestone-21-ad-hoc-task-execution-surface.md`.
2. Investigate the current implementation state in `server.py`,
   `mcp_contract.py`, `registry.py`, and the task modules that are plausible
   user-facing ad hoc candidates.
3. Define which registered tasks are eligible for user-facing ad hoc
   execution and keep helper-only tasks internal.
4. Extend the task runner to support explicit input coercion for scalar and
   local Flyte I/O values as needed.
5. Preserve structured task execution summaries, clear limitations, and
   machine-readable output reporting.
6. Add tests for supported tasks, unsupported tasks, input coercion, and task
   execution results.
7. Update docs and the checklist so the new state is honest, reviewable, and
   aligned with the milestone plan.
8. If you materially revise the detailed milestone plan, save the revision
   under `docs/realtime_refactor_plans/` and archive superseded versions under
   `docs/realtime_refactor_plans/archive/`.
9. Stop when blocked, when the user-facing task surface would become too broad
   for one batch, or when the next step should be split into a narrower slice.

Important constraints:

- Keep saved workflow recipe execution as the main reproducible execution path.
- Do not expose every registered task automatically.
- Keep ad hoc task execution explicit, bounded, and machine-readable.
- Avoid hidden shell glue or prompt-only inference for task inputs.
- Keep README, DESIGN, checklist docs, capability docs, MCP contract, and
  tests aligned.

Report back with:

- checklist item(s) completed
- files changed
- validation run
- current checklist status
- new or archived plan documents created
- remaining blockers or assumptions
```
