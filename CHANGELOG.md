# Changelog

This file records milestone-level changes in FLyteTest so repo scope, MCP
surface changes, prompt-driven handoff work, and in-progress work notes are
easier to track over time.

Guidelines:

- add new entries immediately below `## Unreleased`, above all existing sections — newest section always first; never append to the bottom
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

### Milestone N — Short Title (YYYY-MM-DD)

- [x] YYYY-MM-DD description
```

## Unreleased

### Critique follow-up — first-run FASTQ walkthrough (2026-04-26)

- [x] 2026-04-26 Step 05b: added a "First run, end-to-end" section to `SCIENTIST_GUIDE.md` between the experiment-loop overview and the prior-run reuse section. Walks the seven calls — `list_entries → list_bundles → load_bundle → run_workflow(dry_run=True) → validate_run_recipe → run_slurm_recipe → monitor_slurm_job` — using `variant_calling_germline_minimal` (NA12878 chr20) as the worked example. Each step has 2-3 lines on what the scientist sees and what could go wrong; preflight-failure step cites `staging.py:check_offline_staging` and the `StagingFinding` kinds.

### Critique follow-up — scientist glossary block (2026-04-26)

- [x] 2026-04-26 Step 05a: added a five-term `## Glossary` block at the top of `SCIENTIST_GUIDE.md`, immediately after the title and before TL;DR. Definitions cover recipe, bundle, manifest, run record, and execution profile — the five terms that appear most often in tool descriptions and decline messages but were never defined in user-facing docs. One line per definition; no nesting; no emoji.

### Critique follow-up — split CHANGELOG.md (2026-04-26)

- [x] 2026-04-26 Step 04c: split `CHANGELOG.md` (was 1932 lines) into a live file (~530 lines) plus `CHANGELOG.archive.md` (1409 lines). The split point sits between the GATK Milestone A block (kept) and the older Track A / MCP Reshape work (moved). Strict 90-day cutoff didn't apply (project history is only ~20 days deep), so the cut was chosen by the natural milestone boundary that satisfies the <600-line acceptance target. Added a one-line pointer at the bottom of `CHANGELOG.md`.

### Critique follow-up — retention policy for docs/archive (2026-04-26)

- [x] 2026-04-26 Step 04b: rewrote `docs/archive/README.md` to document a 60-day retention window (anything older recoverable from git tags / commit history). No deletions were made — the oldest archive entry is 2026-04-06 (20 days old), so nothing has crossed the cutoff yet. First eligible pruning date is 2026-06-05. Acceptance: file count is 50 (already under the <80 target); README documents the policy and the prune workflow.

### Critique follow-up — strip boilerplate test docstrings (2026-04-26)

- [x] 2026-04-26 Step 04a: removed 230 occurrences of the boilerplate sentence "This test keeps the current contract explicit and guards the documented behavior against regression." across 25 test files. Each occurrence was the trailing line of a docstring; the test-specific summary line was preserved. Test counts unchanged (902 passed). The class-level variant ("This test class keeps...") is intentionally outside the acceptance criterion of step 04a and was not touched.

### Critique follow-up — dedupe ReferenceGenome (2026-04-26)

- [x] 2026-04-26 Step 03: collapsed two `ReferenceGenome` definitions into one. Kept the `planner_types.py` version (carries `PlannerSerializable` mixin); deleted the plain dataclass from `types/assets.py`. The asset version was a strict subset, so consolidation just adds 3 optional fields (`source_result_dir`, `source_manifest_path`, `notes`) to consumers. Updated 5 import sites: `tests/test_resolver.py`, `tests/test_planner_types.py`, `tests/test_serialization_regression.py`, `src/flytetest/planner_adapters.py`, `src/flytetest/types/__init__.py`. Added a `from flytetest.planner_types import ReferenceGenome` to `types/assets.py` for the 4 forward-reference annotations that still mention `ReferenceGenome` as a field type. Updated one snapshot in `test_braker3_bundle_serialize_exact_shape` to reflect the 3 new fields. 902 tests pass.

### Critique follow-up — collapse MCP entry points (2026-04-26)

- [x] 2026-04-26 Step 01 decision: keep the experiment loop (`list_entries → list_bundles → load_bundle → run_task / run_workflow`) as the canonical scientist entry point; un-register `prompt_and_run` and `plan_request` from the MCP surface. Decision document in `docs/2026-04-25-critique-followup/critique-followup_plan.md`.
- [x] 2026-04-26 Step 02: removed `"plan_request"` and `PRIMARY_TOOL_NAME` from `LIFECYCLE_TOOLS` in `src/flytetest/mcp_contract.py`; removed the corresponding `TOOL_DESCRIPTIONS` entries; deleted the two `mcp.tool(...)` registration lines in `src/flytetest/server.py:create_mcp_server`. Python definitions for `plan_request` and `prompt_and_run` retained for internal callers and existing tests; `PRIMARY_TOOL_NAME` constant retained because four MCP resource functions still surface it as `"primary_tool"`. 902 tests pass.

### On-ramp implementation — run_tool extension + my_custom_filter (2026-04-24)

- [x] 2026-04-24 `config.py`: extended `run_tool` with `python_callable` + `callable_kwargs` keyword-only parameters; Python-callable mode invokes a function in-process with no subprocess overhead; native executable mode (Rscript, compiled C++, system binary) now explicitly documented alongside the existing SIF/container path; all three modes tested in `tests/test_run_tool.py` (10 tests).
- [x] 2026-04-24 `tasks/_filter_helpers.py` (new): pure-Python `filter_vcf` — plain-text VCF QUAL threshold filter; no external dependencies; missing QUAL (`.`) treated as below threshold; 8 unit tests in `tests/test_my_filter.py`.
- [x] 2026-04-24 `tasks/variant_calling.py`: added `my_custom_filter` task (Python-callable mode, `vcf_path: File → File`, `min_qual: float = 30.0`); appended `"my_filtered_vcf"` to `MANIFEST_OUTPUT_KEYS`; manifest written as `run_manifest_my_custom_filter.json`.
- [x] 2026-04-24 `registry/_variant_calling.py`: added `RegistryEntry` for `my_custom_filter` (`pipeline_stage_order=22`, `accepted/produced=VariantCallSet`, `runtime_images={}`, `module_loads=("python/3.11.9",)`).
- [x] 2026-04-24 `server.py`: appended `"my_custom_filter": (("min_qual", False),)` to `TASK_PARAMETERS`; no other server changes.
- [x] 2026-04-24 Tests: `MyCustomFilterInvocationTests` (Layer 2), `MyCustomFilterRegistryTests` (Layer 3), `MyCustomFilterMCPExposureTests` (Layer 4) — 22 tests total across all three layers in `tests/test_variant_calling.py`.
- [x] 2026-04-24 `.codex/user_tasks.md`: replaced "SIF images — three cases" with a three-mode execution table (SIF, native, Python callable) including the new `run_tool` callable form; updated testing section to document that pure-Python tasks need no `run_tool` patch; linked to `my_custom_filter` as the copyable template.
- [x] 2026-04-24 `.codex/agent/scaffold.md`: corrected Core Principle 1 from "four file edits" to the accurate six required touch points; updated Generation Order step 1 to list all three `run_tool` modes.

### Docs polish — bug fixes, README rewrite, SCIENTIST_GUIDE GATK runbook, rcc README (2026-04-24)

- [x] 2026-04-24 Bug fixes (pre-existing in `8c513f5`): stale `build_gatk_local_sif.sh` reference replaced in `bundles.py` fetch_hints (`pull_gatk_image.sh` + `build_bwa_mem2_sif.sh`); duplicate step-3 numbering and stale `target=` MCP snippet removed from `stage_gatk_local.sh`; `module_loads` corrected for `pre_call_coverage_qc` (added `multiqc`), `post_call_qc_summary` (bcftools + multiqc, no gatk), and `annotate_variants_snpeff` (snpeff only).
- [x] 2026-04-24 `README.md`: rewrote from 656 → 103 lines; now a stable landing page with 7 sections (summary, orientation table, scope snapshot, quick start, doc map, limits, repo layout); removed task/workflow enumeration, milestone history, and MCP parameter galleries.
- [x] 2026-04-24 `SCIENTIST_GUIDE.md`: added "GATK Germline Variant Calling" section (~118 lines); covers prerequisites, 5-step runbook (prepare_reference → preprocess_sample → germline_short_variant_discovery → QC → annotation), key parameter notes (module_loads escape hatch, run_record_path, scontrol vs sacct distinction), further reading links.
- [x] 2026-04-24 `scripts/rcc/README.md`: added four new sections — Container images (SIF table + module-first priority rule), module_loads (full-replacement semantics + escape hatch), GATK data staging sequence (5-step ordered guide), Slurm job lifecycle commands (scontrol vs sacct distinction).

### MCP surface polish — runtime_images key, shared_fs_roots, dry_run staging (2026-04-24)

- [x] 2026-04-24 `bundles.py`: renamed `"sif_path"` → `"gatk_sif"` in GATK bundle `runtime_images` so `load_bundle(**bundle)` spreads the GATK SIF to the correct task parameter without manual override; affects `variant_calling_germline_minimal` and `variant_calling_vqsr_chr20`.
- [x] 2026-04-24 `server.py`: `run_slurm_recipe` now accepts `shared_fs_roots: list[str] | None = None` and passes it to `SlurmWorkflowSpecExecutor.submit`; matches `validate_run_recipe` behaviour so scientists get staging enforcement at submission time, not only at validation time.
- [x] 2026-04-24 `server.py`: `run_task` and `run_workflow` `dry_run=True` now call `check_offline_staging` on the frozen artifact and populate `staging_findings` in the `DryRunReply`; `supported` remains `True` regardless of findings (informational only); scientists can inspect staging issues before committing to submission.

### User-authoring on-ramp — guide + scaffolding agent (2026-04-24)

- [x] 2026-04-24 added `.codex/user_tasks.md` — condensed user-facing walkthrough for bringing custom Python logic into an existing pipeline family; covers module layout, binding contract via `accepted_planner_types`, `MANIFEST_OUTPUT_KEYS`, three SIF modes (pure-Python / native / containerized), and three-layer no-SIF testing strategy; worked example uses a custom variant filter after `joint_call_gvcfs`.
- [x] 2026-04-24 added `.codex/agent/scaffold.md` — unified specialist role prompt that turns a stated user intent into a coordinated patch (task wrapper + registry entry + test stub + CHANGELOG line); enforces signature/registry mirroring, MANIFEST_OUTPUT_KEYS contract, and decline conditions for new planner types / new families / MCP-surface edits.
- [x] 2026-04-24 updated `CLAUDE.md` specialist-guides table and `.codex/agent/README.md` role index to list the new guide and scaffolding role.

### GATK Milestone I — Complete (2026-04-24)

Scientific completeness + task-pattern unification. Every GATK task is
now `@variant_calling_env.task`-decorated with `File`/`Dir` I/O; hard-filter
fallback, QC bookends, and SnpEff annotation fill the remaining biology
gaps from the 2026-04-23 review.

- [x] 2026-04-24 Step 01: ported bwa_mem2_index, bwa_mem2_mem, sort_sam, mark_duplicates to @variant_calling_env.task with File/Dir I/O; added library_id (default f"{sample_id}_lib") and platform (default "ILLUMINA") to bwa_mem2_mem; preprocess_sample workflow updated to consume File returns; signature now returns File instead of dict.
- [x] 2026-04-24 Step 02: ported merge_bam_alignment, gather_vcfs, variant_recalibrator, apply_vqsr, calculate_genotype_posteriors to @variant_calling_env.task; added sample_count (int) and annotations (list[str] | None) to variant_recalibrator; four workflows updated (preprocess_sample_from_ubam, genotype_refinement, scattered_haplotype_caller, post_genotyping_refinement).
- [x] 2026-04-24 Step 03: variant_recalibrator: annotations override + auto-add InbreedingCoeff when mode==SNP and sample_count>=10 (GATK Best Practices); effective annotation list recorded in manifest inputs; renamed scattered_haplotype_caller → sequential_interval_haplotype_caller everywhere (src, tests, docs); manifest assumptions updated to describe synchronous-serial execution explicitly (Milestone K HPC work).
- [x] 2026-04-24 Step 04: added variant_filtration task (stage 17) wrapping GATK VariantFiltration with GATK Best Practices hard-filtering defaults; added small_cohort_filter workflow (stage 8) with two-pass SNP→INDEL structure; registry entries wired with showcase_module; docs/tool_refs/gatk4.md updated.
- [x] 2026-04-24 Step 05: added collect_wgs_metrics (Picard, stage 18), bcftools_stats (stage 19), multiqc_summarize (stage 20); added pre_call_coverage_qc (workflow stage 9) and post_call_qc_summary (workflow stage 10); MultiQC aggregates via deterministic copy-into-scan-root; tool refs authored (picard_wgs_metrics.md, bcftools.md, multiqc.md).
- [x] 2026-04-24 Step 06: added snpeff_annotate task (stage 21) and annotate_variants_snpeff workflow (stage 11); snpeff_data_dir declared as offline-staging-checkable; scripts/rcc/download_snpeff_db.sh added; docs/tool_refs/snpeff.md authored.
- [x] 2026-04-24 Step 07: all 14 new/ported tasks added to TASK_PARAMETERS; planning intent extended for filter/QC/annotation keywords (GATK-specific only to avoid cross-family conflicts); docs/gatk_pipeline_overview.md refreshed (21 tasks + 11 workflows + new DAG).
- [x] 2026-04-24 full pytest green (858 passed, 1 skipped).
- [!] Breaking: bwa_mem2_index, bwa_mem2_mem, sort_sam, mark_duplicates, merge_bam_alignment, gather_vcfs, variant_recalibrator, apply_vqsr, calculate_genotype_posteriors signatures changed from (str, ..., results_dir) → (File, ...). External callers must migrate.
- [!] Breaking: preprocess_sample, preprocess_sample_from_ubam, genotype_refinement, post_genotyping_refinement return File not dict.
- [!] Breaking: scattered_haplotype_caller no longer exists; use sequential_interval_haplotype_caller.
- Remaining deferred: real scheduler-level scatter (Milestone K), VEP annotation (Milestone K), MultiQC config customization (Milestone K), somatic/CNV/SV families (out of scope).

### GATK Milestone H Migration — Breaking-Change Follow-up (2026-04-23)

Post-H migration sweep for external consumers of the two breaking changes.

- [x] 2026-04-23 audited manifest reads repo-wide; 0 task-level reads found referencing run_manifest.json from a task output directory — all server.py and test hits are workflow-level reads.
- [x] 2026-04-23 audited post_genotyping_refinement callers; 0 live call sites pass ref_path=; 0 saved recipes reference post_genotyping_refinement.
- [x] 2026-04-23 doc sweep: docs/gatk_pipeline_overview.md and mcp_showcase.md are accurate; no old signature examples found.
- [x] 2026-04-23 full pytest green (808 passed, 1 skipped).

### GATK Milestone H — Complete (2026-04-23)

GATK production wiring: MCP surface exposure, P0 fixes, signature and
idempotency cleanups. Closes the claim-vs-reality gap from the
2026-04-23 review — GATK is now reachable through the experiment loop.

- [x] 2026-04-23 Step 01: bwa_mem2_mem shell quoting (shlex.quote) + per-stage manifest filenames (run_manifest_<stage>.json) on all 16 tasks.
- [x] 2026-04-23 Step 02: 14 showcase_module assignments + 7 TASK_PARAMETERS entries + README/mcp_showcase.md update + resolver gracefully handles unregistered planner types.
- [x] 2026-04-23 Step 03: variant_calling planning intent branch covering all 14 MCP targets; variant_calling_germline_minimal KnownSites typed binding dropped; haplotype_caller stale assumption refreshed.
- [x] 2026-04-23 Step 04: post_genotyping_refinement ref_path dropped; prepare_reference idempotency (force=False); GenomicsDB ephemeral-only documented in pipeline overview.
- [x] 2026-04-23 full pytest green (808 passed, 1 skipped).
- Breaking: task-level manifests moved from run_manifest.json to run_manifest_<stage>.json. Workflow-level manifests unchanged.
- Breaking: post_genotyping_refinement no longer accepts ref_path. Any caller passing it must drop the keyword.
- Deferred to Milestone I: port 9 plain-Python helpers to Flyte task pattern; biology gaps (hard-filtering, variant annotation, post-call stats, pre-call coverage QC); true scatter parallelism; VQSR annotation parameterization; read-group parameterization.

### GATK Milestone H Step 04 — Workflow cleanups (2026-04-23)
- [x] 2026-04-23 dropped unused ref_path from post_genotyping_refinement; registry inputs and accepted_planner_types updated.
- [x] 2026-04-23 prepare_reference gained force=False idempotency; steps skip when outputs present; manifest tracks skipped_steps.
- [x] 2026-04-23 documented GenomicsDB ephemeral-only workspace as non-goal in pipeline overview.
- [x] 2026-04-23 added 4 PrepareReferenceIdempotencyTests + 2 PostGenotypingRefinementSignatureTests.
- [!] Breaking: post_genotyping_refinement no longer accepts ref_path. Any caller passing it must drop the keyword.

### GATK Milestone H Step 03 — Planning intent + bundle integrity (2026-04-23)
- [x] 2026-04-23 added variant_calling intent branch to planning.py covering all 14 MCP targets.
- [x] 2026-04-23 fixed variant_calling_germline_minimal: dropped stale KnownSites typed binding; scalar known_sites is authoritative.
- [x] 2026-04-23 swept haplotype_caller manifest assumption (Milestone F intervals now documented inline).
- [x] 2026-04-23 added 4 VariantCallingIntentTests + 1 bundle-consistency test.

### GATK Milestone H Step 02 — MCP surface wiring (2026-04-23)
- [x] 2026-04-23 set showcase_module on 7 variant_calling workflow entries.
- [x] 2026-04-23 set showcase_module on 7 Milestone A task entries.
- [x] 2026-04-23 added TASK_PARAMETERS entries for the 7 exposed tasks.
- [x] 2026-04-23 README "Current local MCP execution" list updated; biological scope updated.
- [x] 2026-04-23 mcp_showcase.md updated with 14 new entries.
- [x] 2026-04-23 added 5 MCP contract + server dispatch tests.
- [x] 2026-04-23 resolver gracefully handles unregistered planner types as missing requirements (instead of KeyError).
- Plain-Python helper tasks remain workflow-internal; full port deferred to Milestone I.

### GATK Milestone H Step 01 — P0 security + provenance fixes (2026-04-23)
- [x] 2026-04-23 bwa_mem2_mem: shlex.quote on ref_path, r1_path, r2_path, rg, output_bam.
- [x] 2026-04-23 per-stage manifest filenames (run_manifest_<stage>.json) on all 16 variant_calling tasks.
- [x] 2026-04-23 added BwaMem2MemShellQuotingTests (2 tests) and PerStageManifestFilenameTests (2 tests).
- [x] 2026-04-23 updated existing manifest tests to use per-stage filenames.
- [!] Breaking: task-level manifests moved from {results_dir}/run_manifest.json to {results_dir}/run_manifest_<stage>.json. Workflow-level manifests unchanged.

### GATK Milestone G — Complete (2026-04-23)

CalculateGenotypePosteriors and full GATK pipeline closure.

- [x] 2026-04-23 `calculate_genotype_posteriors` task (stage 16) + 5 unit tests.
- [x] 2026-04-23 `post_genotyping_refinement` workflow (stage 7) + 3 unit tests.
- [x] 2026-04-23 `docs/gatk_pipeline_overview.md` written (89 lines, ≤150).
- [x] 2026-04-23 `docs/tool_refs/gatk4.md` updated with CGP section.
- [x] 2026-04-23 full pytest suite green (787 passed, 1 skipped).
- Phase 3 GATK pipeline: complete (Milestones A–G, 16 tasks, 7 workflows).
- Remaining deferred: job arrays, hard-filtering (`VariantFiltration`), VQSR-on-CGP.

### GATK Milestone G Step 02 — post_genotyping_refinement workflow (2026-04-23)
- [x] 2026-04-23 added post_genotyping_refinement workflow (stage 7, single CGP call + manifest).
- [x] 2026-04-23 added registry entry (pipeline_stage_order=7, reusable_as_reference=True).
- [x] 2026-04-23 added 3 unit tests in PostGenotypingRefinementTests.
- [x] 2026-04-23 extended workflows MANIFEST_OUTPUT_KEYS with refined_vcf_cgp.

### GATK Milestone G Step 01 — calculate_genotype_posteriors task (2026-04-23)
- [x] 2026-04-23 added calculate_genotype_posteriors task (stage 16); no -R flag; --supporting-callsets optional.
- [x] 2026-04-23 added registry entry (pipeline_stage_order=16).
- [x] 2026-04-23 added 5 unit tests in CalculateGenotypePosteriorTests.
- [x] 2026-04-23 extended MANIFEST_OUTPUT_KEYS with cgp_vcf.
- [x] 2026-04-23 added calculate_genotype_posteriors to _VARIANT_CALLING_TASK_NAMES.

### GATK Milestone F — Complete (2026-04-23)

Interval-scoped HaplotypeCaller: optional intervals on `haplotype_caller`,
`gather_vcfs` task (stage 15), `scattered_haplotype_caller` workflow (stage 6).

- [x] 2026-04-23 `haplotype_caller` extended with optional `intervals` parameter (backward compatible).
- [x] 2026-04-23 `gather_vcfs` task (stage 15) + 4 unit tests.
- [x] 2026-04-23 `scattered_haplotype_caller` workflow (stage 6) + 5 unit tests.
- [x] 2026-04-23 `docs/tool_refs/gatk4.md` — `gather_vcfs` section added.
- [x] 2026-04-23 full pytest suite green (778 passed, 1 skipped).
- Deferred: `CalculateGenotypePosteriors` (Milestone G), `VariantAnnotator` (Milestone G).

### GATK Milestone F Step 03 — scattered_haplotype_caller workflow (2026-04-23)
- [x] 2026-04-23 added scattered_haplotype_caller workflow (stage 6); synchronous for-loop scatter.
- [x] 2026-04-23 added registry entry (workflow stage 6, reusable_as_reference=True).
- [x] 2026-04-23 added 5 unit tests in ScatteredHaplotypeCallerTests.
- [x] 2026-04-23 extended workflows MANIFEST_OUTPUT_KEYS with scattered_gvcf.

### GATK Milestone F Step 02 — gather_vcfs task (2026-04-23)
- [x] 2026-04-23 added gather_vcfs task (stage 15) with -I loop and --CREATE_INDEX.
- [x] 2026-04-23 added registry entry (pipeline_stage_order=15).
- [x] 2026-04-23 added 4 unit tests in GatherVcfsTests.
- [x] 2026-04-23 extended MANIFEST_OUTPUT_KEYS with gathered_gvcf.
- [x] 2026-04-23 added gather_vcfs to _VARIANT_CALLING_TASK_NAMES in contract test.

### GATK Milestone F Step 01 — haplotype_caller interval support (2026-04-23)
- [x] 2026-04-23 extended haplotype_caller with optional intervals parameter (backward compatible).
- [x] 2026-04-23 added 2 new tests; all existing HaplotypeCaller tests pass.

### GATK Milestone E — Complete (2026-04-23)

uBAM preprocessing path: `UnmappedBAM` type, `merge_bam_alignment` (task stage 14),
`preprocess_sample_from_ubam` workflow (stage 5).

- [x] 2026-04-23 `UnmappedBAM` planner type + round-trip serialization test.
- [x] 2026-04-23 `merge_bam_alignment` task (stage 14) + 5 unit tests.
- [x] 2026-04-23 `preprocess_sample_from_ubam` workflow (stage 5) + 4 unit tests.
- [x] 2026-04-23 `docs/tool_refs/gatk4.md` — `merge_bam_alignment` section added.
- [x] 2026-04-23 full pytest suite green (766 passed, 1 skipped).
- Deferred: interval-scoped `HaplotypeCaller` (Milestone F), `CalculateGenotypePosteriors` (Milestone G).

### GATK Milestone E Step 03 — preprocess_sample_from_ubam workflow (2026-04-23)
- [x] 2026-04-23 added preprocess_sample_from_ubam workflow (align → merge → dedup → BQSR, no sort_sam).
- [x] 2026-04-23 added registry entry (workflow stage 5, accepted_planner_types includes UnmappedBAM).
- [x] 2026-04-23 extended MANIFEST_OUTPUT_KEYS with preprocessed_bam_from_ubam.
- [x] 2026-04-23 added 4 unit tests in PreprocessSampleFromUbamWorkflowTests.

### GATK Milestone E Step 02 — merge_bam_alignment task (2026-04-23)
- [x] 2026-04-23 added merge_bam_alignment task (stage 14) with all 9 MergeBamAlignment flags.
- [x] 2026-04-23 added registry entry; extended MANIFEST_OUTPUT_KEYS with merged_bam.
- [x] 2026-04-23 added 5 unit tests in MergeBamAlignmentTests.

### GATK Milestone E Step 01 — UnmappedBAM planner type (2026-04-23)
- [x] 2026-04-23 added UnmappedBAM to src/flytetest/planner_types.py.
- [x] 2026-04-23 added round-trip test in tests/test_planner_types.py.

### GATK Milestone D — Complete (2026-04-23)

Closes Milestone D of the Phase 3 GATK port (tracker:
`docs/gatk_milestone_d/checklist.md`). Adds VQSR to the germline variant
calling pipeline: two tasks (`variant_recalibrator`, `apply_vqsr`), a
`genotype_refinement` workflow, the `variant_calling_vqsr_chr20` fixture
bundle, and `scripts/rcc/download_vqsr_training_vcfs.sh`.

- [x] 2026-04-23 variant_recalibrator task (stage 12) + 7 unit tests.
- [x] 2026-04-23 apply_vqsr task (stage 13) + 9 unit tests.
- [x] 2026-04-23 genotype_refinement workflow (stage 4) + 4 unit tests.
- [x] 2026-04-23 variant_calling_vqsr_chr20 bundle + download script.
- [x] 2026-04-23 docs/tool_refs/gatk4.md updated with variant_recalibrator + apply_vqsr sections.
- [x] 2026-04-23 full pytest green; python -m compileall clean.
- Deferred: merge_bam_alignment, interval-scoped HaplotypeCaller, CalculateGenotypePosteriors.

### GATK Milestone D Step 04 — VQSR fixture bundle + download script (2026-04-23)
- [x] 2026-04-23 added variant_calling_vqsr_chr20 bundle to src/flytetest/bundles.py.
- [x] 2026-04-23 created scripts/rcc/download_vqsr_training_vcfs.sh (10 files: 5 VCFs + 5 indices from gs://gcp-public-data--broad-references/hg38/v0/).

### GATK Milestone D Step 03 — genotype_refinement workflow (2026-04-23)
- [x] 2026-04-23 added genotype_refinement workflow to src/flytetest/workflows/variant_calling.py.
- [x] 2026-04-23 added genotype_refinement registry entry (workflow stage 4, reusable_as_reference=True).
- [x] 2026-04-23 added 4 unit tests in GenotypeRefinementRegistryTests + WorkflowTests.
- [x] 2026-04-23 extended workflows MANIFEST_OUTPUT_KEYS with refined_vcf.

### GATK Milestone D Step 02 — apply_vqsr task (2026-04-23)
- [x] 2026-04-23 added apply_vqsr to src/flytetest/tasks/variant_calling.py.
- [x] 2026-04-23 added apply_vqsr registry entry (stage 13).
- [x] 2026-04-23 added 9 unit tests (ApplyVQSRRegistryTests, InvocationTests, ManifestTests).
- [x] 2026-04-23 added apply_vqsr to _VARIANT_CALLING_TASK_NAMES in contract test.

### GATK Milestone D Step 01 — variant_recalibrator task (2026-04-23)
- [x] 2026-04-23 added variant_recalibrator to src/flytetest/tasks/variant_calling.py.
- [x] 2026-04-23 added variant_recalibrator registry entry (stage 12).
- [x] 2026-04-23 added 7 unit tests (VariantRecalibratorRegistryTests, InvocationTests, ManifestTests).
- [x] 2026-04-23 extended MANIFEST_OUTPUT_KEYS with recal_file, tranches_file, vqsr_vcf.
- [x] 2026-04-23 added variant_recalibrator to _VARIANT_CALLING_TASK_NAMES in contract test.

### GATK Milestone C — Complete (2026-04-23)

Closes Milestone C of the Phase 3 GATK port (tracker:
`docs/gatk_milestone_c/checklist.md`). Delivers the live-cluster
validation prompt set for the variant_calling family and refreshes
`docs/mcp_full_pipeline_prompt_tests.md` with a Variant Calling
Pipeline section. Documentation-only — no new Python, tasks,
workflows, registry entries, or planner types.

- [x] 2026-04-23 docs/mcp_variant_calling_cluster_prompt_tests.md: Scenarios 1–8.
- [x] 2026-04-23 docs/mcp_full_pipeline_prompt_tests.md: Variant Calling Pipeline section (Stages 0–3).
- [x] 2026-04-23 AGENTS.md cluster prompt docs section added.
- [x] 2026-04-23 docs/gatk_milestone_c_submission_prompt.md authored.
- [x] 2026-04-23 full pytest green; python -m compileall clean.
- Deferred to future milestones: merge_bam_alignment (uBAM path), VQSR, interval-scoped HaplotypeCaller.

### GATK Milestone C Step 05 — Full pipeline doc refresh for variant calling (2026-04-23)

- [x] 2026-04-23 retitled docs/mcp_full_pipeline_prompt_tests.md to cover both annotation and variant calling families.
- [x] 2026-04-23 appended Variant Calling Pipeline section (Stages 0–3) referencing docs/mcp_variant_calling_cluster_prompt_tests.md.
- [x] 2026-04-23 extended Prerequisites with GATK4 SIF + germline fixture staging note.

### GATK Milestone C Step 04 — Cluster lifecycle scenarios (2026-04-23)

- [x] 2026-04-23 added Scenario 6 (cancel idempotency) for haplotype_caller.
- [x] 2026-04-23 added Scenario 7 (NODE_FAIL retry).
- [x] 2026-04-23 added Scenario 8 (OUT_OF_MEMORY escalation retry).

### GATK Milestone C Step 03 — Workflow happy-path cluster scenarios (2026-04-23)

- [x] 2026-04-23 added Scenario 3 (prepare_reference) to docs/mcp_variant_calling_cluster_prompt_tests.md.
- [x] 2026-04-23 added Scenario 4 (preprocess_sample).
- [x] 2026-04-23 added Scenario 5 (germline_short_variant_discovery end-to-end).

### GATK Milestone C Step 02 — Cluster prompt doc skeleton + single-task happy path (2026-04-23)

- [x] 2026-04-23 created docs/mcp_variant_calling_cluster_prompt_tests.md with Prerequisites, Scenario 1, Scenario 2 (haplotype_caller).
- [x] 2026-04-23 copied quick-reference table and "supported: false" troubleshooting block from mcp_cluster_prompt_tests.md.

### GATK Milestone C Step 01 — Plan + checklist skeleton (2026-04-23)

- [x] 2026-04-23 created docs/gatk_milestone_c/milestone_c_plan.md.
- [x] 2026-04-23 created docs/gatk_milestone_c/checklist.md.

### GATK Milestone B — Complete (2026-04-23)

Four preprocessing tasks and three end-to-end workflow compositions.
Full pipeline: raw reads → joint-called VCF.

- [x] 2026-04-23 4 preprocessing tasks: bwa_mem2_index, bwa_mem2_mem, sort_sam, mark_duplicates.
- [x] 2026-04-23 3 workflows: prepare_reference, preprocess_sample, germline_short_variant_discovery.
- [x] 2026-04-23 ReadPair planner type.
- [x] 2026-04-23 Fixture bundle `variant_calling_germline_minimal` added to bundles.py.
- [x] 2026-04-23 scripts/rcc/pull_gatk_image.sh added.
- [x] 2026-04-23 AGENTS.md, DESIGN.md §5.6, docs/tool_refs/gatk4.md updated.
- [x] 2026-04-23 Full pytest suite green (733 passed, 1 skipped, 45 subtests).
- Deferred: merge_bam_alignment (uBAM path), VQSR, Milestone C cluster validation.

### GATK Milestone B Step 08 — germline_short_variant_discovery workflow (2026-04-23)
- [x] 2026-04-23 added `germline_short_variant_discovery` to workflow module (synchronous for-loop).
- [x] 2026-04-23 added registry entry (category=workflow, stage_order 3).
- [x] 2026-04-23 extended workflow `MANIFEST_OUTPUT_KEYS` with `"genotyped_vcf"`.
- [x] 2026-04-23 added 4 tests (registry shape, validation errors, call counts, manifest); all passing.

### GATK Milestone B Step 07 — preprocess_sample workflow (2026-04-23)
- [x] 2026-04-23 added `preprocess_sample` to workflow module.
- [x] 2026-04-23 added registry entry (category=workflow, stage_order 2).
- [x] 2026-04-23 extended workflow `MANIFEST_OUTPUT_KEYS` with `"preprocessed_bam"`.
- [x] 2026-04-23 added 3 tests (registry shape, sub-task call order, manifest); all passing.

### GATK Milestone B Step 06 — prepare_reference workflow (2026-04-23)
- [x] 2026-04-23 created `src/flytetest/workflows/variant_calling.py` with `prepare_reference` (plus `preprocess_sample` and `germline_short_variant_discovery` stubs for steps 07–08).
- [x] 2026-04-23 added `prepare_reference` registry entry (category=workflow, stage_order 1).
- [x] 2026-04-23 created `tests/test_variant_calling_workflows.py`.
- [x] 2026-04-23 added 4 tests (registry shape, sub-task call order, per-VCF indexing, manifest); all passing.

### GATK Milestone B Step 05 — mark_duplicates task (2026-04-23)
- [x] 2026-04-23 added `mark_duplicates` to `src/flytetest/tasks/variant_calling.py`.
- [x] 2026-04-23 added `mark_duplicates` registry entry (stage_order 11).
- [x] 2026-04-23 extended `MANIFEST_OUTPUT_KEYS` with `"dedup_bam"`, `"duplicate_metrics"`.
- [x] 2026-04-23 added 4 tests (registry shape, cmd shape, missing-file error, manifest); all passing.

### GATK Milestone B Step 04 — sort_sam task (2026-04-23)
- [x] 2026-04-23 added `sort_sam` to `src/flytetest/tasks/variant_calling.py`.
- [x] 2026-04-23 added `sort_sam` registry entry (stage_order 10).
- [x] 2026-04-23 extended `MANIFEST_OUTPUT_KEYS` with `"sorted_bam"`.
- [x] 2026-04-23 added 4 tests (registry shape, cmd shape, missing-file error, manifest); all passing.

### GATK Milestone B Step 03 — bwa_mem2_mem task (2026-04-23)
- [x] 2026-04-23 added `bwa_mem2_mem` using shell pipeline (bwa-mem2 | samtools view).
- [x] 2026-04-23 added `bwa_mem2_mem` registry entry (stage_order 9).
- [x] 2026-04-23 extended `MANIFEST_OUTPUT_KEYS` with `"aligned_bam"`.
- [x] 2026-04-23 added 7 tests (registry shape, pipeline string, R2 conditional, read-group, manifest, error); all passing.

### GATK Milestone B Step 02 — bwa_mem2_index task (2026-04-23)
- [x] 2026-04-23 added `bwa_mem2_index` to `src/flytetest/tasks/variant_calling.py`.
- [x] 2026-04-23 added `bwa_mem2_index` registry entry (stage_order 8).
- [x] 2026-04-23 extended `MANIFEST_OUTPUT_KEYS` with `"bwa_index_prefix"`.
- [x] 2026-04-23 added 4 tests (registry shape, cmd shape, missing-file error, manifest); all passing.

### GATK Milestone B Step 01 — ReadPair planner type (2026-04-23)
- [x] 2026-04-23 added `ReadPair` dataclass to `src/flytetest/planner_types.py`.
- [x] 2026-04-23 added paired and single-end round-trip tests to `tests/test_planner_types.py`.

### GATK Milestone A — Complete (2026-04-22)

All seven GATK4 germline variant calling tasks are implemented, tested, and
registered. The full pipeline runs BAM-in → VCF-out:
`create_sequence_dictionary` → `index_feature_file` → `base_recalibrator` →
`apply_bqsr` → `haplotype_caller` → `combine_gvcfs` → `joint_call_gvcfs`.

- [x] 2026-04-22 29 unit tests passing (`tests/test_variant_calling.py`).
- [x] 2026-04-22 7 manifest-contract parametrized tests added to
  `tests/test_registry_manifest_contract.py`; all align with `MANIFEST_OUTPUT_KEYS`.
- [x] 2026-04-22 tool-reference doc created at `docs/tool_refs/gatk4.md`.
- [x] 2026-04-22 `AGENTS.md` Tasks section updated with `variant_calling.py` note.
- [x] 2026-04-22 `DESIGN.md` updated: `_variant_calling.py` replaces catalog-only
  `_gatk.py` placeholder; §5.6 Germline Variant Calling added.
- [x] 2026-04-22 `docs/tool_refs/stage_index.md` Germline Variant Calling section added.
- [x] 2026-04-22 `docs/gatk_milestone_a/checklist.md` marked Complete.
- Deferred: alignment/dedup (Milestone B), VQSR (deferred), workflow compositions.

### GATK Milestone A Step 09 — joint_call_gvcfs task + registry entry (2026-04-22)

- [x] 2026-04-22 added `import tempfile` to `src/flytetest/tasks/variant_calling.py`.
- [x] 2026-04-22 added `joint_call_gvcfs` task: runs `gatk GenomicsDBImport` (ephemeral
  tempdir workspace, sample-name map written per invocation) then `gatk GenotypeGVCFs`
  (gendb:// URI); validates non-empty gvcfs, non-empty intervals, and 1:1 sample_ids.
- [x] 2026-04-22 added `joint_call_gvcfs` `RegistryEntry` to `VARIANT_CALLING_ENTRIES`
  (pipeline_stage_order 7, accepted_planner_types `ReferenceGenome`/`VariantCallSet`,
  produced_planner_types `VariantCallSet`).
- [x] 2026-04-22 extended `MANIFEST_OUTPUT_KEYS` with `"joint_vcf"`.
- [x] 2026-04-22 added 7 tests: 3 validation rejections, cmd-sequence ordering,
  sample-map format, registry shape, manifest emission — all 29 tests passing.

### GATK Milestone A Step 08 — combine_gvcfs task + registry entry (2026-04-22)

- [x] 2026-04-22 added `combine_gvcfs` task to `src/flytetest/tasks/variant_calling.py`:
  runs `gatk CombineGVCFs -R … -O … -V <gvcf>` (repeated per input) via `run_tool`,
  raises `ValueError` on empty list, emits `run_manifest.json` with `combined_gvcf` key.
- [x] 2026-04-22 added `combine_gvcfs` `RegistryEntry` to `VARIANT_CALLING_ENTRIES`
  (pipeline_stage_order 6, accepted_planner_types `ReferenceGenome`/`VariantCallSet`,
  produced_planner_types `VariantCallSet`).
- [x] 2026-04-22 extended `MANIFEST_OUTPUT_KEYS` with `"combined_gvcf"`.
- [x] 2026-04-22 added 4 tests to `tests/test_variant_calling.py`: registry shape,
  empty-list rejection, `-V`-per-input ordering, manifest emission — all 22 tests passing.

### GATK Milestone A Step 07 — haplotype_caller task + registry entry (2026-04-22)

- [x] 2026-04-22 added `haplotype_caller` task to
  `src/flytetest/tasks/variant_calling.py`: runs `gatk HaplotypeCaller -R … -I …
  -O … --emit-ref-confidence GVCF` via `run_tool`; emits
  `<sample_id>.g.vcf` + companion index in manifest.
- [x] 2026-04-22 added `haplotype_caller` `RegistryEntry` to
  `VARIANT_CALLING_ENTRIES` (pipeline_stage_order 5,
  accepted_planner_types `ReferenceGenome` / `AlignmentSet`,
  produced_planner_types `VariantCallSet`,
  8 CPU / 32 GiB local; 16 CPU / 64 GiB / 24:00:00 Slurm).
- [x] 2026-04-22 extended `MANIFEST_OUTPUT_KEYS` with `"gvcf"`.
- [x] 2026-04-22 added 3 tests to `tests/test_variant_calling.py`: registry
  shape, cmd shape (`--emit-ref-confidence GVCF`, output ends in `.g.vcf`),
  manifest emission — all 18 variant-calling tests passing.

### GATK Milestone A Step 06 — apply_bqsr task + registry entry (2026-04-22)

- [x] 2026-04-22 added `apply_bqsr` task to
  `src/flytetest/tasks/variant_calling.py`: runs `gatk ApplyBQSR -R … -I …
  --bqsr-recal-file … -O …` via `run_tool`; surfaces companion `.bai` in
  manifest; emits `run_manifest.json`.
- [x] 2026-04-22 added `apply_bqsr` `RegistryEntry` to
  `VARIANT_CALLING_ENTRIES` (pipeline_stage_order 4,
  accepted_planner_types `ReferenceGenome` / `AlignmentSet`,
  produced_planner_types `AlignmentSet`,
  4 CPU / 16 GiB local; 8 CPU / 32 GiB / 06:00:00 Slurm).
- [x] 2026-04-22 extended `MANIFEST_OUTPUT_KEYS` with `"recalibrated_bam"`.
- [x] 2026-04-22 added 3 tests to `tests/test_variant_calling.py`: registry
  shape, cmd shape (`--bqsr-recal-file` before `-O`, output named
  `sample1_recalibrated.bam`), manifest emission — all 15 variant-calling
  tests passing.

### GATK Milestone A Step 05 — base_recalibrator task + registry entry (2026-04-21)

- [x] 2026-04-21 added `base_recalibrator` task to
  `src/flytetest/tasks/variant_calling.py`: runs `gatk BaseRecalibrator -R … -I … -O …
  --known-sites …` (repeated per site) via `run_tool`; raises `ValueError` on empty
  `known_sites`; emits `run_manifest.json`.
- [x] 2026-04-21 added `base_recalibrator` `RegistryEntry` to
  `VARIANT_CALLING_ENTRIES` (pipeline_stage_order 3,
  accepted_planner_types `ReferenceGenome` / `AlignmentSet` / `KnownSites`,
  4 CPU / 16 GiB local; 8 CPU / 32 GiB / 06:00:00 Slurm).
- [x] 2026-04-21 extended `MANIFEST_OUTPUT_KEYS` with `"bqsr_report"`.
- [x] 2026-04-21 added 4 tests to `tests/test_variant_calling.py`: registry
  shape, empty-known-sites rejection, cmd shape (two `--known-sites` flags), manifest
  emission — all 12 variant-calling tests passing.

### GATK Milestone A Step 04 — index_feature_file task + registry entry (2026-04-21)

- [x] 2026-04-21 added `index_feature_file` task to
  `src/flytetest/tasks/variant_calling.py`: runs `gatk IndexFeatureFile -I
  …` via `run_tool`, derives index suffix (`.idx` for plain VCF, `.tbi` for
  `.vcf.gz`), emits `run_manifest.json`.
- [x] 2026-04-21 added `index_feature_file` `RegistryEntry` to
  `VARIANT_CALLING_ENTRIES` (pipeline_stage_order 2,
  accepted_planner_types `KnownSites`).
- [x] 2026-04-21 extended `MANIFEST_OUTPUT_KEYS` with `"feature_index"`.
- [x] 2026-04-21 added 4 tests to `tests/test_variant_calling.py`: registry
  shape, `.tbi` for `.vcf.gz`, `.idx` for plain VCF, manifest emission —
  all 8 variant-calling tests passing.

### GATK Milestone A Step 02 — variant_calling_env + registry skeleton (2026-04-21)

- [x] 2026-04-21 added `VARIANT_CALLING_WORKFLOW_NAME`, `VARIANT_CALLING_RESULTS_PREFIX`,
  and `VARIANT_CALLING_SIF_DEFAULT` constants to `src/flytetest/config.py`.
- [x] 2026-04-21 added `variant_calling_env` (`TaskEnvironmentConfig` with 4 CPU / 16 GiB)
  to `TASK_ENVIRONMENT_CONFIGS` and exposed alias in `src/flytetest/config.py`.
- [x] 2026-04-21 created `src/flytetest/registry/_variant_calling.py` with empty
  `VARIANT_CALLING_ENTRIES` tuple; wired into `REGISTRY_ENTRIES` in `__init__.py`
  (replacing the `_gatk.py` placeholder import).
- [x] 2026-04-21 updated `AGENTS.md` and `.codex/registry.md` with `_variant_calling.py`
  family listing; noted `_gatk.py` as reference-only.
- [x] 2026-04-21 added scaffolding smoke test `test_variant_calling_family_registered`
  to `tests/test_registry.py` (deleted in Step 03).

### GATK Milestone A Step 03 — create_sequence_dictionary task + registry entry (2026-04-21)

- [x] 2026-04-21 created `src/flytetest/tasks/variant_calling.py` with
  `create_sequence_dictionary` task: runs `gatk CreateSequenceDictionary -R …
  -O …` via `run_tool` + Apptainer, emits `run_manifest.json` via
  `build_manifest_envelope` (stage `"create_sequence_dictionary"`).
- [x] 2026-04-21 added `create_sequence_dictionary` `RegistryEntry` to
  `VARIANT_CALLING_ENTRIES` in `src/flytetest/registry/_variant_calling.py`
  (pipeline_family `"variant_calling"`, pipeline_stage_order 1).
- [x] 2026-04-21 deleted Step 02 scaffolding test
  `test_variant_calling_family_registered` from `tests/test_registry.py`.
- [x] 2026-04-21 added `tests/test_variant_calling.py` with 4 tests covering
  registry entry shape, correct GATK command invocation, default SIF fallback,
  and manifest emission — all passing.

### GATK Milestone A Step 01 — Planner types for variant calling (2026-04-21)

- [x] 2026-04-21 added `AlignmentSet`, `VariantCallSet`, `KnownSites` planner
  dataclasses to `src/flytetest/planner_types.py` (inherit
  `PlannerSerializable`; `VariantCallSet.variant_type` discriminates GVCF vs
  VCF; `KnownSites` carries VQSR-facing fields for forward compatibility).
- [x] 2026-04-21 extended `__all__` in `planner_types.py` to export the three
  new types.
- [x] 2026-04-21 added round-trip coverage in `tests/test_planner_types.py`:
  `test_alignment_set_round_trips`,
  `test_variant_call_set_round_trips_gvcf`,
  `test_variant_call_set_round_trips_vcf`,
  `test_known_sites_round_trips_with_vqsr_fields`,
  `test_known_sites_defaults_minimal` — 13/13 passing.


Older entries: see [`CHANGELOG.archive.md`](CHANGELOG.archive.md).
