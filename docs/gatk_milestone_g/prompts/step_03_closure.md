# Step 03 — End-to-End Pipeline Reference + GATK Pipeline Closure

## Model

**Sonnet 4.6** (`claude-sonnet-4-6`). The pipeline overview doc must be
accurate across 7 workflows, 16 tasks, and 3 milestones of accumulated scope.
Haiku risks omitting items or mis-ordering the DAG.

## Goal

1. Add `calculate_genotype_posteriors` section to `docs/tool_refs/gatk4.md`.
2. Write `docs/gatk_pipeline_overview.md` (≤150 lines) — the canonical
   end-to-end GATK pipeline reference.
3. Milestone CHANGELOG entry + submission prompt.
4. All §8 verification gates.
5. Merge `gatkport-g` → `main`.

## What to build

### `docs/tool_refs/gatk4.md`

Append after `apply_vqsr` (or last existing section):

**`## calculate_genotype_posteriors`** — GATK4 CGP, FLyteTest path, command
shape (no `-R`; optional `--supporting-callsets` per entry), key argument
rationale (population priors vs pedigree-only; `supporting_callsets` from
`1000G_omni2.5.hg38.vcf.gz`), no-Stargazer note, Milestone G scope notes
(composable after VQSR or direct after joint calling).

### `docs/gatk_pipeline_overview.md`

≤150 lines. Structure:

```markdown
# GATK4 Germline Variant Calling — Pipeline Overview

One-stop reference for the full FLyteTest GATK4 pipeline.
Detailed per-task notes: docs/tool_refs/gatk4.md
Fixture bundles: src/flytetest/bundles.py
Download scripts: scripts/rcc/

## Input paths

Two preprocessing paths produce a BQSR-recalibrated BAM:

- **FASTQ path**: preprocess_sample (Milestone B)
- **uBAM path**: preprocess_sample_from_ubam (Milestone E)

## Pipeline DAG

[text diagram — raw input → preprocessing → per-sample GVCF → joint calling
→ optional VQSR → optional CGP → final VCF]

## Task inventory

Table: task name | stage | milestone | key inputs → outputs

## Workflow inventory

Table: workflow name | stage | milestone | composes

## Fixture bundles

- variant_calling_germline_minimal — small chr20 slice (Milestone B)
- variant_calling_vqsr_chr20 — full chr20 NA12878 WGS (Milestone D)

## Deferred items

- merge_bam_alignment uBAM path: complete (Milestone E)
- Interval-scoped HaplotypeCaller: complete (Milestone F)
- CalculateGenotypePosteriors: complete (Milestone G)
- Job arrays / parallel scatter: deferred
- VariantFiltration (hard-filtering): deferred
- VQSR on CGP output: user-composable
```

### Milestone CHANGELOG entry

```
### GATK Milestone G — Complete (YYYY-MM-DD)
CalculateGenotypePosteriors and full GATK pipeline closure.
- [x] YYYY-MM-DD calculate_genotype_posteriors task (stage 16) + 5 unit tests.
- [x] YYYY-MM-DD post_genotyping_refinement workflow (stage 7) + 3 unit tests.
- [x] YYYY-MM-DD docs/gatk_pipeline_overview.md written (≤150 lines).
- [x] YYYY-MM-DD docs/tool_refs/gatk4.md updated with CGP section.
- [x] YYYY-MM-DD full pytest green.
- Phase 3 GATK pipeline: complete.
- Remaining deferred: job arrays, hard-filtering, VQSR-on-CGP.
```

### `docs/gatk_milestone_g_submission_prompt.md` (≤100 lines)

Include scope summary, what-was-built, key-files table, verification
commands, scope boundaries. Mark "Phase 3 GATK pipeline: complete" explicitly.

### Checklist + merge

Mark Step 03 + milestone Complete. Merge `gatkport-g` → `main`.

## Verification

```bash
VIRTUAL_ENV=.venv PATH=".venv/bin:$PATH" PYTHONPATH=src python -m compileall src/flytetest/
VIRTUAL_ENV=.venv PATH=".venv/bin:$PATH" PYTHONPATH=src pytest
rg "async def|await |asyncio\.gather|\.cid\b|IPFS|Pinata|TinyDB" src/flytetest/tasks/variant_calling.py src/flytetest/workflows/variant_calling.py
rg "calculate_genotype_posteriors|post_genotyping_refinement" src/flytetest/registry/_variant_calling.py
test -f docs/gatk_pipeline_overview.md
wc -l docs/gatk_pipeline_overview.md
wc -l docs/gatk_milestone_g_submission_prompt.md
VIRTUAL_ENV=.venv PATH=".venv/bin:$PATH" PYTHONPATH=src python -c "import flytetest.server"
```

## Commit message

```
variant_calling: close Milestone G — CGP, post_genotyping_refinement, pipeline overview
```

## Merge

```bash
git checkout main && git merge --no-ff gatkport-g && git branch -d gatkport-g
```
