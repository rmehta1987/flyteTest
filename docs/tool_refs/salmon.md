# Salmon

## Purpose

Build transcriptome indices and quantify transcript abundance from RNA-seq reads.

## Input Data

- transcriptome FASTA for indexing
- paired-end or single-end read files for quantification
- library type settings

## Output Data

- Salmon index directory
- `quant.sf`
- run metadata such as `cmd_info.json`, logs, and auxiliary files

## Key Inputs

- transcriptome FASTA for indexing
- paired-end or single-end read files for quantification
- library type settings

## Key Outputs

- Salmon index directory
- `quant.sf`
- run metadata such as `cmd_info.json`, logs, and auxiliary files

## Pipeline Fit

- transcript-level quantification in the older RNA-seq QC/quant baseline
- index and quant remain separate boundaries in FLyteTest
- Salmon outputs are not yet wired into the genome-annotation workflows

## Official Documentation

- [Salmon documentation home](https://salmon.readthedocs.io/)
- [Preparing transcriptome indices](https://salmon.readthedocs.io/en/latest/salmon.html#preparing-transcriptome-indices-mapping-based-mode)
- [Quantifying in mapping-based mode](https://salmon.readthedocs.io/en/latest/salmon.html#quantifying-in-mapping-based-mode)
- [Salmon output file formats](https://salmon.readthedocs.io/en/latest/file_formats.html)

## Tutorial And Training References

- [GTN Reference-based RNA-Seq data analysis](https://training.galaxyproject.org/training-material/topics/transcriptomics/tutorials/ref-based/tutorial.html)
- [GTN QC + Mapping + Counting workflow](https://training.galaxyproject.org/training-material/topics/transcriptomics/tutorials/ref-based/workflows/qc-mapping-counting-paired-and-single.html)

## Code Reference

- [`src/flytetest/tasks/quant.py`](src/flytetest/tasks/quant.py)
- that module implements the Salmon index, quantification, and manifest collection boundaries

## Native Command Context

- the current FLyteTest baseline uses `salmon index` and `salmon quant --validateMappings`
- `salmon index` builds an index from a transcriptome FASTA, not a genome FASTA
- `salmon quant` is the sample-level boundary and accepts either paired-end reads with `-1`/`-2` or single-end reads with `-r`
- `quant.sf` is the main quantification output; `cmd_info.json` and auxiliary files are secondary run artifacts

## Apptainer Command Context

- use `apptainer exec <image>.sif salmon index ...` and `apptainer exec <image>.sif salmon quant ...`
- bind the transcriptome, reads, and output directories explicitly so the container sees the same paths as the native run
- containerization should not blur the index-versus-quant split or change the expected `quant.sf` output location

## Prompt Template

```text
Use docs/tool_refs/salmon.md as the reference for the Salmon stage.

Goal:
Run or refine the legacy transcript-quantification path using `salmon index` and `salmon quant`.

Inputs:
- transcriptome FASTA for index creation
- RNA-seq reads for quantification
- output directories for the index and per-sample quant results
- optional `salmon_sif` container image

Constraints:
- keep index creation and sample quantification as separate boundaries
- treat Salmon as part of the older `rnaseq_qc_quant` baseline, not the annotation workflows
- preserve `quant.sf` as the primary output contract

Deliver:
- the command pattern or task change
- expected index and `quant.sf` outputs
- any assumptions that are inferred from current repo behavior
```

## Notes And Caveats

- Salmon here is a transcriptome-level quantification tool for the older RNA-seq QC/quant baseline, not a genome annotation engine.
- The current example builds an index from a transcriptome FASTA and quantifies reads against that index.
- Decoy handling and richer library configuration can be added later, but they are outside this milestone.
