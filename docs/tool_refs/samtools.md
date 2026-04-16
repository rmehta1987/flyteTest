# samtools

## Purpose

Manipulate SAM/BAM alignment files for downstream transcript-evidence and annotation workflows.

## Input Data

- one or more SAM/BAM alignment files
- merge, sort, or index subcommand parameters

## Output Data

- merged or transformed BAM files
- optional BAM index files depending on the subcommand

## Key Inputs

- one or more SAM/BAM alignment files
- merge, sort, or index subcommand parameters

## Key Outputs

- merged or transformed BAM files
- optional BAM index files depending on the subcommand

## Pipeline Fit

- transcript evidence generation between STAR alignment and genome-guided Trinity or StringTie

## Official Documentation

- [Samtools documentation hub](https://www.htslib.org/doc)
- [samtools manual](https://www.htslib.org/doc/samtools.html)
- [samtools merge manual](https://www.htslib.org/doc/samtools-merge.html)
- [samtools sort manual](https://www.htslib.org/doc/samtools-sort.html)
- [samtools index manual](https://www.htslib.org/doc/samtools-index.html)

## Tutorial References

- [GTN Reference-based RNA-Seq data analysis tutorial](https://training.galaxyproject.org/training-material/topics/transcriptomics/tutorials/ref-based/tutorial.html)
- [GTN QC + Mapping + Counting workflow from the same tutorial set](https://training.galaxyproject.org/training-material/topics/transcriptomics/tutorials/ref-based/workflows/qc-mapping-counting-paired-and-single.html)
- GTN’s transcriptomics training materials place samtools in practical RNA-seq mapping and BAM-handling contexts.

## Code Reference

- [`src/flytetest/tasks/transcript_evidence.py`](src/flytetest/tasks/transcript_evidence.py)
- that module implements the explicit BAM merge boundary used before genome-guided Trinity and StringTie

## Native Command Context

- `samtools merge` is the explicit BAM-merge boundary used by this repo’s transcript-evidence stage.
- The current milestone merges a single STAR-produced BAM, so the stage stays visible even though multi-sample merging is not implemented yet.
- `samtools sort` and `samtools index` remain the native follow-on commands if downstream tools need coordinate-sorted BAMs and indexes as separate artifacts.

## Apptainer Command Context

- Use `apptainer exec <image>.sif samtools <subcommand> ...` when running samtools in a containerized task.
- `exec` runs the requested command directly inside the container, which fits FLyteTest’s deterministic subcommand execution better than relying on a container default runscript.
- [Apptainer user guide: running containers in the foreground](https://apptainer.org/docs/user/main/running_services.html)
- The official Apptainer CLI docs describe `exec` for SIF images and sandbox directories, which matches the repo’s current local-and-container execution model.

## Prompt Template

```text
Use docs/tool_refs/samtools.md as the reference for the samtools stage.

Goal:
Run or refine the BAM-handling boundary in transcript evidence generation.

Inputs:
- one or more STAR-produced BAM inputs
- target output path for the merged or transformed BAM
- optional `samtools_sif` container image

Constraints:
- keep the explicit samtools stage visible even when the current milestone only merges a single BAM
- do not silently fold sort or index into the merge stage unless the task contract changes
- preserve deterministic output naming in the result bundle

Deliver:
- the samtools command pattern or task change
- expected BAM and optional BAI outputs
- any assumptions that are inferred from the current milestone
```

## Notes And Caveats

- FLyteTest currently uses samtools for the explicit BAM merge stage in `transcript_evidence_generation`.
- The first implementation merges a single STAR-produced BAM so the pipeline preserves the merge stage boundary for future multi-sample expansion.
- Additional samtools stages such as sort and index can be split into separate tasks later if downstream tools require them explicitly.
