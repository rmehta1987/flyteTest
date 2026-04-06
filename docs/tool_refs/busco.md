# BUSCO

## Purpose

Assess annotation or protein-set completeness against lineage-specific conserved ortholog sets.

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

## Native Command Context

- BUSCO is a command-line QC tool for genome, transcriptome, or protein inputs.
- The official user guide documents `--in` for input, `--mode` for genome/proteins/transcriptome, and lineage selection via `--lineage_dataset` or `--auto-lineage`.
- For eukaryotic genome mode, the guide notes Miniprot as the default predictor.

## Apptainer Command Context

- A containerized run should call the BUSCO CLI inside an Apptainer image with the workspace and lineage data mounted read-write as needed.
- Keep output paths, temporary files, and lineage datasets explicit so the run is reproducible outside the container.
- This repo now supports optional BUSCO Apptainer execution through the `busco_sif` workflow and task inputs.
- A repo-local runtime was smoke-tested with `tools/busco/busco_v6.0.0_cv1.sif` plus explicit lineage directories under `data/busco_downloads/lineages/`.

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
