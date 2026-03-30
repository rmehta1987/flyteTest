# TransDecoder

## Purpose

Predict coding regions from transcript assemblies and produce coding-support features for downstream annotation.

## Key Inputs

- PASA assemblies FASTA
- PASA assemblies GFF3 for lifting predicted ORFs onto genome coordinates
- optional minimum protein-length threshold

## Key Outputs

- transcript-level coding sequence predictions
- protein translations
- genome-coordinate GFF3 support files for downstream consensus steps

## Pipeline Fit

- coding prediction after PASA transcript assembly
- design notes use TransDecoder output as one of the evidence sources feeding EVidenceModeler

## Notes And Caveats

- FLyteTest now implements a first TransDecoder stage as `transdecoder_train_from_pasa` plus the composed `transdecoder_from_pasa` workflow.
- The design notes specifically reference a TransDecoder genome GFF3 derived from PASA assemblies, but they do not provide the exact TransDecoder command sequence.
- The current implementation makes that inference explicit by running a standard `TransDecoder.LongOrfs` followed by `TransDecoder.Predict`, then lifting ORFs onto genome coordinates with a configurable helper script that defaults to `cdna_alignment_orf_to_genome_orf.pl`.
- Future milestones should consume the resulting genome-coordinate GFF3 as transcript-derived evidence for EVM rather than hiding it inside a larger opaque task.
