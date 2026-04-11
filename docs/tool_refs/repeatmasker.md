# RepeatMasker

## Purpose

Run repeat masking on genome FASTA inputs and provide repeat annotations that
can be converted into the BED-style overlap input used during post-PASA repeat
filtering.

## Input Data

- FASTA file containing the query DNA sequence(s)
- database selection, such as a species/group choice from Dfam or Repbase
  libraries, or a custom repeat-library FASTA passed with `-lib`
- options such as masking level, speed, and specific DNA species searches

## Key Inputs

- genome FASTA query sequence, such as `data/repeatmasker/genome_raw.fasta`
- repeat source, either a configured species/database choice or a custom repeat
  library FASTA passed with `-lib`
- for the current FLyteTest repeat-filter conversion task only: a RepeatMasker
  `.out` annotation file produced by an upstream RepeatMasker run

Local fixture context for optional smoke planning:

- this repo does not ship checked-in RepeatMasker fixture files because `data/`
  is local staging space
- restore the GTN tutorial fixture files with
  `scripts/rcc/download_minimal_repeatmasker_fixture.sh`
- use synthetic inputs or an external RepeatMasker `.out` file when planning
  the conversion boundary if the GTN fixture has not been staged yet

## Output Data

- masked FASTA (`.masked`)
- output table (`.out`)
- summary table (`.tbl`)
- optional annotation/GFF (`.gff`)
- optional alignment/map (`.align` or `.map`)

## Key Outputs

- RepeatMasker `.masked` FASTA containing the masked query sequence
- RepeatMasker `.out` annotation table listing masked repeats
- RepeatMasker `.tbl` summary of repeat content
- optional RepeatMasker GFF output when the run uses `-gff`
- optional alignment/map output when RepeatMasker is asked to emit it
- for the current FLyteTest repeat-filter conversion task only: converted
  `repeatmasker.gff3` and three-column `repeatmasker.bed` files used by the
  overlap-filtering step

## Pipeline Fit

- RepeatMasker itself is an upstream repeat-masking stage on the genome FASTA.
- The current FLyteTest repeat-filtering workflow starts after PASA post-EVM
  refinement and consumes a pre-existing RepeatMasker `.out` file before BUSCO
  or functional annotation.

## Official Documentation

- RepeatMasker home and docs: https://www.repeatmasker.org/
- `rmOutToGFF3.pl` ships with RepeatMasker utility scripts and is the conversion utility named in the notes

## Tutorial References

- GTN RepeatMasker tutorial: https://training.galaxyproject.org/training-material/topics/genome-annotation/tutorials/repeatmasker/tutorial.html

## Code Reference

- [`src/flytetest/tasks/filtering.py`](src/flytetest/tasks/filtering.py)
- that module implements the downstream RepeatMasker conversion boundary used by repeat filtering

## Repo Smoke Fixture

- The GTN RepeatMasker tutorial links the input genome and two pre-computed
  Mucor mucedo repeat libraries from Zenodo record `7085837`.
- Stage those tutorial files under `data/repeatmasker/` with:

```bash
bash scripts/rcc/download_minimal_repeatmasker_fixture.sh
```

- The expected staged files are:
  - `data/repeatmasker/genome_raw.fasta`
  - `data/repeatmasker/Muco_library_RM2.fasta`
  - `data/repeatmasker/Muco_library_EDTA.fasta`
- The source URLs are:
  - `https://zenodo.org/record/7085837/files/genome_raw.fasta`
  - `https://zenodo.org/record/7085837/files/Muco_library_RM2.fasta`
  - `https://zenodo.org/record/7085837/files/Muco_library_EDTA.fasta`

## Native Command Context

- Official RepeatMasker accepts FASTA input and produces the masked FASTA,
  `.out`, `.tbl`, and optional `.gff` / `.align` / `.map` outputs.
- Use `-species` for a configured RepeatMasker/Dfam species choice, or `-lib`
  for a custom repeat-library FASTA. The GTN tutorial uses the
  `genome_raw.fasta` query and either a Dfam species selection or one of the
  precomputed Mucor mucedo repeat-library FASTAs.
- Use `-xsmall` for soft-masking where repeat regions are lower-case in the
  `.masked` FASTA, and use `-gff` when a GFF repeat annotation file is needed.
- A CLI approximation of the GTN custom-library run is:

```bash
RepeatMasker -xsmall -gff -lib Muco_library_RM2.fasta genome_raw.fasta
```

- The current FLyteTest task `repeatmasker_out_to_bed` is not the native
  RepeatMasker run. It is the downstream adapter for an already-produced
  RepeatMasker `.out` file:

```bash
rmOutToGFF3.pl genome_raw.fasta.out > repeatmasker.gff3
awk '{print $1 "\t" $4 "\t" $5}' repeatmasker.gff3 > repeatmasker.bed
```

## Apptainer Command Context

- if RepeatMasker is containerized locally, bind the genome FASTA, repeat
  library/database, and output directories and run the native `RepeatMasker`
  command inside the container
- if only the downstream conversion utility is containerized locally, bind the
  input and output directories and run the same `rmOutToGFF3.pl` command inside
  the container
- this repo treats any single-image repeat-filter runtime as a local deployment choice

## Prompt Template

```text
Use docs/tool_refs/repeatmasker.md as the reference for the RepeatMasker stage.

Goal:
Plan native RepeatMasker execution or refine `repeatmasker_out_to_bed` for the
repeat-filtering stage.

Inputs:
- genome FASTA input for a native RepeatMasker run
- species/database choice or custom repeat-library FASTA for native RepeatMasker
- RepeatMasker `.out` file for the downstream FLyteTest conversion task
- optional `rmOutToGFF3.pl` path
- optional `repeat_filter_sif`

Constraints:
- keep native RepeatMasker inputs/outputs separate from the downstream `.out`
  conversion boundary
- do not imply RepeatMasker execution itself is implemented when changing only
  `repeatmasker_out_to_bed`
- keep downstream BUSCO, EggNOG, AGAT, and submission-prep out of scope

Deliver:
- the native RepeatMasker command pattern or the conversion task change
- expected RepeatMasker outputs, including `.masked`, `.out`, `.tbl`, and
  optional GFF
- expected downstream `repeatmasker.gff3` and `repeatmasker.bed` outputs when
  planning the FLyteTest conversion boundary
```

## Notes And Caveats

- FLyteTest currently implements RepeatMasker output conversion, not RepeatMasker execution.
- The repo does not currently include checked-in RepeatMasker smoke fixtures; use the downloader above to stage the GTN inputs locally.
- The downstream BED coordinates are intentionally copied from the converted
  GFF fields used by the existing BRaker/EVM notes rather than normalized
  further.
