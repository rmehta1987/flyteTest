# samtools

## Purpose

Manipulate SAM/BAM alignment files for downstream transcript-evidence and annotation workflows.

## Key Inputs

- one or more SAM/BAM alignment files
- merge, sort, or index subcommand parameters

## Key Outputs

- merged or transformed BAM files
- optional BAM index files depending on the subcommand

## Pipeline Fit

- transcript evidence generation between STAR alignment and genome-guided Trinity or StringTie

## Notes And Caveats

- FLyteTest currently uses samtools for the explicit BAM merge stage in `transcript_evidence_generation`.
- The first implementation merges a single STAR-produced BAM so the pipeline preserves the merge stage boundary for future multi-sample expansion.
- Additional samtools stages such as sort and index can be split into separate tasks later if downstream tools require them explicitly.
