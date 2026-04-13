Historical note: Milestone 18b landed on 2026-04-11 with shared GFF3 parsing,
formatting, escaping, and ID / Parent value helpers for EggNOG and
repeat-filtering.

Use this prompt only when reviewing or repairing the Milestone 18b shared GFF3
utilities slice. For new work, start from the next unchecked milestone in
`docs/realtime_refactor_checklist.md`.

```text
You are continuing the FLyteTest `realtime` architecture refactor under the rules in:

- /home/rmeht/Projects/flyteTest/AGENTS.md
- /home/rmeht/Projects/flyteTest/DESIGN.md
- /home/rmeht/Projects/flyteTest/docs/realtime_refactor_checklist.md
- /home/rmeht/Projects/flyteTest/docs/realtime_refactor_plans/2026-04-10-milestone-18b-shared-gff3-utilities.md
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

- EggNOG and repeat-filtering currently duplicate GFF3 parsing, formatting,
  escaping, and ID / Parent filtering helpers.
- This slice is focused on deterministic GFF3 mechanics, not biological policy.
- The current output ordering and escaping behavior must remain intact.

Task:

1. Read `docs/realtime_refactor_plans/2026-04-10-milestone-18b-shared-gff3-utilities.md`.
2. Investigate the current implementation state in the EggNOG and repeat-
   filtering modules, especially `src/flytetest/tasks/eggnog.py` and
   `src/flytetest/tasks/filtering.py`.
3. Add a shared `gff3` utility module with ordered attribute parsing and
   formatting helpers.
4. Centralize escaping and ID / Parent filtering helpers needed by EggNOG
   propagation and repeat-filter cleanup.
5. Migrate the current EggNOG and repeat-filter callers while preserving exact
   GFF3 output ordering and behavior.
6. Add focused tests that prove the shared helpers preserve the current file
   outputs.
7. Update docs and the checklist so the new state is honest, reviewable, and
   aligned with the milestone plan.
8. If you materially revise the detailed milestone plan, save the revision
   under `docs/realtime_refactor_plans/` and archive superseded versions under
   `docs/realtime_refactor_plans/archive/`.
9. Stop when blocked, when a compatibility guardrail would be at risk, or
   when the next step would require a larger risky batch that should be split.

Important constraints:

- Keep the slice focused on deterministic GFF3 mechanics.
- Do not change the biological meaning of the current EggNOG or repeat-
  filtering stages.
- Preserve attribute ordering, escaping semantics, and current output fidelity.
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
