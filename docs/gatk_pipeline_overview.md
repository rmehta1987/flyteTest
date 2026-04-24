# GATK4 Germline Variant Calling — Pipeline Overview

One-stop reference for the full FLyteTest GATK4 germline variant calling pipeline.

Detailed per-task notes: `docs/tool_refs/gatk4.md`
Fixture bundles: `src/flytetest/bundles.py`
Download scripts: `scripts/rcc/`

## Input Paths

Two preprocessing paths produce a BQSR-recalibrated BAM:

- **FASTQ path** — `preprocess_sample` (Milestone B): align, sort, dedup, BQSR.
- **uBAM path** — `preprocess_sample_from_ubam` (Milestone E): align, merge with uBAM, dedup, BQSR. No `sort_sam` step; MergeBamAlignment sorts to coordinate order.

## Pipeline DAG

```
FASTQs or uBAM
    │
    ▼
preprocess_sample | preprocess_sample_from_ubam
    │
    ▼
(optional) scattered_haplotype_caller  ←── intervals
    │              OR
haplotype_caller (whole-genome)
    │
    ▼                     ┌─────────────────────┐
combine_gvcfs             │  germline_short_     │
    │                     │  variant_discovery   │
joint_call_gvcfs          │  (end-to-end)        │
    │                     └─────────────────────┘
    ▼
(optional) genotype_refinement  ← VQSR (SNP then INDEL pass)
    │
    ▼
(optional) post_genotyping_refinement  ← CalculateGenotypePosteriors
    │
    ▼
  final VCF
```

## Task Inventory

| Task | Stage | Milestone | Key I/O |
|---|---|---|---|
| `create_sequence_dictionary` | 1 | A | ref FASTA → .dict |
| `index_feature_file` | 1 | A | VCF → .tbi/.idx |
| `bwa_mem2_index` | 1 | B | ref FASTA → BWA-MEM2 index |
| `bwa_mem2_mem` | 2 | B | FASTQ + ref → unsorted BAM |
| `sort_sam` | 3 | B | BAM → coordinate-sorted BAM |
| `mark_duplicates` | 4 | B | BAM → dedup BAM + metrics |
| `base_recalibrator` | 5 | A | BAM + known-sites → BQSR table |
| `apply_bqsr` | 5 | A | BAM + BQSR table → recalibrated BAM |
| `haplotype_caller` | 5 | A | BAM + ref → per-sample GVCF |
| `combine_gvcfs` | 6 | A | per-sample GVCFs → cohort GVCF |
| `joint_call_gvcfs` | 7 | A | cohort GVCF + intervals → joint VCF |
| `variant_recalibrator` | 12 | D | joint VCF + training VCFs → recal model |
| `apply_vqsr` | 13 | D | joint VCF + recal model → VQSR VCF |
| `merge_bam_alignment` | 14 | E | aligned BAM + uBAM → merged BAM |
| `gather_vcfs` | 15 | F | per-interval GVCFs → single GVCF |
| `calculate_genotype_posteriors` | 16 | G | joint/VQSR VCF → CGP VCF |

## Workflow Inventory

| Workflow | Stage | Milestone | Composes |
|---|---|---|---|
| `prepare_reference` | 1 | A | create_sequence_dictionary, index_feature_file, bwa_mem2_index |
| `preprocess_sample` | 2 | B | bwa_mem2_mem, sort_sam, mark_duplicates, base_recalibrator, apply_bqsr |
| `germline_short_variant_discovery` | 3 | B | preprocess_sample, haplotype_caller, combine_gvcfs, joint_call_gvcfs |
| `genotype_refinement` | 4 | D | variant_recalibrator (×2), apply_vqsr (×2) — two-pass VQSR |
| `preprocess_sample_from_ubam` | 5 | E | bwa_mem2_mem, merge_bam_alignment, mark_duplicates, base_recalibrator, apply_bqsr |
| `scattered_haplotype_caller` | 6 | F | haplotype_caller (×N intervals), gather_vcfs |
| `post_genotyping_refinement` | 7 | G | calculate_genotype_posteriors |

## Fixture Bundles

| Bundle | Scope | Use |
|---|---|---|
| `variant_calling_germline_minimal` | Small chr20 slice, NA12878 | Milestone B smoke tests |
| `variant_calling_vqsr_chr20` | Full chr20 NA12878 WGS + 6 training VCFs | Milestone D VQSR tests |

## Deferred Items

- Job arrays / parallel scatter — deferred; scatter is synchronous `for` loop.
- `VariantFiltration` (hard-filtering) — deferred; user-composable with existing tasks.
- VQSR on CGP output — user-composable; out of scope for Milestone G.
- `SplitIntervals` — out of scope; users supply interval lists directly.
- GenomicsDB workspace incremental update — out of scope; `joint_call_gvcfs`
  builds the workspace in a `TemporaryDirectory` and deletes it on
  function exit, precluding GATK's `--genomicsdb-update-workspace-path`
  re-entry pattern. Acceptable for cohorts that are re-joint-called from
  per-sample GVCFs each run; not suitable for incremental-cohort designs.
