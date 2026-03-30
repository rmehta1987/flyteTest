# FLyteTest Development Guide

This repository is evolving from a single Flyte v2 RNA-seq example into a prompt-driven genome annotation workflow system.
The intended user experience is:

- users describe the analysis they want in natural language
- the system maps that request to prebuilt Flyte tasks and workflows
- the pipeline executes without the user editing Python code

This file defines how agents and developers should work in the repo.

## Current State

- Current workflow entrypoint: `flyte_rnaseq_workflow.py`
- Current implemented scope: RNA-seq QC/quantification, transcript evidence generation, PASA transcript alignment/assembly, and TransDecoder coding prediction from PASA outputs
- Current target scope from the attached pipeline notes: RNA-seq evidence generation through consensus annotation, post-processing, QC, and submission preparation

## Pipeline Source Notes

The attached `Braker3 + Evidence Modeler Annotation Notes.docx.pdf` describes a concrete annotation pipeline with the following major stages:

- transcript evidence generation with Trinity, STAR, samtools, and StringTie
- PASA transcript alignment and assembly refinement
- TransDecoder coding region prediction from PASA assemblies
- protein evidence alignment with Exonerate against UniProt and RefSeq proteins
- consensus gene model creation with EVidenceModeler
- PASA-based gene model updates to add UTRs and alternative transcripts
- transposable-element filtering with RepeatMasker output and funannotate repeat filtering
- annotation QC with BUSCO
- functional annotation with EggNOG-mapper
- final statistics and format conversion with AGAT
- optional NCBI submission preparation with `table2asn`

Important constraint:

- the notes clearly use `braker.gff3` as an ab initio input to EVM, but they do not spell out the exact BRAKER3 execution commands in the extracted text
- therefore, treat BRAKER3 as a required upstream task family and EVM input source, but do not invent unsupported BRAKER3 substeps without documenting the assumption

## Core Principles

### 1. Prefer composition over runtime code generation

The system should satisfy user requests by selecting and composing pre-registered tasks and workflows.

Good:

- "Run transcript evidence generation from RNA-seq reads."
- "Create a consensus annotation using BRAKER3, PASA, protein evidence, and EVM."
- "Assess the final annotation with BUSCO and EggNOG."

Avoid as the default:

- generating new task code at runtime for end users
- changing workflow source code to satisfy ordinary user requests

### 2. Keep tasks narrow and pipeline-faithful

Each task should represent one meaningful tool invocation or one deterministic transformation.

Examples drawn from the attached pipeline:

- `trinity_denovo_assemble`
- `star_genome_index`
- `star_align_sample`
- `samtools_merge_bams`
- `trinity_genome_guided_assemble`
- `stringtie_assemble`
- `pasa_accession_extract`
- `pasa_seqclean`
- `pasa_align_assemble`
- `transdecoder_train_from_pasa`
- `exonerate_align_chunk`
- `exonerate_to_evm_gff3`
- `braker3_predict`
- `evm_partition_inputs`
- `evm_write_commands`
- `evm_recombine_outputs`
- `pasa_update_gene_models`
- `repeatmasker_out_to_bed`
- `funannotate_remove_bad_models`
- `funannotate_repeat_blast`
- `gffread_proteins`
- `busco_assess_proteins`
- `eggnog_map`
- `add_eggnog_names_to_gff3`
- `agat_statistics`
- `table2asn_prepare`

Avoid large opaque tasks that combine multiple biological stages.

### 3. Workflows should map to biological intent

Tasks capture tool-level execution details.
Workflows should represent analysis stages that users can request.

Examples:

- `rnaseq_qc_quant`
- `transcript_evidence_generation`
- `protein_evidence_alignment`
- `consensus_annotation_evm`
- `annotation_refinement_pasa`
- `annotation_repeat_filtering`
- `annotation_functional_qc`
- `ncbi_submission_prep`
- `end_to_end_genome_annotation`

### 4. Preserve the actual pipeline order

The attached notes imply the following dependency structure:

1. raw RNA-seq reads and genome setup
2. Trinity de novo assembly
3. STAR index and RNA-seq alignment
4. merged BAM generation
5. Trinity genome-guided assembly and StringTie assembly
6. PASA transcript preparation and alignment/assembly
7. TransDecoder training set generation from PASA assemblies
8. protein evidence alignment with Exonerate
9. BRAKER3 ab initio predictions
10. EVM consensus annotation
11. PASA gene model update rounds
12. repeat/TE filtering
13. BUSCO and EggNOG functional annotation
14. AGAT statistics and optional NCBI submission preparation

When adding tasks and workflows, keep this ordering explicit.

### 5. Be honest about assumptions

If a tool step is not explicitly described in the pipeline notes, document that it is inferred.
This especially applies to:

- exact BRAKER3 invocation details
- any inferred protein database preprocessing
- cluster-specific module loading details that may need abstraction

### 6. Reproducibility matters more than novelty

Prefer stable, inspectable, and repeatable execution over clever autonomous behavior.

## Recommended Repo Direction

As the project grows, move from one workflow file to a package layout like:

```text
src/flytetest/
  config.py
  registry.py
  marshal.py
  tasks/
    qc.py
    transcript_evidence.py
    protein_evidence.py
    annotation.py
    filtering.py
    functional.py
    submission.py
  workflows/
    rnaseq_qc_quant.py
    transcript_evidence.py
    consensus_annotation.py
    annotation_postprocess.py
    end_to_end_annotation.py
```

## Flyte Conventions

- Use Flyte v2 APIs
- Prefer `flyte.TaskEnvironment`
- Prefer `flyte.io.File` and `flyte.io.Dir`
- Keep task signatures explicit and typed
- Keep helper functions deterministic and reusable
- Return structured artifacts and lightweight summaries where possible

## Prompt-Driven System Conventions

The future prompt layer should rely on a registry of supported entities.

Catalog entries should include:

- name
- category: `task` or `workflow`
- short description
- biological stage
- inputs
- outputs
- runtime requirements
- container/HPC constraints

Ordinary user requests should be handled by:

1. parse prompt into an intent and requested endpoint
2. match that request to supported workflows
3. bind required assets and scalar parameters
4. run the selected Flyte workflow
5. summarize outputs in a stable manifest

## Pipeline-Specific Task Families

### Transcript evidence

- de novo Trinity assembly
- STAR genome indexing and mapping
- BAM merge/sort/index
- genome-guided Trinity
- StringTie assembly
- PASA transcript preparation and PASA alignment/assembly
- TransDecoder from PASA outputs

### Protein evidence

- protein dataset staging
- Exonerate chunked alignment
- Exonerate output conversion and concatenation for EVM

### Ab initio annotation

- BRAKER3 execution
- normalization of BRAKER3 outputs for EVM

### Consensus annotation and refinement

- EVM input construction
- EVM partitioning, command generation, execution, and recombination
- PASA gene model update rounds

### Repeat filtering and cleanup

- RepeatMasker output conversion
- GFF-to-protein extraction with `gffread`
- funannotate overlap-based repeat filtering
- funannotate repeat blast filtering
- final repeat-free GFF3 and protein FASTA creation

### Functional annotation and QC

- BUSCO runs across one or more lineages
- EggNOG-mapper annotation
- transcript-to-gene mapping generation
- annotation-name propagation into gene features
- AGAT statistics and format conversion

### Submission preparation

- CDS product propagation for NCBI
- GFF cleanup for `table2asn`
- `table2asn` packaging

## Validation Expectations

Before considering a task or workflow complete:

- Python should compile cleanly
- task inputs and outputs should be documented
- the workflow should state where it sits in the larger annotation graph
- README usage examples should match code
- result directories should contain predictable artifacts
- local execution path and HPC/container path should both be considered

## Good Near-Term Milestones

1. Split the current single file into `tasks` and `workflows` modules
2. Add a registry with transcript-evidence, protein-evidence, annotation, filtering, and QC categories
3. Implement transcript evidence workflows from the notes
4. Implement the EVM consensus workflow around `braker.gff3`, PASA, and protein evidence
5. Implement the post-processing workflows for PASA updates, TE filtering, BUSCO, and EggNOG
6. Add a prompt-to-plan layer that selects from registered workflows
7. Add an MCP server only if client/tool interoperability becomes important

## Decision Rule

When choosing between a simple deterministic design and a more autonomous agentic design:

- choose the deterministic design first
- add autonomy only where it clearly improves user outcomes without reducing reproducibility
