# StringTie

## Purpose

Assemble transcripts and summarize transcript abundance from genome-aligned RNA-seq data.

## Key Inputs

- coordinate-sorted RNA-seq BAM files
- reference genome and optional annotation context

## Key Outputs

- assembled transcript GTF
- abundance tables and summary files

## Pipeline Fit

- transcript evidence generation after RNA-seq alignment
- design notes place StringTie alongside genome-guided Trinity before PASA

## Notes And Caveats

- StringTie is now implemented as a standalone assembly task in the initial transcript-evidence workflow.
- The current task emits `transcripts.gtf` and `gene_abund.tab` from the merged BAM without an external annotation guide.
- The PASA transcript-alignment workflow now consumes `transcripts.gtf` through `--trans_gtf`.
- BAM preprocessing expectations still remain explicit task boundaries around STAR alignment and BAM merge.
