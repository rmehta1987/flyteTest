# EVidenceModeler

## Purpose

Combine ab initio predictions, transcript evidence, and protein evidence into consensus gene models.

## Key Inputs

- ab initio predictions such as BRAKER3 GFF3
- transcript-alignment-derived evidence GFF3
- protein evidence GFF3
- evidence weights and partition settings

## Key Outputs

- partitioned EVM work products
- recombined consensus annotation GFF3

## Pipeline Fit

- central consensus annotation stage after transcript, protein, and ab initio evidence generation

## Notes And Caveats

- EVidenceModeler is not implemented in FLyteTest yet.
- The design notes describe weighting categories such as `ABINITIO_PREDICTION`, `PROTEIN`, `TRANSCRIPT`, and `OTHER_PREDICTION`.
- Future FLyteTest workflows should keep partitioning, command generation, execution, and recombination explicit rather than folding them into one opaque task.
