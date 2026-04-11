Historical note: Milestone 18c landed on 2026-04-11 with a shared manifest
envelope helper for the common `stage` / `assumptions` / `inputs` / `outputs`
shape, plus optional code-reference and tool-reference fields.

Use this prompt only when reviewing or repairing the Milestone 18c standard
manifest-envelope slice. For new work, start from the next unchecked milestone
in `docs/realtime_refactor_checklist.md`.

```text
You are continuing the FLyteTest `realtime` architecture refactor under the rules in:

- /home/rmeht/Projects/flyteTest/AGENTS.md
- /home/rmeht/Projects/flyteTest/DESIGN.md
- /home/rmeht/Projects/flyteTest/docs/realtime_refactor_checklist.md
- /home/rmeht/Projects/flyteTest/docs/realtime_refactor_plans/2026-04-10-milestone-18c-standard-manifest-envelope.md
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

- Task modules currently build their manifest dictionaries manually.
- Most manifests share the same common envelope shape around `stage`,
  `assumptions`, `inputs`, and `outputs`.
- Some modules also want a stable code-reference or tool-reference pointer in
  the manifest record.

Task:

1. Read `docs/realtime_refactor_plans/2026-04-10-milestone-18c-standard-manifest-envelope.md`.
2. Investigate the current implementation state in the task modules that write
   manifests, especially the modules touched by the 18a and 18b slices if those
   helpers make the migration easier.
3. Add a small manifest-envelope helper that standardizes the common
   `stage` / `assumptions` / `inputs` / `outputs` shape.
4. Decide whether `code_reference` or `tool_ref` should be required or optional
   in the shared envelope.
5. Update task modules to use the helper while preserving task-specific fields
   and current result-bundle paths.
6. Add focused tests that check the standardized envelope without forcing a
   global manifest schema rewrite.
7. Update docs and the checklist so the new state is honest, reviewable, and
   aligned with the milestone plan.
8. If you materially revise the detailed milestone plan, save the revision
   under `docs/realtime_refactor_plans/` and archive superseded versions under
   `docs/realtime_refactor_plans/archive/`.
9. Stop when blocked, when a compatibility guardrail would be at risk, or
   when the next step would require a larger risky batch that should be split.

Important constraints:

- Keep the slice manifest-shape focused.
- Do not change biological task behavior.
- Do not force every manifest into an identical global schema.
- Preserve current output paths and replay behavior.
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
