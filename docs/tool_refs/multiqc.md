# MultiQC

## Purpose

Aggregate QC tool outputs from multiple sources (Picard, bcftools, FastQC, GATK
MarkDuplicates) into a single HTML report. Used in both pre-call and post-call QC.

## Input/Output Data

**Inputs:**
- One or more QC tool output files (Picard WGS metrics, insert-size metrics,
  bcftools stats, GATK MarkDuplicates metrics, FastQC output)

**Outputs:**
- MultiQC HTML report

## FLyteTest Path

Task: `flytetest.tasks.variant_calling.multiqc_summarize`
Workflows: `flytetest.workflows.variant_calling.pre_call_coverage_qc`,
           `flytetest.workflows.variant_calling.post_call_qc_summary`

## Official Documentation

- MultiQC: https://multiqc.info/

## Native Command Context

```bash
multiqc scan_dir/ -n cohort_multiqc.html -o output_dir/
```

## Apptainer Command Context

```bash
apptainer exec --cleanenv data/images/multiqc.sif \
  multiqc scan_dir/ -n cohort_multiqc.html -o output_dir/
```

## Notes and Caveats

- FLyteTest copies all QC input files into a deterministic scan directory before
  running MultiQC, so the report is self-contained regardless of original file locations.
- MultiQC auto-detects tool outputs by filename suffix (e.g. `_wgs_metrics.txt`,
  `_bcftools_stats.txt`, `_duplicate_metrics.txt`).
- No per-project `multiqc_config.yaml` customization in Milestone I; templating
  is a Milestone K item.
