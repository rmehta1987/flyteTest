# BUSCO

## Purpose

Assess annotation or protein-set completeness against lineage-specific conserved ortholog sets.

## Input Data

- predicted proteins or annotations converted to the required BUSCO input form
- one or more selected lineage datasets

## Output Data

- BUSCO completeness summaries
- lineage-specific report directories and tables

## Key Inputs

- predicted proteins or annotations converted to the required BUSCO input form
- one or more selected lineage datasets

## Key Outputs

- BUSCO completeness summaries
- lineage-specific report directories and tables

## Pipeline Fit

- downstream QC after consensus annotation and filtering
- implemented in the current FLyteTest milestone as the first post-repeat-filter QC layer

## Official Documentation

- BUSCO user guide: https://busco.ezlab.org/busco_userguide.html
- BUSCO source and installation notes: https://gitlab.com/ezlab/busco

## Tutorial / Training References

- Galaxy Training Network BUSCO tutorial: https://training.galaxyproject.org/training-material/by-tool/iuc/busco/busco.html
- Galaxy genome annotation topic, which includes BUSCO in the broader workflow context: https://training.galaxyproject.org/training-material/topics/genome-annotation/

## Code Reference

- [`src/flytetest/tasks/functional.py`](src/flytetest/tasks/functional.py)
- that module defines the BUSCO lineage defaults, the auto-lineage omission behavior, and the manifest-bearing QC collector

## Native Command Context

- BUSCO is a command-line QC tool for genome, transcriptome, or protein inputs.
- The official user guide documents `--in` for input, `--mode` for genome/proteins/transcriptome, and lineage selection via `--lineage_dataset` or `--auto-lineage`.
- For eukaryotic genome mode, the guide notes Miniprot as the default predictor.
- FLyteTest’s production BUSCO task defaults to `-m prot` and `-c 8`, and it omits `-l` when the lineage label is `auto` or `auto-lineage`.
- The repo’s default lineage list is `eukaryota_odb10,metazoa_odb10,insecta_odb10,arthropoda_odb10,diptera_odb10`.

## Apptainer Command Context

- A containerized run should call the BUSCO CLI inside an Apptainer image with the workspace and lineage data mounted read-write as needed.
- Keep output paths, temporary files, and lineage datasets explicit so the run is reproducible outside the container.
- This repo now supports optional BUSCO Apptainer execution through the `busco_sif` workflow and task inputs.
- A repo-local runtime was smoke-tested with `data/images/busco_v6.0.0_cv1.sif` plus explicit lineage directories under `data/busco_downloads/lineages/`.
- Image provenance from `apptainer inspect`:
  - `org.label-schema.usage.singularity.deffile.from: ezlabgva/busco:v6.0.0_cv1`

## Repo Smoke Fixture

- The lightweight BUSCO image smoke uses the upstream eukaryota test genome
  from `https://gitlab.com/ezlab/busco/-/raw/master/test_data/eukaryota/genome.fna?ref_type=heads`.
- The fixture is staged under `data/busco/test_data/eukaryota/` by
  `scripts/rcc/download_minimal_busco_fixture.sh`.
- The smoke command preserves the upstream test shape:

```bash
busco -i genome.fna -c 8 -m geno -f --out test_eukaryota
```

- On RCC, use `scripts/rcc/run_m18_hpc_smoke.sh` as the one-command Milestone
  18 path when `BUSCO_SIF` points at the BUSCO v6 SIF. That wrapper stages the
  fixture, submits the BUSCO image smoke, then exercises the Milestone 18
  Slurm retry/resubmission record path with a frozen BUSCO genome-mode fixture
  recipe that also points at `data/busco/test_data/eukaryota/genome.fna`. The
  fixture recipe uses `busco_mode=geno` and `lineage_dataset=auto-lineage` so
  FLyteTest omits `-l`, matching the lightweight upstream command shape.
- The production `annotation_qc_busco` workflow still runs downstream of
  repeat filtering on the final protein FASTA. The Milestone 18 HPC smoke is a
  smaller scheduler/runtime test and does not require a repeat-filter result
  directory.
- The production task does not use `-f`; that flag is part of the smoke fixture only.

## Prompt Template

```text
Use docs/tool_refs/busco.md as the reference for the BUSCO stage.

Goal:
Plan or implement `busco_assess_proteins` or `annotation_qc_busco` for annotation QC.

Inputs:
- predicted protein FASTA from the cleaned annotation stage
- BUSCO lineage selection
- output directory for BUSCO reports
- optional `busco_sif` container image

Constraints:
- keep BUSCO downstream of structural annotation and cleanup
- record lineage choice explicitly because it changes interpretation
- preserve the standard BUSCO summary files in the result bundle

Deliver:
- the BUSCO command pattern or task change
- expected run directory and summary outputs
- any assumptions inferred from lineage/runtime availability
```

## Notes And Caveats

- FLyteTest now implements BUSCO downstream of repeat filtering as a dedicated annotation-QC workflow.
- The design notes expect BUSCO to run across multiple lineages, so the workflow keeps lineage selection explicit instead of inferring one automatically.
- The notes use `_odb10` lineage names, but a fresh real BUSCO install may instead use newer lineage directories such as `_odb12`; pass explicit local lineage paths when you want runtime validation to be version-stable.
- BUSCO is a QC layer, not a gene model generator.
