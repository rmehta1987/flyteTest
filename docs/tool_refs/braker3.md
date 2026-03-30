# BRAKER3

## Purpose

Generate ab initio gene predictions to provide a core evidence source for consensus annotation.

## Key Inputs

- reference genome
- supporting evidence configured for BRAKER3 runs

## Key Outputs

- BRAKER3 prediction outputs
- `braker.gff3` as the key downstream consensus input described in the design notes

## Pipeline Fit

- ab initio annotation stage before EVidenceModeler

## Notes And Caveats

- BRAKER3 is not implemented in FLyteTest yet.
- The attached pipeline notes clearly require `braker.gff3` as an EVM input, but they do not spell out the exact BRAKER3 execution commands.
- Until a fuller protocol is added, FLyteTest should treat BRAKER3 as a required upstream task family and document invocation details as inferred rather than authoritative.
