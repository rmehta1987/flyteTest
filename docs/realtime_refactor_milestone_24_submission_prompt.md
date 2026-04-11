Use this prompt when handing the Milestone 24 PASA refinement asset-
generalization slice off to another Codex session or when starting the next
implementation pass.

```text
You are continuing the FLyteTest `realtime` architecture refactor under the rules in:

- /home/rmeht/Projects/flyteTest/AGENTS.md
- /home/rmeht/Projects/flyteTest/DESIGN.md
- /home/rmeht/Projects/flyteTest/docs/realtime_refactor_checklist.md
- /home/rmeht/Projects/flyteTest/docs/realtime_refactor_plans/2026-04-10-milestone-24-pasa-refinement-asset-generalization-boundary.md
- /home/rmeht/Projects/flyteTest/docs/realtime_refactor_plans/2026-04-10-post-m17-asset-surface-follow-up-audit.md
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

- The PASA post-EVM refinement family is a candidate for future genericization,
  but it may still be most truthful to keep it explicitly PASA-backed.
- This slice is partly a boundary-decision milestone, not necessarily a forced
  rename.

Task:

1. Read `docs/realtime_refactor_plans/2026-04-10-milestone-24-pasa-refinement-asset-generalization-boundary.md`.
2. Investigate the current implementation state in `tasks/pasa.py`,
   `types/assets.py`, planner adapters, resolver code, and the relevant tests.
3. Decide whether a stable biology-facing annotation-refinement asset layer is
   justified now.
4. If justified, add generic sibling names while keeping PASA names readable.
5. Preserve replay of historical PASA refinement manifests.
6. Add tests for generic-name round-tripping, legacy manifest loading, and
   current manifest emission when the generic layer is adopted.
7. Update docs and the checklist so the new state is honest, reviewable, and
   aligned with the milestone plan.
8. If you materially revise the detailed milestone plan, save the revision
   under `docs/realtime_refactor_plans/` and archive superseded versions under
   `docs/realtime_refactor_plans/archive/`.
9. Stop when the right outcome is clearly “not yet”; documenting that boundary
   cleanly is an acceptable milestone result.

Important constraints:

- Do not force a rename if PASA remains the clearest truthful boundary.
- Do not rewrite historical manifests in place.
- Keep the current PASA-backed implementation truth visible.
- Keep README, DESIGN, checklist docs, capability docs, planner behavior, and
  tests aligned.

Report back with:

- checklist item(s) completed
- files changed
- validation run
- current checklist status
- new or archived plan documents created
- remaining blockers or assumptions
```
