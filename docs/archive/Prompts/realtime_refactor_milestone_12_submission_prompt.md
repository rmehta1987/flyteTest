Milestone 12 resource-aware recipe planning has landed in this branch. Use this
prompt only when handing follow-up audit or stabilization work to another Codex
session.

```text
You are continuing the FLyteTest `realtime` architecture refactor under the rules in:

- /home/rmeht/Projects/flyteTest/AGENTS.md
- /home/rmeht/Projects/flyteTest/DESIGN.md
- /home/rmeht/Projects/flyteTest/docs/realtime_refactor_checklist.md
- /home/rmeht/Projects/flyteTest/docs/realtime_refactor_plans/2026-04-08-milestone-12-resource-aware-recipe-planning.md
- /home/rmeht/Projects/flyteTest/docs/realtime_refactor_plans/README.md
- /home/rmeht/Projects/flyteTest/README.md
- /home/rmeht/Projects/flyteTest/docs/capability_maturity.md

Read the relevant repo-local guides under `.codex/` for the area you touch,
especially:

- /home/rmeht/Projects/flyteTest/.codex/documentation.md
- /home/rmeht/Projects/flyteTest/.codex/testing.md
- /home/rmeht/Projects/flyteTest/.codex/workflows.md
- /home/rmeht/Projects/flyteTest/.codex/tasks.md

Context:

- Milestones 9 through 11 already moved the MCP surface to recipe-backed
  execution, explicit input binding, and the EggNOG / AGAT expansions.
- Milestone 12 makes resource requests and execution profiles first-class in
  the saved recipe flow without introducing Slurm submission yet.
- `src/flytetest/specs.py` already defines `ResourceSpec`,
  `RuntimeImageSpec`, and `ExecutionProfile`.
- `src/flytetest/registry.py` carries compatibility metadata with execution
  defaults, supported execution profiles, and declarative local resource
  defaults for current workflow targets.
- Keep the current runnable MCP targets, manifest contracts, and compatibility
  exports intact.
- Do not add Slurm submission, scheduler monitoring, or cancellation in this
  slice.

Follow-up audit task:

1. Read `docs/realtime_refactor_plans/2026-04-08-milestone-12-resource-aware-recipe-planning.md`.
2. Investigate the current implementation state in `planning.py`, `server.py`,
   `spec_artifacts.py`, `spec_executor.py`, `registry.py`, `specs.py`, and the
   relevant tests.
3. Verify that resource requests and execution profiles remain explicit,
   inspectable, and replayable in saved recipes.
4. Make only the changes needed to correct drift or gaps.
5. Update documentation and tests so the new state is honest, reviewable, and
   aligned with the milestone plan.
6. Mark any newly completed checklist item(s) in
   `docs/realtime_refactor_checklist.md` when they land.
7. If you materially revise the detailed milestone plan, save the revision
   under `docs/realtime_refactor_plans/` and archive superseded versions under
   `docs/realtime_refactor_plans/archive/`.
8. Stop when blocked, when a compatibility guardrail would be at risk, or when
   the next step would require a larger risky batch that should be split.

Important constraints:

- Preserve the recipe-first execution boundary.
- Keep resource requests frozen into the saved recipe instead of hidden inside
  natural-language prompt text.
- Do not widen the runnable MCP surface unless the new work intentionally
  requires it.
- Do not overwrite unrelated user changes in a dirty worktree.
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
