# TransDecoder

## Purpose

Predict coding regions from transcript assemblies and produce coding-support features for downstream annotation.

## Input Data

- PASA assemblies FASTA
- PASA assemblies GFF3 for lifting predicted ORFs onto genome coordinates
- optional minimum protein-length threshold

## Output Data

- transcript-level coding sequence predictions
- protein translations
- genome-coordinate GFF3 support files for downstream consensus steps

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

## Official Documentation

- project source and docs hub: https://github.com/TransDecoder/TransDecoder
- the repo README points to the project wiki as the canonical documentation source
- the source tree exposes `TransDecoder.LongOrfs` and `TransDecoder.Predict` as the phase-specific entrypoints

## Tutorial References

- GTN tool page: https://training.galaxyproject.org/training-material/by-tool/iuc/transdecoder/transdecoder.html
- GTN tutorial context: https://training.galaxyproject.org/training-material/topics/transcriptomics/tutorials/full-de-novo/tutorial.html
- the GTN material is the clearest training reference for the common Trinity plus TransDecoder transcriptomics flow

## Code Reference

- [`src/flytetest/tasks/transdecoder.py`](src/flytetest/tasks/transdecoder.py)
- that module implements the PASA-derived LongOrfs/Predict flow and the genome-coordinate ORF lift

## Native Command Context

- FLyteTest currently treats the TransDecoder step as an inferred two-phase run: `TransDecoder.LongOrfs` followed by `TransDecoder.Predict`
- the upstream notes do not spell out every flag, so any exact option set should be treated as implementation detail rather than a claim about the original pipeline
- lifting predicted ORFs back to genome coordinates with `cdna_alignment_orf_to_genome_orf.pl` is a repo-local inference layered on top of the standard TransDecoder phases
- the genome-coordinate GFF3 is the evidence artifact the later consensus stages expect

## Apptainer Command Context

- when containerized, the native sequence maps cleanly to `apptainer exec <image> TransDecoder.LongOrfs -t <transcripts.fa> ...` and then `apptainer exec <image> TransDecoder.Predict -t <transcripts.fa> ...`
- bind-mount the transcript FASTA, PASA outputs, and result directory explicitly so the generated `.transdecoder_dir` and downstream GFF3 stay on persistent storage
- if the stage needs genome-coordinate output, keep the ORF-to-genome lift as a separate command inside or after the container run
- exact container flags and helper-script paths are environment-specific and remain inferred unless the local workflow implementation documents them

## Prompt Template

```text
Use docs/tool_refs/transdecoder.md as the reference for the TransDecoder stage.

Goal:
Run or refine `transdecoder_train_from_pasa` on PASA-derived transcript assemblies.

Inputs:
- PASA transcript FASTA or comparable transcript assembly input
- output directory for long-ORF and prediction products
- optional `transdecoder_sif` container image

Constraints:
- keep the stage downstream of PASA transcript assembly
- preserve the distinction between ORF discovery and coding prediction if the implementation keeps them separate
- do not imply full annotation refinement beyond the current stage boundary

Deliver:
- the TransDecoder command pattern or task change
- expected peptide/CDS outputs and support files
- any assumptions inferred from current repo behavior
```

## Notes And Caveats

- FLyteTest now implements a first TransDecoder stage as `transdecoder_train_from_pasa` plus the composed `transdecoder_from_pasa` workflow.
- The design notes specifically reference a TransDecoder genome GFF3 derived from PASA assemblies, but they do not provide the exact TransDecoder command sequence.
- The current implementation makes that inference explicit by running a standard `TransDecoder.LongOrfs` followed by `TransDecoder.Predict`, then lifting ORFs onto genome coordinates with a configurable helper script that defaults to `cdna_alignment_orf_to_genome_orf.pl`.
- Future milestones should consume the resulting genome-coordinate GFF3 as transcript-derived evidence for EVM rather than hiding it inside a larger opaque task.
