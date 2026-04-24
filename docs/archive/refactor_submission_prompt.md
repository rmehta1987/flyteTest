Use this prompt when handing the refactor off to another Codex session or when
starting the next implementation pass.

```text
You are continuing the FLyteTest refactor under the rules in:

- /home/rmeht/Projects/flyteTest/AGENTS.md
- /home/rmeht/Projects/flyteTest/DESIGN.md
- /home/rmeht/Projects/flyteTest/docs/braker3_evm_notes.md
- /home/rmeht/Projects/flyteTest/docs/refactor_completion_checklist.md
- /home/rmeht/Projects/flyteTest/docs/tutorial_context.md

Context:

- The source of truth is the updated `docs/braker3_evm_notes.md`.
- Do not treat a workflow as complete just because it exists; use the checklist
  acceptance criteria.
- EggNOG is now implemented; the AGAT statistics, conversion, and cleanup
  slices are implemented, and `table2asn` remains the remaining deferred stage
  until Milestones 0 through 9 in
  `docs/refactor_completion_checklist.md` are complete.
- Preserve the current stop rule and avoid broadening scope.
- Use `docs/tutorial_context.md` for Galaxy tutorial references, local fixture
  paths, prompt structure, and Apptainer/task-planning guidance.

Task:

1. Read the checklist and determine which milestone item is the next unmet
   requirement on the critical path.
2. Investigate the current implementation state in code, README, registry, and
   tests.
3. Make only the changes needed to satisfy that checklist item faithfully
   against `docs/braker3_evm_notes.md`.
4. Update documentation and tests so the new state is honest and reviewable.
5. Report back with:
   - the checklist item completed
   - files changed
   - validation run
   - any remaining assumptions or blockers

Important constraints:

- Be explicit when behavior is inferred from notes instead of directly stated.
- Prefer deterministic local-first implementations over cluster-specific job
  submission logic unless the checklist item requires otherwise.
- Do not overwrite unrelated user changes in a dirty worktree.
- Keep README, manifests, registry entries, and workflow signatures aligned.
```
