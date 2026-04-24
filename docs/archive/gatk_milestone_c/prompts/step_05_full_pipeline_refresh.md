# Step 05 — Refresh `docs/mcp_full_pipeline_prompt_tests.md`

## Model

**Sonnet 4.6** (`claude-sonnet-4-6`). This step edits a ~500-line
existing doc (15 annotation stages) and must add a new Variant Calling
Pipeline section without perturbing the existing Stages 1–15. Stage
ordering, section headers, and the "## Prerequisites" block have subtle
dependencies (stage → stage bundle threading) that Haiku is prone to
corrupt. Sonnet is the right tool for careful integration into an
existing long-form doc.

## Goal

Extend `docs/mcp_full_pipeline_prompt_tests.md` with a new top-level
section named **Variant Calling Pipeline** that walks the scientist
through the raw-reads → joint-VCF path using the three variant_calling
workflows on real cluster Slurm submissions. The existing 15
annotation stages must remain byte-identical in content; only ordering
and a new final section are added.

## Context

- Existing doc (read first): `docs/mcp_full_pipeline_prompt_tests.md`
  — 499 lines, 15 stages, annotation-focused.
- Companion cluster prompt file (written in Steps 02–04):
  `docs/mcp_variant_calling_cluster_prompt_tests.md`.
- Variant calling is a separate pipeline family from annotation; it is
  **not** a continuation of Stages 1–15. The new section must make
  this independence explicit so a scientist does not attempt to feed
  annotation bundles into variant calling stages.

## Inputs to read first

- `docs/mcp_full_pipeline_prompt_tests.md` lines 1–100 —
  Prerequisites, Stage 0 (get_pipeline_status), Stage 1.
- `docs/mcp_full_pipeline_prompt_tests.md` lines 90–220 — Stage 1
  layout (template for variant stage entries).
- `docs/mcp_variant_calling_cluster_prompt_tests.md` — Scenarios 3, 4,
  and 5 (source for the workflow-prompt blocks you reuse).
- `src/flytetest/bundles.py:126-174` — `variant_calling_germline_minimal`
  bundle values.

## What to build

### Extend the top-level intro

Update the `# MCP Full Annotation Pipeline Prompt Tests` title to
`# MCP Full Pipeline Prompt Tests` (drop "Annotation" so the doc covers
both families) and add a new sentence to the opening paragraph:

> A companion **Variant Calling Pipeline** section at the bottom walks
> the germline short-variant path independently of the annotation
> stages — variant calling does not share result bundles with
> annotation and is safe to run in parallel.

### Extend Prerequisites

Add under the existing Prerequisites list (do not delete any existing
bullets):

- "For the Variant Calling Pipeline section: GATK4 SIF image at
  `data/images/gatk4.sif` (`bash scripts/rcc/pull_gatk_image.sh`),
  reference FASTA + dbSNP + Mills VCFs staged under
  `data/references/hg38/`, paired FASTQs under `data/reads/` — see
  the `variant_calling_germline_minimal` bundle in
  `src/flytetest/bundles.py` for exact paths."

### New section at end of file

After Stage 15 (the last annotation stage) and before any trailing
appendix/footer, insert:

```
---

# Variant Calling Pipeline

End-to-end prompt scenarios for the GATK4 germline short-variant path.
These stages are independent of the annotation pipeline above — they
do not share result bundles, and they run under a separate registry
family (`pipeline_family="variant_calling"`).

Run them in order; each stage consumes the result bundle of the
previous one.

## Variant Stage 0 — Sanity check

Use the `list_entries` prompt from Scenario 1 of
`docs/mcp_variant_calling_cluster_prompt_tests.md`. Confirm
`prepare_reference`, `preprocess_sample`, and
`germline_short_variant_discovery` appear with `"slurm"` in
`supported_execution_profiles`.

## Variant Stage 1 — Reference preparation (one-time)

Goal: produce `.fai`, `.dict`, BWA-MEM2 index, and known-sites `.tbi`
beside the reference FASTA. Run this once per reference; reuse across
cohorts.

Estimated time: 5–15 minutes.

Reuse the `run_workflow` prompt block from Scenario 3 of
`docs/mcp_variant_calling_cluster_prompt_tests.md` verbatim. Pass
criteria: result bundle contains `run_manifest.json` with key
`"prepared_ref"`.

## Variant Stage 2 — Sample preprocessing

Goal: raw paired FASTQ → BQSR-recalibrated BAM.

Prerequisite: Variant Stage 1 completed.

Estimated time: 20–60 minutes per sample.

Reuse the `run_workflow` prompt block from Scenario 4 of
`docs/mcp_variant_calling_cluster_prompt_tests.md` verbatim. Pass
criteria: `run_manifest.json` contains key `"preprocessed_bam"`
pointing at a `*_recal.bam` with a sibling `.bai` or `.bam.bai`.

## Variant Stage 3 — Germline short variant discovery

Goal: cohort-level raw reads → joint-called VCF.

Prerequisite: Variant Stage 1 completed. (Stage 2 is not a
prerequisite — this stage re-runs per-sample preprocessing inside the
workflow.)

Estimated time: 45–120 minutes for the chr20 fixture.

Reuse the `run_workflow` prompt block from Scenario 5 of
`docs/mcp_variant_calling_cluster_prompt_tests.md` verbatim. Pass
criteria: `run_manifest.json` contains key `"genotyped_vcf"` pointing
at a `.vcf.gz` with companion `.tbi`.

## When a variant stage fails

Variant calling uses the same Slurm lifecycle as annotation — if a
stage fails with `NODE_FAIL` or `OUT_OF_MEMORY`, apply Scenario 7 or 8
of `docs/mcp_variant_calling_cluster_prompt_tests.md` rather than
writing a new recipe.

---
```

Do NOT reproduce the full prompt blocks — reference the cluster doc by
Scenario number and file path. Reproducing them would put two copies of
the same prompt on disk; the single-source-of-truth is the cluster
doc.

## Files to create or update

- `docs/mcp_full_pipeline_prompt_tests.md` (edit in place — add intro
  sentence, Prerequisites bullet, new Variant Calling Pipeline
  section).
- `CHANGELOG.md`.
- `docs/gatk_milestone_c/checklist.md` (mark Step 05 Complete).

## Do not modify

- Any existing Stage 1–15 prompt block or Pass criteria.
- The existing Prerequisites bullets (only append).
- The Stage 0 `get_pipeline_status` block.

## CHANGELOG

```
### GATK Milestone C Step 05 — Full pipeline doc refresh for variant calling (YYYY-MM-DD)

- [x] YYYY-MM-DD retitled docs/mcp_full_pipeline_prompt_tests.md to cover both annotation and variant calling families.
- [x] YYYY-MM-DD appended Variant Calling Pipeline section (Stages 0–3) referencing docs/mcp_variant_calling_cluster_prompt_tests.md.
- [x] YYYY-MM-DD extended Prerequisites with GATK4 SIF + germline fixture staging note.
```

## Verification

```bash
rg -n "^# Variant Calling Pipeline" docs/mcp_full_pipeline_prompt_tests.md
rg -n "Variant Stage [0-3]" docs/mcp_full_pipeline_prompt_tests.md
rg -n "prepare_reference|preprocess_sample|germline_short_variant_discovery" docs/mcp_full_pipeline_prompt_tests.md
rg -n "pull_gatk_image\.sh" docs/mcp_full_pipeline_prompt_tests.md
rg -n "mcp_variant_calling_cluster_prompt_tests" docs/mcp_full_pipeline_prompt_tests.md
# Existing annotation stages must remain intact
rg -c "^## Stage " docs/mcp_full_pipeline_prompt_tests.md   # expect >= 15
rg "async def|await |asyncio\.gather|\.cid\b|IPFS|Pinata|TinyDB" docs/mcp_full_pipeline_prompt_tests.md
```

First five must return matches; stage count must be ≥ 15; Stargazer
grep gate must return zero hits.

## Commit message

```
variant_calling: refresh mcp_full_pipeline_prompt_tests.md for variant calling (Milestone C Step 05)
```

## Checklist

- [ ] Title updated to "MCP Full Pipeline Prompt Tests".
- [ ] Intro paragraph names the Variant Calling Pipeline section and
  its independence from annotation.
- [ ] Prerequisites appended (not replaced).
- [ ] Variant Calling Pipeline section added after Stage 15.
- [ ] Variant stages reference cluster doc Scenarios 3, 4, 5 rather
  than duplicating prompt blocks.
- [ ] All existing annotation stages unchanged (`git diff --stat` only
  shows additions and the single title/intro edit).
- [ ] CHANGELOG updated.
- [ ] Step 05 marked Complete in checklist.
