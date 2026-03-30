# AGAT

## Purpose

Generate annotation statistics and perform GFF/GTF format conversions or cleanup steps.

## Key Inputs

- GFF3 or GTF annotation files
- optional companion FASTA or conversion settings depending on the subcommand

## Key Outputs

- annotation statistics reports
- converted or normalized annotation files

## Pipeline Fit

- downstream post-processing and reporting after annotation refinement and functional annotation

## Notes And Caveats

- AGAT is not implemented in FLyteTest yet.
- AGAT is a task family rather than one single behavior; future implementations should model statistics and conversion steps separately.
- This repo should keep any format normalization explicit so downstream submission preparation remains auditable.
