Use this prompt when handing the BUSCO milestone off to another Codex session
or when starting the next post-BUSCO implementation pass.

```text
You are continuing FLyteTest after the BUSCO annotation-QC milestone under the rules in:

- /home/rmeht/Projects/flyteTest/AGENTS.md
- /home/rmeht/Projects/flyteTest/DESIGN.md
- /home/rmeht/Projects/flyteTest/docs/braker3_evm_notes.md
- /home/rmeht/Projects/flyteTest/README.md
- /home/rmeht/Projects/flyteTest/docs/tool_refs/stage_index.md
- /home/rmeht/Projects/flyteTest/docs/tool_refs/busco.md

Context:

- The source of truth is `docs/braker3_evm_notes.md`.
- The repo now implements transcript evidence, PASA, TransDecoder, protein evidence, BRAKER3, pre-EVM assembly, EVM, PASA post-EVM refinement, repeat filtering, and BUSCO QC.
- The current BUSCO boundary starts from the repeat-filtered protein FASTA collected in `annotation_repeat_filtering`.
- EggNOG is now implemented; preserve the current stop rule and do not broaden
  into AGAT or `table2asn` unless the new task explicitly changes milestone
  scope.
- Use `README.md` and `src/flytetest/registry.py` as the public contract for names, inputs, outputs, and current scope language.

Task:

1. Confirm the active post-BUSCO milestone or the next unmet checklist item before changing code.
2. Investigate the current implementation state in code, README, registry, and tests.
3. Make only the changes needed for the chosen downstream stage without reopening the validated transcript-to-PASA-to-EVM-to-post-EVM-to-repeat-filter-to-BUSCO contracts.
4. Update documentation and tests so the new state is honest and reviewable.
5. Report back with:
   - the milestone or checklist item completed
   - files changed
   - validation run
   - any remaining assumptions or blockers

Important constraints:

- Be explicit when behavior is inferred from notes instead of directly stated.
- Keep one BUSCO lineage run as one task boundary if you touch the BUSCO family again.
- Prefer deterministic local-first implementations over cluster-specific job-submission logic unless the milestone explicitly requires otherwise.
- Do not overwrite unrelated user changes in a dirty worktree.
- Keep README, manifests, registry entries, workflow signatures, and compatibility exports aligned.
```
