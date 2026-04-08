Use this prompt when handing the `realtime` architecture refactor off to
another Codex session or when starting the next implementation pass.

```text
You are continuing the FLyteTest `realtime` architecture refactor under the rules in:

- /home/rmeht/Projects/flyteTest/AGENTS.md
- /home/rmeht/Projects/flyteTest/DESIGN.md
- /home/rmeht/Projects/flyteTest/docs/realtime_refactor_checklist.md
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

- The source of truth for the architecture target is `DESIGN.md`.
- The source of truth for the architecture refactor task breakdown is `docs/realtime_refactor_checklist.md`, which should remain the quick-reference progress tracker.
- `docs/realtime_refactor_plans/` is the place to keep detailed per-slice plan history for this refactor, with superseded or completed revisions moved into `docs/realtime_refactor_plans/archive/`.
- The existing `docs/refactor_completion_checklist.md` remains the notes-faithful pipeline milestone gate and should not be replaced by this refactor tracker.
- Preserve the current runnable workflows, `flyte_rnaseq_workflow.py`
  compatibility exports, existing manifest contracts, and the MCP
  recipe-backed handler set unless the selected checklist item
  explicitly changes one of them.
- Do not introduce a database-first or storage-first rewrite as a prerequisite.
- Keep current Flyte `File` and `Dir` task signatures unless the selected checklist item explicitly allows a compatibility-safe change.
- Treat deterministic execution and dynamic workflow creation as compatible:
  deterministic means typed, inspectable, replayable, and explicit about
  assumptions; dynamic means a prompt may produce a new saved `WorkflowSpec` or
  registered-stage composition when enough context is available.

Task:

1. Read `docs/realtime_refactor_checklist.md` and determine the next unchecked item on the critical path unless you were explicitly assigned a parallel lane.
2. Investigate the current implementation state in code, README, registry, planner, MCP server, and tests for that checklist item.
3. Make only the changes needed to satisfy that checklist item while preserving the documented compatibility guardrails.
4. Update documentation and tests so the new state is honest, reviewable, and aligned with the checklist.
5. Mark the completed checklist item(s) in `docs/realtime_refactor_checklist.md`.
6. If you create or materially revise a detailed implementation plan for the slice, save it under `docs/realtime_refactor_plans/` using a dated descriptive filename, and move superseded or completed plan revisions into `docs/realtime_refactor_plans/archive/`.
7. If the selected item is fully complete, no blocker remains, and continuing would not violate a compatibility guardrail or force a risky multi-slice jump, immediately continue to the next unchecked critical-path item in the same session.
8. Repeat this loop until one of the following stop conditions occurs:
   - the next item is blocked by a missing decision, missing dependency, or environment limitation
   - the next item would require a larger risky jump that should be split into a fresh slice
   - a compatibility guardrail would be at risk
   - the checklist is complete
9. Report back with:
   - checklist item(s) completed
   - files changed
   - validation run
   - current checklist status
   - any new or archived plan documents created
   - remaining blockers or assumptions

Important constraints:

- Prefer incremental refactors around compatibility seams instead of rewrites.
- Keep the current planner behavior and MCP recipe-backed day-one handler set
  as compatibility subsets until the selected milestone intentionally broadens
  them, as Milestone 10 did for BUSCO and Milestone 11 plans to do for
  EggNOG/AGAT.
- Do not describe "deterministic" as meaning "static workflow list only";
  dynamic workflow generation remains a project goal when it is saved,
  typed, and reviewable.
- Continue through multiple small checklist items in one session when it is safe to do so, but stop before forcing a large risky batch.
- Be explicit when something is target-state only and not yet implemented.
- Do not overwrite unrelated user changes in a dirty worktree.
- Keep README, DESIGN, checklist docs, registry metadata, planner behavior, MCP contract, and tests aligned.
```
