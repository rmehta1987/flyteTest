# BUSCO

## Purpose

Assess annotation or protein-set completeness against lineage-specific conserved ortholog sets.

## Key Inputs

- predicted proteins or annotations converted to the required BUSCO input form
- one or more selected lineage datasets

## Key Outputs

- BUSCO completeness summaries
- lineage-specific report directories and tables

## Pipeline Fit

- downstream QC after consensus annotation and filtering

## Notes And Caveats

- BUSCO is not implemented in FLyteTest yet.
- The design notes expect BUSCO to run across multiple lineages, so future task design should make lineage selection explicit.
- BUSCO is a QC layer, not a gene model generator.
