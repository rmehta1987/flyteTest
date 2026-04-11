# STAR

## Purpose

Create genome indices and align RNA-seq reads to a reference genome.

## Input Data

- reference genome FASTA
- RNA-seq FASTQ files
- splice-aware alignment parameters

## Output Data

- STAR genome index
- alignment BAM files
- alignment logs and summary metrics

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

## Official Documentation

- [STAR GitHub repository](https://github.com/alexdobin/STAR)
- [STAR manual PDF](https://github.com/alexdobin/STAR/blob/master/doc/STARmanual.pdf)

## Tutorial References

- [GTN RNA-seq Alignment with STAR](https://galaxyproject.github.io/training-material/topics/transcriptomics/tutorials/rna-seq-bash-star-align/tutorial.html)
- [GTN Reference-based RNA-Seq data analysis](https://galaxyproject.github.io/training-material/topics/transcriptomics/tutorials/ref-based/tutorial.html)

## Code Reference

- [`src/flytetest/tasks/transcript_evidence.py`](src/flytetest/tasks/transcript_evidence.py)
- that module implements the STAR genome-index and alignment boundaries in transcript evidence generation

## Native Command Context

- the current milestone uses STAR as two explicit tasks: `genomeGenerate` for indexing and a separate alignment run for each sample
- the repo implementation always builds a fresh index for determinism instead of reusing a cached genome directory
- gzipped paired-end FASTQs are handled with `--readFilesCommand zcat` when both mates end in `.gz`
- a typical minimal shape is `STAR --runMode genomeGenerate ...` for indexing and `STAR --genomeDir ... --readFilesIn ... --outSAMtype BAM SortedByCoordinate ...` for alignment

## Apptainer Command Context

- the Apptainer wrapper should pass the same STAR arguments through unchanged and bind the genome, FASTQ, and output paths explicitly
- a typical shape is `apptainer exec <image>.sif STAR ...`
- containerization should not change the deterministic fresh-index behavior or the sample-level alignment boundary in this milestone

## Prompt Template

```text
Use docs/tool_refs/star.md as the reference for the STAR stage.

Goal:
Run or refine STAR genome indexing and RNA-seq alignment in transcript evidence generation.

Inputs:
- genome FASTA for indexing
- RNA-seq FASTQ inputs for alignment
- output directories for the index and alignment products
- optional `star_sif` container image

Constraints:
- keep genome indexing and sample alignment as separate boundaries
- preserve BAM output paths that downstream samtools and StringTie stages can consume
- if multi-sample alignment is not yet implemented, say that explicitly

Deliver:
- the STAR command pattern or task/workflow change
- expected index directory and alignment/BAM outputs
- any assumptions inferred from current milestone behavior
```

## Notes And Caveats

- STAR is now used in the initial `transcript_evidence_generation` workflow through separate index and alignment tasks.
- The first implementation always builds a fresh STAR index for determinism instead of reusing a prebuilt one.
- Gzipped paired-end FASTQs are handled by adding `--readFilesCommand zcat` when both mates end in `.gz`.
