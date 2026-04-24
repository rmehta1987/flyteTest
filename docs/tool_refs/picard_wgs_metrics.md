# Picard CollectWgsMetrics + CollectInsertSizeMetrics

## Purpose

Collect whole-genome sequencing coverage and insert-size distribution metrics from a
coordinate-sorted, indexed BAM file. Used in pre-call QC to confirm adequate coverage
before variant calling.

## Input/Output Data

**Inputs:**
- Coordinate-sorted, indexed BAM (from `mark_duplicates` or `apply_bqsr`)
- Reference FASTA with `.fai` and `.dict`

**Outputs:**
- WGS metrics text file (coverage mean/median, PCT_EXC_*, etc.)
- Insert size metrics text file + histogram PDF

## FLyteTest Path

Task: `flytetest.tasks.variant_calling.collect_wgs_metrics`
Workflow: `flytetest.workflows.variant_calling.pre_call_coverage_qc`

## Official Documentation

- Picard CollectWgsMetrics: https://gatk.broadinstitute.org/hc/en-us/articles/360037224111
- Picard CollectInsertSizeMetrics: https://gatk.broadinstitute.org/hc/en-us/articles/360037055031

## Native Command Context

```bash
gatk CollectWgsMetrics -R ref.fa -I sample.bam -O sample_wgs_metrics.txt
gatk CollectInsertSizeMetrics -I sample.bam -O sample_insert_size.txt -H sample_histogram.pdf
```

## Apptainer Command Context

```bash
apptainer exec --cleanenv data/images/gatk4.sif \
  gatk CollectWgsMetrics -R ref.fa -I sample.bam -O sample_wgs_metrics.txt
```

## Notes and Caveats

- Both Picard tools are bundled inside the GATK4 SIF image.
- BAM must be coordinate-sorted; queryname-sorted BAM will fail.
- Reference must have `.fai` (samtools faidx) and `.dict` (CreateSequenceDictionary) present.
- MultiQC auto-detects Picard output by filename patterns ending in `_wgs_metrics.txt` and `_insert_size_metrics.txt`.
