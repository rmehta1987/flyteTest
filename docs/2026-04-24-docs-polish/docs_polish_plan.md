# Docs Polish Milestone Plan — 2026-04-24

## Context

The HPC scientist review (`hpc_scientist_review_responses.md`) found concrete bugs
introduced during the SIF/module refactor, plus a systemic discoverability problem:
the GATK variant-calling path is not legible to a first-time HPC user from the top-
level docs alone. The README at 656 lines has become a maintenance burden. This
milestone fixes the bugs, rewrites the README to a stable 200–300 line landing page,
and adds the missing GATK chr20 runbook to SCIENTIST_GUIDE.md.

## Pillars

1. **Correctness** — fix the three concrete bugs before any docs work
2. **Discoverability** — one canonical path from staging to Slurm submission in a
   place a scientist reads first
3. **Stability** — README becomes a stable landing page that doesn't need updating
   every milestone; inventories live in dedicated docs

## Steps

| # | Name | Scope |
|---|---|---|
| 01 | Bug fixes | bundles.py, stage_gatk_local.sh, registry module_loads |
| 02 | README rewrite | Trim 656 → ≤300 lines; audience-first doc map |
| 03 | SCIENTIST_GUIDE GATK runbook | Add chr20 end-to-end runbook section |
| 04 | scripts/rcc/README.md | HPC operator reference (SIFs, modules, staging) |
| 05 | Closure | Tests, CHANGELOG, merge |

## Bugs to fix (Step 01)

### bundles.py fetch_hint (line 171)
`"Build GATK4+bwa-mem2 SIF: bash scripts/rcc/build_gatk_local_sif.sh"` references
a deleted script. Replace with:
- `"Build bwa-mem2+samtools SIF: bash scripts/rcc/build_bwa_mem2_sif.sh"`
- `"Pull GATK4 SIF: bash scripts/rcc/pull_gatk_image.sh"`

### stage_gatk_local.sh (lines 161–167)
- Duplicate step `3.` — renumber to 3, 4, 5
- MCP example says `run_workflow(target='prepare_reference', ...)` — correct
  parameter is `workflow_name`; remove the stale example entirely or correct it

### Registry module_loads (src/flytetest/registry/_variant_calling.py)
Three workflow entries have `"gatk"` in module_loads when they don't use GATK tools:
- `pre_call_coverage_qc`: uses GATK CollectWgsMetrics + MultiQC
  → `("python/3.11.9", "apptainer/1.4.1", "gatk", "multiqc")`
- `post_call_qc_summary`: uses bcftools_stats + multiqc_summarize
  → `("python/3.11.9", "apptainer/1.4.1", "bcftools", "multiqc")`
- `annotate_variants_snpeff`: uses snpeff_annotate only
  → `("python/3.11.9", "apptainer/1.4.1", "snpeff")`

## README rewrite target structure (Step 02)

Per `docs/readme_replacement_outline.md`:
1. Title + one-paragraph summary
2. What FLyteTest Is (orientation table)
3. Current Scope (compact table by pipeline family)
4. Quick Start (scientist / developer / HPC ops — 3 short subsections)
5. Documentation Map (audience-first: Scientists / Developers / HPC+ops / Architecture)
6. Current Limits
7. Repository Layout

Content to move OUT of README:
- Full task/workflow inventory → already in `docs/gatk_pipeline_overview.md`
- Architecture detail → `DESIGN.md`
- MCP tool reference → `SCIENTIST_GUIDE.md`
- HPC/container operations → `scripts/rcc/README.md`

## Out of scope

- `runtime_images` key mismatch (`"sif_path"` vs `"gatk_sif"`) — architectural,
  separate milestone
- `run_slurm_recipe` missing `shared_fs_roots` — architectural, separate milestone
- `dry_run` empty `staging_findings` — architectural, separate milestone

## Verification gates

- [ ] `PYTHONPATH=src python -m pytest tests/ -q` — 858 pass, 1 skip
- [ ] `wc -l README.md` ≤ 300
- [ ] `grep -n "prepare_reference\|chr20" SCIENTIST_GUIDE.md` — GATK section present
- [ ] Registry module_loads correct for all three workflows
- [ ] No reference to `build_gatk_local_sif.sh` anywhere in tracked files
