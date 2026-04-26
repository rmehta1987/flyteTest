# FlyteTest MCP — What's Changing for You

A practical guide for biologists driving FlyteTest through an MCP-aware client (Claude Code, an IDE assistant, etc.). This document describes the scientist-facing experience after the MCP surface reshape. For the implementation-level plan, see `IMPLEMENTATION_PLAN.md`.

## Glossary

- **Recipe** — a frozen, JSON-serializable plan describing exactly what will run. Once a recipe exists, nothing about the run is invented at submit time.
- **Bundle** — a curated set of inputs (reference, evidence, intervals, containers) that turns a registered task or workflow into a one-call starter kit. See `list_bundles`.
- **Manifest** — the per-stage record of inputs, outputs, and tool versions written by every task. Provenance lives here.
- **Run record** — the durable record of a Slurm submission: job ID, stdout / stderr paths, lifecycle state, exit code.
- **Execution profile** — `local` or `slurm`. Picks the executor and governs whether `check_offline_staging` enforces shared-filesystem reachability.

## TL;DR

- **Four-step experiment loop replaces the old "prepare → approve → run" dance.** You browse, pick a starter kit (or supply your own inputs), and run.
- **Bundles** are curated starter kits for common analyses (e.g. BRAKER3 on a small eukaryote, BUSCO protein QC). `load_bundle("braker3_small_eukaryote")` hands you everything you need.
- **Outputs from prior runs can feed the next run.** A `$ref` in place of a file path says "use the GFF from recipe `2026-04-16T12-00-00Z-abc123`." No more copy-pasting result paths.
- **Submit-time staging checks catch unreachable containers and tool DBs.** You find out in 30 seconds, not after a 2-hour queue wait.
- **You need to pass a `source_prompt`** containing your original plain-language question. This is the provenance field that gets frozen into the reproducibility recipe.

## The experiment loop (what you actually do)

### Step 1 — Browse what's available

```
list_entries(category="workflow", pipeline_family="annotation")
```

Returns every registered annotation workflow with its biological contract: what input types it accepts, what it produces, where it sits in the pipeline ("stage 2 of the annotation family"), and what HPC resources are sensible defaults. Filter by `pipeline_family` to ask "what's in variant_calling?" or "what's in postprocessing?"

You can also browse tasks:

```
list_entries(category="task", pipeline_family="annotation")
```

Tasks are single stages (e.g. one Exonerate chunk, one BUSCO run on a proteome) — useful when you're *tuning* a stage rather than running the whole pipeline.

### Step 2 — Grab a starter kit or supply your own inputs

```
list_bundles(pipeline_family="annotation")
```

Returns curated bundles with an `available` flag. A bundle whose backing data isn't on this machine shows `available: false` with a reason ("BUSCO lineage dir missing at data/busco/lineages/eukaryota_odb10") — you see exactly what to download.

For an available bundle:

```
bundle = load_bundle("braker3_small_eukaryote")
# returns {"bindings": {...typed inputs...},
#          "inputs": {"braker_species": "demo_species"},
#          "runtime_images": {"braker_sif": "...", "star_sif": "..."},
#          "tool_databases": {...},
#          "pipeline_family": "annotation", "description": "..."}
```

Spread it directly into the run tool. If you're using your own data, skip `load_bundle()` and pass `bindings` / `inputs` / `runtime_images` explicitly — the shape is the same.

### Step 3 — Run

**Workflow (full pipeline):**

```
run_workflow(
    "braker3_annotation_workflow",
    **bundle,
    source_prompt="Annotate the new P. tetraurelia assembly using RNA-seq from sample S5 and the Ciliophora protein set.",
)
```

**Task (single stage, for experimentation):**

```
run_task(
    "exonerate_align_chunk",
    bindings={"ReferenceGenome": {"fasta_path": "my_assembly.fa"},
              "ProteinEvidenceSet": {"protein_fasta_path": "my_proteins.fa"}},
    inputs={"exonerate_model": "protein2genome"},
    source_prompt="Tune Exonerate on a single chunk before scaling up.",
)
```

Both return:

```
{
    "supported": True,
    "recipe_id": "2026-04-17T14-22-05Z-abc123",   # save this; it reproduces the run later
    "run_record_path": "results/.../run_record.json",
    "artifact_path": ".runtime/specs/<recipe_id>.json",
    "execution_profile": "local",
    "outputs": {
        "annotation_gff": "/abs/path/to/annotation.gff3",
        "proteins_fasta": "/abs/path/to/proteins.fa",
    },
    "limitations": [],
}
```

**Outputs are named.** No more guessing which positional path is the GFF and which is the FASTA — the keys match what the registry entry declares.

### Step 4 — Check Slurm submissions before they burn queue time

Before `sbatch` is called on an HPC cluster, the server now checks that every container (.sif), tool database, and resolved input path lives on a compute-visible filesystem. If something is unreachable, you get a structured decline listing exactly what's missing — not a 2-hour queue wait followed by a node-side runtime error.

You can also run this check explicitly on any frozen recipe:

```
validate_run_recipe(artifact_path=".runtime/specs/<recipe_id>.json",
                    execution_profile="slurm",
                    shared_fs_roots=["/project/pi-account/", "/scratch/myuser/"])
```

## Reusing prior run outputs

The single best ergonomic improvement for iterative analyses is the `$ref` binding form. Instead of copy-pasting the GFF path from your last BRAKER3 run into your next BUSCO run, you reference it by `recipe_id`:

```
run_workflow(
    "busco_annotation_qc_workflow",
    bindings={
        "ReferenceGenome": {"fasta_path": "my_assembly.fa"},
        "AnnotationGff": {"$ref": {"run_id": "2026-04-16T12-00-00Z-abc123",
                                   "output_name": "annotation_gff"}},
    },
    inputs={"lineage_dataset": "eukaryota_odb10", "busco_mode": "proteins"},
    source_prompt="QC the BRAKER3 annotation from yesterday's run.",
)
```

The server resolves the reference through the durable asset index, freezes the concrete path into the new recipe, and runs. Your reproducibility artifact records the actual path — if the asset index changes later, your recipe still replays correctly.

You can mix forms inside one call: a raw-path `ReferenceGenome`, a `$ref`-based `AnnotationGff`, and a `$manifest`-resolved `ReadSet` are all valid simultaneously.

## When a run declines

Every decline comes with three recovery channels:

- **`suggested_bundles`** — available starter kits that would unblock this exact target.
- **`suggested_prior_runs`** — entries from your durable asset index whose outputs match what this target accepts. "You already have a BAM from last week; use `$ref`."
- **`next_steps`** — human-readable suggestions including reformulating the request, calling `list_available_bindings()` to find unbound workspace files, or switching to a different target.

You should rarely hit a dead-end decline; when you do, the reply tells you what to try next.

## What to do with your existing scripts

If you have client code calling the old `run_task(task_name, inputs={...})` or `run_workflow(workflow_name, inputs={...})` shape, it **will stop working** at this milestone. The coordinated migration is intentional (DESIGN §8.7) — no backwards-compatibility shim is provided. Update your scripts to:

- Pass typed biological inputs in `bindings` (keyed by planner-type name like `"ReferenceGenome"`, `"ReadSet"`, `"ProteinEvidenceSet"`) rather than mixing paths and scalars in one flat dict.
- Pass scalar knobs (species names, model choices, thresholds) in `inputs`.
- Pass HPC resources in `resources` with `queue` and `account` explicitly (the server will never invent these; registry hints are only defaults for cpu/memory/walltime).
- Always pass `source_prompt` — your original plain-language question. This is what makes the run traceable months later. An empty prompt is permitted but surfaces an advisory in the reply's `limitations`.
- Read outputs from `reply["outputs"]` (a name-keyed dict), not from the removed `reply["output_paths"]` list.

## When to use the power-user tools

The old `prepare_run_recipe` → `approve_composed_recipe` → `run_local_recipe` / `run_slurm_recipe` sequence still exists. It is now the "inspect-before-execute" path for planner-composed novel DAGs (multi-stage compositions that don't correspond to a single registered workflow). For every registered workflow entry — BRAKER3, BUSCO, Exonerate, etc. — use `run_workflow` directly; the freeze step happens transparently and no explicit approval is required.

## Things you no longer need to do

- Manage `artifact_path` strings between tool calls — `run_task` / `run_workflow` freeze internally and return a `recipe_id`.
- Remember which positional index in an output list is the GVCF vs. the TBI — outputs are named.
- Copy-paste a result path from one run into the next — use `$ref`.
- Discover a BUSCO lineage download is missing only after a 2-hour Slurm wait — staging preflight catches it before submission.
- Remember that BRAKER3 wants a BAM for RNA-seq evidence and a FASTA for protein evidence — bundles package these for you.

---

## GATK Germline Variant Calling

End-to-end runbook for running the chr20 NA12878 germline variant calling
smoke test on HPC. For the full biological inventory (21 tasks, 11 workflows),
see `docs/gatk_pipeline_overview.md`.

### Prerequisites

Before starting, ensure the following are in place:

- **Reference data and reads staged:**
  `bash scripts/rcc/stage_gatk_local.sh` (downloads chr20 FASTA, known-sites VCF slices via tabix, generates synthetic reads with wgsim)
- **Container images:**
  - GATK: `bash scripts/rcc/pull_gatk_image.sh` OR `module load gatk/4.5.0`
  - bwa-mem2: `bash scripts/rcc/build_bwa_mem2_sif.sh`
- **Fixtures verified:** `bash scripts/rcc/check_gatk_fixtures.sh`
- **MCP server running:** `PYTHONPATH=src python3 -m flytetest.server`
- **Queue and account** obtained from your HPC admin (required for Slurm submission; never inferred)

### Step 1 — Load the starter bundle

```python
bundle = load_bundle("variant_calling_germline_minimal")
# Returns: bindings, inputs, runtime_images, tool_databases, fetch_hints
```

The bundle pre-fills paths for chr20 data and SIF locations. Inspect it before
proceeding. If `available=False`, follow the `fetch_hints` in the reply.

### Step 2 — Prepare reference (dry run first)

```python
recipe = run_workflow(
    workflow_name="prepare_reference",
    **bundle,
    execution_profile="slurm",
    resource_request={"queue": "<your-queue>", "account": "<your-account>"},
    dry_run=True,
)
# Returns a DryRunReply with recipe_id, artifact_path, and staging_findings
```

Inspect the frozen recipe and staging preflight results:

```python
validate = validate_run_recipe(artifact_path=recipe["artifact_path"])
```

If validation passes (`validate["supported"] == True`), submit:

```python
result = run_slurm_recipe(artifact_path=recipe["artifact_path"])
```

### Step 3 — Monitor and proceed

```python
status = monitor_slurm_job(run_record_path=result["run_record_path"])
```

Note: `scontrol show job <id>` only works while the job is **running**.
Use `sacct -j <id>` for completed or failed jobs:

```bash
sacct -j <job_id> --format=JobID,State,ExitCode,Elapsed,MaxRSS
```

If the job fails with OOM or TIMEOUT:

```python
retry = retry_slurm_job(
    run_record_path=result["run_record_path"],
    resource_overrides={"memory": "64Gi", "walltime": "04:00:00"},
)
```

### Step 4 — Preprocess sample then call variants

Repeat the `dry_run=True` → `validate_run_recipe` → `run_slurm_recipe` pattern for:

```
workflow_name="preprocess_sample"
workflow_name="germline_short_variant_discovery"
```

Each workflow builds on outputs from the previous. The bundle provides sensible
defaults; override `resource_request` as needed for your cluster.

### Step 5 — Post-call QC and annotation (optional)

```
workflow_name="post_call_qc_summary"     # bcftools stats + MultiQC report
workflow_name="annotate_variants_snpeff" # SnpEff functional annotation
```

For `post_call_qc_summary`, ensure `bcftools` and `multiqc` modules are loaded or
their SIFs are provided. For `annotate_variants_snpeff`, ensure the SnpEff database
is pre-staged: `bash scripts/rcc/download_snpeff_db.sh GRCh38.105`.

### Key parameter notes

- `workflow_name` — the registered workflow name (not `target`)
- `execution_profile` — `"local"` for testing, `"slurm"` for cluster submission
- `resource_request.queue` and `resource_request.account` — must come from the user; never inferred
- `module_loads` — full replacement of defaults; use the escape hatch to extend:
  ```python
  from flytetest.spec_executor import DEFAULT_SLURM_MODULE_LOADS
  resource_request = {"module_loads": [*DEFAULT_SLURM_MODULE_LOADS, "bcftools/1.20"], ...}
  ```
- `run_record_path` — durable path returned by `run_slurm_recipe`; required for `monitor_slurm_job` and `retry_slurm_job`

### Further reading

- `docs/gatk_pipeline_overview.md` — full biological inventory (21 tasks, 11 workflows)
- `scripts/rcc/README.md` — SIF management, module configuration, and Slurm lifecycle commands
- `AGENTS.md` — MCP/Slurm behavioural rules for coding agents
