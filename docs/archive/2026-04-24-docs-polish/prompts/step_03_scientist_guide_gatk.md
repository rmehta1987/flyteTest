# Step 03 — SCIENTIST_GUIDE.md: GATK Germline Variant Calling Runbook

Add a "GATK Germline Variant Calling" section to `SCIENTIST_GUIDE.md`. This is the
canonical end-to-end runbook for a bioinformatician running the chr20 NA12878 smoke
test on HPC. It should be the first place a new user goes after reading the README.

Read `SCIENTIST_GUIDE.md` first to understand the existing structure and voice.
Read `docs/gatk_pipeline_overview.md` for biological context.
Do not duplicate content already in the overview doc — link to it.

---

## Section to add

Append a new top-level section after the existing content (or insert before the
final "Further reading" / closing section if one exists). Title:

```
## GATK Germline Variant Calling
```

### Subsections

#### Prerequisites

What must be in place before starting:
- Data staged: `bash scripts/rcc/stage_gatk_local.sh` (downloads chr20 FASTA,
  known-sites VCF slices via tabix, generates synthetic reads with wgsim)
- SIFs pulled or HPC modules confirmed:
  - GATK: `bash scripts/rcc/pull_gatk_image.sh` OR `module load gatk/4.5.0`
  - bwa-mem2: `bash scripts/rcc/build_bwa_mem2_sif.sh`
- Fixtures verified: `bash scripts/rcc/check_gatk_fixtures.sh`
- MCP server running: `PYTHONPATH=src python -m flytetest.server`
- Queue and account obtained from your HPC admin (required for Slurm submission)

#### Step 1 — Load the starter bundle

```python
bundle = load_bundle("variant_calling_germline_minimal")
# Returns: bindings, inputs, runtime_images, tool_databases, fetch_hints
```

The bundle pre-fills paths for chr20 data and SIF locations. Inspect it before
proceeding. If the bundle shows `available=False`, follow the `fetch_hints`.

#### Step 2 — Prepare reference (dry run first)

```python
recipe = run_workflow(
    workflow_name="prepare_reference",
    **bundle,
    execution_profile="slurm",
    resource_request={"queue": "<your-queue>", "account": "<your-account>"},
    dry_run=True,
)
# Returns a DryRunReply with recipe_id and artifact_path
```

Inspect the frozen recipe:
```python
validate = validate_run_recipe(artifact_path=recipe["artifact_path"])
```

If validation passes, submit:
```python
result = run_slurm_recipe(artifact_path=recipe["artifact_path"])
```

#### Step 3 — Monitor and proceed

```python
status = monitor_slurm_job(run_record_path=result["run_record_path"])
```

Note: `scontrol show job <id>` only works while the job is **running**.
Use `sacct -j <id>` for completed or failed jobs.

If the job fails with OOM or TIMEOUT:
```python
retry = retry_slurm_job(
    run_record_path=result["run_record_path"],
    resource_overrides={"memory": "64Gi", "walltime": "04:00:00"},
)
```

#### Step 4 — Preprocess sample then call variants

Repeat the dry_run → validate → submit pattern for:
```
workflow_name="preprocess_sample"
workflow_name="germline_short_variant_discovery"
```

Each workflow builds on outputs from the previous. The bundle provides sensible
defaults; override `resource_request` as needed for your cluster.

#### Step 5 — Post-call QC and annotation (optional)

```
workflow_name="post_call_qc_summary"    # bcftools stats + MultiQC report
workflow_name="annotate_variants_snpeff" # SnpEff functional annotation
```

For `post_call_qc_summary`, ensure `bcftools` and `multiqc` modules are loaded or
their SIFs are provided. For `annotate_variants_snpeff`, ensure the SnpEff database
is pre-staged (`bash scripts/rcc/download_snpeff_db.sh GRCh38.105`).

#### Key parameter notes

- `workflow_name` — the registered workflow name (not `target`)
- `execution_profile` — `"local"` for testing, `"slurm"` for cluster submission
- `resource_request.queue` and `resource_request.account` — must come from the user;
  not inferred from registry hints
- `module_loads` — full replacement of defaults; use the escape hatch
  (`from flytetest.spec_executor import DEFAULT_SLURM_MODULE_LOADS`) to extend
- `run_record_path` — durable path returned by `run_slurm_recipe`; needed for
  `monitor_slurm_job` and `retry_slurm_job`

#### Further reading

- `docs/gatk_pipeline_overview.md` — full biological inventory (21 tasks, 11 workflows)
- `scripts/rcc/README.md` — SIF management and module configuration
- `AGENTS.md` — MCP/Slurm behavioural rules for coding agents

---

## Verification

```bash
grep -n "prepare_reference\|dry_run\|run_record_path\|scontrol\|sacct" SCIENTIST_GUIDE.md
wc -l SCIENTIST_GUIDE.md   # should grow by ~80-100 lines; total still reasonable
```
