# FastQC

## Purpose

Generate per-FASTQ quality control reports for raw or trimmed sequencing reads.

## Key Inputs

- FASTQ or FASTQ.GZ read files
- optional runtime/container choice

## Key Outputs

- HTML report per input FASTQ
- ZIP archive per input FASTQ

## Pipeline Fit

- early QC on raw RNA-seq reads
- currently part of the implemented `rnaseq_qc_quant` workflow

## Notes And Caveats

- FastQC reports are descriptive QC outputs, not alignment or expression results.
- For paired-end data, each mate file is reported separately.
- Current FLyteTest behavior runs FastQC directly on the provided read pair and bundles the outputs into the run manifest.
