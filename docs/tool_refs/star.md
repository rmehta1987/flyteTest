# STAR

## Purpose

Create genome indices and align RNA-seq reads to a reference genome.

## Key Inputs

- reference genome FASTA
- RNA-seq FASTQ files
- splice-aware alignment parameters

## Key Outputs

- STAR genome index
- alignment BAM files
- alignment logs and summary metrics

## Pipeline Fit

- transcript evidence generation after genome setup
- upstream of BAM merging, genome-guided Trinity, and StringTie in the design notes

## Notes And Caveats

- STAR is now used in the initial `transcript_evidence_generation` workflow through separate index and alignment tasks.
- The first implementation always builds a fresh STAR index for determinism instead of reusing a prebuilt one.
- Gzipped paired-end FASTQs are handled by adding `--readFilesCommand zcat` when both mates end in `.gz`.
