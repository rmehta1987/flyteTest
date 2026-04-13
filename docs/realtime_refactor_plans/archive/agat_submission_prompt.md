Use this prompt when handing the AGAT milestone off to another Codex session
or when starting the next post-EggNOG implementation pass.

```text
You are continuing FLyteTest after the EggNOG milestone and the AGAT
statistics, conversion, and cleanup slices under the rules in:

- /home/rmeht/Projects/flyteTest/AGENTS.md
- /home/rmeht/Projects/flyteTest/DESIGN.md
- /home/rmeht/Projects/flyteTest/docs/braker3_evm_notes.md
- /home/rmeht/Projects/flyteTest/docs/refactor_completion_checklist.md
- /home/rmeht/Projects/flyteTest/docs/tutorial_context.md
- /home/rmeht/Projects/flyteTest/docs/tool_refs/agat.md

Context:

- The source of truth is `docs/braker3_evm_notes.md`.
- The repo now implements through EggNOG functional annotation after
  repeat filtering.
- AGAT statistics and conversion are implemented on the EggNOG-annotated GFF3
  bundle, and AGAT cleanup is implemented on the AGAT conversion bundle.
- `table2asn` remains deferred.
- Use `README.md`, `src/flytetest/registry.py`, and the AGAT tool reference as
  the public contract for names, inputs, outputs, and current scope language.

Task:

1. Confirm the next milestone boundary after AGAT cleanup without broadening
   into `table2asn` unless that milestone is explicitly opened.
2. Investigate the current implementation state in code, README, registry, and
   tests.
3. Make only the changes needed to satisfy the chosen AGAT checklist item
   faithfully against `docs/braker3_evm_notes.md`.
4. Update documentation and tests so the new state is honest and reviewable.
5. Report back with:
   - the milestone or checklist item completed
   - files changed
   - validation run
   - any remaining assumptions or blockers

Important constraints:

- Be explicit when behavior is inferred from notes instead of directly stated.
- Keep AGAT scoped to post-processing and reporting after EggNOG.
- Preserve the current stop rule and do not broaden into `table2asn` unless the
  new task explicitly changes milestone scope.
- Do not overwrite unrelated user changes in a dirty worktree.
- Keep README, manifests, registry entries, workflow signatures, and
  compatibility exports aligned.
```
