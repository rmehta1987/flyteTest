# Trinity

## Purpose

Assemble transcripts from RNA-seq reads. Trinity supports de novo and
genome-guided modes upstream, and FLyteTest now wires both modes in the
transcript-evidence branch.

## Key Inputs

- RNA-seq reads
- optionally a genome-guided BAM for genome-guided mode

## Key Outputs

- transcript FASTA assemblies
- assembly working directories and logs

## Pipeline Fit

- transcript evidence generation
- design notes call for both de novo Trinity and genome-guided Trinity products
- FLyteTest now uses Trinity first for the de novo branch, then again after BAM merge for the genome-guided branch

## Official Documentation

- Trinity wiki home: https://github.com/trinityrnaseq/trinityrnaseq/wiki
- Running Trinity: https://github.com/trinityrnaseq/trinityrnaseq/wiki/Running-Trinity
- Genome-guided Trinity: https://github.com/trinityrnaseq/trinityrnaseq/wiki/Genome-Guided-Trinity-Transcriptome-Assembly
- Installing Trinity: https://github.com/trinityrnaseq/trinityrnaseq/wiki/Installing-Trinity

## Tutorial And Training References

- GTN Trinity tool page: https://training.galaxyproject.org/training-material/by-tool/iuc/trinity/trinity.html
- GTN de novo transcriptome assembly tutorial: https://training.galaxyproject.org/training-material/topics/transcriptomics/tutorials/full-de-novo/tutorial.html
- Trinity wiki training materials point to RNA-Seq workshop resources for de novo and genome-guided use cases: https://github.com/trinityrnaseq/trinityrnaseq/wiki

## Native Command Context

- Trinity is run from the `Trinity` script in the installation directory.
- The official wiki documents genome-guided runs with a coordinate-sorted BAM, `--genome_guided_bam`, `--genome_guided_max_intron`, `--max_memory`, and `--CPU`.
- Example shape: `Trinity --genome_guided_bam rnaseq.coordSorted.bam --genome_guided_max_intron 10000 --max_memory 50G --CPU 6`
- FLyteTest now exposes de novo Trinity for the current single-sample paired-end path using explicit `--left/--right` inputs as a documented simplification of the notes' multi-sample `--samples_file` example.

## Apptainer Command Context

- Trinity's official container docs cover Singularity images; Apptainer uses the same execution model, so the wrapper is the Apptainer equivalent of the documented Singularity command.
- Inferred example shape: `apptainer exec -e Trinity.sif Trinity --genome_guided_bam rnaseq.coordSorted.bam --genome_guided_max_intron 10000 --max_memory 50G --CPU 6`
- Keep absolute paths for host-mounted inputs and outputs when running in a container.

## Prompt Template

```text
Use docs/tool_refs/trinity.md as the reference for Trinity assembly work.

Goal:
Run or implement the appropriate Trinity boundary in FLyteTest.

Inputs:
- RNA-seq reads for de novo assembly or aligned BAM evidence for genome-guided assembly
- output directory for Trinity artifacts
- optional `trinity_sif` container image

Constraints:
- keep de novo and genome-guided Trinity as distinct task boundaries
- preserve the mode-specific output contract in the result bundle
- keep any remaining all-sample or `--samples_file` limitations explicit

Deliver:
- the command pattern or task/workflow change
- expected Trinity output directory and key FASTA products
- any assumptions that are inferred from the current notes-alignment state
```

## Notes And Caveats

- FLyteTest now implements both de novo Trinity and genome-guided Trinity in the transcript-evidence workflow.
- De novo Trinity is currently modeled as a single-sample paired-end task even though the notes show a multi-sample `--samples_file` example.
- Genome-guided Trinity is modeled as its own task after the BAM merge stage.
- PASA transcript preparation and align/assemble are now implemented and consume Trinity-derived transcript assemblies, while downstream coding prediction still remains future work.
