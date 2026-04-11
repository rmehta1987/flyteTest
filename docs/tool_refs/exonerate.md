# Exonerate

## Purpose

Align protein evidence to the genome and convert the results into annotation-support formats.

## Input Data

- one or more local protein FASTA files
- reference genome
- deterministic chunking or partition inputs for parallel runs

## Output Data

- raw Exonerate alignments
- converted GFF3 evidence suitable for EVidenceModeler
- deterministic chunk manifests and collected result bundles

## Key Inputs

- one or more local protein FASTA files
- reference genome
- deterministic chunking or partition inputs for parallel runs

Lightweight local fixture examples for milestone-scoped testing:

- `data/braker3/protein_data/fastas/proteins.fa`
- `data/braker3/reference/genome.fa`

## Key Tasks

- stage local protein FASTA inputs
- chunk protein FASTA files deterministically
- run Exonerate per chunk
- convert each Exonerate chunk output into EVM-ready GFF3
- concatenate raw and converted chunk outputs into stable final artifacts

## Key Outputs

- raw Exonerate alignments
- converted GFF3 evidence suitable for EVidenceModeler
- deterministic chunk manifests and collected result bundles

## Pipeline Fit

- protein evidence generation before consensus annotation
- design notes describe chunked execution across many jobs
- this milestone keeps protein FASTAs local and explicit rather than fetching UniProt or RefSeq automatically

## Notes And Caveats

- Exonerate is implemented in FLyteTest as a local-input protein-evidence milestone.
- Raw and converted outputs are both important in the design notes and should remain distinct artifacts.
- The current task family keeps chunk alignment, conversion, and concatenation as separate deterministic steps.
- The current real-data test suite uses the local fixture layout in `tests/test_protein_evidence.py` with subsets copied from `data/braker3/protein_data/fastas/proteins.fa`.
- This milestone does not include BRAKER3, EVM, PASA update rounds, repeat filtering, BUSCO, EggNOG, AGAT, or submission prep.

## Official Documentation

- Maintained fork README: [github.com/nathanweeks/exonerate](https://github.com/nathanweeks/exonerate)
- Legacy manpage reference: [animalgenome.org/bioinfo/resources/manuals/exonerate/exonerate.man.html](https://www.animalgenome.org/bioinfo/resources/manuals/exonerate/exonerate.man.html)
- The manpage is the clearest primary source for command-line flags; the fork README is the clearest current source for build and container notes.

## Tutorial And Training References

- GTN coverage is weak for Exonerate specifically; we did not find a dedicated Exonerate walkthrough.
- Closest adjacent GTN material is the broader genome annotation track, including [Genome annotation with Funannotate](https://training.galaxyproject.org/training-material/topics/genome-annotation/tutorials/funannotate/tutorial.html).
- For milestone context, the GTN assembly/annotation recordings page is useful background but does not cover the local-input Exonerate implementation directly.

## Code Reference

- [`src/flytetest/tasks/protein_evidence.py`](src/flytetest/tasks/protein_evidence.py)
- that module implements chunk staging, `--showtargetgff yes`, per-chunk stdout capture, conversion, and result collection

## Native Command Context

- The upstream command shape is `exonerate [options] <query path> <target path>`, with `--query`, `--target`, and `--model` documented in the manpage.
- FLyteTest uses that native alignment model against local protein FASTA chunks and a local genome, rather than fetching UniProt or RefSeq automatically.
- The repo’s current command shape includes `--model protein2genome`, `--showtargetgff yes`, and stdout redirection to a per-chunk `.exonerate.out` file.
- `exonerate --help` and `exonerate --version` are the quickest sanity checks for the installed binary and supported options.

## Apptainer Command Context

- The upstream fork documents Docker-based execution; there is no repo-specific Apptainer recipe in the primary docs.
- The practical Apptainer pattern is to bind local input and output paths into the container and run `exonerate` inside that mounted workspace.
- In FLyteTest, that container path should preserve the same local-input behavior and deterministic chunk outputs as the native command path.

## Prompt Template

```text
Use docs/tool_refs/exonerate.md as the reference for protein-evidence alignment.

Goal:
Run or implement `exonerate_align_chunk` and its downstream GFF3 conversion boundary.

Inputs:
- genome FASTA
- chunked protein FASTA inputs
- output paths for raw Exonerate output and EVM-ready GFF3
- optional `exonerate_sif` container image

Constraints:
- keep chunked alignment and GFF3 normalization as explicit stages
- preserve deterministic recombination of chunk outputs
- rely on official Exonerate documentation and repo-local notes because GTN coverage is weak

Deliver:
- the Exonerate command pattern or task change
- expected chunk outputs and EVM-ready GFF3 artifacts
- any assumptions that are inferred from current pipeline notes
```
