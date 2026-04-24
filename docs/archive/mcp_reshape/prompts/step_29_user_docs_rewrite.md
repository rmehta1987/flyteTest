Use this prompt when starting Step 29 or when handing it off to another session.

```text
You are continuing the FLyteTest scientist-centered MCP surface reshape under the rules in:

- /home/rmeht/Projects/flyteTest/AGENTS.md
- /home/rmeht/Projects/flyteTest/docs/mcp_reshape/checklist.md
- /home/rmeht/Projects/flyteTest/docs/mcp_reshape/mcp_reshape_plan.md  (§14 — user-facing docs)

Context:

- This is Step 29. Depends on Step 28 (context-load files refreshed) and
  on Steps 21-25 being stable. Rewrites the end-user walkthroughs so a new
  scientist picks up the experiment loop end-to-end without reading plan
  prose or hunting through `.codex/`.

Key decisions already made (do not re-litigate):

- Primary walkthrough = experiment loop
  (`list_entries → list_bundles → load_bundle → run_task / run_workflow`).
  `prepare_run_recipe` is an inspect-before-execute appendix, not the main
  path.
- Typed-binding templates live in `docs/tutorial_context.md`; every
  template shows the three binding forms (raw path / `$manifest` / `$ref`).
- Worked example for `$ref` cross-run reuse is mandatory — it's how a
  scientist chains "BRAKER3 output → EVM input" without re-specifying the
  GFF path.
- `docs/braker3_evm_notes.md` is biology-authoritative; do NOT rewrite it.
  Only fix stale shape references surfaced by grep.

Task:

1. `docs/mcp_showcase.md` — primary walkthrough, rewritten:
   - Open with the experiment loop in one paragraph.
   - Worked example 1: `load_bundle("braker3_small_eukaryote")` →
     `run_workflow("braker3_annotation_workflow", **bundle,
     source_prompt="...")` → inspect `recipe_id` + `outputs` dict.
   - Worked example 2: `list_entries(pipeline_family="annotation")` →
     pick a task → `run_task("exonerate_align_chunk", bindings={...},
     inputs={...})`.
   - Worked example 3: `$ref` chain — BRAKER3 output becomes EVM input
     via `bindings={"AnnotationGff": {"$ref": {"run_id": ...,
     "output_name": "annotation_gff"}}}`.
   - Appendix: Inspect-Before-Execute (prepare_run_recipe +
     validate_run_recipe + run_slurm_recipe) — one short section.
   - New subsection "Binding grammar" showing all three forms side-by-side
     (raw path / `$manifest` / `$ref`) with a one-line comment on each.
     (Alternative: a dedicated `docs/binding_grammar.md` linked from
     showcase — pick whichever reads cleaner; don't duplicate.)
   - Short "Adding a Pipeline Family" section linking
     `.codex/registry.md`.

2. `docs/tutorial_context.md` — typed-binding prompt templates:
   - One template per supported planner type (`ReferenceGenome`,
     `ReadSet`, `ProteinEvidenceSet`, `AnnotationEvidenceSet`, etc.) —
     each showing the raw-path form and referencing the `$ref` and
     `$manifest` forms.
   - Add a `$ref` cross-run-reuse example showing the conversation: "run
     BRAKER3 → the reply includes `recipe_id` → pass that recipe_id as
     `run_id` in the next call's `$ref` binding". Make the continuity
     between replies obvious.

3. `docs/braker3_evm_notes.md` — do NOT rewrite. `rg -n 'run_task\(|
   run_workflow\(|inputs\s*=\s*\{' docs/braker3_evm_notes.md`; for each
   hit, only update the call syntax to the new shape. Leave the biology
   narrative alone.

Verification:

- `rg -n 'run_task\(|run_workflow\(' docs/` — every hit uses the new
  shape; no flat `inputs=...` executable examples remain.
- `rg -n '\$ref|\$manifest' docs/mcp_showcase.md` — present (the grammar
  subsection exists).
- A fresh-eyes read of `docs/mcp_showcase.md` answers: "How do I run my
  first BRAKER3 workflow?" in the first 30 lines.
- `rg -n "load_bundle\(" docs/` — at least one worked example in each of
  `docs/mcp_showcase.md` and `docs/tutorial_context.md`.

Commit message: "docs: rewrite user walkthroughs around the experiment loop and binding grammar".

Then mark Step 29 Complete in docs/mcp_reshape/checklist.md.
```
