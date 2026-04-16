Use this prompt when handing the Milestone 23 protein-evidence nested
asset-cleanup slice off to another Codex session or when starting the next
implementation pass.

```text
You are continuing the FLyteTest `realtime` architecture refactor under the rules in:

- /home/rmeht/Projects/flyteTest/AGENTS.md
- /home/rmeht/Projects/flyteTest/DESIGN.md
- /home/rmeht/Projects/flyteTest/docs/realtime_refactor_checklist.md
- /home/rmeht/Projects/flyteTest/docs/realtime_refactor_plans/2026-04-10-milestone-23-protein-evidence-nested-asset-cleanup.md
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

- Milestone 17 already cleaned up the first generic/legacy asset pairs.
- The next family-scoped cleanup candidate is the nested Exonerate-specific
  naming inside the protein-evidence family.
- The top-level protein-evidence bundle should remain stable.

Task:

1. Read `docs/realtime_refactor_plans/2026-04-10-milestone-23-protein-evidence-nested-asset-cleanup.md`.
2. Investigate the current implementation state in `tasks/protein_evidence.py`,
   `types/assets.py`, planner adapters, resolver code, and the relevant tests.
3. Identify which nested Exonerate-specific asset names are worth
   genericizing.
4. Add generic sibling names only where a stable biology-facing meaning exists.
5. Preserve the top-level `protein_evidence_result_bundle` contract and
   historical manifest replay.
6. Add tests for nested generic-name round-tripping, legacy manifest loading,
   and current manifest emission.
7. Update docs and the checklist so the new state is honest, reviewable, and
   aligned with the milestone plan.
8. If you materially revise the detailed milestone plan, save the revision
   under `docs/realtime_refactor_plans/` and follow that directory's README
   for plan lifecycle rules.
9. Stop when the slice would broaden into top-level bundle redesign or broader
   workflow changes.

Important constraints:

- Keep the slice limited to nested protein-evidence assets.
- Do not casually rename the top-level bundle.
- Do not rewrite historical manifests in place.
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
