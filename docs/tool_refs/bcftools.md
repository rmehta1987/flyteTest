# bcftools stats

## Purpose

Compute per-site and summary statistics for a VCF/GVCF file. Output is plain text
that MultiQC can parse to produce a per-cohort QC report.

## Input/Output Data

**Inputs:**
- VCF or GVCF file (plain or bgzip-compressed)

**Outputs:**
- Plain text stats file (MultiQC-parseable)

## FLyteTest Path

Task: `flytetest.tasks.variant_calling.bcftools_stats`
Workflow: `flytetest.workflows.variant_calling.post_call_qc_summary`

## Official Documentation

- bcftools stats: https://samtools.github.io/bcftools/bcftools.html#stats

## Native Command Context

```bash
bcftools stats input.vcf > cohort_bcftools_stats.txt
```

## Apptainer Command Context

```bash
apptainer exec --cleanenv data/images/bcftools.sif \
  bash -c "bcftools stats input.vcf > cohort_bcftools_stats.txt"
```

## Notes and Caveats

- `bcftools stats` writes to stdout; FLyteTest routes output via shell redirect inside a `bash -c` invocation.
- Output filename must match `*_bcftools_stats.txt` for MultiQC auto-detection.
- For joint-called VCFs with many samples the stats file can be large.
