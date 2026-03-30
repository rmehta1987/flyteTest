# PASA

## Purpose

Align transcript assemblies to the genome, refine transcript structures, and later update gene models.

## Key Inputs

- transcript assemblies such as Trinity de novo and Trinity genome-guided outputs
- reference genome
- StringTie transcript evidence
- PASA database configuration
- UniVec input for `seqclean`

## Key Outputs

- PASA transcript alignment and assembly products
- refined transcript structures
- SQLite-backed PASA database and config state for the run
- updated gene models in later refinement rounds

## Pipeline Fit

- transcript preparation and alignment after transcript evidence generation
- later used again to update consensus gene models with UTRs and alternative transcripts

## Notes And Caveats

- FLyteTest now implements a first PASA task family for accession extraction, Trinity transcript combination, `seqclean`, SQLite config preparation, and `Launch_PASA_pipeline.pl` align/assemble.
- The design notes explicitly mention substantial external dependencies such as SQLite or MySQL, samtools, BioPerl, minimap2, BLAT, and gmap.
- The current workflow consumes `trinity_gg/Trinity-GG.fasta` and `stringtie/transcripts.gtf` from the transcript evidence stage, and can optionally consume an external de novo Trinity FASTA.
- The PASA template config is treated as an external input because the exact alignAssembly config content is environment-specific in the notes.
- PASA should remain a task family with explicit setup, align/assemble, and later update stages rather than one opaque step.
- TransDecoder is now implemented as the next downstream stage, while PASA gene-model update rounds, Exonerate, BRAKER3, and EVM remain outside the current PASA milestone.
