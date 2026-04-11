# StringTie

## Purpose

Assemble transcripts and summarize transcript abundance from genome-aligned RNA-seq data.

## Input Data

- coordinate-sorted RNA-seq BAM files
- reference genome and optional annotation context

## Output Data

- assembled transcript GTF
- abundance tables and summary files

## Key Inputs

- coordinate-sorted RNA-seq BAM files
- reference genome and optional annotation context

## Key Outputs

- assembled transcript GTF
- abundance tables and summary files

## Pipeline Fit

- transcript evidence generation after RNA-seq alignment
- design notes place StringTie alongside genome-guided Trinity before PASA

## Official Documentation

- [StringTie manual](https://ccb.jhu.edu/software/stringtie/index.shtml?t=manual)
- [StringTie FAQ](https://ccb.jhu.edu/software/stringtie/index.shtml?t=faq)

## Tutorial / Training References

- [GTN StringTie tool page](https://training.galaxyproject.org/training-material/by-tool/iuc/stringtie/stringtie.html)
- [GTN: De novo transcriptome reconstruction with RNA-Seq](https://training.galaxyproject.org/training-material/topics/transcriptomics/tutorials/de-novo/tutorial.html)

## Code Reference

- [`src/flytetest/tasks/transcript_evidence.py`](src/flytetest/tasks/transcript_evidence.py)
- that module implements the current StringTie assembly boundary and its `transcripts.gtf` / abundance outputs

## Native Command Context

- StringTie expects coordinate-sorted SAM, BAM, or CRAM input from RNA-seq alignments.
- The official manual supports `-G` for guide annotation, but this repo's current milestone runs the standalone assembly path without a guide.
- In FLyteTest, the current task emits `transcripts.gtf` and `gene_abund.tab` from the merged STAR BAM and passes the GTF onward to PASA via `--trans_gtf`.

## Apptainer Command Context

- The container wrapper is environment-specific, but the tool invocation remains a normal `stringtie` command inside the image.
- A minimal pattern is `apptainer exec <image>.sif stringtie -o <out.gtf> <sorted.bam>`.
- Keep bind mounts explicit for the input BAM, output directory, and any optional guide annotation or genome context used by the surrounding workflow.

## Prompt Template

```text
Use docs/tool_refs/stringtie.md as the reference for the StringTie stage.

Goal:
Run or refine `stringtie_assemble` within transcript evidence generation.

Inputs:
- merged or sample-level coordinate-sorted BAM input
- output paths for `transcripts.gtf` and abundance tables
- optional `stringtie_sif` container image

Constraints:
- keep the StringTie assembly boundary separate from STAR alignment and PASA
- preserve `transcripts.gtf` as the main downstream handoff
- if guide annotation options are introduced, document them explicitly

Deliver:
- the StringTie command pattern or task change
- expected GTF and abundance outputs
- any assumptions inferred from the current milestone
```

## Notes And Caveats

- StringTie is now implemented as a standalone assembly task in the initial transcript-evidence workflow.
- The current task emits `transcripts.gtf` and `gene_abund.tab` from the merged BAM without an external annotation guide.
- The PASA transcript-alignment workflow now consumes `transcripts.gtf` through `--trans_gtf`.
- BAM preprocessing expectations still remain explicit task boundaries around STAR alignment and BAM merge.
