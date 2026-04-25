# FLyteTest — Showcase for Biological Sciences Faculty and Research Staff

_Target audience: PIs, postdocs, research computing staff familiar with Nextflow or
Snakemake. Assume skepticism. Assume they have real data and real cluster time to protect._

---

## The question you're already asking

> "We have Nextflow. We have Snakemake. They work. Why would we replace them?"

You shouldn't replace them — not for pipelines you've already written and tuned.

FLyteTest is for the part that comes **before** you open your `.nf` file: deciding
what to run, with what parameters, on which data, right now, without writing any
workflow code at all. It is for the scientist at the bench — or the PI reviewing a
student's analysis — who wants to say "run GATK germline calling on this sample"
and have something happen, correctly and reproducibly, without a three-day
configuration sprint.

If you have a Nextflow pipeline you love: keep it. FLyteTest is what you use when
you don't have one yet, when you want to prototype a new analysis step, or when you
want to verify a result end-to-end without touching a DSL.

---

## What it does, in one sentence

FLyteTest takes a plain-language request, freezes it into an auditable run recipe,
checks that all data and containers are on the cluster's shared filesystem, and
submits the Slurm job — leaving a durable record you can replay, audit, or hand to
a collaborator three years later.

---

## The five things that matter to your lab

### 1. You don't write workflow code for standard analyses

The full GATK4 germline variant calling pipeline — reference prep, alignment,
duplicate marking, BQSR, HaplotypeCaller, joint genotyping, VQSR, coverage QC, and
SnpEff annotation — is registered and ready. Describe what you want:

```python
# In an MCP-connected Claude session:

bundle = load_bundle("variant_calling_germline_minimal")
# Returns: reference paths, read paths, SIF locations, known-sites VCFs
# All pre-filled for the chr20 NA12878 smoke test

recipe = run_workflow(
    workflow_name="germline_short_variant_discovery",
    **bundle,
    execution_profile="slurm",
    resource_request={
        "queue": "caslake",
        "account": "rcc-staff",
        "memory": "32Gi",
        "walltime": "04:00:00",
    },
    dry_run=True,
)
```

`dry_run=True` means nothing runs yet. You get back a frozen recipe with:
- the exact GATK commands that will execute
- which containers will be used
- which input paths are resolved
- staging findings (is everything visible from compute nodes?)

Review it. Then submit one line:

```python
result = run_slurm_recipe(artifact_path=recipe["artifact_path"])
# Returns: job_id, run_record_path, stdout/stderr log paths
```

That's the whole submit flow. No `.nf` file. No conda environment. No YAML
configuration tree. One conversation.

---

### 2. The job is inspectable before a single CPU-hour is spent

Every `dry_run=True` call writes a frozen **run recipe** — a JSON artifact that
records:
- `workflow_name`: exactly which biological stage executes
- `inputs`: resolved absolute paths (not relative symlinks that break later)
- `runtime_images`: which SIF or module is used for each tool
- `resource_spec`: CPU, memory, walltime
- `staging_findings`: anything unreachable from compute nodes, caught before submission

You can open it, read it, email it to a collaborator, or pass it to `validate_run_recipe`
for an explicit preflight:

```python
validation = validate_run_recipe(
    artifact_path=recipe["artifact_path"],
    shared_fs_roots=["/scratch/midway3", "/project/rcc"],
)
# Returns: supported=True/False, findings list
# Any missing SIF, missing reference, or path not on shared FS appears here
# before Slurm ever sees the job
```

**Why this matters:** on a cluster with a 2FA-gated login, a job that fails 4 hours
in because a container wasn't staged costs real money and real time. `validate_run_recipe`
catches it in under a second on the login node.

---

### 3. Every run is a durable, replayable artifact

After submission:

```python
status = monitor_slurm_job(run_record_path=result["run_record_path"])
```

The run record captures: job ID, submit time, scheduler state, exit code, stdout/stderr
paths, walltime used. It persists on disk. Six months later, a reviewer asks "what
parameters did you use for that BQSR run?" You open the record and show them.

If the job fails with OOM:

```python
retry = retry_slurm_job(
    run_record_path=result["run_record_path"],
    resource_overrides={"memory": "64Gi", "walltime": "06:00:00"},
)
```

Same frozen recipe, escalated resources. The retry record links back to the original.
The chain of evidence is complete.

---

### 4. It enforces GATK Best Practices — not your memory of them

The 21 registered GATK tasks span the full germline calling pipeline:

| Stage | Tasks |
|---|---|
| Reference prep | `create_sequence_dictionary`, `index_feature_file`, `bwa_mem2_index` |
| Alignment | `bwa_mem2_mem`, `sort_sam`, `mark_duplicates`, `merge_bam_alignment` |
| BQSR | `base_recalibrator`, `apply_bqsr` |
| Variant calling | `haplotype_caller`, `combine_gvcfs`, `joint_call_gvcfs`, `gather_vcfs` |
| Refinement | `variant_recalibrator`, `apply_vqsr`, `calculate_genotype_posteriors`, `variant_filtration` |
| QC | `collect_wgs_metrics`, `bcftools_stats`, `multiqc_summarize` |
| Annotation | `snpeff_annotate` |

And 10 registered workflows that compose them into biologically ordered stages:

| Workflow | What it does |
|---|---|
| `prepare_reference` | dict + known-sites index + BWA-MEM2 index |
| `preprocess_sample` | align → sort → dedup → BQSR |
| `germline_short_variant_discovery` | per-interval HaplotypeCaller → joint call |
| `genotype_refinement` | CGP posterior refinement |
| `small_cohort_filter` | VQSR or hard-filter for small cohorts |
| `pre_call_coverage_qc` | WGS metrics before calling |
| `post_call_qc_summary` | bcftools stats + MultiQC report |
| `annotate_variants_snpeff` | SnpEff functional annotation |

Each task enforces the documented GATK parameter contract. You can't accidentally
pass the wrong known-sites VCF to the wrong stage — the binding resolver checks
types and raises a structured decline before submitting anything.

---

### 5. You can add your own analysis in Python — no DSL required

If GATK's hard-filter doesn't meet your lab's threshold, you add a custom filter:

```python
# src/flytetest/tasks/_my_lab_filter.py
def filter_vcf(in_path: Path, out_path: Path, min_qual: float) -> None:
    """Your lab's QUAL threshold logic."""
    with in_path.open() as fh_in, out_path.open("w") as fh_out:
        for line in fh_in:
            if line.startswith("#"):
                fh_out.write(line)  # always keep headers
                continue
            qual = line.split("\t")[5]
            if qual != "." and float(qual) >= min_qual:
                fh_out.write(line)
```

Wire it to the task system in ~30 lines:

```python
# Append to src/flytetest/tasks/variant_calling.py
@variant_calling_env.task
def my_custom_filter(vcf_path: File, min_qual: float = 30.0) -> File:
    in_vcf = require_path(Path(vcf_path.download_sync()), "Input VCF")
    out_dir = project_mkdtemp("my_custom_filter_")
    out_vcf = out_dir / "my_filtered.vcf"
    run_tool(python_callable=filter_vcf,
             callable_kwargs={"in_path": in_vcf, "out_path": out_vcf, "min_qual": min_qual})
    # ... manifest + return File
```

It is now a registered, MCP-exposed, Slurm-submittable task — indistinguishable from
the built-in GATK tasks. It has the same staging preflight, the same run record, the
same retry path. You wrote Python, not Nextflow DSL.

---

## Live demo — 8 minutes, three scenes

> _Run these in a terminal with the MCP server active.
> Prerequisites: `bash scripts/rcc/stage_gatk_local.sh` completed,
> GATK and bwa-mem2 SIFs staged._

### Scene 1 — Discover and load (2 minutes)

```python
# What analyses are registered?
entries = list_entries()
# → 44 registered tasks and workflows across annotation and variant calling families

# What starter kits exist?
bundles = list_bundles(pipeline_family="variant_calling")
# → variant_calling_germline_minimal (chr20 NA12878, available=True/False)
# → variant_calling_vqsr_chr20 (full VQSR demo)

# Load the germline kit
bundle = load_bundle("variant_calling_germline_minimal")
# → bindings: ReferenceGenome (chr20.fa), ReadPair (NA12878 reads)
# → runtime_images: gatk_sif, bwa_sif
# → fetch_hints if data not staged
```

**What to say:** "This is the catalogue. Every entry is typed — not a string you hope
is correct, but a validated biological contract. If the data isn't staged, the
`fetch_hints` tell you exactly which script to run."

---

### Scene 2 — Dry run and preflight (3 minutes)

```python
recipe = run_workflow(
    workflow_name="prepare_reference",
    **bundle,
    execution_profile="slurm",
    resource_request={"queue": "caslake", "account": "rcc-staff",
                      "memory": "16Gi", "walltime": "01:00:00"},
    dry_run=True,
)

print(recipe["artifact_path"])   # frozen JSON on disk — open it
print(recipe["staging_findings"])  # empty if everything is reachable

validate = validate_run_recipe(
    artifact_path=recipe["artifact_path"],
    shared_fs_roots=["/scratch/midway3", "/project/rcc"],
)
print(validate["supported"])    # True
print(validate["findings"])     # [] if all paths visible from compute nodes
```

**What to say:** "Open that JSON. That is the exact command that will run. Not an
approximation. Not a template. The exact resolved inputs and the exact container.
You audit it here, before the cluster sees it."

---

### Scene 3 — Submit, monitor, retry (3 minutes)

```python
result = run_slurm_recipe(
    artifact_path=recipe["artifact_path"],
    shared_fs_roots=["/scratch/midway3", "/project/rcc"],
)
print(result["job_id"])            # Slurm job ID
print(result["run_record_path"])   # durable record path

# Later:
status = monitor_slurm_job(run_record_path=result["run_record_path"])
print(status["scheduler_state"])   # RUNNING / COMPLETED / FAILED

# If OOM:
retry = retry_slurm_job(
    run_record_path=result["run_record_path"],
    resource_overrides={"memory": "48Gi"},
)
```

**What to say:** "The run record is a file. You can `cat` it, email it, commit it
to your analysis repo. It is evidence. The retry links to the original. Six months
from now when a reviewer asks what walltime you used, you open the record."

---

## What FLyteTest is not

| Not this | Why |
|---|---|
| A Nextflow replacement | Nextflow is excellent for multi-sample pipelines you run weekly. FLyteTest is for exploration, one-off analyses, and auditing. |
| A workflow language | There is no DSL to learn. Biology is the interface. |
| A job scheduler | Slurm does the scheduling. FLyteTest does the reasoning about what to submit and whether it is ready. |
| Magic | Every decision is inspectable. The frozen recipe is a plain JSON file. |

---

## Anticipated objections

**"Our Nextflow pipeline for WGS is already written and tested."**
Great — keep it. FLyteTest integrates with the same data and the same cluster.
Use FLyteTest when you need to prototype a new step, validate a result independently,
or hand a new student a working starting point without having them touch your pipeline.

**"We need scatter-gather across 100 samples."**
The current scatter implementation is serial (per-interval loop on one node).
Multi-sample scatter with job-array fan-out is planned but not yet implemented.
For large production cohorts today: Nextflow/Snakemake. For development, validation,
and single-sample work: FLyteTest.

**"How do I know the GATK parameters are correct?"**
Each task enforces the documented GATK4 Best Practices command shape. The test suite
has 902 tests, including invocation tests that verify parameter passing for each task.
The `variant_recalibrator` implementation enforces InbreedingCoeff for cohorts ≥10
samples automatically. The biological choices are documented in code, not in someone's
memory.

**"Who maintains this when you leave?"**
The codebase is documented in `AGENTS.md`, `DESIGN.md`, and `.codex/`. The scaffold
agent (`/.codex/agent/scaffold.md`) can produce a new registered task from a short
intent description. New students can add biology without understanding the Slurm or
MCP layers. The architecture is layered specifically so that biological knowledge
lives in tasks and workflows, not in infrastructure code.

**"Our data is too sensitive to put through an AI."**
FLyteTest runs entirely on-premise. The MCP server runs on your login node.
No data leaves your cluster. Claude (or any MCP client) issues tool calls to your
local server; the server plans and submits Slurm jobs from your session. Nothing is
uploaded, logged, or transmitted to Anthropic.

**"I can write a bash script that does this."**
Yes. FLyteTest wraps what that bash script does and adds: type-checked inputs,
staging preflight, durable run records, retry with resource escalation, and a
catalogue of registered analyses that a language model can reason about. The bash
script is still there — it's just inside a typed, auditable envelope.

---

## Current scope (honest)

| Supported today | Status |
|---|---|
| GATK4 germline calling (chr20 smoke test to full cohort) | Full pipeline |
| Eukaryotic genome annotation (BRAKER3, EVM, PASA, BUSCO, EggNOG) | Full pipeline |
| Custom pure-Python task authoring (on-ramp + scaffold agent) | Supported |
| Slurm submit / monitor / retry / cancel | Supported |
| Staging preflight (shared-FS check before sbatch) | Supported |
| Frozen, auditable run recipes | Supported |

| Not yet supported | Notes |
|---|---|
| Job-array scatter (100-sample fan-out) | Planned — Milestone K |
| VEP annotation | SnpEff only for now |
| S3/GCS artifact backends | Local filesystem only |
| STAR, HISAT2 RNA-seq pipelines | Annotation RNA-seq evidence only |

---

## Try it yourself — 15-minute setup

```bash
# 1. Clone and set up
git clone <repo> && cd flyteTest
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements-cluster.txt

# 2. Stage the GATK chr20 smoke data (~2 GB)
bash scripts/rcc/stage_gatk_local.sh
bash scripts/rcc/pull_gatk_image.sh          # or: module load gatk/4.5.0
bash scripts/rcc/build_bwa_mem2_sif.sh
bash scripts/rcc/check_gatk_fixtures.sh      # all green?

# 3. Start the MCP server
PYTHONPATH=src python3 -m flytetest.server

# 4. Connect Claude (or any MCP client) and run the three-scene demo above
```

Full HPC setup guide: `scripts/rcc/README.md`
GATK runbook: `SCIENTIST_GUIDE.md` — GATK Germline Variant Calling section

---

## What we are asking for

Not adoption. Not replacing your pipelines. We are asking for **30 minutes on a login
node** to show you that a new student can run a correctly-parameterised GATK analysis,
inspect the frozen recipe, submit it to Slurm, and monitor it — without writing a
single line of workflow code, without breaking your existing environment, and without
sending any data off-cluster.

If that is useful, we can talk about what analyses you actually need to run.
