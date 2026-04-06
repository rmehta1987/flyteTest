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

- AGAT is deferred in FLyteTest scope for now.
- AGAT is a task family rather than one monolithic behavior; future implementations should model statistics, conversion, and cleanup steps separately.
- This repo should keep any format normalization explicit so downstream submission preparation remains auditable.

## Official Documentation

- Project home and command family overview: [nbisweden.github.io/AGAT](https://nbisweden.github.io/AGAT/)
- Installation notes, including Docker and Singularity container examples: [nbisweden.github.io/AGAT/install/](https://nbisweden.github.io/AGAT/install/)
- Tool-level docs for representative subcommands:
  - [agat_convert_sp_gxf2gxf.pl](https://nbisweden.github.io/AGAT/tools/agat_convert_sp_gxf2gxf/)
  - [agat_sp_statistics.pl](https://nbisweden.github.io/AGAT/tools/agat_sp_statistics/)
- The official docs clearly treat AGAT as many small scripts, split across `_sp_` and `_sq_` families.

## Tutorial And Training References

- GTN coverage for AGAT specifically is weak; we did not find a dedicated AGAT walkthrough.
- The closest training context is general genome annotation and GFF/GTF format material, which is useful background but not AGAT-specific implementation guidance.

## Native Command Context

- AGAT is invoked as a set of Perl scripts, for example `agat_convert_sp_gxf2gxf.pl -g input.gff -o output.gff` and `agat_sp_statistics.pl --gff input.gff`.
- `_sp_` scripts slurp the file into memory for standardization and repair; `_sq_` scripts stream linearly and are more lightweight.
- For FLyteTest, that means AGAT should be modeled as several explicit subcommands rather than one opaque annotation-cleanup task.

## Apptainer Command Context

- The official install docs give Docker and Singularity examples; there is no repo-specific Apptainer recipe in the primary docs.
- A practical Apptainer pattern is to pull the same biocontainer image and bind the local annotation workspace, then run the chosen AGAT script inside the container.
- This Apptainer guidance is an inference from the official Singularity workflow, not a separate upstream AGAT document.

## Prompt Template

```text
Use docs/tool_refs/agat.md as the reference for AGAT post-processing work.

Goal:
Plan or implement the `agat_statistics` stage for cleaned annotation outputs.

Inputs:
- final or near-final annotation GFF3
- optional companion FASTA or mapping files depending on the AGAT subcommand
- output path for statistics or normalized annotation products
- optional `agat_sif` container image

Constraints:
- keep AGAT scoped to post-processing and reporting after the main annotation graph
- state the exact AGAT subcommand rather than saying only "run AGAT"
- treat command shapes as inferred until the stage is fully implemented

Deliver:
- the AGAT command pattern or task change
- expected statistics or normalized annotation outputs
- any assumptions that need to stay explicit
```
