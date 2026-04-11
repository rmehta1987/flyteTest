# table2asn

## Purpose

Create NCBI GenBank submission records from genome sequence plus annotation inputs.

## Input Data

- template `.sbt` submit-block file
- genome FASTA `.fsa`
- optional feature table `.tbl` or GenBank-specific GFF input
- optional `.src`, `.pep`, or `.qvl` inputs when the submission requires them

## Output Data

- submission ASN.1 `.sqn`
- optional validation `.val` and `.stats`
- optional discrepancy report `.dr`
- optional GenBank flatfile `.gbf`

## Key Inputs

- template `.sbt` submit-block file
- genome FASTA `.fsa`
- optional feature table `.tbl` or GenBank-specific GFF input
- optional `.src`, `.pep`, or `.qvl` inputs when the submission requires them

## Key Outputs

- submission ASN.1 `.sqn`
- optional validation `.val` and `.stats`
- optional discrepancy report `.dr`
- optional GenBank flatfile `.gbf`

## Pipeline Fit

- downstream submission-preparation stage after annotation cleanup and validation
- deferred in FLyteTest scope for now; this repo should not treat table2asn as an active workflow milestone yet

## Official Documentation

- [NCBI table2asn reference](https://www.ncbi.nlm.nih.gov/genbank/table2asn/)
- [NCBI Eukaryotic Annotated Genome Submission Guide](https://www.ncbi.nlm.nih.gov/genbank/eukaryotic_genome_submission/)
- [NCBI Genome Submission Portal](https://submit.ncbi.nlm.nih.gov/about/genome/)

## Tutorial / Training References

- GTN coverage appears weak or absent for `table2asn`; I did not find a direct table2asn tutorial in current GTN search results.
- For broader submission context, the GTN genome-annotation material points users back to NCBI submission documentation rather than a detailed table2asn walkthrough.

## Code Reference

- [`src/flytetest/workflows/functional.py`](src/flytetest/workflows/functional.py)
- that workflow entrypoint is the closest live code boundary today; it stops before submission-prep and keeps `table2asn` deferred

## Native Command Context

- NCBI documents the common genome-submission pattern as `table2asn -t template.sbt -indir path_to_files -M n -Z`
- the repo would stage cleaned genome FASTA plus matching annotation inputs before invoking the command
- exact flags should follow the NCBI `-help` output for the packaged version in use

## Apptainer Command Context

- expected wrapper shape: `apptainer exec <table2asn_image.sif> table2asn -t template.sbt -indir <submission_dir> -M n -Z`
- keep the submission directory bind-mounted read/write so `.sqn`, `.val`, and `.dr` files land in the expected result bundle

## Prompt Template

```text
Use docs/tool_refs/table2asn.md as the reference for future table2asn work.

Goal:
Plan or implement the deferred `table2asn_prepare` submission step.

Inputs:
- cleaned submission directory with genome FASTA and annotation-derived submission files
- NCBI template `.sbt`
- optional `table2asn_sif` container image

Constraints:
- treat this as future submission-prep work unless the milestone explicitly includes it
- follow NCBI submission guidance instead of inventing repo-local flags
- record version-specific behavior and validation outputs

Deliver:
- the command pattern or implementation plan
- expected `.sqn`, `.val`, and `.dr` outputs
- any assumptions that still need confirmation from NCBI documentation
```

## Notes And Caveats

- FLyteTest currently defers `table2asn` implementation and should treat it as future submission-prep work, not as an active pipeline step
- NCBI notes that `table2asn` is the replacement for the older `tbl2asn`
- command behavior is version-sensitive, so this repo should record the exact packaged binary and validation outputs when the stage is eventually implemented
