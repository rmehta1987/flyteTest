# Full Eukaryotic Annotation Pipeline — Natural Language Prompt

Paste the block below directly into an MCP-connected agent session (Codex, OpenCode, etc.).
The agent will run all 11 stages in order, dry-running each one, waiting for your confirmation
of staging findings, submitting to Slurm, and monitoring until completion before moving on.

---

Use the flytetest MCP server to run the full eukaryotic genome annotation pipeline on the
small demo fixture on RCC Midway3. Work through the stages below in order. For each stage:
dry-run first, show me the staging_findings, wait for my go-ahead, then submit and monitor
until the job reaches final_scheduler_state COMPLETED before starting the next stage. All
paths are absolute on Midway3 under /scratch/midway3/mehta5/flyteTest/. Use partition
caslake and account rcc-staff for every Slurm job unless I say otherwise.

---

Stage 1 — Transcript evidence. Call vc_germline_discovery — wait, wrong family. Call the
transcript evidence workflow using the paired RNA-seq reads at
data/transcriptomics/ref-based/reads_1.fq.gz and reads_2.fq.gz against the reference genome
at data/braker3/reference/genome.fa. Sample ID is demo_sample. Use 16 CPUs, 64Gi memory,
8-hour walltime. No container SIFs needed for STAR or Trinity unless you find them at
data/images/ — use empty strings if absent and rely on cluster modules.

Stage 2 — Protein evidence alignment. Call annotation_protein_evidence with the reference
genome at data/braker3/reference/genome.fa and the protein FASTA at
data/braker3/protein_data/fastas/proteins.fa. Use the Exonerate SIF at
data/images/exonerate_2.2.0--1.sif, 100 proteins per chunk, 16 CPUs, 64Gi, 4-hour walltime.

Stage 3 — BRAKER3 ab initio annotation. Call annotation_braker3 with the reference genome at
data/braker3/reference/genome.fa, the RNA-seq BAM at data/braker3/rnaseq/RNAseq.bam as
rnaseq_bam_path, the protein FASTA at data/braker3/protein_data/fastas/proteins.fa as
protein_fasta_path, species name demo_species, and the BRAKER3 SIF at
data/images/braker3.sif. Use 16 CPUs, 64Gi, 24-hour walltime.

Stage 4 — PASA transcript alignment and assembly. Run the pasa_transcript_alignment workflow.
The genome is data/braker3/reference/genome.fa. The transcript_evidence_results directory
comes from the Stage 1 output — get it from inspect_run_result on the Stage 1 run record.
The PASA align template is at data/pasa/pasa.alignAssembly.Template.txt. Use gmap as the
aligner, demo_pasa as the database name, the PASA SIF at data/images/pasa.sif, 8 CPUs,
32Gi, 4-hour walltime.

Stage 5 — EVM input preparation. Run consensus_annotation_evm_prep. The genome is
data/braker3/reference/genome.fa. Get the braker3_results, pasa_results, and
protein_evidence_results directories from inspect_run_result on the Stage 3, 4, and 2 run
records respectively. Use 4 CPUs, 16Gi, 1-hour walltime.

Stage 6 — EVidenceModeler consensus annotation. Run consensus_annotation_evm. The genome
is data/braker3/reference/genome.fa. Get the evm_prep_results directory from the Stage 5
run record. Use segmentsize 100000, overlap 10000, 8 CPUs, 32Gi, 4-hour walltime.

Stage 7 — PASA post-EVM refinement. Run annotation_refinement_pasa. The genome is
data/braker3/reference/genome.fa. Get the evm_results from Stage 6 and pasa_results from
Stage 4 via inspect_run_result. The annotation compare template is at
data/pasa/pasa.annotationCompare.Template.txt. Use demo_pasa_refinement as the database
name, 2 update rounds, the PASA SIF at data/images/pasa.sif, 8 CPUs, 32Gi, 4-hour walltime.

Stage 8 — AGAT post-processing. Run annotation_postprocess_agat. Get the annotation GFF3
output path from the Stage 7 run record. Genome is data/braker3/reference/genome.fa. Use
the AGAT SIF at data/images/agat.sif if it exists, 4 CPUs, 16Gi, 1-hour walltime.

Stage 9 — BUSCO quality assessment. Call annotation_busco_qc with the protein FASTA output
from Stage 8, lineage eukaryota_odb10, mode proteins, and the BUSCO SIF at
data/images/busco.sif. Use 8 CPUs, 32Gi, 2-hour walltime.

Stage 10 — EggNOG functional annotation. Call annotation_eggnog with the protein FASTA and
annotated GFF3 from Stage 8. The EggNOG database is at data/eggnog/. Use the EggNOG SIF at
data/images/eggnog-mapper.sif if it exists, 16 CPUs, 64Gi, 8-hour walltime.

Stage 11 — NCBI submission format. Call annotation_table2asn with the annotated GFF3 from
Stage 10, genome data/braker3/reference/genome.fa, locus tag DEMO. Use 4 CPUs, 16Gi,
1-hour walltime.

After each stage completes, tell me the job ID, run record path, and the key output path
before moving on. If any stage fails, show me the stderr tail and stop.
