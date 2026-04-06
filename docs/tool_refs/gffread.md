# gffread

## Purpose

Extract protein FASTA files from the current annotation GFF3 during repeat-filtering cleanup.

## Key Inputs

- current annotation GFF3
- reference genome FASTA

Typical repeat-filtering boundaries in this repo:

- `post_pasa_updates.sort.gff3`
- `bed_repeats_removed.gff3`
- `all_repeats_removed.gff3`

## Key Outputs

- protein FASTA emitted by `gffread -y`
- period-stripped protein FASTA used by the later funannotate repeat blast step

## Pipeline Fit

- repeat-filtering cleanup stage after PASA refinement
- reused before overlap filtering, before repeat blasting, and after final repeat removal

## Official Documentation

- gffread repository and docs: https://github.com/gpertea/gffread

## Tutorial References

- GTN Funannotate tutorial context is adjacent background, but the repo-local notes are the concrete source for this post-PASA gffread usage

## Native Command Context

- the notes use `gffread -y proteins.fa -g genome.fa annotation.gff3`
- the notes then remove periods from protein sequences before diamond-backed repeat blasting
- FLyteTest keeps both outputs explicit: the raw gffread protein FASTA and the period-stripped companion FASTA

## Apptainer Command Context

- containerized execution follows the same `gffread -y ... -g ...` boundary with local input and output directories bound into the image

## Prompt Template

```text
Use docs/tool_refs/gffread.md as the reference for repeat-filter protein extraction.

Goal:
Refine `gffread_proteins` for the current repeat-filtering stage.

Inputs:
- annotation GFF3
- genome FASTA
- optional `gffread` binary path
- optional `repeat_filter_sif`

Constraints:
- keep protein extraction separate from overlap filtering and repeat blasting
- preserve both the raw protein FASTA and the period-stripped FASTA
- document any assumptions around header or sequence sanitization explicitly

Deliver:
- the gffread command pattern or task change
- expected protein FASTA outputs
- any assumptions that remain inferred from the notes
```

## Notes And Caveats

- The notes use gffread at multiple points in repeat filtering; this repo keeps those calls explicit rather than hiding them inside funannotate tasks.
- Period stripping is a deterministic follow-on transform from the notes and is not presented here as a separate biological stage.
