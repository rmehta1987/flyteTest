# Step 03 — Workflow Happy-Path Scenarios

## Model

**Sonnet 4.6** (`claude-sonnet-4-6`). Three new scenarios that compose
the Milestone B workflows; each uses the typed `run_workflow` surface
and requires correct binding shapes (`ReferenceGenome`, `ReadPair`,
`KnownSites`). Getting the binding shape wrong breaks the prompt in
subtle ways — worth Sonnet's precision over Haiku's speed.

## Goal

Append three scenarios (Scenarios 3–5) to
`docs/mcp_variant_calling_cluster_prompt_tests.md`, covering:

- `prepare_reference` (one-time reference indexing).
- `preprocess_sample` (FASTQ → recalibrated BAM).
- `germline_short_variant_discovery` (full pipeline: raw reads → joint
  VCF).

## Context

- Step 02 created the doc with Prerequisites + Scenarios 1 and 2.
- Workflows are defined in
  `src/flytetest/workflows/variant_calling.py`; confirm their
  signatures and `MANIFEST_OUTPUT_KEYS` before writing.
- Registry entries are in `src/flytetest/registry/_variant_calling.py`
  under `category="workflow"` with `pipeline_stage_order` 1–3.
- The fixture bundle `variant_calling_germline_minimal` applies to all
  three workflows (`applies_to` field).
- `prepare_reference` must run before `preprocess_sample`, which must
  run before `germline_short_variant_discovery`. Scenario 3 therefore
  precedes Scenario 4 which precedes Scenario 5; each downstream
  scenario inputs a results-dir path from the upstream scenario's
  manifest.

## Inputs to read first

- `src/flytetest/workflows/variant_calling.py` — workflow signatures,
  parameters, `MANIFEST_OUTPUT_KEYS`.
- `src/flytetest/registry/_variant_calling.py` — workflow registry
  entries; check interface field names and order.
- `src/flytetest/bundles.py:126-174` — bundle paths.
- `docs/mcp_cluster_prompt_tests.md` lines 101–211 — the
  `run_task`-then-`monitor_slurm_job` pattern you are mirroring (change
  to `run_workflow`).

## What to build

Append to `docs/mcp_variant_calling_cluster_prompt_tests.md`, **after
Scenario 2 and before the Quick-reference table**:

### Scenario 3 — prepare_reference (one-time)

- Goal: build `.fai`, `.dict`, BWA-MEM2 index, and per-known-site
  `.idx`/`.tbi` for the chr20 fixture.
- Estimated time: 5–15 minutes.
- Prerequisite: GATK4 SIF and reference FASTA + known-sites VCFs
  staged on the shared filesystem.
- Prompt block: `run_workflow` with:
  - `workflow_name: "prepare_reference"`
  - `bindings: {"ReferenceGenome": {"fasta_path": "data/references/hg38/chr20.fa"}, "KnownSites": [{"vcf_path": "data/references/hg38/dbsnp_138.hg38.vcf", "resource_name": "dbsnp"}, {"vcf_path": "data/references/hg38/Mills_and_1000G_gold_standard.indels.hg38.vcf", "resource_name": "mills"}]}`
  - `inputs: {"results_dir": "results/germline_minimal/prepare_reference/"}`
  - `resources: {"cpu": 8, "memory": "32Gi", "partition": "caslake", "account": "rcc-staff", "walltime": "00:30:00"}`
  - `execution_profile: "slurm"`
  - `runtime_images: {"sif_path": "data/images/gatk4.sif"}`
  - `source_prompt: "One-time reference preparation for NA12878 chr20 germline fixture"`
  - Print `supported`, `recipe_id`, `run_record_path`,
    `execution_profile`, `limitations`.
- Poll step: reuse the polling prompt from Scenario 2, Step 2c.
- Manifest inspection: the `prepared_ref` key in
  `<results_dir>/run_manifest.json` must equal the reference FASTA
  path.
- Pass criteria: `final_scheduler_state: "COMPLETED"`; companion files
  (`.fai`, `.dict`, BWA-MEM2 `.bwt.2bit.64`/`.0123`/`.amb`/`.ann`/
  `.pac`, `.tbi` or `.idx` per known-site) land in the same directory
  as each input file (tasks emit alongside the input as documented in
  `docs/tool_refs/gatk4.md`).

### Scenario 4 — preprocess_sample

- Goal: raw paired FASTQ → coordinate-sorted, duplicate-marked, BQSR-
  recalibrated BAM.
- Estimated time: 20–60 minutes.
- Prerequisite: Scenario 3 completed (reference companion files
  present).
- Prompt block: `run_workflow` with:
  - `workflow_name: "preprocess_sample"`
  - `bindings: {"ReferenceGenome": {"fasta_path": "data/references/hg38/chr20.fa"}, "ReadPair": {"sample_id": "NA12878_chr20", "r1_path": "data/reads/NA12878_chr20_R1.fastq.gz", "r2_path": "data/reads/NA12878_chr20_R2.fastq.gz"}, "KnownSites": [{"vcf_path": "data/references/hg38/dbsnp_138.hg38.vcf", "resource_name": "dbsnp"}]}`
  - `inputs: {"results_dir": "results/germline_minimal/preprocess_sample/"}`
  - `resources: {"cpu": 16, "memory": "64Gi", "partition": "caslake", "account": "rcc-staff", "walltime": "02:00:00"}`
  - `execution_profile: "slurm"`
  - `runtime_images: {"sif_path": "data/images/gatk4.sif"}`
  - `source_prompt: "Preprocess NA12878 chr20 FASTQ to recalibrated BAM"`
- Poll step: reuse Scenario 2c polling prompt.
- Manifest inspection: `preprocessed_bam` in
  `<results_dir>/run_manifest.json` points at a
  `*_recal.bam` file with sibling `.bai` or `.bam.bai`.
- Pass criteria: `final_scheduler_state: "COMPLETED"`;
  `preprocessed_bam` readable; `stderr_path` contains no
  `ERROR` lines from `bwa-mem2`, `samtools`, or `gatk`.

### Scenario 5 — germline_short_variant_discovery (end-to-end)

- Goal: full pipeline — raw reads → joint-called VCF.
- Estimated time: 45–120 minutes (per-sample fan-out plus joint
  genotyping).
- Prerequisite: Scenario 3 completed (reference companion files
  present). Scenario 4 is **not** a prerequisite; this workflow re-runs
  `preprocess_sample` internally per sample.
- Prompt block: `run_workflow` with:
  - `workflow_name: "germline_short_variant_discovery"`
  - `bindings: {"ReferenceGenome": {"fasta_path": "data/references/hg38/chr20.fa"}, "KnownSites": [{"vcf_path": "data/references/hg38/dbsnp_138.hg38.vcf", "resource_name": "dbsnp"}]}`
  - `inputs: {"sample_ids": ["NA12878_chr20"], "r1_paths": ["data/reads/NA12878_chr20_R1.fastq.gz"], "r2_paths": ["data/reads/NA12878_chr20_R2.fastq.gz"], "intervals": ["chr20"], "cohort_id": "NA12878_chr20", "results_dir": "results/germline_minimal/germline_short_variant_discovery/"}`
  - `resources: {"cpu": 16, "memory": "64Gi", "partition": "caslake", "account": "rcc-staff", "walltime": "04:00:00"}`
  - `execution_profile: "slurm"`
  - `runtime_images: {"sif_path": "data/images/gatk4.sif"}`
  - `source_prompt: "End-to-end germline short variant discovery on NA12878 chr20 cohort"`
- Poll step: reuse Scenario 2c polling prompt.
- Manifest inspection: `genotyped_vcf` in
  `<results_dir>/run_manifest.json` points at a `.vcf.gz` file with
  companion `.tbi`.
- Pass criteria: `final_scheduler_state: "COMPLETED"`;
  `bcftools view -h <genotyped_vcf>` (run on the cluster, outside
  OpenCode) shows at least one `##contig=<ID=chr20>` line and a sample
  column named `NA12878_chr20`.

Before each scenario header, add a `---` separator (matching the doc's
existing convention).

## Verify workflow names resolve

Before writing Pass criteria for any scenario, run:

```bash
rg -n "^    \"(prepare_reference|preprocess_sample|germline_short_variant_discovery)\"" src/flytetest/registry/_variant_calling.py
```

If any name is missing, stop — the registry is out of sync with the
Milestone B plan and must be fixed before continuing.

## Files to create or update

- `docs/mcp_variant_calling_cluster_prompt_tests.md` (append three
  scenarios + separators; do not modify existing Scenarios 1–2).
- `CHANGELOG.md` (append entry under `## Unreleased`).
- `docs/gatk_milestone_c/checklist.md` (mark Step 03 Complete).

## CHANGELOG

```
### GATK Milestone C Step 03 — Workflow happy-path cluster scenarios (YYYY-MM-DD)

- [x] YYYY-MM-DD added Scenario 3 (prepare_reference) to docs/mcp_variant_calling_cluster_prompt_tests.md.
- [x] YYYY-MM-DD added Scenario 4 (preprocess_sample).
- [x] YYYY-MM-DD added Scenario 5 (germline_short_variant_discovery end-to-end).
```

## Verification

```bash
rg -n "^## Scenario 3 " docs/mcp_variant_calling_cluster_prompt_tests.md
rg -n "^## Scenario 4 " docs/mcp_variant_calling_cluster_prompt_tests.md
rg -n "^## Scenario 5 " docs/mcp_variant_calling_cluster_prompt_tests.md
rg -n "prepare_reference|preprocess_sample|germline_short_variant_discovery" docs/mcp_variant_calling_cluster_prompt_tests.md
rg "async def|await |asyncio\.gather|\.cid\b|IPFS|Pinata|TinyDB" docs/mcp_variant_calling_cluster_prompt_tests.md
# Confirm Scenario ordering — prepare_reference must appear before preprocess_sample must appear before germline_short_variant_discovery
rg -n "^## Scenario [345] " docs/mcp_variant_calling_cluster_prompt_tests.md | sort -k2n
```

First four must match; the Stargazer grep gate must return zero hits.

## Commit message

```
variant_calling: add workflow cluster scenarios (Milestone C Step 03)
```

## Checklist

- [ ] Three scenarios appended in biological order.
- [ ] Each `workflow_name` resolves in `VARIANT_CALLING_ENTRIES`.
- [ ] Binding shapes match the Milestone B planner types
  (`ReferenceGenome`, `ReadPair`, `KnownSites`).
- [ ] Pass criteria reference the correct workflow-manifest keys
  (`prepared_ref`, `preprocessed_bam`, `genotyped_vcf`).
- [ ] Stargazer grep gate passes.
- [ ] CHANGELOG updated.
- [ ] Step 03 marked Complete in checklist.
