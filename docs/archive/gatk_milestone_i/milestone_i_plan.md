# GATK4 Germline Variant Calling — Milestone I

Scientific completeness + task-pattern unification. Converts GATK from
"runs end-to-end through MCP" (state after Milestone H) to "produces a
VCF a scientist can publish from, with every task following the same
Flyte pattern." Addresses the P2 biology gaps and the P3 #11
architectural inconsistency flagged in the 2026-04-23 review.

Source-of-truth references:

- `AGENTS.md`, `DESIGN.md`, `.codex/` — project rules and patterns.
- `docs/gatk_milestone_h/milestone_h_plan.md` §7 — the scope boundary
  Milestone I inherits.
- GATK Best Practices — germline hard-filtering and QC guidance.
- Tool manuals: Picard `CollectWgsMetrics`, `bcftools stats`, MultiQC,
  SnpEff (or VEP).

## §1 Context

Milestone H landed the MCP surface wiring and the two P0 fixes (shell
injection, manifest collision). Two classes of deferred work remain:

1. **Task-pattern unification (P3 #11).** Nine GATK task helpers ship as
   plain Python functions returning `dict`, rather than
   `@variant_calling_env.task` functions with `File` / `Dir` I/O and
   `run_tool()` wrapping. This violates `.codex/tasks.md`, prevents the
   nine helpers from being exposed individually through MCP, and blocks
   Milestone-19-style per-node caching and resume for the sub-steps of
   multi-task workflows. The helpers are: `bwa_mem2_index`,
   `bwa_mem2_mem`, `sort_sam`, `mark_duplicates`, `merge_bam_alignment`,
   `gather_vcfs`, `variant_recalibrator`, `apply_vqsr`,
   `calculate_genotype_posteriors`.
2. **Biology completeness (P2 #5–#10).** Five gaps keep the current
   pipeline below publication-grade:
   - No hard-filtering fallback (`VariantFiltration`) for cohorts too
     small for VQSR (<30k SNPs / <2k indels) — the very fixture bundle
     `variant_calling_germline_minimal` hits this threshold.
   - No pre-call coverage QC (Picard `CollectWgsMetrics`).
   - No post-call summary stats (`bcftools stats` + MultiQC).
   - No variant annotation (SnpEff or VEP) — final VCF is raw genotypes.
   - VQSR annotation sets and read-group fields are hardcoded; need
     caller parameterization and auto-adds for cohort-size-dependent
     annotations (`InbreedingCoeff` for ≥10 samples).

Milestone I covers both threads. `scattered_haplotype_caller` is
renamed honestly (`sequential_interval_haplotype_caller`) — real
scheduler-level scatter (job arrays or per-interval sbatch fan-out) is
explicitly deferred to Milestone K as HPC infrastructure work.

## §2 Pillars / Invariants

Same four pillars as Milestones A–H. Additionally for Milestone I:

- Every new task cites its tool manual section or GATK Best Practices
  article in the registry entry `description` or `composition_constraints`.
- Hard-filter expressions come verbatim from GATK Best Practices —
  not invented. Any deviation requires an explicit assumption note in
  the task manifest.
- Annotation tool choice (SnpEff vs VEP): SnpEff is selected for
  Milestone I based on simpler local-SIF workflow and no external
  cache dependency for hg38; VEP is a Milestone K candidate if users
  need ENSEMBL-native identifiers or plugin ecosystems.
- New family `MANIFEST_OUTPUT_KEYS` additions must match the
  registry-manifest contract (`tests/test_registry_manifest_contract.py`).

## §3 Data Model

### Signature changes — ported helpers (Steps 01–02)

Every ported helper moves from

```python
def helper(ref_path: str, ..., results_dir: str, sif_path: str = "") -> dict:
```

to

```python
@variant_calling_env.task
def helper(reference_fasta: File, ..., gatk_sif: str = "") -> File | tuple[File, ...]:
```

Internal scratch uses `project_mkdtemp()`; outputs are Flyte `File`
instances; manifests continue per-stage (`run_manifest_<stage>.json`,
from Milestone H Step 01). Return-type choice per helper:

| Helper | Return |
|---|---|
| `bwa_mem2_index` | `Dir` (index prefix directory) |
| `bwa_mem2_mem` | `File` (unsorted aligned BAM) |
| `sort_sam` | `File` (coordinate-sorted BAM) |
| `mark_duplicates` | `tuple[File, File]` (dedup BAM, metrics file) |
| `merge_bam_alignment` | `File` (coordinate-sorted merged BAM) |
| `gather_vcfs` | `File` (gathered GVCF) |
| `variant_recalibrator` | `tuple[File, File]` (recal, tranches) |
| `apply_vqsr` | `File` (VQSR-filtered VCF) |
| `calculate_genotype_posteriors` | `File` (CGP VCF) |

### New planner type

`CohortSizeHint` is *not* added as a planner type. Sample count comes
from the existing `VariantCallSet.sample_ids` tuple; Step 03 uses its
length to decide the auto-`InbreedingCoeff` add.

### New tasks (Steps 04–06)

| Task | Stage | Step |
|---|---|---|
| `variant_filtration` | 17 | 04 |
| `collect_wgs_metrics` | 18 | 05 |
| `bcftools_stats` | 19 | 05 |
| `multiqc_summarize` | 20 | 05 |
| `snpeff_annotate` | 21 | 06 |

### New workflows (Steps 04–06)

| Workflow | Stage | Step |
|---|---|---|
| `small_cohort_filter` | 8 | 04 |
| `pre_call_coverage_qc` | 9 | 05 |
| `post_call_qc_summary` | 10 | 05 |
| `annotate_variants_snpeff` | 11 | 06 |

### Renamed workflow

`scattered_haplotype_caller` → `sequential_interval_haplotype_caller`
(Step 03). Breaking change: callers must update the workflow name.

### New `MANIFEST_OUTPUT_KEYS`

Tasks module:

```python
"filtered_vcf",        # variant_filtration
"wgs_metrics",         # collect_wgs_metrics
"insert_size_metrics", # collect_wgs_metrics (companion)
"bcftools_stats_txt",  # bcftools_stats
"multiqc_report_html", # multiqc_summarize
"snpeff_vcf",          # snpeff_annotate
"snpeff_genes_txt",    # snpeff_annotate (companion)
```

Workflows module:

```python
"small_cohort_filtered_vcf",   # small_cohort_filter
"pre_call_qc_bundle",           # pre_call_coverage_qc
"post_call_qc_bundle",          # post_call_qc_summary
"annotated_vcf",                # annotate_variants_snpeff
```

### Registry stage orders

Existing stages 1–16 unchanged. New task stages 17–21. New workflow
stages 8–11.

## §4 Implementation Notes

### Step 01 — Port preprocessing helpers

`bwa_mem2_index`, `bwa_mem2_mem`, `sort_sam`, `mark_duplicates` move to
`@variant_calling_env.task` with `File` / `Dir` I/O. Update
`preprocess_sample` workflow to consume `.path` / `File` returns instead
of `dict["outputs"]["..."]` accessors.

Read-group parameterization in `bwa_mem2_mem`: add
`library_id: str | None = None` and `platform: str = "ILLUMINA"`.
Default `library_id` to `f"{sample_id}_lib"` when `None`.

### Step 02 — Port remaining helpers

Five tasks + their calling workflows:

- `merge_bam_alignment` → `preprocess_sample_from_ubam`
- `gather_vcfs` → `sequential_interval_haplotype_caller` (renamed in Step 03)
- `variant_recalibrator` + `apply_vqsr` → `genotype_refinement`
- `calculate_genotype_posteriors` → `post_genotyping_refinement`

### Step 03 — Parameter cleanups + honest scatter

VQSR annotation parameterization:

```python
def variant_recalibrator(
    reference_fasta: File,
    cohort_vcf: File,
    known_sites: list[File],
    known_sites_flags: list[dict],
    mode: str,
    cohort_id: str,
    sample_count: int,                         # NEW — used for InbreedingCoeff auto-add
    annotations: list[str] | None = None,      # NEW — override defaults
    gatk_sif: str = "",
) -> tuple[File, File]:
```

Default annotations per mode (unchanged from Milestone D). If
`sample_count >= 10` and `mode == "SNP"` and `annotations is None`,
auto-add `"InbreedingCoeff"` to the default list. Manifest records the
effective list.

Read-group params documented in Step 01 are threaded through the
`ReadPair` planner type if callers pass one; otherwise sensible
defaults (`library_id=f"{sample_id}_lib"`, `platform="ILLUMINA"`).

Honest scatter rename: `scattered_haplotype_caller` →
`sequential_interval_haplotype_caller`. Update all references:
registry, workflows module, tests, docs, `gatk_pipeline_overview.md`.
Add a workflow-level manifest assumption:

```python
"Execution is synchronous — all intervals run serially inside one task "
"invocation. True scheduler-level scatter (job arrays or per-interval "
"sbatch fan-out) is Milestone K HPC work.",
```

### Step 04 — Hard-filtering fallback

New task `variant_filtration` invoking GATK `VariantFiltration` with
Best Practices default expressions:

SNP filter:
```
QD < 2.0
FS > 60.0
MQ < 40.0
MQRankSum < -12.5
ReadPosRankSum < -8.0
SOR > 3.0
```

INDEL filter:
```
QD < 2.0
FS > 200.0
ReadPosRankSum < -20.0
SOR > 10.0
```

Task accepts optional `snp_filter_expressions: list[str] | None = None`
and `indel_filter_expressions: list[str] | None = None` for override.
Source: GATK Best Practices article on
`Hard-filtering germline short variants`.

Workflow `small_cohort_filter` runs two passes:

1. `variant_filtration(mode="SNP", vcf=joint_vcf, ...)` → SNP-filtered VCF
2. `variant_filtration(mode="INDEL", vcf=snp_filtered, ...)` → final VCF

Mirrors the two-pass structure of `genotype_refinement`. Intended as
an alternative to `genotype_refinement` when the cohort is too small
for VQSR.

### Step 05 — QC bookends

Three tasks + two workflows.

**`collect_wgs_metrics`** — Picard. Inputs: coordinate-sorted BAM +
reference FASTA. Outputs: WGS metrics text file + insert-size metrics
text file (via `CollectInsertSizeMetrics`).

**`bcftools_stats`** — bcftools. Input: VCF/GVCF. Output: text stats
file. Used for both joint-called and filtered VCFs.

**`multiqc_summarize`** — MultiQC. Input: directory containing one or
more tool stats/logs (from `collect_wgs_metrics`, `bcftools_stats`,
`fastqc`, `mark_duplicates`). Output: HTML + data directory.

**`pre_call_coverage_qc`** — workflow composing `collect_wgs_metrics`
over a list of BAMs, aggregated into a single MultiQC summary.

**`post_call_qc_summary`** — workflow composing `bcftools_stats` on a
target VCF + `multiqc_summarize`.

### Step 06 — Variant annotation (SnpEff)

Task `snpeff_annotate` — SnpEff. Inputs: VCF + SnpEff database name
(e.g., `hg38`). Outputs: annotated VCF + genes summary text file.
Database cache directory passed via `snpeff_data_dir` scalar.

Workflow `annotate_variants_snpeff` — thin wrapper around the task,
mirroring `post_genotyping_refinement`'s single-task composition style.

### Step 07 — Closure

- Expose all new tasks and workflows through MCP (set `showcase_module`,
  add `TASK_PARAMETERS` entries for each new task).
- Extend `planning.py` variant_calling intent branch with keywords for
  the new targets: `filter`, `hard-filter`, `filtration`, `coverage`,
  `stats`, `multiqc`, `annotate`, `annotation`, `snpeff`.
- Add fixture bundle entries where applicable (e.g.,
  `variant_calling_small_cohort_filter` pointing at the same chr20
  fixture that was too small for VQSR).
- Update `docs/gatk_pipeline_overview.md` to reflect 21 tasks + 11
  workflows; refresh the pipeline DAG.
- CHANGELOG milestone entry.
- `docs/gatk_milestone_i_submission_prompt.md` (≤100 lines).
- Smoke test each new workflow through `run_workflow` dry-run.
- Merge `gatkport-i` → `main`.

## §5 Backward Compatibility

- **Ported helpers: signatures change.** Any external caller of
  `bwa_mem2_mem(ref_path=...)` etc. must migrate to `File`-based calls.
  In-repo callers are the workflow bodies themselves; Steps 01–02 update
  them together.
- **`scattered_haplotype_caller` renamed.** Any recipe or prompt
  pinning that name must update to `sequential_interval_haplotype_caller`.
- **New tasks and workflows are additive.** No impact on existing
  pipelines that don't opt in.
- **VQSR `annotations` parameter is additive** with safe defaults.
  Existing callers see identical behavior unless they have ≥10 samples
  in SNP mode, in which case `InbreedingCoeff` is auto-added — this
  *is* a behavior change but a GATK-recommended one.

## §6 Steps

| # | Step | Prompt |
|---|------|--------|
| 01 | Port preprocessing helpers + read-group params + adapt preprocess_sample | `prompts/step_01_port_preprocessing.md` |
| 02 | Port remaining 5 helpers + adapt 4 workflows | `prompts/step_02_port_remaining_helpers.md` |
| 03 | VQSR parameterization + honest scatter rename | `prompts/step_03_parameter_cleanups.md` |
| 04 | `variant_filtration` + `small_cohort_filter` | `prompts/step_04_hard_filtering.md` |
| 05 | QC bookends — Picard + bcftools + MultiQC | `prompts/step_05_qc_bookends.md` |
| 06 | Variant annotation via SnpEff | `prompts/step_06_variant_annotation.md` |
| 07 | Closure — MCP re-wire, CHANGELOG, submission prompt, merge | `prompts/step_07_closure.md` |

## §7 Out of Scope (this milestone)

- **Real scheduler-level scatter** for interval-parallel HaplotypeCaller.
  Milestone K HPC infrastructure work; requires new `sbatch` fan-out or
  Flyte map-task primitives.
- **VEP variant annotation.** SnpEff-only in Milestone I; VEP candidate
  for Milestone K when ENSEMBL-native identifiers or plugins are needed.
- **Incremental GenomicsDB workspace.** Already documented as a
  permanent non-goal in `gatk_pipeline_overview.md#deferred-items`.
- **MultiQC config customization.** Default config only; per-project
  `multiqc_config.yaml` templating is Milestone K.
- **Somatic variant calling** (Mutect2). Distinct family; separate
  milestone if ever needed.
- **CNV / structural variant calling.** Out of scope for the germline
  short-variant pipeline.
- **Cross-family planner-type sharing** (e.g., reusing `VariantCallSet`
  in a non-GATK family). Milestone J+ when such families exist.

## §8 Verification Gates

- `python -m compileall src/flytetest/` clean.
- `pytest tests/test_variant_calling.py -xvs` green.
- `pytest tests/test_variant_calling_workflows.py -xvs` green.
- `pytest tests/test_registry.py -xvs` green.
- `pytest tests/test_registry_manifest_contract.py -xvs` green.
- `pytest tests/test_server.py -xvs` green.
- `pytest tests/test_mcp_contract.py -xvs` green.
- `pytest tests/test_planning.py -xvs` green.
- `pytest tests/test_bundles.py -xvs` green.
- `pytest` full suite green; count recorded in CHANGELOG.
- `rg "async def|await |asyncio\.gather|\.cid\b|IPFS|Pinata|TinyDB" src/flytetest/tasks/variant_calling.py src/flytetest/workflows/variant_calling.py` → zero hits.
- `rg "def " src/flytetest/tasks/variant_calling.py | rg -v "@variant_calling_env\.task" -B1 | rg "^def "` — every `def` directly under the module (not indented inside another function) should be preceded by `@variant_calling_env.task`. Sanity-check: zero non-decorated task-level defs.
- `rg "results_dir" src/flytetest/tasks/variant_calling.py` → zero hits (all helpers ported to `project_mkdtemp`).
- `rg "scattered_haplotype_caller" src/flytetest/` → zero hits; only `sequential_interval_haplotype_caller` present.
- `rg "showcase_module" src/flytetest/registry/_variant_calling.py | grep -v '""' | wc -l` → 20+ (14 from H + 5 new tasks + 4 new workflows, minus any still-internal).
- Smoke through MCP: `run_workflow` dry-run succeeds for
  `small_cohort_filter`, `pre_call_coverage_qc`, `post_call_qc_summary`,
  `annotate_variants_snpeff`.
