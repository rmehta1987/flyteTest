# Trinity

## Purpose

Assemble transcripts from RNA-seq reads using de novo or genome-guided modes.

## Key Inputs

- RNA-seq reads
- optionally a genome-guided BAM for genome-guided mode

## Key Outputs

- transcript FASTA assemblies
- assembly working directories and logs

## Pipeline Fit

- transcript evidence generation
- design notes call for both de novo Trinity and genome-guided Trinity products

## Notes And Caveats

- FLyteTest now implements genome-guided Trinity only; de novo Trinity remains a future transcript-evidence milestone.
- Genome-guided Trinity is modeled as its own task after the BAM merge stage.
- PASA transcript preparation and align/assemble are now implemented and consume Trinity-derived transcript assemblies, while downstream coding prediction still remains future work.
