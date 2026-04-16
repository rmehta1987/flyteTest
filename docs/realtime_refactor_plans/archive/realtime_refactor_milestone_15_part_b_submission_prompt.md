Use this prompt when handing the Milestone 15 Part B TaskEnvironment catalog
slice off to another Codex session or when starting the next implementation
pass.

```text
You are continuing the FLyteTest `realtime` architecture refactor under the rules in:

- /home/rmeht/Projects/flyteTest/AGENTS.md
- /home/rmeht/Projects/flyteTest/DESIGN.md
- /home/rmeht/Projects/flyteTest/docs/realtime_refactor_checklist.md
- /home/rmeht/Projects/flyteTest/docs/realtime_refactor_plans/2026-04-09-milestone-15-part-b-taskenvironment-catalog.md
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

- Milestone 15 is the registry-driven dynamic composition milestone and should
  remain focused on typed, bounded, reviewable workflow composition.
- This Part B slice does not change the Milestone 15 planner or composition
  contract.
- The goal here is to refactor the task-runtime layer so future task families
  can inherit shared `TaskEnvironment` defaults from a single declarative
  catalog.
- A small number of heavier families already carry explicit resource and
  description overrides so the catalog reflects actual runtime differences.
- Compatibility aliases should remain available for current imports and
  manifests.

Task:

1. Read `docs/realtime_refactor_plans/2026-04-09-milestone-15-part-b-taskenvironment-catalog.md`.
2. Investigate the current implementation state in `src/flytetest/config.py`,
   `tests/flyte_stub.py`, `tests/test_config.py`, `README.md`, `CHANGELOG.md`,
   and the task/workflow modules that consume the exported environments.
3. Centralize shared task-environment defaults in one helper so new task
   families can be declared from a compact catalog entry.
4. Add or adjust explicit overrides for the heaviest current task families so
   the catalog reflects real workload differences.
5. Preserve compatibility aliases such as `WORKFLOW_NAME` and the exported
   environment handles used by existing task and workflow modules.
6. Keep the shared defaults intentionally modest unless a specific family has
   a documented reason to override them.
7. Add or update focused tests that verify the catalog contents, shared
   defaults, per-family overrides, and alias stability.
8. Update user-facing docs so they describe the shared task-defaults layer
   honestly.
9. If you materially revise the detailed slice plan, save the revision under
   `docs/realtime_refactor_plans/` and archive superseded versions under
   `docs/realtime_refactor_plans/archive/`.
10. Stop when the catalog refactor is complete, when a compatibility guardrail
   would be at risk, or when the next step would require a larger risky batch
   that should be split.

Important constraints:

- Do not pin a single repository-wide container image unless that becomes an
  explicit design decision.
- Do not change the Milestone 15 planner/composition contract in this slice.
- Keep README, DESIGN, checklist docs, task-environment config, and tests
  aligned.

Report back with:

- checklist item(s) completed
- files changed
- validation run
- current checklist status
- new or archived plan documents created
- remaining blockers or assumptions
```
