# Step 02 — Cluster Prompt Doc Skeleton + Sanity + Single-Task Happy Path

## Model

**Sonnet 4.6** (`claude-sonnet-4-6`). The new doc must mirror the voice,
section ordering, and "**Pass criteria**" conventions of
`docs/mcp_cluster_prompt_tests.md` while swapping in variant_calling
bindings. Haiku often regresses on faithful structural mirroring of a
400-line reference doc.

## Goal

Create `docs/mcp_variant_calling_cluster_prompt_tests.md` with the
prerequisites block, Scenario 1 (sanity: list variant_calling entries),
and Scenario 2 (happy path: `load_bundle` → `run_task` →
`monitor_slurm_job`) targeting the `haplotype_caller` task on a tiny
germline fixture.

## Context

- Reference doc (read before editing): `docs/mcp_cluster_prompt_tests.md`
  — §Scenario 1 and §Scenario 2 are the direct templates.
- Fixture bundle: `variant_calling_germline_minimal` in
  `src/flytetest/bundles.py` (do not invent paths — reuse bundle values
  verbatim).
- Registry entries live in `src/flytetest/registry/_variant_calling.py`.
  Check `list_entries(pipeline_family="variant_calling")` output keys
  before writing Pass criteria (`rg -n "name=" src/flytetest/registry/_variant_calling.py`).
- Container-pull script: `scripts/rcc/pull_gatk_image.sh` (already
  present; reference it in Prerequisites).
- Known-sites indexing path: `haplotype_caller` requires a `.fai` and
  `.dict` on the reference; the `prepare_reference` workflow produces
  those, so Scenario 2 assumes `prepare_reference` was already run once.

## Inputs to read first

- `docs/mcp_cluster_prompt_tests.md` — lines 1–200 (Prerequisites +
  Scenarios 1 and 2).
- `src/flytetest/bundles.py:126-174` — the germline bundle definition.
- `src/flytetest/registry/_variant_calling.py` — confirm exact task
  names and their `outputs[*].name` lists.
- `src/flytetest/tasks/variant_calling.py` — confirm
  `MANIFEST_OUTPUT_KEYS`.

## What to build

### `docs/mcp_variant_calling_cluster_prompt_tests.md`

Top-of-file sections in order:

1. `# MCP Variant Calling Cluster Prompt Tests` — one-paragraph intro
   that names this as the live-cluster companion to
   `mcp_cluster_prompt_tests.md` for the `variant_calling` family, and
   says these scenarios exercise real `sbatch`/`squeue`/`scontrol`/
   `sacct`/`scancel`.
2. `## Prerequisites` — list:
   - MCP server running inside an authenticated RCC login session
     (CILogon 2FA complete — `sbatch` works from this shell).
   - `sbatch`, `squeue`, `scontrol`, `sacct`, `scancel` on `PATH`.
   - GATK4 SIF image present at `data/images/gatk4.sif`
     (`bash scripts/rcc/pull_gatk_image.sh` if missing).
   - Germline fixture bundle paths resolvable on the cluster's shared
     filesystem (see §fetch_hints in `variant_calling_germline_minimal`
     — dbSNP/Mills VCFs under `data/references/hg38/`, NA12878 reads
     under `data/reads/`).
   - A prior `prepare_reference` run has produced `.fai`, `.dict`, and
     BWA-MEM2 index files alongside `chr20.fa` (reference is frozen
     between runs).
   - Connectivity check prompt — reuse the list_entries prompt shape
     from `mcp_cluster_prompt_tests.md` lines 26–36 but filter output to
     `pipeline_family="variant_calling"`.

3. `## Scenario 1 — Sanity check: list variant_calling Slurm-capable targets`
   - Goal, estimated time (seconds).
   - Prompt block that calls `list_entries` with
     `pipeline_family="variant_calling"` and prints `supported`,
     `server_tools`, entries with `supported_execution_profiles`
     containing `"slurm"`, `limitations`.
   - **Pass criteria**:
     - `supported: true`.
     - `server_tools` includes `prepare_run_recipe`, `run_slurm_recipe`,
       `monitor_slurm_job`, `cancel_slurm_job`, `retry_slurm_job`,
       `list_slurm_run_history`, `run_task`, `run_workflow`,
       `load_bundle`.
     - Entries list contains `haplotype_caller`, `combine_gvcfs`,
       `joint_call_gvcfs`, `bwa_mem2_mem`, `sort_sam`,
       `mark_duplicates`, `base_recalibrator`, `apply_bqsr`,
       `create_sequence_dictionary`, `index_feature_file`,
       `bwa_mem2_index`, plus the three workflows (`prepare_reference`,
       `preprocess_sample`, `germline_short_variant_discovery`).
     - Each entry's `slurm_resource_hints` contains `cpu`, `memory`,
       `walltime`.

4. `## Scenario 2 — Happy path: load_bundle → run_task(haplotype_caller) → poll COMPLETED`
   - Goal, estimated time (15–45 minutes on `caslake` for the chr20
     NA12878 slice).
   - **Step 2a — Load the germline bundle**: prompt that calls
     `load_bundle` with `name: "variant_calling_germline_minimal"` and
     prints `supported`, `bindings`, `inputs`, `runtime_images`,
     `tool_databases`, `limitations`. Pass criteria: `supported: true`;
     `bindings.ReadPair.sample_id` is `"NA12878_chr20"`;
     `runtime_images.sif_path` is `"data/images/gatk4.sif"`.
   - **Step 2b — Freeze + submit `haplotype_caller`**: prompt that
     calls `run_task` with:
     - `task_name: "haplotype_caller"`
     - `bindings: {"ReferenceGenome": {"fasta_path": "data/references/hg38/chr20.fa"}, "AlignmentSet": {"bam_path": "<recal_bam_from_prior_preprocess_sample_run>", "sample_id": "NA12878_chr20"}}`
     - `inputs: {"results_dir": "results/germline_minimal/haplotype_caller/"}`
     - `resources: {"cpu": 4, "memory": "16Gi", "partition": "caslake", "account": "rcc-staff", "walltime": "01:00:00"}`
     - `execution_profile: "slurm"`
     - `runtime_images: {"sif_path": "data/images/gatk4.sif"}`
     - `source_prompt: "Call germline short variants on NA12878 chr20 slice for cluster validation"`
     - Print `supported`, `recipe_id`, `run_record_path`,
       `execution_profile`, `limitations`.
     - **Pass criteria for 2b**: `supported: true`; `recipe_id`
       timestamp-target format (see `spec_artifacts.py`);
       `run_record_path` ends in `slurm_run_record.json`;
       `execution_profile: "slurm"`.
   - **Step 2c — Poll until terminal**: reuse the polling prompt
     shape from `mcp_cluster_prompt_tests.md` lines 138–151 verbatim
     (change only the narrative sentence above the prompt block to
     reference `haplotype_caller`). Pass criteria: while active,
     `final_scheduler_state: null`; on completion,
     `final_scheduler_state: "COMPLETED"`, both `stdout_path` and
     `stderr_path` non-null.
   - **Step 2d — Inspect the manifest**: prompt that reads
     `<results_dir>/run_manifest.json` and prints the `outputs` dict.
     Pass criteria: `outputs` contains key `"gvcf"` pointing at a
     `.g.vcf.gz` file inside `results_dir`.

5. `## Quick reference: fields to print for each tool` — copy the table
   from `mcp_cluster_prompt_tests.md` lines 471–483 verbatim (no
   variant_calling-specific rows; the tool surface is unchanged).

6. `## If a tool returns supported: false` — copy the four-item
   numbered list from `mcp_cluster_prompt_tests.md` lines 485–494
   verbatim.

**Do NOT yet add Scenarios 3–6** — those land in Step 03 and Step 04.

## Files to create or update

- `docs/mcp_variant_calling_cluster_prompt_tests.md` (create).
- `CHANGELOG.md` (append entry under `## Unreleased`).
- `docs/gatk_milestone_c/checklist.md` (mark Step 02 Complete).

## CHANGELOG

```
### GATK Milestone C Step 02 — Cluster prompt doc skeleton + single-task happy path (YYYY-MM-DD)

- [x] YYYY-MM-DD created docs/mcp_variant_calling_cluster_prompt_tests.md with Prerequisites, Scenario 1, Scenario 2 (haplotype_caller).
- [x] YYYY-MM-DD copied quick-reference table and "supported: false" troubleshooting block from mcp_cluster_prompt_tests.md.
```

## Verification

```bash
test -f docs/mcp_variant_calling_cluster_prompt_tests.md
rg -n "^## Scenario 1 " docs/mcp_variant_calling_cluster_prompt_tests.md
rg -n "^## Scenario 2 " docs/mcp_variant_calling_cluster_prompt_tests.md
rg -n "variant_calling_germline_minimal" docs/mcp_variant_calling_cluster_prompt_tests.md
rg -n "haplotype_caller" docs/mcp_variant_calling_cluster_prompt_tests.md
rg "async def|await |asyncio\.gather|\.cid\b|IPFS|Pinata|TinyDB" docs/mcp_variant_calling_cluster_prompt_tests.md
```

First five must return matches; the last (Stargazer grep gate) must
return no matches.

## Commit message

```
variant_calling: add cluster prompt doc skeleton + single-task happy path (Milestone C Step 02)
```

## Checklist

- [ ] Doc created at `docs/mcp_variant_calling_cluster_prompt_tests.md`.
- [ ] Prerequisites block references `scripts/rcc/pull_gatk_image.sh`.
- [ ] Scenario 1 Pass criteria names all eleven tasks and three
  workflows by exact registry name.
- [ ] Scenario 2 uses `variant_calling_germline_minimal` bundle values
  verbatim.
- [ ] Scenario 2 Pass criteria verifies `run_manifest.json` contains
  `"gvcf"` key.
- [ ] Stargazer grep gate passes (zero hits).
- [ ] CHANGELOG entry added.
- [ ] Step 02 marked Complete in `docs/gatk_milestone_c/checklist.md`.
