# EggNOG-mapper

## Purpose

Assign functional annotations, orthology-informed names, and related annotation metadata.

## Key Inputs

- predicted proteins or other supported sequence inputs
- EggNOG databases and runtime configuration

## Key Outputs

- functional annotation tables
- name or function mappings that can be propagated into GFF3 features

## Pipeline Fit

- downstream functional annotation after structural annotation and QC

## Notes And Caveats

- EggNOG-mapper is not implemented in FLyteTest yet.
- The design notes treat functional annotation as a later-stage enrichment step, not part of primary gene model generation.
- Future implementation should keep database staging separate from the actual mapping run where practical.
