Use this prompt when handing the Milestone 22 TransDecoder asset-cleanup slice
off to another Codex session or when starting the next implementation pass.

```text
You are continuing the FLyteTest `realtime` architecture refactor under the rules in:

- /home/rmeht/Projects/flyteTest/AGENTS.md
- /home/rmeht/Projects/flyteTest/DESIGN.md
- /home/rmeht/Projects/flyteTest/docs/realtime_refactor_checklist.md
- /home/rmeht/Projects/flyteTest/docs/realtime_refactor_plans/2026-04-10-milestone-22-transdecoder-generic-asset-follow-up.md
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

- Milestone 17 already introduced generic-first adoption for the first three
  concrete generic/legacy asset pairs.
- The next family-scoped cleanup candidate is the current TransDecoder-backed
  coding-prediction boundary.
- This slice should stay narrow and compatibility-safe.

Task:

1. Read `docs/realtime_refactor_plans/2026-04-10-milestone-22-transdecoder-generic-asset-follow-up.md`.
2. Investigate the current implementation state in `tasks/transdecoder.py`,
   `types/assets.py`, planner adapters, resolver code, and the relevant tests.
3. Decide what biology-facing concept should represent the current
   TransDecoder-backed boundary.
4. If justified, add generic sibling names or types while keeping the
   TransDecoder-branded names readable.
5. Preserve replay of historical manifests that only use the current
   TransDecoder-branded keys.
6. Add tests for generic-name round-tripping, legacy manifest loading, and
   current manifest emission.
7. Update docs and the checklist so the new state is honest, reviewable, and
   aligned with the milestone plan.
8. If you materially revise the detailed milestone plan, save the revision
   under `docs/realtime_refactor_plans/` and follow that directory's README
   for plan lifecycle rules.
9. Stop when blocked, when the biology-facing boundary is still too vague to
   genericize safely, or when the next step should be split further.

Important constraints:

- Keep the slice limited to the TransDecoder family.
- Do not rewrite historical manifests in place.
- Do not force a generic rename if the biology-facing concept is not stable
  enough yet.
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
