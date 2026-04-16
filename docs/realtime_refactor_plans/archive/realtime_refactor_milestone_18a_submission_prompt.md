Historical note: Milestone 18a landed on 2026-04-11 with shared manifest IO
helpers for JSON conversion, JSON read/write, and deterministic file/directory
copying across the first migrated task modules.

Use this prompt only when reviewing or repairing the Milestone 18a shared
manifest-IO slice. For new work, start from the next unchecked milestone in
`docs/realtime_refactor_checklist.md`.

```text
You are continuing the FLyteTest `realtime` architecture refactor under the rules in:

- /home/rmeht/Projects/flyteTest/AGENTS.md
- /home/rmeht/Projects/flyteTest/DESIGN.md
- /home/rmeht/Projects/flyteTest/docs/realtime_refactor_checklist.md
- /home/rmeht/Projects/flyteTest/docs/realtime_refactor_plans/2026-04-10-milestone-18a-shared-manifest-io-utilities.md
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

- The current task modules duplicate the same manifest JSON and deterministic
  file-copy helpers in several places.
- This slice is purely mechanical and should reduce duplication without
  changing biological behavior or manifest semantics.
- The current `run_manifest.json` contracts must remain readable and truthful.

Task:

1. Read `docs/realtime_refactor_plans/2026-04-10-milestone-18a-shared-manifest-io-utilities.md`.
2. Investigate the current implementation state in the duplicated task modules,
   especially `src/flytetest/tasks/eggnog.py`, `src/flytetest/tasks/functional.py`,
   `src/flytetest/tasks/pasa.py`, and `src/flytetest/tasks/filtering.py`.
3. Add a shared manifest helper module for JSON-compatible conversion,
   manifest read/write helpers, and deterministic file-copy helpers.
4. Migrate a small first set of the most duplicated call sites to the helper
   module while preserving current output paths and manifest behavior.
5. Keep the helper API narrowly scoped to the current mechanical extraction.
6. Add focused tests for the shared helpers and one or two migrated call sites.
7. Update docs and the checklist so the new state is honest, reviewable, and
   aligned with the milestone plan.
8. If you materially revise the detailed milestone plan, save the revision
   under `docs/realtime_refactor_plans/` and archive superseded versions under
   `docs/realtime_refactor_plans/archive/`.
9. Stop when blocked, when a compatibility guardrail would be at risk, or
   when the next step would require a larger risky batch that should be split.

Important constraints:

- Keep the slice purely mechanical.
- Do not change manifest semantics, result-bundle paths, or biological stage
  behavior.
- Do not introduce consensus-specific naming logic into the helper layer.
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
