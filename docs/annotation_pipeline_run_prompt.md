# Full Eukaryotic Annotation Pipeline — MCP Submission Prompt

Use the flytetest MCP server. Run the full eukaryotic genome annotation pipeline
in stage order. Each stage must complete (final_scheduler_state: COMPLETED) before
submitting the next. Do a dry run for each stage first, confirm staging_findings is
empty, then submit to Slurm and monitor until completion.

All paths are absolute on RCC Midway3. Shared FS roots for every call:
  ["/scratch/midway3", "/project/rcc"]

Cluster resources for every call unless noted:
  partition: caslake
  account:   rcc-staff

---

## Stage 1 — Transcript evidence (Trinity + STAR + StringTie)

Tool: run_workflow
workflow_name: transcript_evidence_generation

inputs:
  genome: /scratch/midway3/mehta5/flyteTest/data/braker3/reference/genome.fa
  left:   /scratch/midway3/mehta5/flyteTest/data/transcriptomics/ref-based/reads_1.fq.gz
  right:  /scratch/midway3/mehta5/flyteTest/data/transcriptomics/ref-based/reads_2.fq.gz
  sample_id: demo_sample
  star_threads: 8
  trinity_cpu: 8
  trinity_max_memory_gb: 32

bindings:
  ReferenceGenome: {fasta_path: /scratch/midway3/mehta5/flyteTest/data/braker3/reference/genome.fa}
  ReadSet:
    sample_id: demo_sample
    left_reads_path: /scratch/midway3/mehta5/flyteTest/data/transcriptomics/ref-based/reads_1.fq.gz
    right_reads_path: /scratch/midway3/mehta5/flyteTest/data/transcriptomics/ref-based/reads_2.fq.gz

runtime_images:
  star_sif:      /scratch/midway3/mehta5/flyteTest/data/images/star_2.7.10b.sif
  trinity_sif:   /scratch/midway3/mehta5/flyteTest/data/images/trinity.sif
  samtools_sif:  ""   (use cluster module)

resource_request:
  cpu: 16, memory: 64Gi, walltime: 08:00:00

Save the run_record_path as TRANSCRIPT_EVIDENCE_RECORD.
The output results directory path will be needed for Stage 2 (PASA).

---

## Stage 2 — Protein evidence (Exonerate chunks)

Tool: run_workflow
workflow_name: protein_evidence_alignment

bindings:
  ReferenceGenome:
    fasta_path: /scratch/midway3/mehta5/flyteTest/data/braker3/reference/genome.fa
  ProteinEvidenceSet:
    reference_genome:
      fasta_path: /scratch/midway3/mehta5/flyteTest/data/braker3/reference/genome.fa
    protein_fasta_path: /scratch/midway3/mehta5/flyteTest/data/braker3/protein_data/fastas/proteins.fa

inputs:
  genome:              /scratch/midway3/mehta5/flyteTest/data/braker3/reference/genome.fa
  proteins_per_chunk:  100

runtime_images:
  exonerate_sif: /scratch/midway3/mehta5/flyteTest/data/images/exonerate_2.2.0--1.sif

resource_request:
  cpu: 16, memory: 64Gi, walltime: 04:00:00

Save the run_record_path as PROTEIN_EVIDENCE_RECORD.

---

## Stage 3 — BRAKER3 ab initio annotation

Tool: run_workflow
workflow_name: ab_initio_annotation_braker3

bindings:
  ReferenceGenome:
    fasta_path: /scratch/midway3/mehta5/flyteTest/data/braker3/reference/genome.fa
  TranscriptEvidenceSet:
    reference_genome:
      fasta_path: /scratch/midway3/mehta5/flyteTest/data/braker3/reference/genome.fa
  ProteinEvidenceSet:
    reference_genome:
      fasta_path: /scratch/midway3/mehta5/flyteTest/data/braker3/reference/genome.fa
    protein_fasta_path: /scratch/midway3/mehta5/flyteTest/data/braker3/protein_data/fastas/proteins.fa

inputs:
  genome:             /scratch/midway3/mehta5/flyteTest/data/braker3/reference/genome.fa
  rnaseq_bam_path:    /scratch/midway3/mehta5/flyteTest/data/braker3/rnaseq/RNAseq.bam
  braker_species:     demo_species

runtime_images:
  braker3_sif: /scratch/midway3/mehta5/flyteTest/data/images/braker3.sif

resource_request:
  cpu: 16, memory: 64Gi, walltime: 24:00:00

Save the run_record_path as BRAKER3_RECORD.

---

## Stage 4 — PASA transcript alignment and assembly

Prerequisite: Stage 1 (transcript_evidence_generation) must be COMPLETED.
Get the output results directory from TRANSCRIPT_EVIDENCE_RECORD via
inspect_run_result to find the transcript_evidence results_dir path.

Tool: run_workflow
workflow_name: pasa_transcript_alignment

inputs:
  genome:                    /scratch/midway3/mehta5/flyteTest/data/braker3/reference/genome.fa
  transcript_evidence_results: <results_dir from Stage 1 output>
  univec_fasta:              /scratch/midway3/mehta5/flyteTest/data/braker3/reference/UniVec_Core.fa
  pasa_config_template:      /scratch/midway3/mehta5/flyteTest/data/braker3/reference/pasa.alignAssembly.Template.txt
  pasa_db_name:              demo_pasa
  pasa_aligners:             gmap
  seqclean_threads:          4
  pasa_cpu:                  8

bindings:
  ReferenceGenome:
    fasta_path: /scratch/midway3/mehta5/flyteTest/data/braker3/reference/genome.fa
  TranscriptEvidenceSet:
    reference_genome:
      fasta_path: /scratch/midway3/mehta5/flyteTest/data/braker3/reference/genome.fa

runtime_images:
  pasa_sif: /scratch/midway3/mehta5/flyteTest/data/images/pasa.sif

resource_request:
  cpu: 8, memory: 32Gi, walltime: 04:00:00

Save run_record_path as PASA_ALIGN_RECORD.

---

## Stage 5 — EVM input preparation

Prerequisite: Stages 2, 3, and 4 must be COMPLETED.
Get output dirs from PROTEIN_EVIDENCE_RECORD, BRAKER3_RECORD, PASA_ALIGN_RECORD
via inspect_run_result to find their results_dir paths.

Tool: run_workflow
workflow_name: consensus_annotation_evm_prep

inputs:
  genome:                    /scratch/midway3/mehta5/flyteTest/data/braker3/reference/genome.fa
  braker3_results:           <results_dir from Stage 3 output>
  pasa_results:              <results_dir from Stage 4 output>
  protein_evidence_results:  <results_dir from Stage 2 output>

bindings:
  ReferenceGenome:
    fasta_path: /scratch/midway3/mehta5/flyteTest/data/braker3/reference/genome.fa

resource_request:
  cpu: 4, memory: 16Gi, walltime: 01:00:00

Save run_record_path as EVM_PREP_RECORD.

---

## Stage 6 — EVidenceModeler consensus annotation

Prerequisite: Stage 5 must be COMPLETED.

Tool: run_workflow
workflow_name: consensus_annotation_evm

inputs:
  genome:       /scratch/midway3/mehta5/flyteTest/data/braker3/reference/genome.fa
  evm_prep_results: <results_dir from Stage 5 output>
  segmentsize:  100000
  overlap:      10000

bindings:
  ReferenceGenome:
    fasta_path: /scratch/midway3/mehta5/flyteTest/data/braker3/reference/genome.fa

resource_request:
  cpu: 8, memory: 32Gi, walltime: 04:00:00

Save run_record_path as EVM_RECORD.

---

## Stage 7 — PASA post-EVM refinement

Prerequisite: Stages 4 and 6 must be COMPLETED.

Tool: run_workflow
workflow_name: annotation_refinement_pasa

inputs:
  genome:            /scratch/midway3/mehta5/flyteTest/data/braker3/reference/genome.fa
  evm_results:       <results_dir from Stage 6 output>
  pasa_results:      <results_dir from Stage 4 output>
  pasa_config_template: /scratch/midway3/mehta5/flyteTest/data/braker3/reference/pasa.alignAssembly.Template.txt
  pasa_db_name:      demo_pasa_refinement
  num_update_rounds: 2

bindings:
  ReferenceGenome:
    fasta_path: /scratch/midway3/mehta5/flyteTest/data/braker3/reference/genome.fa

runtime_images:
  pasa_sif: /scratch/midway3/mehta5/flyteTest/data/images/pasa.sif

resource_request:
  cpu: 8, memory: 32Gi, walltime: 04:00:00

Save run_record_path as PASA_REFINE_RECORD.

---

## Stage 8 — AGAT post-processing + repeat filtering

Prerequisite: Stage 7 must be COMPLETED.

Tool: run_workflow
workflow_name: annotation_postprocess_agat

inputs:
  annotation_gff3: <GFF3 output path from Stage 7>
  genome:          /scratch/midway3/mehta5/flyteTest/data/braker3/reference/genome.fa

runtime_images:
  agat_sif: /scratch/midway3/mehta5/flyteTest/data/images/agat.sif

resource_request:
  cpu: 4, memory: 16Gi, walltime: 01:00:00

Save run_record_path as AGAT_RECORD.

---

## Stage 9 — BUSCO quality assessment

Prerequisite: Stage 8 must be COMPLETED.

Tool: run_workflow
workflow_name: annotation_qc_busco

inputs:
  proteins_fasta: <protein FASTA output from Stage 8>
  lineage:        eukaryota_odb10
  busco_mode:     proteins

runtime_images:
  busco_sif: /scratch/midway3/mehta5/flyteTest/data/images/busco.sif

resource_request:
  cpu: 8, memory: 32Gi, walltime: 02:00:00

Save run_record_path as BUSCO_RECORD.

---

## Stage 10 — EggNOG functional annotation

Prerequisite: Stage 8 must be COMPLETED.

Tool: run_workflow
workflow_name: annotation_functional_eggnog

inputs:
  proteins_fasta:   <protein FASTA output from Stage 8>
  annotation_gff3:  <GFF3 output from Stage 8>
  eggnog_db_dir:    /scratch/midway3/mehta5/flyteTest/data/eggnog/

tool_databases:
  eggnog_db: /scratch/midway3/mehta5/flyteTest/data/eggnog/eggnog.db

runtime_images:
  eggnog_sif: /scratch/midway3/mehta5/flyteTest/data/images/eggnog-mapper.sif

resource_request:
  cpu: 16, memory: 64Gi, walltime: 08:00:00

Save run_record_path as EGGNOG_RECORD.

---

## Stage 11 — table2asn (NCBI submission format)

Prerequisite: Stage 10 must be COMPLETED.

Tool: run_workflow
workflow_name: annotation_postprocess_table2asn

inputs:
  annotated_gff3: <annotated GFF3 from Stage 10>
  genome:         /scratch/midway3/mehta5/flyteTest/data/braker3/reference/genome.fa
  locus_tag:      DEMO

resource_request:
  cpu: 4, memory: 16Gi, walltime: 01:00:00

---

## Instructions for the agent

1. Work through stages 1–11 in order.
2. For each stage:
   a. Call run_workflow with dry_run=True
   b. Confirm supported=True and staging_findings=[] before proceeding
   c. Call run_slurm_recipe with the artifact_path
   d. Poll monitor_slurm_job until final_scheduler_state=COMPLETED
   e. Call inspect_run_result on the run_record_path to get output paths for the next stage
3. If a stage fails, report the stderr_tail from monitor_slurm_job and stop.
4. Do not submit the next stage until the current one is COMPLETED.
5. Record every job_id and run_record_path in your response as you go.
