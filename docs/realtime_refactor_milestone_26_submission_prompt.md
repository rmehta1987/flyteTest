Use this prompt when handing the Milestone 26 consensus asset-generalization
slice off to another Codex session or when starting the next implementation
pass.

```text
You are continuing the FLyteTest `realtime` architecture refactor under the rules in:

- /home/rmeht/Projects/flyteTest/AGENTS.md
- /home/rmeht/Projects/flyteTest/DESIGN.md
- /home/rmeht/Projects/flyteTest/docs/realtime_refactor_checklist.md
- /home/rmeht/Projects/flyteTest/docs/realtime_refactor_plans/2026-04-10-milestone-25-consensus-asset-generalization-boundary.md
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

- The current consensus asset family is explicitly EVM-backed and truthful.
- A generic consensus layer may be useful later, but only if planner pressure
  or a second implementation path justifies it.
- This slice is partly a boundary-decision milestone, not necessarily a forced
  rename.

Task:

1. Read `docs/realtime_refactor_plans/2026-04-10-milestone-25-consensus-asset-generalization-boundary.md`.
2. Investigate the current implementation state in `tasks/consensus.py`,
   `types/assets.py`, planner adapters, resolver code, and the relevant tests.
3. Decide whether the repo currently needs a generic consensus-annotation
   asset layer.
4. If justified, add generic sibling names while keeping EVM names readable.
5. Preserve replay of historical EVM manifests and result bundles.
6. Add tests for generic-name round-tripping, legacy manifest loading, and
   current manifest emission when the generic layer is adopted.
7. Update docs and the checklist so the new state is honest, reviewable, and
   aligned with the milestone plan.
8. If you materially revise the detailed milestone plan, save the revision
   under `docs/realtime_refactor_plans/` and follow that directory's README
   for plan lifecycle rules.
9. Stop when the right outcome is clearly “not yet”; documenting that boundary
   cleanly is an acceptable milestone result.

Important constraints:

- Do not force a generic consensus rename without real planner or execution
  pressure.
- Do not rewrite historical manifests in place.
- Keep the current EVM-backed implementation truth visible.
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
