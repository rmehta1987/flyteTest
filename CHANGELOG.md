# Changelog

This file records milestone-level changes in FLyteTest so repo scope, MCP
surface changes, and prompt-driven handoff work are easier to track over time.

Guidelines:

- add new entries at the top under `Unreleased` until a milestone is finalized
- describe what actually changed, not planned work
- keep scope boundaries honest, especially for deferred post-PASA stages
- link to prompt or checklist docs when they were part of the milestone handoff
- use strikethrough for milestone items that were later removed, renamed, or superseded during refactoring, and add a short note explaining what replaced them

Entry template:

```markdown
## Unreleased

### Milestone name or date

- added:
  - short factual change
- changed:
  - short factual change
- deferred:
  - short factual change
- ~~removed or superseded item~~
  - replaced by: short explanation
  - reason: refactor, scope correction, renamed contract, or other concise note
```

## Unreleased

### Authenticated Slurm access boundary

- changed:
  - `run_slurm_recipe`, `monitor_slurm_job`, and `cancel_slurm_job` now report
    explicit unsupported-environment limitations when FLyteTest is running
    outside an already-authenticated scheduler-capable environment
  - Slurm lifecycle diagnostics now distinguish missing CLI commands and
    scheduler reachability issues from ordinary lifecycle state
  - README, MCP showcase docs, capability notes, and the Milestone 16 Part 2
    handoff docs now describe the supported Slurm topology as a local
    MCP/server process running inside an authenticated HPC session

### TaskEnvironment catalog refactor

- added:
  - centralized shared Flyte `TaskEnvironment` defaults in
    `src/flytetest/config.py`
  - introduced a declarative task-environment catalog plus compatibility
    aliases for current task families
  - added explicit per-family runtime overrides for BRAKER3 annotation and
    BUSCO QC so the catalog reflects real workload differences
  - added focused tests for the shared defaults and alias stability
- changed:
  - reduced repetition in the task-environment setup so future task families
    can inherit shared runtime policy from one place

### Local recipe execution robustness

- changed:
  - collection-shaped workflow inputs such as `protein_fastas: list[File]`
    now bypass the local `flyte run --local` wrapper in MCP/server execution
    and use direct Python workflow invocation instead
  - this avoids the current Flyte 2.1.2 CLI serialization gap where
    collection inputs are parsed as JSON but nested `File` / `Dir` values are
    not rehydrated for workflow execution

### AGAT post-processing milestone

- added:
  - implemented the AGAT statistics slice as `agat_statistics` plus the
    `annotation_postprocess_agat` workflow wrapper
  - implemented the AGAT conversion slice as `agat_convert_sp_gxf2gxf` plus
    the `annotation_postprocess_agat_conversion` workflow wrapper
  - implemented the AGAT cleanup slice as `agat_cleanup_gff3` plus the
    `annotation_postprocess_agat_cleanup` workflow wrapper
  - added synthetic AGAT coverage in `tests/test_agat.py`
  - updated the AGAT tool reference, stage index, capability snapshot,
    registry, compatibility exports, and prompt handoff docs to reflect the
    new post-EggNOG boundary
- changed:
  - advanced the implemented biological scope from EggNOG functional
    annotation into the AGAT post-processing slices on the
    EggNOG-annotated and AGAT-converted GFF3 bundles
- deferred:
  - `table2asn` remains a downstream stage outside these slices

### EggNOG functional annotation milestone

- added:
  - implemented the `annotation_functional_eggnog` workflow for the
    post-BUSCO functional-annotation milestone
  - added the EggNOG task family: `eggnog_map` and `collect_eggnog_results`
  - added synthetic EggNOG coverage in `tests/test_eggnog.py`
  - updated the EggNOG tool reference, stage index, capability matrix, tutorial
    context, and milestone checklist to track the new boundary
- changed:
  - advanced the implemented biological scope from BUSCO-based annotation QC
    into EggNOG functional annotation while keeping AGAT and `table2asn`
    deferred
  - updated the registry, compatibility exports, README milestone tables,
    planning adapters, and prompt handoff docs to expose the new boundary
    explicitly
- deferred:
  - AGAT and `table2asn` remain downstream stages outside this milestone

### BUSCO annotation QC milestone

- added:
  - implemented the `annotation_qc_busco` workflow for post-repeat-filtering annotation QC
  - added the BUSCO task family: `busco_assess_proteins` and `collect_busco_results`
  - added synthetic BUSCO coverage in `tests/test_functional.py`
  - added a BUSCO milestone handoff prompt in `docs/busco_submission_prompt.md`
- changed:
  - advanced the implemented biological scope from repeat-filtered GFF3/protein collection through BUSCO-based annotation QC while keeping EggNOG, AGAT, and submission-prep deferred
  - updated the registry, compatibility exports, README milestone tables, stage index, and BUSCO tool reference to expose the new QC boundary explicitly
  - validated the BUSCO workflow with a real repo-local Apptainer runtime and explicit `_odb12` lineage datasets, and updated BUSCO docs to reflect the tested `flyte run` CLI surface and runtime paths
- deferred:
  - EggNOG, AGAT, and `table2asn` remain downstream stages outside this milestone

### Repeat filtering and cleanup milestone

- added:
  - implemented the post-PASA `annotation_repeat_filtering` workflow for RepeatMasker conversion, gffread protein extraction, funannotate overlap filtering, repeat blasting, deterministic removal transforms, and final repeat-free GFF3/protein FASTA collection
  - added the repeat-filtering task family: `repeatmasker_out_to_bed`, `gffread_proteins`, `funannotate_remove_bad_models`, `remove_overlap_repeat_models`, `funannotate_repeat_blast`, `remove_repeat_blast_hits`, and `collect_repeat_filter_results`
  - added synthetic repeat-filtering tests plus local RepeatMasker fixture-path coverage in `tests/test_repeat_filtering.py`
- changed:
  - advanced the implemented biological scope from PASA post-EVM refinement through repeat filtering and cleanup while keeping the later functional and submission stages deferred
  - updated the registry, compatibility exports, README milestone tables, tutorial context, and tool references to expose the repeat-filtering boundary explicitly
  - implemented `trinity_denovo_assemble`, updated `transcript_evidence_generation` to collect both Trinity branches, and removed PASA's external de novo Trinity FASTA requirement in favor of the transcript-evidence bundle
- deferred:
  - BUSCO, EggNOG, AGAT, and `table2asn` remain downstream stages outside this milestone

### Documentation and planning

- clarified the active milestone, stop rule, and stage-by-stage notes alignment in `README.md`
- added tutorial-backed prompt-planning context in `docs/tutorial_context.md`
- added stage-oriented tool-reference landing pages and prompt starters under `docs/tool_refs/`
- added refactor milestone tracking and handoff materials in `docs/refactor_completion_checklist.md` and `docs/refactor_submission_prompt.md`

### Codebase structure and workflow coverage

- split the repo into a package layout under `src/flytetest/` with separate task, workflow, type, registry, planning, and server modules
- implemented deterministic workflow coverage through PASA post-EVM refinement while keeping repeat filtering, BUSCO, EggNOG, AGAT, and `table2asn` deferred
- preserved the notes-faithful pre-EVM filename contract for `transcripts.gff3`, `predictions.gff3`, and `proteins.gff3`

### MCP showcase

- added a narrow FastMCP stdio server in `src/flytetest/server.py`
- limited the runnable MCP showcase to:
  - workflow `ab_initio_annotation_braker3`
  - task `exonerate_align_chunk`
- added prompt planning in `src/flytetest/planning.py` for explicit local-path extraction and hard downstream-stage declines
- added small read-only MCP resources for scope discovery:
  - `flytetest://scope`
  - `flytetest://supported-targets`
  - `flytetest://example-prompts`
- added a compact additive `result_summary` block to `prompt_and_run` responses for success, decline, and failure cases

### Validation and fixtures

- added synthetic MCP server coverage in `tests/test_server.py`
- staged lightweight tutorial-derived local fixture files under `data/` for bounded smoke testing

## Prompt Tracking

Current prompt/handoff docs already in the repo:

- `docs/refactor_submission_prompt.md`
- `docs/tutorial_context.md`
- `docs/tool_refs/stage_index.md`

Future improvement idea:

- add a small prompt archive directory for accepted milestone prompts once the current MCP contract stabilizes
- add an environment preflight layer that checks for the active interpreter, `mcp`, `flyte`, and other required tools instead of assuming they are already available
