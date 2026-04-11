# FastQC

## Purpose

Generate per-FASTQ quality control reports for raw or trimmed sequencing reads.

## Input Data

- FASTQ or FASTQ.GZ read files
- optional runtime/container choice

## Output Data

- HTML report per input FASTQ
- ZIP archive per input FASTQ

## Key Inputs

- FASTQ or FASTQ.GZ read files
- optional runtime/container choice

## Key Outputs

- HTML report per input FASTQ
- ZIP archive per input FASTQ

## Pipeline Fit

- early QC on raw RNA-seq reads
- currently part of the legacy `rnaseq_qc_quant` baseline, before the active genome-annotation milestones

## Official Documentation

- [FastQC homepage](https://www.bioinformatics.babraham.ac.uk/projects/fastqc/)
- [What is FastQC?](https://www.bioinformatics.babraham.ac.uk/projects/fastqc/Help/1%20Introduction/1.1%20What%20is%20FastQC.html)
- [Opening a sequence file](https://www.bioinformatics.babraham.ac.uk/projects/fastqc/Help/2%20Basic%20Operations/2.1%20Opening%20a%20sequence%20file.html)

## Tutorial References

- [GTN FastQC tool reference](https://training.galaxyproject.org/training-material/by-tool/devteam/fastqc.html)
- [GTN Quality Control tutorial](https://training.galaxyproject.org/topics/sequence-analysis/tutorials/quality-control/tutorial.html)
- [GTN FAQ for FastQC reports](https://training.galaxyproject.org/training-material/topics/sequence-analysis/tutorials/quality-control/faqs/)

## Code Reference

- [`src/flytetest/tasks/qc.py`](src/flytetest/tasks/qc.py)
- that module implements the current paired-end FastQC boundary and result-directory capture

## Native Command Context

- FLyteTest runs FastQC as a direct command-line QC step on one paired-end read set.
- the current task invokes `fastqc --quiet <R1> <R2> --outdir <qc_dir>`
- outputs are the standard FastQC HTML and ZIP report files for each mate, treated as descriptive QC only

## Apptainer Command Context

- when `fastqc_sif` is provided, the same command is executed through `apptainer exec <image>.sif`
- container use should not change the input pairing, output layout, or report semantics
- if no image is supplied, the task uses the native FastQC binary instead

## Prompt Template

```text
Use docs/tool_refs/fastqc.md as the reference for the FastQC stage.

Goal:
Run or refine the FastQC step in the legacy `rnaseq_qc_quant` baseline.

Inputs:
- paired or single-end FASTQ inputs
- repo-local output directory for QC reports
- optional `fastqc_sif` container image

Constraints:
- keep FastQC scoped to descriptive read-quality reporting
- preserve separate reports per input FASTQ
- prefer local execution unless a container image is explicitly provided

Deliver:
- the command pattern or task change
- expected HTML and ZIP outputs
- any assumptions that are inferred from current repo behavior
```

## Notes And Caveats

- FastQC reports are descriptive QC outputs, not alignment or expression results.
- For paired-end data, each mate file is reported separately.
- In this repo, FastQC is an early sanity-check stage and not a substitute for downstream alignment, quantification, or annotation QC.
- Current FLyteTest behavior bundles the FastQC outputs into the run manifest for the legacy RNA-seq baseline.
