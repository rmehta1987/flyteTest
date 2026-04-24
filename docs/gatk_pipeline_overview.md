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
    ├──► pre_call_coverage_qc ──► MultiQC coverage report
    │
    ▼
sequential_interval_haplotype_caller  ←── intervals (Milestone K → real scatter)
    │              OR
haplotype_caller (whole-genome)
    │
    ▼
combine_gvcfs → joint_call_gvcfs
    │
    ▼
    ├──► genotype_refinement (VQSR: large cohort)
    ├──► small_cohort_filter (hard-filter: small cohort)
    └──► post_genotyping_refinement (CGP, optional after either branch)
              │
              ▼
          post_call_qc_summary ──► MultiQC post-call report
              │
              ▼
          annotate_variants_snpeff ──► annotated VCF
```

## Task Inventory

| Task | Stage | Milestone | Key I/O |
|---|---|---|---|
| `create_sequence_dictionary` | 1 | A | ref FASTA → .dict |
| `index_feature_file` | 2 | A | VCF → .tbi/.idx |
| `base_recalibrator` | 3 | A | BAM + known-sites → BQSR table |
| `apply_bqsr` | 4 | A | BAM + BQSR table → recalibrated BAM |
| `haplotype_caller` | 5 | A | BAM + ref → per-sample GVCF |
| `combine_gvcfs` | 6 | A | per-sample GVCFs → cohort GVCF |
| `joint_call_gvcfs` | 7 | A | cohort GVCF + intervals → joint VCF |
| `bwa_mem2_index` | 8 | B→I | ref FASTA → BWA-MEM2 index Dir |
| `bwa_mem2_mem` | 9 | B→I | FASTQ + ref → unsorted BAM |
| `sort_sam` | 10 | B→I | BAM → coordinate-sorted BAM |
| `mark_duplicates` | 11 | B→I | BAM → dedup BAM + metrics |
| `variant_recalibrator` | 12 | D→I | joint VCF + training VCFs → recal model |
| `apply_vqsr` | 13 | D→I | joint VCF + recal model → VQSR VCF |
| `merge_bam_alignment` | 14 | E→I | aligned BAM + uBAM → merged BAM |
| `gather_vcfs` | 15 | F→I | per-interval GVCFs → single GVCF |
| `calculate_genotype_posteriors` | 16 | G→I | joint/VQSR VCF → CGP VCF |
| `variant_filtration` | 17 | I | joint VCF → hard-filtered VCF (SNP or INDEL pass) |
| `collect_wgs_metrics` | 18 | I | BAM + ref → WGS metrics + insert-size metrics |
| `bcftools_stats` | 19 | I | VCF → bcftools stats text |
| `multiqc_summarize` | 20 | I | QC files → MultiQC HTML report |
| `snpeff_annotate` | 21 | I | VCF + SnpEff db → annotated VCF + genes summary |

## Workflow Inventory

| Workflow | Stage | Milestone | Composes |
|---|---|---|---|
| `prepare_reference` | 1 | A | create_sequence_dictionary, index_feature_file, bwa_mem2_index |
| `preprocess_sample` | 2 | B→I | bwa_mem2_mem, sort_sam, mark_duplicates, base_recalibrator, apply_bqsr |
| `germline_short_variant_discovery` | 3 | B | preprocess_sample, haplotype_caller, combine_gvcfs, joint_call_gvcfs |
| `genotype_refinement` | 4 | D→I | variant_recalibrator (×2), apply_vqsr (×2) — two-pass VQSR |
| `preprocess_sample_from_ubam` | 5 | E→I | bwa_mem2_mem, merge_bam_alignment, mark_duplicates, base_recalibrator, apply_bqsr |
| `sequential_interval_haplotype_caller` | 6 | F→I | haplotype_caller (×N intervals serially), gather_vcfs |
| `post_genotyping_refinement` | 7 | G→I | calculate_genotype_posteriors |
| `small_cohort_filter` | 8 | I | variant_filtration (SNP pass), variant_filtration (INDEL pass) |
| `pre_call_coverage_qc` | 9 | I | collect_wgs_metrics (per sample), multiqc_summarize |
| `post_call_qc_summary` | 10 | I | bcftools_stats, multiqc_summarize |
| `annotate_variants_snpeff` | 11 | I | snpeff_annotate |

## Fixture Bundles

| Bundle | Scope | Use |
|---|---|---|
| `variant_calling_germline_minimal` | Small chr20 slice, NA12878 | Milestone B smoke tests; also the small-cohort hard-filtering use case |
| `variant_calling_vqsr_chr20` | Full chr20 NA12878 WGS + 6 training VCFs | Milestone D VQSR tests |

## Deferred Items

- **Real scheduler-level scatter** — `sequential_interval_haplotype_caller` runs all intervals serially inside one task invocation. Job arrays or per-interval sbatch fan-out are Milestone K HPC infrastructure work.
- **VEP variant annotation** — SnpEff only in Milestone I; VEP is a Milestone K candidate when ENSEMBL-native identifiers or plugins are needed.
- **MultiQC config customization** — Default config only; per-project `multiqc_config.yaml` templating is Milestone K.
- **Somatic variant calling** (Mutect2) — Distinct family; separate milestone if ever needed.
- **CNV / structural variant calling** — Out of scope for the germline short-variant pipeline.
- **Incremental GenomicsDB workspace** — `joint_call_gvcfs` builds the workspace in a `TemporaryDirectory` and deletes it on function exit; `--genomicsdb-update-workspace-path` re-entry pattern is out of scope for this design.
