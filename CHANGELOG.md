# Changelog

This file records milestone-level changes in FLyteTest so repo scope, MCP
surface changes, prompt-driven handoff work, and in-progress work notes are
easier to track over time.

Guidelines:

- add new entries at the top under `Unreleased` until a milestone is finalized
- describe what actually changed, not planned work
- keep scope boundaries honest, especially for deferred post-PASA stages
- link to prompt or checklist docs when they were part of the milestone handoff
- use strikethrough for milestone items that were later removed, renamed, or superseded during refactoring, and add a short note explaining what replaced them
- treat this file as the shared working memory for meaningful units of work;
  update it after each completed slice instead of waiting for a final wrap-up
- use dated checklist items or dated bullets for completed work so the timeline
  is obvious to later agents
- record what was tried, what worked, what failed, what remains blocked, and
  any dead ends that should not be retried without a new reason
- add newly discovered follow-up tasks while implementation is still in
  progress so they are not lost between sessions

Entry template:

```markdown
## Unreleased

### Milestone name or date

- [ ] short factual change
- [x] completed factual change (2026-04-11)
- [ ] blocked follow-up or discovered task
- [ ] failed approach to avoid retrying without a new reason
- ~~removed or superseded item~~
  - replaced by: short explanation
  - reason: refactor, scope correction, renamed contract, or other concise note
```

## Unreleased

### Validation sweep after Milestone 15 review

- [x] 2026-04-11 fixed the `prepare_evm_transcript_inputs` signature typo so
  the pre-EVM consensus workflow and tests consistently use `pasa_results`
- [x] 2026-04-11 verified full local unittest discovery after the Milestone 15
  review fixes: 237 tests passing, 1 live Slurm smoke skipped because `sbatch`
  is required

### Milestone 15 Phase 2: Planning Integration & Approval Gating

- [x] 2026-04-11 extended `_planning_goal_for_typed_request()` to try
  registry-constrained composition fallback when hardcoded patterns don't match
- [x] 2026-04-11 integrated composition algorithm into planning layer via
  `_try_composition_fallback()` function that queries synthesis-eligible stages
  and attempts path discovery for common output types
- [x] 2026-04-11 added `requires_user_approval` flag to `plan_typed_request()`
  response so composed workflows are explicitly marked as needing approval
- [x] 2026-04-11 implemented approval gating in `_prepare_run_recipe_impl()`
  to prevent artifact save when composition requires approval
- [x] 2026-04-11 fixed `_workflow_spec_for_typed_goal()` to support
  arbitrary multi-stage workflow specs (not just hardcoded 2-entry repeat+BUSCO)
- [x] 2026-04-11 created `tests/test_planning_composition.py` with focused
  integration tests for composition fallback and approval gating
- [x] 2026-04-11 updated README.md with Workflow Composition section
  explaining discovery, approval requirements, and bounding parameters
- [x] 2026-04-11 updated docs/capability_maturity.md marking Registry-driven
  composition as "Current" instead of "Close", added M15 Phase 2 to Near-Term
  Priorities
- [x] 2026-04-11 fixed a regression where unrelated prompts and known day-one
  missing-input declines could fall through to registry-composition candidates
- [x] 2026-04-11 verified the focused composition/planning coverage after adding
  regression tests for fallback intent gating
- [x] 2026-04-11 backward compatible: hardcoded patterns checked before
  composition fallback, existing requests behave identically

### Milestone 16 Slurm lifecycle observability

- [x] 2026-04-11 added durable Slurm run-record loading and reconciliation
  through `squeue`, `scontrol show job`, and `sacct`
- [x] 2026-04-11 added explicit `monitor_slurm_job` and `cancel_slurm_job`
  MCP operations for submitted jobs
- [x] 2026-04-11 added terminal-state recording for stdout, stderr, exit code,
  and cancellation details in the durable run record
- [x] 2026-04-11 added focused tests for reconciliation, cancellation, and
  stale-record handling
- [x] 2026-04-11 changed the Slurm execution boundary so it now tracks job
  lifecycle state explicitly instead of treating submission as the end of the
  scheduler contract

### Protein-evidence Slurm smoke

- [x] 2026-04-11 added RCC wrapper scripts for submitting, monitoring, and
  cancelling the protein-evidence Slurm recipe from frozen run records
- [x] 2026-04-11 added a validated protein-evidence Slurm path that freezes
  the recipe, submits it, and persists the latest run-record and artifact
  pointers under `.runtime/runs/`
- [x] 2026-04-11 added supporting smoke and debug helpers for the
  protein-evidence HPC workflow
- [x] 2026-04-11 changed the protein-evidence stage so it now has an explicit
  HPC validation path in addition to the local fixture and workflow tests

### Tool reference normalization

- [x] 2026-04-11 normalized `docs/tool_refs/` so every tool reference now
  includes `Input Data`, `Output Data`, and `Code Reference` sections
- [x] 2026-04-11 added code back-links from the tool refs to the relevant task
  and workflow modules, including the deferred `table2asn` boundary
- [x] 2026-04-11 updated `docs/tool_refs/README.md` and
  `docs/tool_refs/stage_index.md` so the stage index and tool-reference
  guidance reflect the implemented workflow surface more honestly
- [x] 2026-04-11 refreshed stale stage notes in the BRaker3, PASA, EVM,
  TransDecoder, Trinity, BUSCO, EggNOG, AGAT, Exonerate, Salmon, FastQC, and
  repeat-filtering references to match the current code paths

### Authenticated Slurm access boundary

- [x] 2026-04-11 changed `run_slurm_recipe`, `monitor_slurm_job`, and
  `cancel_slurm_job` so they now report explicit unsupported-environment
  limitations when FLyteTest is running outside an already-authenticated
  scheduler-capable environment
- [x] 2026-04-11 changed Slurm lifecycle diagnostics so they distinguish
  missing CLI commands and scheduler reachability issues from ordinary
  lifecycle state
- [x] 2026-04-11 updated README, MCP showcase docs, capability notes, and the
  Milestone 16 Part 2 handoff docs so they describe the supported Slurm
  topology as a local MCP/server process running inside an authenticated HPC
  session
- [x] 2026-04-11 updated README and MCP showcase docs with Codex CLI and
  OpenCode client setup examples plus the validated prompt sequence for
  prepare, submit, monitor, and cancel on the protein-evidence Slurm path

### TaskEnvironment catalog refactor

- [x] 2026-04-11 centralized shared Flyte `TaskEnvironment` defaults in
  `src/flytetest/config.py`
- [x] 2026-04-11 introduced a declarative task-environment catalog plus
  compatibility aliases for current task families
- [x] 2026-04-11 added explicit per-family runtime overrides for BRAKER3
  annotation and BUSCO QC so the catalog reflects real workload differences
- [x] 2026-04-11 added focused tests for the shared defaults and alias
  stability
- [x] 2026-04-11 reduced repetition in the task-environment setup so future
  task families can inherit shared runtime policy from one place

### Local recipe execution robustness

- [x] 2026-04-11 changed collection-shaped workflow inputs such as
  `protein_fastas: list[File]` so they now bypass the local `flyte run
  --local` wrapper in MCP/server execution and use direct Python workflow
  invocation instead
- [x] 2026-04-11 avoided the current Flyte 2.1.2 CLI serialization gap where
  collection inputs are parsed as JSON but nested `File` / `Dir` values are
  not rehydrated for workflow execution

### AGAT post-processing milestone

- [x] 2026-04-11 implemented the AGAT statistics slice as `agat_statistics`
  plus the `annotation_postprocess_agat` workflow wrapper
- [x] 2026-04-11 implemented the AGAT conversion slice as
  `agat_convert_sp_gxf2gxf` plus the `annotation_postprocess_agat_conversion`
  workflow wrapper
- [x] 2026-04-11 implemented the AGAT cleanup slice as `agat_cleanup_gff3`
  plus the `annotation_postprocess_agat_cleanup` workflow wrapper
- [x] 2026-04-11 added synthetic AGAT coverage in `tests/test_agat.py`
- [x] 2026-04-11 updated the AGAT tool reference, stage index, capability
  snapshot, registry, compatibility exports, and prompt handoff docs to
  reflect the new post-EggNOG boundary
- [x] 2026-04-11 advanced the implemented biological scope from EggNOG
  functional annotation into the AGAT post-processing slices on the
  EggNOG-annotated and AGAT-converted GFF3 bundles
- [ ] deferred: `table2asn` remains a downstream stage outside these slices

### EggNOG functional annotation milestone

- [x] 2026-04-11 implemented the `annotation_functional_eggnog` workflow for
  the post-BUSCO functional-annotation milestone
- [x] 2026-04-11 added the EggNOG task family: `eggnog_map` and
  `collect_eggnog_results`
- [x] 2026-04-11 added synthetic EggNOG coverage in `tests/test_eggnog.py`
- [x] 2026-04-11 updated the EggNOG tool reference, stage index, capability
  matrix, tutorial context, and milestone checklist to track the new boundary
- [x] 2026-04-11 advanced the implemented biological scope from BUSCO-based
  annotation QC into EggNOG functional annotation while keeping AGAT and
  `table2asn` deferred
- [x] 2026-04-11 updated the registry, compatibility exports, README
  milestone tables, planning adapters, and prompt handoff docs to expose the
  new boundary explicitly
- [ ] deferred: AGAT and `table2asn` remain downstream stages outside this
  milestone

### BUSCO annotation QC milestone

- [x] 2026-04-11 implemented the `annotation_qc_busco` workflow for post-
  repeat-filtering annotation QC
- [x] 2026-04-11 added the BUSCO task family: `busco_assess_proteins` and
  `collect_busco_results`
- [x] 2026-04-11 added synthetic BUSCO coverage in `tests/test_functional.py`
- [x] 2026-04-11 added a BUSCO milestone handoff prompt in
  `docs/busco_submission_prompt.md`
- [x] 2026-04-11 advanced the implemented biological scope from repeat-
  filtered GFF3/protein collection through BUSCO-based annotation QC while
  keeping EggNOG, AGAT, and submission-prep deferred
- [x] 2026-04-11 updated the registry, compatibility exports, README
  milestone tables, stage index, and BUSCO tool reference to expose the new
  QC boundary explicitly
- [x] 2026-04-11 validated the BUSCO workflow with a real repo-local Apptainer
  runtime and explicit `_odb12` lineage datasets, and updated BUSCO docs to
  reflect the tested `flyte run` CLI surface and runtime paths
- [ ] deferred: EggNOG, AGAT, and `table2asn` remain downstream stages outside
  this milestone

### Repeat filtering and cleanup milestone

- [x] 2026-04-11 implemented the post-PASA `annotation_repeat_filtering`
  workflow for RepeatMasker conversion, gffread protein extraction,
  funannotate overlap filtering, repeat blasting, deterministic removal
  transforms, and final repeat-free GFF3/protein FASTA collection
- [x] 2026-04-11 added the repeat-filtering task family:
  `repeatmasker_out_to_bed`, `gffread_proteins`, `funannotate_remove_bad_models`,
  `remove_overlap_repeat_models`, `funannotate_repeat_blast`,
  `remove_repeat_blast_hits`, and `collect_repeat_filter_results`
- [x] 2026-04-11 added synthetic repeat-filtering tests plus local
  RepeatMasker fixture-path coverage in `tests/test_repeat_filtering.py`
- [x] 2026-04-11 advanced the implemented biological scope from PASA post-EVM
  refinement through repeat filtering and cleanup while keeping the later
  functional and submission stages deferred
- [x] 2026-04-11 updated the registry, compatibility exports, README milestone
  tables, tutorial context, and tool references to expose the repeat-
  filtering boundary explicitly
- [x] 2026-04-11 implemented `trinity_denovo_assemble`, updated
  `transcript_evidence_generation` to collect both Trinity branches, and
  removed PASA's external de novo Trinity FASTA requirement in favor of the
  transcript-evidence bundle
- [ ] deferred: BUSCO, EggNOG, AGAT, and `table2asn` remain downstream stages
  outside this milestone

### Documentation and planning

- [x] 2026-04-11 clarified the active milestone, stop rule, and stage-by-stage
  notes alignment in `README.md`
- [x] 2026-04-11 added tutorial-backed prompt-planning context in
  `docs/tutorial_context.md`
- [x] 2026-04-11 added stage-oriented tool-reference landing pages and prompt
  starters under `docs/tool_refs/`
- [x] 2026-04-11 added refactor milestone tracking and handoff materials in
  `docs/refactor_completion_checklist.md` and
  `docs/refactor_submission_prompt.md`

### Codebase structure and workflow coverage

- [x] 2026-04-11 split the repo into a package layout under `src/flytetest/`
  with separate task, workflow, type, registry, planning, and server modules
- [x] 2026-04-11 implemented deterministic workflow coverage through PASA
  post-EVM refinement while keeping repeat filtering, BUSCO, EggNOG, AGAT,
  and `table2asn` deferred
- [x] 2026-04-11 preserved the notes-faithful pre-EVM filename contract for
  `transcripts.gff3`, `predictions.gff3`, and `proteins.gff3`

### MCP showcase

- [x] 2026-04-11 added a narrow FastMCP stdio server in
  `src/flytetest/server.py`
- [x] 2026-04-11 limited the runnable MCP showcase to workflow
  `ab_initio_annotation_braker3` and task `exonerate_align_chunk`
- [x] 2026-04-11 added prompt planning in `src/flytetest/planning.py` for
  explicit local-path extraction and hard downstream-stage declines
- [x] 2026-04-11 added small read-only MCP resources for scope discovery:
  `flytetest://scope`, `flytetest://supported-targets`, and
  `flytetest://example-prompts`
- [x] 2026-04-11 added a compact additive `result_summary` block to
  `prompt_and_run` responses for success, decline, and failure cases

### Validation and fixtures

- [x] 2026-04-11 added synthetic MCP server coverage in `tests/test_server.py`
- [x] 2026-04-11 staged lightweight tutorial-derived local fixture files under
  `data/` for bounded smoke testing

## Prompt Tracking

Current prompt/handoff docs already in the repo:

- `docs/refactor_submission_prompt.md`
- `docs/tutorial_context.md`
- `docs/tool_refs/stage_index.md`

Future improvement idea:

- [ ] add a small prompt archive directory for accepted milestone prompts
  once the current MCP contract stabilizes
- [ ] add an environment preflight layer that checks for the active
  interpreter, `mcp`, `flyte`, and other required tools instead of assuming
  they are already available
