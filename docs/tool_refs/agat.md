# AGAT

## Purpose

Generate annotation statistics, GFF/GTF conversion, and deterministic cleanup slices around the EggNOG-annotated annotation bundle while keeping `table2asn` separate.

## Key Inputs

- GFF3 or GTF annotation files
- optional companion FASTA for the statistics slice
- AGAT conversion results for the cleanup slice

## Key Outputs

- annotation statistics reports
- converted or normalized annotation files
- cleaned GFF3 files and cleanup summaries

## Pipeline Fit

- downstream post-processing, reporting, and GFF3 cleanup after annotation refinement and functional annotation
- this repo now implements the statistics, conversion, and cleanup boundaries after EggNOG functional annotation

## Notes And Caveats

- AGAT is now implemented in FLyteTest as separate statistics, conversion, and
  cleanup slices after EggNOG functional annotation.
- AGAT is a task family rather than one monolithic behavior, so future
  implementations should keep statistics, conversion, cleanup, and submission
  preparation steps separate.
- This repo should keep any format normalization explicit so downstream
  submission preparation remains auditable.
- The statistics slice models the core `agat_sp_statistics.pl` command from the
  notes and the official AGAT docs. The notes also mention a companion FASTA
  and `-d` histogram output; those details stay explicit and optional.
- The conversion slice models the core `agat_convert_sp_gxf2gxf.pl` command
  family. The notes show a GTF-to-GFF3 example; using the same AGAT converter
  on the EggNOG-annotated GFF3 bundle is an inferred normalization step and is
  kept explicit in the manifest.
- The cleanup slice consumes the AGAT conversion bundle and applies the
  notes-backed deterministic GFF3 attribute edits: propagate parent mRNA `Name`
  values onto child CDS `product` attributes, remove gene-level `Note`
  attributes, and replace CDS products beginning with `-` with `putative`.
- `table2asn` remains deferred and should not be folded into AGAT cleanup.

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

- AGAT is invoked as a set of Perl scripts, for example `agat_sp_statistics.pl --gff input.gff --output stats.tsv` and `agat_convert_sp_gxf2gxf.pl -g input.gtf -o output.gff3`.
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
Plan or implement the `agat_cleanup_gff3` stage for the AGAT-converted GFF3 bundle.

Inputs:
- AGAT conversion results bundle
- converted GFF3 boundary from `annotation_postprocess_agat_conversion`

Constraints:
- keep AGAT scoped to post-processing and reporting after the main annotation graph
- keep the cleanup rules deterministic and notes-backed
- do not run `table2asn` or add submission packaging in this slice

Deliver:
- the AGAT task change
- expected cleaned GFF3 output and cleanup summary
- any assumptions that need to stay explicit
```
