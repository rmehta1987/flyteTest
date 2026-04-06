# RepeatMasker

## Purpose

Provide repeat annotations that can be converted into the BED-style overlap input used during post-PASA repeat filtering.

## Key Inputs

- RepeatMasker `.out` file produced upstream of this milestone

Local fixture context for optional smoke planning:

- `data/repeatmasker/genome_raw.fasta`
- `data/repeatmasker/Muco_library_RM2.fasta`
- `data/repeatmasker/Muco_library_EDTA.fasta`

## Key Outputs

- converted RepeatMasker GFF3
- three-column RepeatMasker BED used by the overlap-filtering step

## Pipeline Fit

- repeat-filtering stage after PASA post-EVM refinement and before BUSCO or functional annotation

## Official Documentation

- RepeatMasker home and docs: https://www.repeatmasker.org/
- `rmOutToGFF3.pl` ships with RepeatMasker utility scripts and is the conversion utility named in the notes

## Tutorial References

- GTN RepeatMasker tutorial: https://training.galaxyproject.org/training-material/topics/genome-annotation/tutorials/repeatmasker/tutorial.html

## Native Command Context

- the notes start this stage from an existing RepeatMasker `.out` file rather than re-running RepeatMasker inside the downstream cleanup workflow
- the documented conversion boundary is `rmOutToGFF3.pl <repeatmasker.out> > repeatmasker.gff3`
- the downstream BED in this repo preserves the notes' simple `awk '{print $1 "\t" $4 "\t" $5}'` extraction from the converted GFF3

## Apptainer Command Context

- if RepeatMasker utilities are containerized locally, bind the input and output directories and run the same `rmOutToGFF3.pl` command inside the container
- this repo treats any single-image repeat-filter runtime as a local deployment choice, not as a notes-backed guarantee

## Prompt Template

```text
Use docs/tool_refs/repeatmasker.md as the reference for the RepeatMasker conversion boundary.

Goal:
Refine `repeatmasker_out_to_bed` for the repeat-filtering stage.

Inputs:
- a RepeatMasker `.out` file
- optional `rmOutToGFF3.pl` path
- optional `repeat_filter_sif`

Constraints:
- do not imply RepeatMasker execution itself is implemented if the task only consumes `.out`
- preserve the notes-shaped GFF3 plus BED boundary explicitly
- keep downstream BUSCO, EggNOG, AGAT, and submission-prep out of scope

Deliver:
- the conversion command pattern or task change
- expected `repeatmasker.gff3` and `repeatmasker.bed` outputs
- any assumptions about the `.out` file or BED formatting
```

## Notes And Caveats

- FLyteTest currently implements RepeatMasker output conversion, not RepeatMasker execution.
- The local `data/repeatmasker/` fixtures are for smoke-test planning and optional upstream `.out` generation when binaries are available.
- The BED coordinates are intentionally notes-shaped rather than normalized beyond the documented `$1/$4/$5` extraction.
