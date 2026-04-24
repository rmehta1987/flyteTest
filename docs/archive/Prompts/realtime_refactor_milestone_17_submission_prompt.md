Historical note: Milestone 17 landed on 2026-04-10 with generic provenance-key
adoption in current manifest emitters, generic-first planner-adapter loading,
and legacy BRAKER manifest replay coverage.

Use this prompt only when reviewing or repairing the Milestone 17
generic-asset-adoption slice. For new work, start from the next unchecked
milestone in `docs/realtime_refactor_checklist.md`.

```text
You are continuing the FLyteTest `realtime` architecture refactor under the rules in:

- /home/rmeht/Projects/flyteTest/AGENTS.md
- /home/rmeht/Projects/flyteTest/DESIGN.md
- /home/rmeht/Projects/flyteTest/docs/realtime_refactor_checklist.md
- /home/rmeht/Projects/flyteTest/docs/realtime_refactor_plans/2026-04-08-milestone-17-generic-asset-adoption.md
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

- Milestone 14 already introduced the generic biology-facing asset names and
  compatibility aliases.
- The goal now is to make the generic names the preferred internal surface
  without breaking legacy replay paths.
- This is a migration and adoption phase, not a compatibility break.
- Historical manifests and run records must remain readable and truthful.

Task:

1. Read `docs/realtime_refactor_plans/2026-04-08-milestone-17-generic-asset-adoption.md`.
2. Investigate the current implementation state in `planner_adapters.py`,
   `resolver.py`, `types/assets.py`, `tasks/`, `workflows/`, and the relevant
   tests.
3. Update planner adapters to emit generic asset names by default wherever the
   semantic meaning is already known.
4. Update local workflow outputs and manifest-producing helpers to prefer the
   generic asset vocabulary while keeping legacy aliases available.
5. Preserve compatibility with historical manifests and legacy callers.
6. Add tests that prove both legacy alias replay and generic-name round-tripping.
7. Update docs and the checklist so the new state is honest, reviewable, and
   aligned with the milestone plan.
8. If you materially revise the detailed milestone plan, save the revision
   under `docs/realtime_refactor_plans/` and archive superseded versions under
   `docs/realtime_refactor_plans/archive/`.
9. Stop when blocked, when a compatibility guardrail would be at risk, or
   when the next step would require a larger risky batch that should be split.

Important constraints:

- Do not remove legacy aliases too early.
- Do not rewrite historical manifests in place.
- Keep the migration additive and compatibility-preserving.
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
