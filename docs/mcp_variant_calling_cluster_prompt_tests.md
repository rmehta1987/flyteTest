# MCP Variant Calling Cluster Prompt Tests

Live-cluster prompt scenarios for the FLyteTest MCP server on RCC, covering the
`variant_calling` pipeline family.  Each scenario is a prompt you paste into
OpenCode (or any MCP client connected to the server).  The client calls the
server tools over JSON-RPC; the server calls real `sbatch`, `squeue`,
`scontrol`, `sacct`, and `scancel` on the cluster.

These are the live-cluster companion to `docs/mcp_cluster_prompt_tests.md`
for the `variant_calling` family.  They cover the same lifecycle paths
(sanity check, happy path, workflow, cancel, retry, escalation) and exercise
the full transport stack (OpenCode → JSON-RPC → MCP server → Slurm).

---

## Prerequisites

Before running any scenario:

- The MCP server is started from inside an authenticated RCC login session
  (CILogon 2FA already completed — `sbatch` works from this shell).
- `sbatch`, `squeue`, `scontrol`, `sacct`, and `scancel` are on `PATH`.
- OpenCode is connected to the server (stdio transport, no remote SSH).
- GATK4 SIF image present at `data/images/gatk4.sif`
  (run `bash scripts/rcc/pull_gatk_image.sh` if missing).
- Germline fixture bundle paths resolvable on the cluster's shared filesystem:
  - Reference FASTA: `data/references/hg38/chr20.fa`
  - Known-sites VCFs: `data/references/hg38/dbsnp_138.hg38.vcf` and
    `data/references/hg38/Mills_and_1000G_gold_standard.indels.hg38.vcf`
  - Paired reads: `data/reads/NA12878_chr20_R1.fastq.gz` and
    `data/reads/NA12878_chr20_R2.fastq.gz`
  - See `src/flytetest/bundles.py` (`variant_calling_germline_minimal`) for
    the full `fetch_hints` list.
- A prior `prepare_reference` run (Scenario 3) has produced `.fai`, `.dict`,
  BWA-MEM2 index files, and per-known-site `.tbi`/`.idx` files alongside
  `chr20.fa`.  Run Scenario 3 once before Scenarios 2, 4, or 5.

Check connectivity before starting:

```text
Use the flytetest MCP server and call list_entries.

Print name and supported_execution_profiles for every entry where
pipeline_family is "variant_calling".
```

Every entry that lists `"slurm"` in `supported_execution_profiles` is
available for these tests.  You should see all eleven tasks and three
workflows from the `variant_calling` family.

---

## Scenario 1 — Sanity check: list variant_calling Slurm-capable targets

**Goal:** Confirm the server is reachable and exposes the expected variant_calling
Slurm targets before submitting any jobs.

**Estimated time:** Seconds (no job submission).

```text
Use the flytetest MCP server.

Call list_entries with:
- pipeline_family: "variant_calling"

Then print exactly:
- supported
- server_tools  (list all tool names)
- entries where supported_execution_profiles contains "slurm"  (name + slurm_resource_hints)
- limitations
```

**Pass criteria:**

- `supported` is `true`.
- `server_tools` includes `prepare_run_recipe`, `run_slurm_recipe`,
  `monitor_slurm_job`, `cancel_slurm_job`, `retry_slurm_job`,
  `list_slurm_run_history`, `run_task`, `run_workflow`, `load_bundle`.
- Slurm-capable entries include all eleven tasks:
  `create_sequence_dictionary`, `index_feature_file`, `base_recalibrator`,
  `apply_bqsr`, `haplotype_caller`, `combine_gvcfs`, `joint_call_gvcfs`,
  `bwa_mem2_index`, `bwa_mem2_mem`, `sort_sam`, `mark_duplicates`; and the
  three workflows: `prepare_reference`, `preprocess_sample`,
  `germline_short_variant_discovery`.
- Each entry's `slurm_resource_hints` contains `cpu`, `memory`, and
  `walltime`.
- `limitations` is empty or describes only scope boundaries (not errors).

---

## Scenario 2 — Happy path: load_bundle → run_task(haplotype_caller) → poll COMPLETED

**Goal:** Full submit-and-monitor cycle for a single `haplotype_caller` run
using the primary scientist loop (`load_bundle` → `run_task`).  Validates the
`final_scheduler_state` polling gate for the variant_calling family.

**Prerequisite:** Scenario 3 (`prepare_reference`) must have been completed so
that `.fai`, `.dict`, and BWA-MEM2 index files exist alongside `chr20.fa`.
A recalibrated BAM from a prior `preprocess_sample` run is also required
(see Scenario 4).

**Estimated time:** 15–45 minutes on `caslake` (chr20 NA12878 slice).

---

**Step 2a — Load the germline bundle:**

```text
Use the flytetest MCP server.

Call load_bundle with exactly this argument:
- name: "variant_calling_germline_minimal"

Then print exactly:
- supported
- bindings   (show ReferenceGenome.fasta_path, ReadPair.sample_id, KnownSites)
- inputs     (show ref_path, known_sites, r1_path, r2_path, results_dir)
- runtime_images
- tool_databases
- limitations
```

**Pass criteria for 2a:**

- `supported` is `true`.
- `bindings.ReadPair.sample_id` is `"NA12878_chr20"`.
- `runtime_images.sif_path` is `"data/images/gatk4.sif"`.
- `limitations` is empty.

---

**Step 2b — Freeze and submit `haplotype_caller`:**

Replace `<recal_bam_path>` with the `preprocessed_bam` path from a prior
`preprocess_sample` run (Scenario 4).

```text
Use the flytetest MCP server.

Call run_task with exactly these arguments:
- task_name: "haplotype_caller"
- bindings: {
    "ReferenceGenome": {"fasta_path": "data/references/hg38/chr20.fa"},
    "AlignmentSet": {"bam_path": "<recal_bam_path>", "sample_id": "NA12878_chr20"}
  }
- inputs: {"results_dir": "results/germline_minimal/haplotype_caller/"}
- resources: {"cpu": 4, "memory": "16Gi", "partition": "caslake", "account": "rcc-staff", "walltime": "01:00:00"}
- execution_profile: "slurm"
- runtime_images: {"sif_path": "data/images/gatk4.sif"}
- source_prompt: "Call germline short variants on NA12878 chr20 slice for cluster validation"

Then print exactly:
- supported
- recipe_id
- run_record_path
- execution_profile
- limitations
```

**Pass criteria for 2b:**

- `supported` is `true`.
- `recipe_id` is a non-null string in timestamp-target format
  (`<YYYYMMDDThhmmss.mmm>Z-haplotype_caller`).
- `run_record_path` is a non-null path ending in `slurm_run_record.json`.
- `execution_profile` is `"slurm"`.
- `limitations` is empty or advisory only.

---

**Step 2c — Poll until terminal:**

Repeat this prompt until `final_scheduler_state` is non-null.  Wait 60–120
seconds between calls while the job is `PENDING` or `RUNNING`.

```text
Use the flytetest MCP server.

Call monitor_slurm_job with the run_record_path from run_task.

Then print exactly:
- supported
- scheduler_state
- final_scheduler_state   (null means keep polling; non-null means stop)
- stdout_path
- stderr_path
- run_record_path
- limitations
```

**Pass criteria for 2c:**

- `supported` is `true` on every call.
- While active: `scheduler_state` is `PENDING` or `RUNNING`;
  `final_scheduler_state` is `null`.
- On completion: `final_scheduler_state` is `COMPLETED`;
  `stdout_path` and `stderr_path` are non-null paths.
- `limitations` is empty (or contains only informational notes).

**If the job fails instead of completing:** See Scenario 7 (retry) or check
`stderr_path` for the error.  A `FAILED` result with exit code `1:0` means the
GATK command itself failed — confirm the BAM has a `.bai` companion and the
reference `.dict` exists.

---

**Step 2d — Inspect the run manifest:**

```text
Use the flytetest MCP server.

Read the file results/germline_minimal/haplotype_caller/run_manifest.json
and print the full outputs dict.
```

**Pass criteria for 2d:**

- `outputs` contains key `"gvcf"` pointing at a `.g.vcf.gz` file inside
  `results/germline_minimal/haplotype_caller/`.
- A companion `.g.vcf.gz.tbi` file is present in the same directory.

---

## Scenario 3 — prepare_reference (one-time)

**Goal:** Build `.fai`, `.dict`, BWA-MEM2 index, and per-known-site `.tbi`/`.idx`
files for the chr20 fixture.  Run once per reference; companion files are reused
by all downstream tasks and workflows.

**Estimated time:** 5–15 minutes.

**Prerequisite:** GATK4 SIF (`data/images/gatk4.sif`), reference FASTA, and
known-sites VCFs staged on the shared filesystem.

---

**Step 3a — Freeze and submit `prepare_reference`:**

```text
Use the flytetest MCP server.

Call run_workflow with exactly these arguments:
- workflow_name: "prepare_reference"
- bindings: {
    "ReferenceGenome": {"fasta_path": "data/references/hg38/chr20.fa"},
    "KnownSites": [
      {"vcf_path": "data/references/hg38/dbsnp_138.hg38.vcf", "resource_name": "dbsnp"},
      {"vcf_path": "data/references/hg38/Mills_and_1000G_gold_standard.indels.hg38.vcf", "resource_name": "mills"}
    ]
  }
- inputs: {"results_dir": "results/germline_minimal/prepare_reference/"}
- resources: {"cpu": 8, "memory": "32Gi", "partition": "caslake", "account": "rcc-staff", "walltime": "00:30:00"}
- execution_profile: "slurm"
- runtime_images: {"sif_path": "data/images/gatk4.sif"}
- source_prompt: "One-time reference preparation for NA12878 chr20 germline fixture"

Then print exactly:
- supported
- recipe_id
- run_record_path
- execution_profile
- limitations
```

**Pass criteria for 3a:**

- `supported` is `true`.
- `recipe_id` non-null (timestamp-target format).
- `run_record_path` ends in `slurm_run_record.json`.
- `execution_profile` is `"slurm"`.

---

**Step 3b — Poll until terminal:**

Use the same polling prompt as Scenario 2, Step 2c with this job's
`run_record_path`.

**Pass criteria for 3b:**

- `final_scheduler_state` is `"COMPLETED"`.
- Companion files present in `data/references/hg38/`:
  `chr20.fa.fai`, `chr20.dict`, `chr20.fa.bwt.2bit.64`, `chr20.fa.0123`,
  `chr20.fa.amb`, `chr20.fa.ann`, `chr20.fa.pac`;
  `dbsnp_138.hg38.vcf.idx` or `.tbi`; same for Mills VCF.

---

**Step 3c — Inspect manifest:**

```text
Use the flytetest MCP server.

Read results/germline_minimal/prepare_reference/run_manifest.json
and print the outputs dict.
```

**Pass criteria for 3c:**

- `outputs.prepared_ref` equals `"data/references/hg38/chr20.fa"`.

---

## Scenario 4 — preprocess_sample

**Goal:** Raw paired FASTQ → coordinate-sorted, duplicate-marked, BQSR-
recalibrated BAM.

**Prerequisite:** Scenario 3 completed (reference companion files present).

**Estimated time:** 20–60 minutes.

---

**Step 4a — Freeze and submit `preprocess_sample`:**

```text
Use the flytetest MCP server.

Call run_workflow with exactly these arguments:
- workflow_name: "preprocess_sample"
- bindings: {
    "ReferenceGenome": {"fasta_path": "data/references/hg38/chr20.fa"},
    "ReadPair": {
      "sample_id": "NA12878_chr20",
      "r1_path": "data/reads/NA12878_chr20_R1.fastq.gz",
      "r2_path": "data/reads/NA12878_chr20_R2.fastq.gz"
    },
    "KnownSites": [
      {"vcf_path": "data/references/hg38/dbsnp_138.hg38.vcf", "resource_name": "dbsnp"}
    ]
  }
- inputs: {"results_dir": "results/germline_minimal/preprocess_sample/"}
- resources: {"cpu": 16, "memory": "64Gi", "partition": "caslake", "account": "rcc-staff", "walltime": "02:00:00"}
- execution_profile: "slurm"
- runtime_images: {"sif_path": "data/images/gatk4.sif"}
- source_prompt: "Preprocess NA12878 chr20 FASTQ to recalibrated BAM"

Then print exactly:
- supported
- recipe_id
- run_record_path
- execution_profile
- limitations
```

**Pass criteria for 4a:**

- `supported` is `true`.
- `recipe_id` non-null; `run_record_path` ends in `slurm_run_record.json`.

---

**Step 4b — Poll until terminal:**

Use the same polling prompt as Scenario 2, Step 2c with this job's
`run_record_path`.

**Pass criteria for 4b:**

- `final_scheduler_state` is `"COMPLETED"`.
- `stderr_path` contains no `ERROR` lines from `bwa-mem2`, `samtools`, or
  `gatk` (check with `grep -i "ERROR" <stderr_path>` on the cluster).

---

**Step 4c — Inspect manifest:**

```text
Use the flytetest MCP server.

Read results/germline_minimal/preprocess_sample/run_manifest.json
and print the outputs dict.
```

**Pass criteria for 4c:**

- `outputs.preprocessed_bam` points at a `*_recal.bam` file.
- A sibling `.bai` or `.bam.bai` file is present in the same directory.

---

## Scenario 5 — germline_short_variant_discovery (end-to-end)

**Goal:** Full pipeline — raw reads → joint-called cohort VCF.

**Prerequisite:** Scenario 3 completed (reference companion files present).
Scenario 4 is not a prerequisite; this workflow re-runs `preprocess_sample`
internally per sample.

**Estimated time:** 45–120 minutes for the single-sample chr20 fixture.

---

**Step 5a — Freeze and submit `germline_short_variant_discovery`:**

```text
Use the flytetest MCP server.

Call run_workflow with exactly these arguments:
- workflow_name: "germline_short_variant_discovery"
- bindings: {
    "ReferenceGenome": {"fasta_path": "data/references/hg38/chr20.fa"},
    "KnownSites": [
      {"vcf_path": "data/references/hg38/dbsnp_138.hg38.vcf", "resource_name": "dbsnp"}
    ]
  }
- inputs: {
    "sample_ids": ["NA12878_chr20"],
    "r1_paths": ["data/reads/NA12878_chr20_R1.fastq.gz"],
    "r2_paths": ["data/reads/NA12878_chr20_R2.fastq.gz"],
    "intervals": ["chr20"],
    "cohort_id": "NA12878_chr20",
    "results_dir": "results/germline_minimal/germline_short_variant_discovery/"
  }
- resources: {"cpu": 16, "memory": "64Gi", "partition": "caslake", "account": "rcc-staff", "walltime": "04:00:00"}
- execution_profile: "slurm"
- runtime_images: {"sif_path": "data/images/gatk4.sif"}
- source_prompt: "End-to-end germline short variant discovery on NA12878 chr20 cohort"

Then print exactly:
- supported
- recipe_id
- run_record_path
- execution_profile
- limitations
```

**Pass criteria for 5a:**

- `supported` is `true`.
- `recipe_id` non-null; `run_record_path` ends in `slurm_run_record.json`.

---

**Step 5b — Poll until terminal:**

Use the same polling prompt as Scenario 2, Step 2c with this job's
`run_record_path`.

**Pass criteria for 5b:**

- `final_scheduler_state` is `"COMPLETED"`.

---

**Step 5c — Inspect manifest:**

```text
Use the flytetest MCP server.

Read results/germline_minimal/germline_short_variant_discovery/run_manifest.json
and print the outputs dict.
```

**Pass criteria for 5c:**

- `outputs.genotyped_vcf` points at a `.vcf.gz` file.
- A companion `.vcf.gz.tbi` file is present in the same directory.
- Running `bcftools view -h <genotyped_vcf>` on the cluster shows at least
  one `##contig=<ID=chr20>` header line and a sample column named
  `NA12878_chr20`.

---

## Scenario 6 — Cancel idempotency: cancel the same job twice

**Goal:** Verify that calling `cancel_slurm_job` twice on the same run record
returns `supported: true` both times and does NOT issue a second `scancel` to
the scheduler.

**Prerequisite:** Complete Scenario 2, Steps 2a and 2b (`load_bundle` +
`run_task`) to get a `run_record_path` for a submitted job.  This scenario
works best while the job is still `PENDING` or `RUNNING` — cancel it before
it finishes.

---

**Step 6a — First cancel:**

```text
Use the flytetest MCP server.

Call cancel_slurm_job with the run_record_path from run_task.

Then print exactly:
- supported
- scheduler_state
- limitations
```

**Pass criteria for 6a:**

- `supported` is `true`.
- `scheduler_state` is `"cancellation_requested"`.
- `limitations` is empty.

---

**Step 6b — Second cancel (idempotency check):**

```text
Use the flytetest MCP server.

Call cancel_slurm_job with the same run_record_path as the first cancel.

Then print exactly:
- supported
- scheduler_state
- limitations
```

**Pass criteria for 6b:**

- `supported` is `true` (idempotent — not an error).
- `scheduler_state` is `"cancellation_requested"` (same as first call).
- `limitations` mentions "already requested" or similar — confirms that
  no second `scancel` was issued.

---

**Step 6c — Confirm final state with monitor:**

```text
Use the flytetest MCP server.

Call monitor_slurm_job with the same run_record_path.

Then print exactly:
- supported
- scheduler_state
- final_scheduler_state
- limitations
```

**Pass criteria for 6c:**

- After the scheduler processes the cancel: `final_scheduler_state` is
  `"CANCELLED"`.
- `supported` is `true`.

---

## Scenario 7 — Retry: resubmit after a retryable infrastructure failure

**Goal:** Verify that `retry_slurm_job` creates a new `run_record_path` and
new `job_id` for the resubmission, and that the child lifecycle is independent
of the parent.

**Prerequisite:** A retryable terminal run record must exist.  Synthesise one
from a prior `haplotype_caller` submission (Scenario 2, Step 2b):

```bash
# Run this in the terminal (not in OpenCode) before the prompts below.
# Replace <run_record_path> with the path from Scenario 2, Step 2b.
bash scripts/rcc/make_m18_retry_smoke_record.sh <run_record_path> NODE_FAIL
```

The script prints the path of the synthetic retryable run record.  Use that
path in the prompts below.

---

**Step 7a — Verify the synthetic record is seen as terminal:**

```text
Use the flytetest MCP server.

Call monitor_slurm_job with the run_record_path printed by make_m18_retry_smoke_record.sh.

Then print exactly:
- supported
- scheduler_state
- final_scheduler_state   (expect: NODE_FAIL)
- limitations
```

**Pass criteria for 7a:**

- `final_scheduler_state` is `"NODE_FAIL"` (terminal, retryable).

---

**Step 7b — Retry the failed job:**

```text
Use the flytetest MCP server.

Call retry_slurm_job with the run_record_path of the NODE_FAIL record.

Then print exactly:
- supported
- job_id           (new Slurm job ID for the retry)
- retry_run_record_path   (path to the new child run record)
- limitations
```

**Pass criteria for 7b:**

- `supported` is `true`.
- `job_id` is a new numeric string different from the parent job.
- `retry_run_record_path` is a different path from the parent run record.
- `limitations` is empty.

---

**Step 7c — Poll the child run record to completion:**

Use the `retry_run_record_path` from Step 7b (not the parent path) with the
same polling prompt as Scenario 2, Step 2c.

**Pass criteria for 7c:**

- While active: `scheduler_state` is `PENDING` or `RUNNING`; polling continues.
- On completion: `final_scheduler_state` is `COMPLETED`.
- `run_record_path` matches the `retry_run_record_path` from Step 7b —
  confirms the child record is independent of the parent.

---

## Scenario 8 — Escalation retry: resubmit after OOM with more memory

**Goal:** Verify that `retry_slurm_job` with `resource_overrides` creates a new
child run record that uses the escalated resources, and that the child lifecycle
reaches COMPLETED or FAILED independently of the parent.

**Prerequisite:** A terminal `OUT_OF_MEMORY` run record must exist.  Synthesise
one from a prior `haplotype_caller` submission:

```bash
# Run this in the terminal (not in OpenCode) before the prompts below.
# Replace <run_record_path> with a path from a prior haplotype_caller Slurm submission.
bash scripts/rcc/make_m18_retry_smoke_record.sh <run_record_path> OUT_OF_MEMORY
```

The script prints the path of the synthetic `OUT_OF_MEMORY` record.  Use that
path in the prompts below.

---

**Step 8a — Verify the synthetic record shows OUT_OF_MEMORY:**

```text
Use the flytetest MCP server.

Call monitor_slurm_job with the run_record_path printed by make_m18_retry_smoke_record.sh.

Then print exactly:
- supported
- scheduler_state
- final_scheduler_state   (expect: OUT_OF_MEMORY)
- limitations
```

**Pass criteria for 8a:**

- `final_scheduler_state` is `"OUT_OF_MEMORY"` (terminal, resource_exhaustion class).

---

**Step 8b — Escalation retry with more memory:**

```text
Use the flytetest MCP server.

Call retry_slurm_job with:
  run_record_path: <path from the terminal OUT_OF_MEMORY run>
  resource_overrides: {"memory": "64Gi"}

Then print exactly:
- supported
- job_id                  (new Slurm job ID)
- retry_run_record_path   (path to the child run record)
- limitations
```

**Pass criteria for 8b:**

- `supported` is `true`.
- `job_id` is a new numeric string different from the parent job.
- `retry_run_record_path` is a different path from the parent run record.
- `limitations` is empty.

---

**Step 8c — Confirm the child record carries the escalated memory:**

```text
Use the flytetest MCP server.

Read and print the child run record JSON at retry_run_record_path.
Then print:
- resource_spec.memory    (expect: 64Gi)
- resource_overrides.memory  (expect: 64Gi)
```

**Pass criteria for 8c:**

- `resource_spec.memory` is `"64Gi"`.
- `resource_overrides.memory` is `"64Gi"`.

---

**Step 8d — Poll the child run record:**

Use the same polling pattern as Scenario 2, Step 2c with `retry_run_record_path`.

**Pass criteria for 8d:**

- While active: `scheduler_state` is `PENDING` or `RUNNING`.
- On completion: `final_scheduler_state` is `COMPLETED`.

---

## Quick reference: fields to print for each tool

| Tool | Fields to print |
|---|---|
| `list_entries` | `supported`, `server_tools`, entries with `slurm_resource_hints` |
| `load_bundle` | `supported`, `bindings`, `inputs`, `runtime_images`, `tool_databases`, `limitations` |
| `run_task` | `supported`, `recipe_id`, `run_record_path`, `execution_profile`, `limitations` |
| `run_workflow` | `supported`, `recipe_id`, `run_record_path`, `execution_profile`, `limitations` |
| `prepare_run_recipe` | `supported`, `artifact_path`, `limitations` |
| `run_slurm_recipe` | `supported`, `job_id`, `run_record_path`, `limitations` |
| `monitor_slurm_job` | `supported`, `scheduler_state`, `final_scheduler_state`, `stdout_path`, `stderr_path`, `run_record_path`, `limitations` |
| `cancel_slurm_job` | `supported`, `scheduler_state`, `limitations` |
| `retry_slurm_job` | `supported`, `job_id`, `retry_run_record_path`, `limitations` |
| `list_slurm_run_history` | `supported`, `returned_count`, entries (`job_id`, `workflow_name`, `effective_scheduler_state`, `run_record_path`) |

## If a tool returns `supported: false`

1. Print the full `limitations` list — it describes the failure in plain text.
2. Check that `sbatch`, `squeue`, `scontrol`, `sacct`, and `scancel` are on
   `PATH` from the shell where the MCP server was started.
3. Check that the `run_record_path` or `artifact_path` argument is a string
   (not a dict) — some clients silently coerce structured fields.
4. If the limitation mentions "schema version": the run record on disk was
   written by an older server version.  Discard it and start a fresh prepare
   + submit cycle.
