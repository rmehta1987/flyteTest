# Open Questions Analysis — User-Authored Workflow Composition Milestone

_Run this with Claude Opus before starting Step 01. The goal is a firm recommendation
on each of the four open design questions so the implementation steps can proceed
without ambiguity. Do not implement anything — reason and recommend only._

---

## Project background (read this before answering)

**FLyteTest** is a bioinformatics pipeline framework that runs GATK4 germline variant
calling and genome annotation workflows on an HPC cluster (Slurm). Scientists interact
with it through an MCP server that exposes:

- **Power tools**: `run_task`, `run_workflow` — two-layer `bindings + inputs` surface
  for experienced users
- **Flat tools**: one Python function per workflow/task (e.g. `vc_germline_discovery`,
  `vc_prepare_reference`) — explicit named parameters, no nested dicts; what most MCP
  clients use

The registry (`src/flytetest/registry/`) is the single source of truth. Every task and
workflow has a `RegistryEntry` with typed inputs/outputs and `accepted_planner_types`
that the MCP planner uses for binding resolution.

**On-ramp milestone already delivered** (code exists today):
- `my_custom_filter` task — pure-Python QUAL threshold filter on a plain-text VCF;
  no container, no subprocess; invoked via `run_tool(python_callable=filter_vcf, ...)`
- `RegistryEntry` for `my_custom_filter`: `accepted_planner_types=("VariantCallSet",)`,
  `pipeline_stage_order=22`, `category="task"`
- `TASK_PARAMETERS["my_custom_filter"] = (("min_qual", False),)`
- Tests: `MyCustomFilterInvocationTests`, `MyCustomFilterRegistryTests`,
  `MyCustomFilterMCPExposureTests` — all passing

**What this milestone adds** (next):
- A flat MCP tool for the task (so MCP clients can call `my_custom_filter` without
  navigating the two-layer power-tool surface)
- A composed workflow that wires `my_custom_filter` into the pipeline
- A flat MCP tool for that composed workflow
- Tests and docs

---

## Existing naming conventions — read these before answering Q1 and Q3

### Workflow Python function names (`src/flytetest/workflows/variant_calling.py`)

```
prepare_reference
preprocess_sample
preprocess_sample_from_ubam
germline_short_variant_discovery      ← the upstream discovery workflow
genotype_refinement
sequential_interval_haplotype_caller
post_genotyping_refinement
small_cohort_filter
pre_call_coverage_qc
post_call_qc_summary
annotate_variants_snpeff
```

### Flat tool names (`src/flytetest/mcp_tools.py`)

```
vc_germline_discovery                 ← wraps germline_short_variant_discovery
vc_prepare_reference
vc_preprocess_sample
vc_genotype_refinement
vc_small_cohort_filter
vc_post_genotyping_refinement
vc_sequential_interval_haplotype_caller
vc_pre_call_coverage_qc
vc_post_call_qc_summary
vc_annotate_variants_snpeff           ← wraps annotate_variants_snpeff (task-level)
```

Note: `vc_germline_discovery` is 4 tokens; `vc_sequential_interval_haplotype_caller`
is 5 tokens. The convention is readability over strict brevity.

### `germline_short_variant_discovery` input surface (the upstream workflow)

```python
def germline_short_variant_discovery(
    reference_fasta: File,
    sample_ids: list[str],
    r1_paths: list[File],
    known_sites: list[File],
    intervals: list[str],
    r2_paths: list[File] | None = None,
    cohort_id: str = "cohort",
    threads: int = 4,
    gatk_sif: str = "",
    bwa_sif: str = "",
) -> File:  # returns a joint-called VCF
```

It runs: `preprocess_sample` (per sample) → `haplotype_caller` → `combine_gvcfs`
→ `joint_call_gvcfs`. Takes FASTQs in, emits a joint VCF.

---

## The four open questions

---

### Q1 — Composed workflow name

**Context:**
The composed workflow applies `my_custom_filter` to an existing VCF. It does NOT
re-run GATK — it starts from a `VariantCallSet` (a VCF already in the registry) and
applies a pure-Python filter.

**Candidate names:**
- `germline_short_variant_discovery_filtered` (from the draft plan) — mirrors the
  upstream name but signals the added step
- `qual_filter_variant_call_set` — describes what it does, not what it follows
- `custom_qual_filter` — shorter, but ambiguous about scope
- `apply_custom_filter` — verb-first, mirrors GATK naming style (`ApplyBQSR`,
  `ApplyVQSR`)

**Tradeoff to reason through:**
The workflow's input is a VCF (VariantCallSet), not raw reads. Naming it
`germline_short_variant_discovery_filtered` implies it re-runs discovery, which it
does not. A scientist browsing `list_entries` will be confused. On the other hand,
a very generic name like `apply_custom_filter` doesn't convey that this is a
quality-filtering step on variant calls.

**Question:** What name best communicates (a) that the input is an existing VCF, not
reads, and (b) that this applies a QUAL threshold filter — while fitting the existing
naming convention?

---

### Q2 — Input surface of the composed workflow

**Two options:**

**Option A — VCF-only (start from an existing VariantCallSet)**
```python
def <workflow_name>(
    vcf_path: File,
    min_qual: float = 30.0,
) -> File:
```
- Simple. The scientist already has a joint VCF (from a prior `vc_germline_discovery`
  run or from `vc_genotype_refinement`) and wants to apply a custom filter.
- Directly chains with `run_workflow` binding of `VariantCallSet`.
- The flat tool only needs `vcf_path` and `min_qual`. No SIF paths, no cluster modules.

**Option B — BAM + re-run (starts from aligned BAM, re-runs discovery + filter)**
```python
def <workflow_name>(
    reference_fasta: File,
    sample_ids: list[str],
    r1_paths: list[File],
    known_sites: list[File],
    intervals: list[str],
    min_qual: float = 30.0,
    gatk_sif: str = "",
    bwa_sif: str = "",
    ...
) -> File:
```
- Mirrors `germline_short_variant_discovery` but adds the custom filter at the end.
- Heavier: runs the full GATK pipeline then filters.
- More useful for users who want a single-button pipeline.
- Much more complex to test without real Slurm.

**Context for reasoning:**
The purpose of this milestone is to demonstrate workflow composition to users — i.e.,
"here is how you add your own step to the end of an existing workflow." Option A is a
purer demonstration of composition: you take an existing result and apply a new step.
Option B demonstrates composition but buries it inside a larger re-run.

The milestone is also explicitly the on-ramp reference. Simplicity and clarity of the
example matter more than operational completeness.

**Question:** Which option better serves the on-ramp goal of demonstrating workflow
composition clearly, and which will be easier to test reliably?

---

### Q3 — Flat tool naming for both the task and the composed workflow

**For the task flat tool** (`my_custom_filter`):
- `vc_custom_filter` — matches the `vc_*` family prefix, short, clear
- `vc_qual_filter` — describes the mechanism, not just "custom"
- `vc_my_custom_filter` — mirrors the task name exactly but verbose

**For the workflow flat tool** (the composed workflow):
Depends on the answer to Q1. Given the convention `vc_<abbreviated_workflow_name>`:
- If the workflow is named `apply_qual_filter`: flat tool = `vc_apply_qual_filter`
- If the workflow is named `qual_filter_variant_call_set`: flat tool =
  `vc_qual_filter` (collision with task above if task is also `vc_qual_filter`)
- The flat tool for `germline_short_variant_discovery` is `vc_germline_discovery`
  (abbreviates by dropping `_short_variant_`) — that abbreviation pattern is available

**Constraint:** No two flat tools in `mcp_tools.py` can share a name. If both the task
and the workflow flat tool contain "qual_filter", they must differ by at least one token.

**Question:** Given the naming convention and the no-collision constraint, what is the
cleanest pair of names for the task flat tool and the workflow flat tool?

---

### Q4 — Scope boundary: single family or multi-family?

**Option A — Stay narrowly in `variant_calling`**
This milestone delivers exactly:
1. Flat tool for `my_custom_filter` (task)
2. Composed workflow (VCF → filter → filtered VCF)
3. Flat tool for the composed workflow
4. Tests and docs

No new biology families. No new planner types. All changes stay in
`mcp_tools.py`, `workflows/variant_calling.py`, `registry/_variant_calling.py`.

**Option B — Add a second reference task in the `annotation` family**
The annotation pipeline (BRAKER3, EVM, AGAT) also has user-extensible points. A
second on-ramp reference task in that family would demonstrate that the pattern
generalizes beyond variant calling.

Possible candidate: a pure-Python GFF3 statistics task (count genes, transcripts,
exons from a GFF3 file — no external binary). This would touch:
- `src/flytetest/tasks/annotation.py` (new task)
- `src/flytetest/tasks/_gff3_helpers.py` (new pure-Python module, or reuse
  existing `src/flytetest/gff3.py`)
- `src/flytetest/registry/_annotation.py` (new entry)
- A new flat tool in `mcp_tools.py`

**Context:**
The audit prompt (`docs/pre_milestone_audit_prompt.md`) already flags checks across
the annotation family. Adding annotation scope to this milestone risks blocking on
annotation-family audit findings before the simpler variant-calling work is done.

The milestone purpose is demonstrating the pattern, not exhaustive coverage. A second
family can be its own follow-up milestone once the pattern is proven in variant_calling.

**Question:** Should this milestone stay narrowly in variant_calling, or does adding a
second family in annotation provide enough additional signal to justify the scope
increase?

---

## What to produce

For each question, give:

  **Q<N>: <name>**
  Recommendation: <your choice, one sentence>
  Reasoning: <2–4 sentences explaining why this choice fits the project's goals
              and constraints better than the alternatives>
  Risk if wrong: <one sentence on what breaks or gets confusing if the other
                  choice is made instead>

Be direct. The goal is a settled decision for each question, not a balanced survey.
After all four questions, add a **Summary** block listing the four decisions as a
punch list that can be dropped straight into the plan.
