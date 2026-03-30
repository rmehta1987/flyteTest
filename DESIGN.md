# FLyteTest Design Specification

## 1. Purpose

This project began as a small Flyte v2 RNA-seq workflow that:

- runs FastQC
- builds a Salmon index
- quantifies transcript abundance with Salmon

The updated target system is broader and is now grounded in the attached `Braker3 + Evidence Modeler Annotation Notes.docx.pdf`.
The end goal is a prompt-driven genome annotation platform in which users can request analyses in natural language and the system executes supported Flyte workflows without modifying source code.

The target platform should cover the full path from RNA-seq evidence generation to consensus genome annotation, post-processing, QC, and submission preparation.

## 2. Design Philosophy

### 2.1 Static code, dynamic composition

Users should not need code changes for ordinary analysis requests.
Instead of generating new Python at runtime, the system should:

1. interpret the user prompt
2. choose from supported tasks and workflows
3. bind typed inputs and parameters
4. execute the selected workflow

This keeps execution reproducible and reviewable.

### 2.2 Model the real pipeline, not a simplified fantasy

The attached notes describe a long multi-stage annotation pipeline with transcript evidence, protein evidence, consensus modeling, PASA updates, repeat filtering, functional annotation, and NCBI preparation.

The design of this repo should reflect those real stages.

### 2.3 Be explicit about inferred steps

The notes clearly use `braker.gff3` as an ab initio input to EVM, but the extracted text does not document the exact BRAKER3 command sequence.

Therefore:

- BRAKER3 should be treated as a required task family and upstream evidence source
- its invocation details should be documented as inferred until a fuller protocol is added

### 2.4 Separate planning from execution

Prompt interpretation should produce a structured analysis plan.
Flyte should execute a pre-registered workflow chosen from that plan.

## 3. Goals

- Build a modular Flyte v2 task library representing the actual annotation pipeline stages in the notes
- Support workflows from RNA-seq evidence generation through BRAKER3/EVM consensus and downstream curation
- Expose a stable prompt-to-plan interface
- Preserve support for both local development and HPC/containerized execution
- Keep outputs predictable and machine-readable

## 4. Non-Goals

- arbitrary runtime generation of new task code for end users
- free-form autonomous rewriting of the workflow graph during ordinary execution
- hiding external evidence or post-processing assumptions behind one opaque task
- inventing undocumented BRAKER3 substeps and presenting them as if they were stated in the notes

## 5. Pipeline Summary From The Attached Notes

The extracted notes describe the following logical stages:

1. directory and input setup
2. Trinity de novo transcriptome assembly
3. STAR genome index generation
4. STAR RNA-seq alignment per sample
5. BAM merge for transcriptome support
6. Trinity genome-guided assembly
7. StringTie transcript assembly and quantification
8. PASA transcript preparation and PASA align/assemble run
9. TransDecoder coding prediction from PASA assemblies
10. protein evidence alignment with Exonerate against UniProt and RefSeq
11. BRAKER3 ab initio predictions producing `braker.gff3`
12. EVidenceModeler consensus annotation
13. PASA update rounds to add UTRs and alternative transcripts
14. repeat filtering using RepeatMasker output and funannotate utilities
15. BUSCO assessment of predicted proteins
16. EggNOG functional annotation and name propagation into GFF3
17. AGAT statistics and format conversions
18. optional NCBI submission preparation with `table2asn`

## 6. Task Families

### 6.1 Setup and staging

Expected tasks:

- `stage_reference_genome`
- `stage_rnaseq_reads`
- `stage_protein_databases`
- `initialize_annotation_workspace`

The notes assume a directory structure with categories such as:

- `reference/`
- `transcript_data/fastqs/`
- `transcript_data/bams/`
- `transcript_data/stringtie/`
- `transcript_data/trinity_denovo/`
- `transcript_data/trinity_gg/`
- `transcript_data/pasa/`
- `protein_data/uniprot_results/`
- `protein_data/refseq_results/`
- `braker/`

Flyte should not depend on this exact on-disk layout, but these stage boundaries are still useful for workflow design.

### 6.2 Transcript evidence generation

Expected tasks:

- `trinity_denovo_assemble`
- `star_genome_index`
- `star_align_sample`
- `samtools_merge_bams`
- `trinity_genome_guided_assemble`
- `stringtie_assemble`

Outputs from this family include:

- de novo Trinity transcript FASTA
- genome-guided Trinity FASTA
- merged BAM
- StringTie GTF and abundance summary

### 6.3 PASA preparation and transcript alignment

Expected tasks:

- `pasa_accession_extract`
- `combine_trinity_fastas`
- `pasa_seqclean`
- `pasa_create_sqlite_db`
- `pasa_align_assemble`

The notes emphasize that PASA has real external dependencies:

- SQLite or MySQL
- samtools
- BioPerl
- minimap2
- BLAT
- gmap

These requirements should be represented explicitly in task metadata and runtime docs.

### 6.4 Coding prediction from transcript evidence

Expected tasks:

- `transdecoder_train_from_pasa`

The notes specifically describe generating:

- `${db}.assemblies.fasta.transdecoder.genome.gff3`

This file is later merged with BRAKER predictions for EVM input.

### 6.5 Protein evidence generation

Expected tasks:

- `fetch_uniprot_proteins`
- `fetch_refseq_proteins`
- `exonerate_align_chunk`
- `exonerate_convert_to_evm_gff3`
- `exonerate_concat_results`

Important pattern from the notes:

- Exonerate is chunked across many jobs
- both raw Exonerate outputs and EVM-compatible converted outputs are needed

### 6.6 Ab initio annotation

Expected tasks:

- `braker3_predict`
- `normalize_braker3_for_evm`

Important note:

- the extracted notes do not describe the exact BRAKER3 command line
- however, they clearly assume a `braker.gff3` output that feeds into EVM as an ab initio prediction source

### 6.7 Consensus annotation with EVidenceModeler

Expected tasks:

- `evm_prepare_predictions_gff3`
- `evm_prepare_proteins_gff3`
- `evm_prepare_transcripts_gff3`
- `evm_partition_inputs`
- `evm_write_commands`
- `evm_execute_partitions`
- `evm_recombine_outputs`
- `evm_convert_and_sort_gff3`

The notes describe EVM source weighting with categories such as:

- `ABINITIO_PREDICTION`
- `PROTEIN`
- `TRANSCRIPT`
- `OTHER_PREDICTION`

That weighting scheme should become a configurable workflow input rather than being hardcoded forever.

### 6.8 PASA-based gene model update

Expected tasks:

- `pasa_load_current_annotations`
- `pasa_update_gene_models_round`
- `pasa_sort_updated_gff3`

Important behavior from the notes:

- at least two PASA update rounds may be required
- the second round loads the first updated GFF3 rather than the original EVM file

### 6.9 Repeat and TE filtering

Expected tasks:

- `repeatmasker_out_to_gff3`
- `repeatmasker_gff3_to_bed`
- `gffread_extract_proteins`
- `sanitize_protein_fasta_for_diamond`
- `funannotate_remove_bad_models_overlap`
- `remove_repeat_overlap_features_from_gff3`
- `funannotate_repeat_blast`
- `reformat_repeat_blast_hits`
- `remove_repeat_blast_features_from_gff3`

This family is important because the notes use two distinct repeat-removal passes:

1. overlap with RepeatMasker-derived BED regions
2. blast-based matching to funannotate repeat databases

### 6.10 QC and functional annotation

Expected tasks:

- `busco_assess_proteins`
- `eggnog_download_databases`
- `eggnog_map`
- `make_tx2gene_table`
- `add_eggnog_names_to_gff3`
- `agat_statistics`
- `agat_convert_gxf`

Important behavior from the notes:

- BUSCO is intended to run against several lineages
- EggNOG annotations need additional rewriting because transcript-level names are not sufficient for downstream gene feature handling

### 6.11 Submission preparation

Expected tasks:

- `propagate_mrna_name_to_cds_product`
- `cleanup_gff3_for_ncbi`
- `table2asn_package`
- `stage_ncbi_upload_bundle`

These steps should be optional and belong to a submission-prep workflow, not the core biological annotation workflow.

## 7. Candidate Workflows

### 7.1 Existing baseline

- `rnaseq_qc_quant`

### 7.2 Transcript evidence workflows

- `transcript_evidence_generation`
  - Trinity de novo
  - STAR index
  - STAR alignment
  - BAM merge
  - Trinity genome-guided
  - StringTie

- `pasa_transcript_alignment`
  - PASA accession extraction
  - transcript combination
  - seqclean
  - PASA align/assemble

### 7.3 Protein evidence workflows

- `protein_evidence_alignment_uniprot`
- `protein_evidence_alignment_refseq`
- `protein_evidence_alignment_combined`

### 7.4 Annotation workflows

- `abinitio_annotation_braker3`
- `consensus_annotation_evm`
- `annotation_refinement_pasa`

### 7.5 Post-processing workflows

- `annotation_repeat_filtering`
- `annotation_functional_qc`
- `annotation_submission_prep`

### 7.6 End-to-end workflows

- `end_to_end_genome_annotation`
  - transcript evidence generation
  - PASA transcript alignment
  - protein evidence alignment
  - BRAKER3
  - EVM consensus
  - PASA updates
  - repeat filtering
  - BUSCO and EggNOG

- `end_to_end_genome_annotation_with_submission_prep`
  - everything above
  - AGAT summary
  - NCBI packaging

## 8. Domain Inputs

The system should support typed inputs for:

- paired-end RNA-seq reads
- optional single-end RNA-seq reads
- reference genome FASTA
- optional repeat-masked genome FASTA
- STAR genome index directory
- protein FASTA collections from UniProt and RefSeq
- PASA config files or equivalents
- BRAKER3 outputs
- RepeatMasker `.out` file
- lineage identifiers for BUSCO
- EggNOG database scope
- NCBI template files for submission prep

Each task and workflow should declare exactly which of these it expects.

## 9. Architecture Overview

The preferred architecture is:

```text
User prompt
  -> prompt interpreter / planner
    -> workflow catalog + task catalog
      -> selected Flyte workflow
        -> Flyte tasks
          -> local or HPC/container execution
            -> structured outputs and manifests
```

The prompt layer should choose from supported workflows, not mutate code.

## 10. Planning Layer

The planning layer should convert free text into a structured request.

Example:

```json
{
  "goal": "consensus_annotation",
  "workflow": "end_to_end_genome_annotation",
  "inputs": {
    "genome_fasta": "/path/to/genome.fa",
    "reads_1": "/path/to/reads_1.fq.gz",
    "reads_2": "/path/to/reads_2.fq.gz",
    "uniprot_fasta": "/path/to/uniprot.fa",
    "refseq_fasta": "/path/to/refseq.fa"
  },
  "options": {
    "run_qc": true,
    "run_busco": true,
    "run_eggnog": true,
    "prepare_ncbi_submission": false,
    "execution_mode": "hpc"
  }
}
```

This structure should be enough to drive workflow selection without editing source.

## 11. Registry

The project should eventually expose a registry of tasks and workflows.

Each registered entity should include:

- name
- category
- description
- biological stage
- input schema
- output schema
- runtime requirements
- tags such as `transcript_evidence`, `protein_evidence`, `abinitio`, `evm`, `pasa`, `repeat_filtering`, `functional_annotation`, `submission`

This registry is the bridge between prompts and Flyte execution.

## 12. Why Registry-Driven Design Matters

If the goal is "the pipeline will do it without modifying code," then most user prompts must resolve to supported workflows rather than ad hoc code generation.

Without a registry:

- the model invents behavior
- the system becomes harder to validate
- reproducibility suffers

With a registry:

- supported capabilities are explicit
- unsupported prompts can fail honestly
- users get consistent results

## 13. Execution Model

### 13.1 Local mode

Local runs are useful for:

- development
- schema validation
- lightweight task testing
- small fixture-based examples

### 13.2 HPC mode

The attached notes strongly imply that the main annotation pipeline is HPC-first.
HPC mode is essential for:

- Trinity assemblies
- STAR alignments over many samples
- chunked Exonerate runs
- EVM partition execution
- PASA update runs
- BUSCO and EggNOG at realistic scale

Containerized execution should remain first-class.
Apptainer/Singularity support is important for cluster portability.

## 14. Result Model

Every workflow should produce:

- a structured result directory
- a machine-readable manifest
- stage-specific outputs in predictable subdirectories

For example:

```text
results/
  run_manifest.json
  qc/
  transcript_evidence/
  pasa/
  transdecoder/
  protein_evidence/
  braker/
  evm/
  annotation_refinement/
  repeat_filtering/
  functional_annotation/
  submission/
```

The manifest should record:

- workflow name
- input paths
- key intermediate products
- final annotation products
- stage completion status
- runtime metadata

## 15. Proposed Package Layout

As functionality expands, the repository should move toward:

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
    protein_evidence.py
    consensus_annotation.py
    annotation_postprocess.py
    submission.py
    end_to_end_annotation.py
```

This is preferable to growing one monolithic workflow file forever.

## 16. Prompt-Driven User Experience

Examples of target user requests:

- "Generate transcript evidence from my RNA-seq reads and genome."
- "Run BRAKER3 plus protein and transcript evidence to create a consensus annotation."
- "Update the annotation with PASA and remove TE-associated models."
- "Assess the final protein set with BUSCO and functionally annotate with EggNOG."
- "Prepare the final GFF3 and SQN bundle for NCBI submission."

The system should classify these requests into supported workflows and compose them from registered tasks.

## 17. Why Not Runtime Code Generation For Users

Generating new Flyte code for every user request would make this system:

- harder to validate
- harder to reproduce on HPC
- harder to maintain across many external tools

For developers, code generation can still help scaffold new tasks.
For end users, declarative workflow selection is the correct default.

## 18. Incremental Roadmap

### Phase 1

- keep the current RNA-seq workflow working
- split code into tasks and workflows modules
- add a registry

### Phase 2

- implement transcript evidence tasks and workflows from the notes
- add PASA preparation and TransDecoder tasks
- add protein evidence alignment tasks

### Phase 3

- implement BRAKER3 as an explicit task family
- implement EVM consensus workflows
- implement PASA update rounds and repeat filtering workflows

### Phase 4

- implement BUSCO, EggNOG, AGAT, and submission-prep workflows
- add a prompt-to-plan layer that maps user requests to registered workflows

### Phase 5

- optionally expose the registry and execution layer through MCP
- optionally add richer client-side routing if the workflow catalog grows large

## 19. Success Criteria

The architecture is successful when:

- transcript evidence, protein evidence, EVM, PASA, repeat filtering, and annotation QC are each represented explicitly
- new tasks can be added without redesigning the whole system
- workflows compose naturally from existing tasks
- most common user prompts are satisfied by selecting supported workflows
- local and HPC execution remain consistent
- outputs are structured and predictable

## 20. Immediate Next Steps

1. refactor the current code into `tasks` and `workflows`
2. define the registry schema for task and workflow discovery
3. implement transcript evidence tasks first
4. implement the EVM consensus workflow using `braker.gff3`, PASA, and Exonerate-derived evidence
5. implement repeat filtering and functional annotation workflows
6. add a simple prompt-to-plan interface that selects from registered workflows
