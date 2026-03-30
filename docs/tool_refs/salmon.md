# Salmon

## Purpose

Build transcriptome indices and quantify transcript abundance from RNA-seq reads.

## Key Inputs

- transcriptome FASTA for indexing
- paired-end or single-end read files for quantification
- library type settings

## Key Outputs

- Salmon index directory
- `quant.sf`
- run metadata such as `cmd_info.json`, logs, and auxiliary files

## Pipeline Fit

- transcript-level quantification in the current RNA-seq workflow
- likely upstream evidence for future expression-aware annotation summaries

## Notes And Caveats

- Current FLyteTest uses `salmon index` and `salmon quant --validateMappings`.
- The current example builds an index from a transcriptome FASTA, not a genome.
- Decoy handling and richer library configuration are future refinements and are not added in this milestone.
