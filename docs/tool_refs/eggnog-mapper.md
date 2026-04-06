# EggNOG-mapper

## Purpose

Assign functional annotations, orthology-informed names, and related annotation metadata.

## Official Documentation

- upstream project README: [github.com/eggnogdb/eggnog-mapper](https://github.com/eggnogdb/eggnog-mapper)
- canonical docs hub from the upstream README: [github.com/jhcepas/eggnog-mapper/wiki](https://github.com/jhcepas/eggnog-mapper/wiki)
- the upstream repo exposes `emapper.py` for annotation runs and `download_eggnog_data.py` / `create_dbs.py` for database staging

## Tutorial / Training References

- GTN tutorial: [Functional annotation of protein sequences](https://training.galaxyproject.org/training-material/topics/genome-annotation/tutorials/functional/tutorial.html)
- GTN workflow page: [Functional annotation](https://training.galaxyproject.org/training-material/topics/genome-annotation/tutorials/functional/workflows/functional.html)
- the GTN material is the clearest hands-on reference for the common EggNOG-mapper protein annotation flow

## Key Inputs

- predicted proteins or other supported sequence inputs
- EggNOG databases and runtime configuration

## Key Outputs

- functional annotation tables
- name or function mappings that can be propagated into GFF3 features

## Pipeline Fit

- downstream functional annotation after structural annotation and QC

## Native Command Context

- the upstream CLI centers on `emapper.py`
- a common native pattern is `emapper.py -i <proteins.faa> --cpu <N> -o <prefix>`
- the GTN tutorial also shows nucleotide-derived input with `emapper.py -m diamond --itype CDS -i <cDNA.fasta> -o <prefix> --cpu <N>`
- database download and staging stay separate from the annotation run in the upstream project

## Apptainer Command Context

- FLyteTest does not implement this stage yet; any container command here is a usage sketch, not a shipped workflow claim
- the direct container form should mirror the native CLI, for example `apptainer exec <image> emapper.py ...`
- bind the EggNOG data directory and output directory explicitly so database lookups and reports stay on persistent storage
- exact image names, environment variables, and helper paths are environment-specific and should be documented by the eventual implementation

## Prompt Template

```text
Use docs/tool_refs/eggnog-mapper.md as the reference for the EggNOG stage.

Goal:
Plan or implement `eggnog_map` for functional annotation of predicted proteins.

Inputs:
- protein FASTA from the cleaned annotation stage
- output directory for EggNOG tabular and annotation products
- optional database location and `eggnog_mapper_sif` image

Constraints:
- keep this stage downstream of structural annotation and cleanup
- record any external database dependency explicitly
- preserve predictable repo-local output files

Deliver:
- the `emapper.py` command pattern or task change
- expected annotation tables and summary outputs
- any assumptions inferred from the runtime environment
```

## Notes And Caveats

- EggNOG-mapper is deferred in FLyteTest for now.
- The design notes treat functional annotation as a later-stage enrichment step, not part of primary gene model generation.
- Future implementation should keep database staging separate from the actual mapping run where practical.
