# MCP Full Annotation Pipeline Prompt Tests

End-to-end prompt scenarios for running the complete BRAKER3/EVM annotation
pipeline on RCC through the FLyteTest MCP server.  Each scenario is a prompt
you paste into OpenCode (or any MCP client connected to the server).

These scenarios follow the biological order defined in
`docs/braker3_evm_notes.md` and exercise each stage sequentially.  Run them
in order — each stage consumes the result bundle of the previous one.

At any point, call `get_pipeline_status` (Stage 0) to see a live progress
checklist of all 15 stages without querying Slurm.

---

## Prerequisites

Before starting:

- MCP server running inside an authenticated RCC login session (CILogon 2FA
  done — `sbatch` works from this shell).
- All pipeline images present under `data/images/`
  (run `scripts/rcc/download_minimal_images.sh` if any are missing).
- A real dataset staged:
  - Assembled genome FASTA (softmasked or unmasked)
  - RNA-seq BAM aligned to the genome
  - Protein evidence FASTA (e.g. OrthoDB proteins for the taxon)
- RepeatMasker library staged and bind-mount path known.
- eggNOG database staged and bind-mount path known.
- See `CHANGELOG.md` Open TODOs for AUGUSTUS_CONFIG_PATH, RepeatMasker library,
  eggNOG database, and EVM 2.x flag confirmation before first run.

Check server connectivity first:

```text
Use the flytetest MCP server and call list_entries.

Print the name and supported_execution_profiles for every entry.
```

---

## Stage 0 — Check pipeline status

Call `get_pipeline_status` at any time to see which of the 15 annotation
pipeline stages have completed.  Run it before starting Stage 1 and after each
stage to confirm progress before moving to the next one.

```text
Use the flytetest MCP server and call get_pipeline_status.

Print the summary (total, completed, failed, running, pending, percent_complete,
next_pending_stage) and the status of every stage.
```

**Pass criteria:**
- Returns a `stages` list with 15 entries.
- `summary.completed` reflects the number of completed stages.
- `summary.next_pending_stage` names the next stage to submit.
- `summary.has_failures` is `false` before proceeding to the next stage.

---

## Stage 1 — Transcript evidence generation

**Goal:** Generate transcript evidence from RNA-seq reads using Trinity, STAR,
and StringTie.

**Estimated time:** 1–4 hours depending on genome size.

```text
Use the flytetest MCP server.

Call prepare_run_recipe with exactly these arguments:
- prompt: "Generate transcript evidence from RNA-seq reads for genome annotation."
- runtime_bindings: {
    "genome": "/path/to/genome.fa",
    "left_reads": "/path/to/reads_R1.fastq.gz",
    "right_reads": "/path/to/reads_R2.fastq.gz",
    "star_sif": "data/images/star_2.7.10b.sif",
    "trinity_sif": "data/images/trinity_2.13.2.sif",
    "stringtie_sif": "data/images/stringtie_2.2.3.sif"
  }
- resource_request: {"cpu": 16, "memory": "64Gi", "partition": "caslake", "account": "rcc-staff", "walltime": "04:00:00"}
- execution_profile: "slurm"

Print artifact_path, supported, and limitations.
```

**Pass criteria:** `supported: true`, `artifact_path` ends in `.json`.

Submit and monitor using the artifact_path (see Scenario 2 in
`mcp_cluster_prompt_tests.md` for the submit/monitor pattern).

---

## Stage 2 — PASA transcript alignment and assembly

**Goal:** Align and assemble transcripts with PASA.

**Prerequisite:** Stage 1 result bundle.

**Estimated time:** 1–3 hours.

```text
Use the flytetest MCP server.

Call prepare_run_recipe with exactly these arguments:
- prompt: "Run PASA transcript alignment and assembly for genome annotation."
- runtime_bindings: {
    "genome": "/path/to/genome.fa",
    "transcript_evidence_results": "/path/to/results/transcript_evidence_results_TIMESTAMP",
    "pasa_sif": "data/images/pasa_2.5.3.sif"
  }
- resource_request: {"cpu": 8, "memory": "32Gi", "partition": "caslake", "account": "rcc-staff", "walltime": "03:00:00"}
- execution_profile: "slurm"

Print artifact_path, supported, and limitations.
```

---

## Stage 3 — TransDecoder coding prediction

**Goal:** Predict coding regions from PASA assemblies using TransDecoder.

**Prerequisite:** Stage 2 result bundle.

**Estimated time:** 30–60 minutes.

```text
Use the flytetest MCP server.

Call prepare_run_recipe with exactly these arguments:
- prompt: "Run TransDecoder coding prediction from PASA assemblies."
- runtime_bindings: {
    "pasa_results": "/path/to/results/pasa_results_TIMESTAMP",
    "transdecoder_sif": "data/images/transdecoder_6.0.0.sif"
  }
- resource_request: {"cpu": 8, "memory": "32Gi", "partition": "caslake", "account": "rcc-staff", "walltime": "01:00:00"}
- execution_profile: "slurm"

Print artifact_path, supported, and limitations.
```

---

## Stage 4 — Protein evidence alignment

**Goal:** Align protein evidence to the genome with Exonerate.

**Prerequisite:** Genome FASTA and protein evidence FASTA.

**Estimated time:** 1–4 hours depending on protein set size.

```text
Use the flytetest MCP server.

Call prepare_run_recipe with exactly these arguments:
- prompt: "Align protein evidence to the genome for EVM input."
- runtime_bindings: {
    "genome": "/path/to/genome.fa",
    "protein_fastas": "/path/to/proteins.fa",
    "exonerate_sif": "data/images/exonerate_2.2.0--1.sif"
  }
- resource_request: {"cpu": 16, "memory": "64Gi", "partition": "caslake", "account": "rcc-staff", "walltime": "04:00:00"}
- execution_profile: "slurm"

Print artifact_path, supported, and limitations.
```

---

## Stage 5 — BRAKER3 ab initio prediction

**Goal:** Run BRAKER3 ab initio gene prediction using RNA-seq and protein
evidence.

**Prerequisite:** Genome FASTA, RNA-seq BAM, protein FASTA.

**Estimated time:** 2–8 hours.

**Note:** Check the AUGUSTUS_CONFIG_PATH TODO in `CHANGELOG.md` before
running.  `.runtime/augustus_config/` may need to be staged and
`AUGUSTUS_CONFIG_PATH` set explicitly.

```text
Use the flytetest MCP server.

Call prepare_run_recipe with exactly these arguments:
- prompt: "Run BRAKER3 ab initio gene prediction for genome annotation."
- runtime_bindings: {
    "genome": "/path/to/genome.fa",
    "rnaseq_bam_path": "/path/to/rnaseq_sorted.bam",
    "protein_fasta_path": "/path/to/proteins.fa",
    "braker3_sif": "data/images/braker3.sif"
  }
- resource_request: {"cpu": 16, "memory": "64Gi", "partition": "caslake", "account": "rcc-staff", "walltime": "08:00:00"}
- execution_profile: "slurm"

Print artifact_path, supported, and limitations.
```

**Pass criteria:** Result bundle contains `braker.gff3`.

---

## Stage 6 — EVM input preparation

**Goal:** Assemble `transcripts.gff3`, `predictions.gff3`, and `proteins.gff3`
for EVidenceModeler.

**Prerequisites:** Stage 2 (PASA), Stage 3 (TransDecoder), Stage 4 (protein
evidence), Stage 5 (BRAKER3) result bundles.

**Estimated time:** 15–30 minutes.

```text
Use the flytetest MCP server.

Call prepare_run_recipe with exactly these arguments:
- prompt: "Prepare EVM input files from PASA, TransDecoder, protein evidence, and BRAKER3 results."
- runtime_bindings: {
    "pasa_results": "/path/to/results/pasa_results_TIMESTAMP",
    "transdecoder_results": "/path/to/results/transdecoder_results_TIMESTAMP",
    "protein_evidence_results": "/path/to/results/protein_evidence_results_TIMESTAMP",
    "braker3_results": "/path/to/results/braker3_results_TIMESTAMP"
  }
- resource_request: {"cpu": 4, "memory": "16Gi", "partition": "caslake", "account": "rcc-staff", "walltime": "00:30:00"}
- execution_profile: "slurm"

Print artifact_path, supported, and limitations.
```

---

## Stage 7 — EVidenceModeler consensus annotation

**Goal:** Run EVM to produce a consensus gene model from all evidence sources.

**Prerequisite:** Stage 6 result bundle.

**Estimated time:** 1–3 hours.

**Note:** Check the EVM 2.x flag TODO in `CHANGELOG.md` — this image uses the
Python CLI, not the Perl 1.x scripts.

```text
Use the flytetest MCP server.

Call prepare_run_recipe with exactly these arguments:
- prompt: "Run EVidenceModeler consensus annotation."
- runtime_bindings: {
    "evm_prep_results": "/path/to/results/evm_prep_results_TIMESTAMP",
    "evm_sif": "data/images/evidencemodeler_2.1.0.sif"
  }
- resource_request: {"cpu": 16, "memory": "64Gi", "partition": "caslake", "account": "rcc-staff", "walltime": "03:00:00"}
- execution_profile: "slurm"

Print artifact_path, supported, and limitations.
```

---

## Stage 8 — PASA post-EVM refinement

**Goal:** Refine EVM gene models using PASA annotation-update rounds.

**Prerequisites:** Stage 2 (PASA) and Stage 7 (EVM) result bundles.

**Estimated time:** 1–3 hours.

```text
Use the flytetest MCP server.

Call prepare_run_recipe with exactly these arguments:
- prompt: "Run PASA post-EVM annotation refinement."
- runtime_bindings: {
    "pasa_results": "/path/to/results/pasa_results_TIMESTAMP",
    "evm_results": "/path/to/results/evm_results_TIMESTAMP",
    "pasa_sif": "data/images/pasa_2.5.3.sif"
  }
- resource_request: {"cpu": 8, "memory": "32Gi", "partition": "caslake", "account": "rcc-staff", "walltime": "03:00:00"}
- execution_profile: "slurm"

Print artifact_path, supported, and limitations.
```

---

## Stage 9 — Repeat filtering

**Goal:** Run RepeatMasker cleanup and funannotate repeat filtering on the
post-PASA annotation.

**Prerequisites:** Stage 8 result bundle and a RepeatMasker `.out` file.

**Note:** Check the RepeatMasker library TODO in `CHANGELOG.md` — the library
path must be confirmed and bind-mounted before this stage runs.

```text
Use the flytetest MCP server.

Call prepare_run_recipe with exactly these arguments:
- prompt: "Run repeat filtering on the post-PASA annotation."
- runtime_bindings: {
    "pasa_refinement_results": "/path/to/results/pasa_refinement_results_TIMESTAMP",
    "repeatmasker_out": "/path/to/repeatmasker.out",
    "repeat_filter_sif": "data/images/repeatmasker_4.2.3.sif"
  }
- resource_request: {"cpu": 8, "memory": "32Gi", "partition": "caslake", "account": "rcc-staff", "walltime": "02:00:00"}
- execution_profile: "slurm"

Print artifact_path, supported, and limitations.
```

---

## Stage 10 — BUSCO QC

**Goal:** Assess annotation completeness against a BUSCO lineage dataset.

**Prerequisite:** Stage 9 result bundle.

**Estimated time:** 15–60 minutes.

```text
Use the flytetest MCP server.

Call prepare_run_recipe with exactly these arguments:
- prompt: "Run BUSCO QC on repeat-filtered proteins."
- runtime_bindings: {
    "repeat_filter_results": "/path/to/results/repeat_filter_results_TIMESTAMP",
    "lineage_dataset": "auto-lineage",
    "busco_cpu": 16,
    "busco_mode": "prot",
    "busco_sif": "data/images/busco_v6.0.0_cv1.sif"
  }
- resource_request: {"cpu": 16, "memory": "32Gi", "partition": "caslake", "account": "rcc-staff", "walltime": "01:00:00"}
- execution_profile: "slurm"

Print artifact_path, supported, and limitations.
```

**Pass criteria:** BUSCO completeness > 90% for a well-assembled genome.

---

## Stage 11 — EggNOG functional annotation

**Goal:** Assign functional annotations using eggNOG-mapper.

**Prerequisite:** Stage 9 result bundle.

**Note:** Check the eggNOG database TODO in `CHANGELOG.md` — the ~50 GB
database must be staged and the bind-mount path confirmed before this runs.

```text
Use the flytetest MCP server.

Call prepare_run_recipe with exactly these arguments:
- prompt: "Run EggNOG functional annotation on repeat-filtered proteins."
- runtime_bindings: {
    "repeat_filter_results": "/path/to/results/repeat_filter_results_TIMESTAMP",
    "eggnog_data_dir": "/path/to/eggnog_data",
    "eggnog_database": "auto",
    "eggnog_cpu": 16,
    "eggnog_sif": "data/images/eggnog_mapper_2.1.13.sif"
  }
- resource_request: {"cpu": 16, "memory": "64Gi", "partition": "caslake", "account": "rcc-staff", "walltime": "04:00:00"}
- execution_profile: "slurm"

Print artifact_path, supported, and limitations.
```

**Pass criteria:** > 60% of genes receive a functional assignment.

---

## Stage 12 — AGAT statistics

**Goal:** Generate GFF3 statistics on the EggNOG-annotated output.

**Prerequisite:** Stage 11 result bundle.

**Estimated time:** 5–15 minutes.

```text
Use the flytetest MCP server.

Call prepare_run_recipe with exactly these arguments:
- prompt: "Run AGAT statistics on the EggNOG-annotated GFF3."
- runtime_bindings: {
    "eggnog_results": "/path/to/results/eggnog_results_TIMESTAMP",
    "annotation_fasta_path": "/path/to/genome.fa",
    "agat_sif": "data/images/agat_1.7.0.sif"
  }
- resource_request: {"cpu": 4, "memory": "16Gi", "partition": "caslake", "account": "rcc-staff", "walltime": "00:30:00"}
- execution_profile: "slurm"

Print artifact_path, supported, and limitations.
```

---

## Stage 13 — AGAT conversion

**Goal:** Convert the annotated GFF3 to a standardised format.

**Prerequisite:** Stage 11 result bundle.

```text
Use the flytetest MCP server.

Call prepare_run_recipe with exactly these arguments:
- prompt: "Run AGAT conversion on the EggNOG-annotated GFF3."
- runtime_bindings: {
    "eggnog_results": "/path/to/results/eggnog_results_TIMESTAMP",
    "agat_sif": "data/images/agat_1.7.0.sif"
  }
- resource_request: {"cpu": 4, "memory": "16Gi", "partition": "caslake", "account": "rcc-staff", "walltime": "00:30:00"}
- execution_profile: "slurm"

Print artifact_path, supported, and limitations.
```

---

## Stage 14 — AGAT cleanup

**Goal:** Run final AGAT cleanup on the converted GFF3.

**Prerequisite:** Stage 13 result bundle.

```text
Use the flytetest MCP server.

Call prepare_run_recipe with exactly these arguments:
- prompt: "Run AGAT cleanup on the converted GFF3."
- runtime_bindings: {
    "agat_conversion_results": "/path/to/results/agat_conversion_results_TIMESTAMP",
    "agat_sif": "data/images/agat_1.7.0.sif"
  }
- resource_request: {"cpu": 4, "memory": "16Gi", "partition": "caslake", "account": "rcc-staff", "walltime": "00:30:00"}
- execution_profile: "slurm"

Print artifact_path, supported, and limitations.
```

---

## Stage 15 — table2asn NCBI submission preparation

**Goal:** Prepare the final annotation for NCBI submission using table2asn.

**Prerequisite:** Stage 14 result bundle, genome FASTA, and a submission
template file.

```text
Use the flytetest MCP server.

Call prepare_run_recipe with exactly these arguments:
- prompt: "Prepare NCBI submission package using table2asn."
- runtime_bindings: {
    "agat_cleanup_results": "/path/to/results/agat_cleanup_results_TIMESTAMP",
    "genome_fasta": "/path/to/genome.fa",
    "submission_template": "/path/to/template.sbt"
  }
- resource_request: {"cpu": 4, "memory": "16Gi", "partition": "caslake", "account": "rcc-staff", "walltime": "00:30:00"}
- execution_profile: "slurm"

Print artifact_path, supported, and limitations.
```

**Pass criteria:** Result bundle contains `.sqn` submission files.

---

## Pipeline Summary

| Stage | Workflow | Key input | Key output |
|---|---|---|---|
| 1 | `transcript_evidence_generation` | Genome + RNA-seq reads | Transcript evidence bundle |
| 2 | `pasa_transcript_alignment` | Transcript evidence | PASA assemblies |
| 3 | `transdecoder_from_pasa` | PASA assemblies | TransDecoder genome GFF3 |
| 4 | `protein_evidence_alignment` | Genome + protein FASTA | Exonerate GFF3 |
| 5 | `ab_initio_annotation_braker3` | Genome + BAM + proteins | `braker.gff3` |
| 6 | `consensus_annotation_evm_prep` | PASA + TransDecoder + proteins + BRAKER3 | EVM input bundle |
| 7 | `consensus_annotation_evm` | EVM input bundle | EVM consensus GFF3 |
| 8 | `annotation_refinement_pasa` | PASA + EVM results | Refined GFF3 |
| 9 | `annotation_repeat_filtering` | Refined GFF3 + RepeatMasker `.out` | Filtered proteins |
| 10 | `annotation_qc_busco` | Filtered proteins | BUSCO completeness report |
| 11 | `annotation_functional_eggnog` | Filtered proteins | Annotated GFF3 |
| 12 | `annotation_postprocess_agat` | Annotated GFF3 | GFF3 statistics |
| 13 | `annotation_postprocess_agat_conversion` | Annotated GFF3 | Converted GFF3 |
| 14 | `annotation_postprocess_agat_cleanup` | Converted GFF3 | Cleaned GFF3 |
| 15 | `annotation_postprocess_table2asn` | Cleaned GFF3 + genome | `.sqn` submission files |

**Before first real run, resolve the open TODOs in `CHANGELOG.md`:**
AUGUSTUS_CONFIG_PATH, RepeatMasker library, eggNOG database, EVM 2.x flags.