Use this prompt when handing the MCP spec cutover off to another Codex
session or when starting the next implementation pass.

```text
You are continuing the FLyteTest MCP spec cutover under the rules in:

- /home/rmeht/Projects/flyteTest/AGENTS.md
- /home/rmeht/Projects/flyteTest/DESIGN.md
- /home/rmeht/Projects/flyteTest/mcp_implementation_plan.md
- /home/rmeht/Projects/flyteTest/docs/realtime_refactor_checklist.md
- /home/rmeht/Projects/flyteTest/docs/realtime_refactor_plans/2026-04-07-milestone-9-mcp-spec-cutover.md
- /home/rmeht/Projects/flyteTest/docs/realtime_refactor_plans/README.md
- /home/rmeht/Projects/flyteTest/README.md
- /home/rmeht/Projects/flyteTest/docs/capability_maturity.md

Read the relevant repo-local guides under `.codex/` for the area you touch,
especially:

- /home/rmeht/Projects/flyteTest/.codex/documentation.md
- /home/rmeht/Projects/flyteTest/.codex/testing.md

Context:

- The source of truth for the cutover is `mcp_implementation_plan.md`.
- The source of truth for the implementation breakdown is
  `docs/realtime_refactor_plans/2026-04-07-milestone-9-mcp-spec-cutover.md`,
  which should remain the detailed slice plan.
- The source of truth for progress tracking is
  `docs/realtime_refactor_checklist.md`, which now includes Milestone 9.
- Day one execution remains limited to `ab_initio_annotation_braker3`,
  `protein_evidence_alignment`, and `exonerate_align_chunk`.
- `prompt_and_run(...)` stays available as a compatibility alias over the new
  recipe flow during the cutover.
- Frozen recipe artifacts live under `.runtime/specs/` so they are easy to
  inspect and do not clutter the repo root.
- The MCP server should execute frozen `WorkflowSpec` artifacts through
  `LocalWorkflowSpecExecutor` rather than by building ad hoc CLI strings.

Task:

1. Read `mcp_implementation_plan.md` and
   `docs/realtime_refactor_plans/2026-04-07-milestone-9-mcp-spec-cutover.md`.
2. Investigate the current implementation state in `server.py`, `planning.py`,
   `spec_artifacts.py`, `spec_executor.py`, `registry.py`, and the relevant
   tests.
3. Make only the changes needed to complete the current Milestone 9 slice.
4. Update docs and tests so the new state is honest, reviewable, and aligned
   with the plan.
5. Mark completed items in `docs/realtime_refactor_checklist.md` when they land.
6. If you materially revise the detailed milestone plan, save the revision
   under `docs/realtime_refactor_plans/` and archive superseded versions under
   `docs/realtime_refactor_plans/archive/`.
7. Stop when blocked, when a compatibility guardrail would be at risk, or when
   the next step would require a larger risky batch that should be split.

Important constraints:

- Preserve the recipe-first execution boundary.
- Keep `prompt_and_run(...)` available until the migration explicitly retires it.
- Do not widen the runnable MCP surface beyond the day-one handler map unless
  the new work intentionally expands it.
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
