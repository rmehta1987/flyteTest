# Step 07 — Milestone I Closure

## Model

**Sonnet 4.6** (`claude-sonnet-4-6`). The closure touches CHANGELOG,
README, pipeline overview, and submission prompt — accuracy across a
large scope matters.

## Goal

1. Expose every new task and workflow from Steps 04–06 through the
   MCP surface (`showcase_module` set earlier in each step; confirm
   here and wire `TASK_PARAMETERS`).
2. Extend the `variant_calling` planning intent to cover the new
   targets.
3. Refresh the canonical pipeline reference doc.
4. Milestone CHANGELOG entry + submission prompt.
5. Full verification gate and merge.

## Context

- Milestone I plan §6 and §8.
- Precedents: `docs/gatk_milestone_g_submission_prompt.md` and the
  closure prompt from Milestone H.
- Branch: `gatkport-i`.

## What to build

### MCP surface confirmation (`src/flytetest/server.py`)

Add `TASK_PARAMETERS` entries for the five new tasks:

```python
# variant_filtration (Step 04)
"variant_filtration": (
    ("mode", True),
    ("cohort_id", True),
    ("gatk_sif", False),
),
# collect_wgs_metrics (Step 05)
"collect_wgs_metrics": (
    ("sample_id", True),
    ("picard_sif", False),
),
# bcftools_stats (Step 05)
"bcftools_stats": (
    ("cohort_id", True),
    ("bcftools_sif", False),
),
# multiqc_summarize (Step 05)
"multiqc_summarize": (
    ("cohort_id", True),
    ("multiqc_sif", False),
),
# snpeff_annotate (Step 06)
"snpeff_annotate": (
    ("cohort_id", True),
    ("snpeff_database", True),
    ("snpeff_data_dir", True),
    ("snpeff_sif", False),
),
```

Workflows inherit dispatch automatically once `showcase_module` is set.

### Planning intent extension (`src/flytetest/planning.py`)

Add to the Milestone-H variant_calling intent branch:

```python
VARIANT_CALLING_KEYWORDS |= frozenset({
    "filter", "filtration", "hard-filter", "hard filter",
    "coverage", "wgs", "insert size", "metrics",
    "stats", "statistics", "multiqc", "qc report",
    "annotate", "annotation", "snpeff", "snp eff",
})
```

Target routing additions:

| Phrase cluster | Target |
|---|---|
| "hard filter / variant filtration / small cohort filter" | `small_cohort_filter` |
| "filter SNPs / filter indels with GATK" | `variant_filtration` |
| "coverage metrics / WGS metrics / insert size" | `pre_call_coverage_qc` |
| "variant stats / bcftools stats / MultiQC" | `post_call_qc_summary` |
| "annotate variants / SnpEff / functional effect" | `annotate_variants_snpeff` |

### Bundles (`src/flytetest/bundles.py`)

Add (or extend) bundles where they make the new workflows directly
runnable:

- `variant_calling_small_cohort_chr20` — reuses the chr20 fixture
  that's too small for VQSR; applies_to: `small_cohort_filter`,
  `variant_filtration`.
- If Step 06 added `variant_calling_snpeff_chr20`, confirm it's
  available.

### `docs/gatk_pipeline_overview.md`

Rewrite the pipeline DAG and inventory tables to cover 21 tasks and
11 workflows. New DAG (text form):

```
FASTQs or uBAM
    │
    ▼
preprocess_sample | preprocess_sample_from_ubam
    │
    ├──► pre_call_coverage_qc ──► MultiQC coverage report
    │
    ▼
sequential_interval_haplotype_caller  ←── intervals (Milestone K → real scatter)
    │              OR
haplotype_caller (whole-genome)
    │
    ▼
combine_gvcfs → joint_call_gvcfs
    │
    ▼
    ├──► genotype_refinement (VQSR: large cohort)
    ├──► small_cohort_filter (hard-filter: small cohort)
    └──► post_genotyping_refinement (CGP, optional after either branch)
              │
              ▼
          post_call_qc_summary ──► MultiQC post-call report
              │
              ▼
          annotate_variants_snpeff ──► annotated VCF
```

Refresh the task table (21 rows; columns: task | stage | milestone |
key I/O), workflow table (11 rows), fixture bundle table, deferred
items section.

### README

Update "Current local MCP execution" list to include every new
variant_calling entry (14 from H + 5 new tasks + 4 new workflows + any
renamed). Update "Biological scope" bullet to mention hard-filtering,
QC bookends, and variant annotation.

### Milestone CHANGELOG entry (prepend under `## Unreleased`)

```
### GATK Milestone I — Complete (YYYY-MM-DD)

Scientific completeness + task-pattern unification. Every GATK task is
now @variant_calling_env.task-decorated with File/Dir I/O; hard-filter
fallback, QC bookends, and SnpEff annotation fill the remaining biology
gaps from the 2026-04-23 review.

- [x] YYYY-MM-DD Step 01: ported bwa_mem2_index, bwa_mem2_mem, sort_sam, mark_duplicates; RG parameterization.
- [x] YYYY-MM-DD Step 02: ported merge_bam_alignment, gather_vcfs, variant_recalibrator, apply_vqsr, calculate_genotype_posteriors.
- [x] YYYY-MM-DD Step 03: VQSR annotation parameterization + InbreedingCoeff auto-add; scattered_haplotype_caller → sequential_interval_haplotype_caller.
- [x] YYYY-MM-DD Step 04: variant_filtration (stage 17) + small_cohort_filter workflow (stage 8).
- [x] YYYY-MM-DD Step 05: collect_wgs_metrics (18) + bcftools_stats (19) + multiqc_summarize (20); pre_call_coverage_qc (workflow 9) + post_call_qc_summary (workflow 10).
- [x] YYYY-MM-DD Step 06: snpeff_annotate (21) + annotate_variants_snpeff (workflow 11).
- [x] YYYY-MM-DD Step 07: MCP TASK_PARAMETERS wired; planning intent extended; docs/gatk_pipeline_overview.md refreshed.
- [x] YYYY-MM-DD full pytest green (<count> passed, <count> skipped).
- Breaking: nine task signatures (Steps 01–02), post_genotyping_refinement no longer accepts ref_path (Milestone H), scattered_haplotype_caller renamed.
- Remaining deferred: real scheduler-level scatter (Milestone K), VEP annotation (Milestone K), MultiQC config customization (Milestone K), somatic/CNV/SV families (out of scope).
```

### `docs/gatk_milestone_i_submission_prompt.md`

Target ≤120 lines (larger than H because the scope is larger).

Structure mirrors the Milestone G and H submission prompts:

- TL;DR ("Phase 3 scientific completeness; task pattern unified").
- "What Was Built" table (scope summary).
- "Key Files" table.
- "Verification" block with the exact commands.
- "Scope Boundaries" section naming the Milestone K deferrals.
- "Phase 3 Status" — complete end-to-end across preprocessing, calling,
  refinement, filtration, QC, and annotation.

### Smoke tests

Dry-run each new workflow through the MCP surface:

```bash
VIRTUAL_ENV=.venv PATH=".venv/bin:$PATH" PYTHONPATH=src python -c "
from flytetest.server import _run_workflow_impl
for wf in ['small_cohort_filter', 'pre_call_coverage_qc', 'post_call_qc_summary', 'annotate_variants_snpeff']:
    result = _run_workflow_impl(workflow_name=wf, bindings={}, inputs={}, dry_run=True)
    assert result.get('supported') is True, (wf, result)
    print(wf, 'ok')
"
```

### Merge

```bash
git checkout main && git merge --no-ff gatkport-i && git branch -d gatkport-i
```

Do not push to remote without explicit user instruction.

## Verification

Full milestone verification gate (from plan §8):

```bash
VIRTUAL_ENV=.venv PATH=".venv/bin:$PATH" PYTHONPATH=src python -m compileall src/flytetest/
VIRTUAL_ENV=.venv PATH=".venv/bin:$PATH" PYTHONPATH=src pytest
rg "async def|await |asyncio\.gather|\.cid\b|IPFS|Pinata|TinyDB" src/flytetest/tasks/variant_calling.py src/flytetest/workflows/variant_calling.py
rg "results_dir" src/flytetest/tasks/variant_calling.py
rg "scattered_haplotype_caller" src/ tests/ docs/ --glob '!docs/gatk_milestone_f/' --glob '!CHANGELOG.md'
rg "showcase_module" src/flytetest/registry/_variant_calling.py | grep -v '""' | wc -l
rg "^def " src/flytetest/tasks/variant_calling.py
# expected: zero hits — every module-level def is decorated
wc -l docs/gatk_milestone_i_submission_prompt.md
rg "### GATK Milestone I — Complete" CHANGELOG.md
```

## Commit message

```
variant_calling: close Milestone I — scientific completeness + task-pattern unified
```

## Checklist

- [ ] `TASK_PARAMETERS` entries added for the 5 new tasks.
- [ ] Planning intent extended for filter/QC/annotation keywords.
- [ ] `docs/gatk_pipeline_overview.md` refreshed (21 tasks, 11 workflows, new DAG).
- [ ] README MCP list and biological scope updated.
- [ ] Milestone CHANGELOG entry prepended under `## Unreleased`.
- [ ] `docs/gatk_milestone_i_submission_prompt.md` authored, ≤120 lines.
- [ ] Full pytest suite green; count recorded.
- [ ] All §8 verification gates pass.
- [ ] MCP dry-run smoke succeeds for all four new workflows.
- [ ] Bundles added where appropriate (small_cohort_chr20; optional snpeff_chr20).
- [ ] Branch merged with `--no-ff`; `gatkport-i` deleted.
- [ ] Checklist fully Complete (all 7 steps).
