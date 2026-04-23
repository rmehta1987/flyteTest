# GATK4 Germline Variant Calling — Milestone D Checklist

Tracks Milestone D of the Phase 3 GATK port described in
`docs/gatk_milestone_d/milestone_d_plan.md`.

Master plan: `docs/gatk_milestone_d/milestone_d_plan.md`
Per-step submission prompts: `docs/gatk_milestone_d/prompts/`

## Branch

Create a new branch `gatkport-d` before starting:
`git checkout -b gatkport-d`

Merge into `main` after all steps are complete and verification gates pass.

## Status Labels

- `Not started`
- `In progress`
- `Blocked`
- `Complete`

## Steps

### VQSR Tasks (each: task impl + registry entry + unit test + CHANGELOG line)

| # | Step | Prompt | Status |
|---|------|--------|--------|
| 01 | `variant_recalibrator` task | `prompts/step_01_variant_recalibrator.md` | Complete |
| 02 | `apply_vqsr` task | `prompts/step_02_apply_vqsr.md` | Complete |

### Workflow Composition

| # | Step | Prompt | Status |
|---|------|--------|--------|
| 03 | `genotype_refinement` workflow | `prompts/step_03_genotype_refinement_workflow.md` | Complete |

### Fixture and Tooling

| # | Step | Prompt | Status |
|---|------|--------|--------|
| 04 | Fixture bundle + download script | `prompts/step_04_fixture_and_download_script.md` | Complete |

### Closure

| # | Step | Prompt | Status |
|---|------|--------|--------|
| 05 | Tool ref + agent-context sweep + CHANGELOG + submission prompt | `prompts/step_05_closure.md` | Not started |

## Verification Gates

Before marking Milestone D Complete, all gates in the plan's §8 must pass:

- `python -m compileall src/flytetest/`
- `pytest tests/test_variant_calling.py -xvs`
- `pytest tests/test_variant_calling_workflows.py -xvs`
- `pytest tests/test_registry_manifest_contract.py -xvs`
- `pytest` full suite green
- `rg "async def|await |asyncio\.gather|\.cid\b|IPFS|Pinata|TinyDB" src/flytetest/tasks/variant_calling.py src/flytetest/workflows/variant_calling.py` → zero hits
- `rg "variant_recalibrator|apply_vqsr|genotype_refinement" src/flytetest/registry/_variant_calling.py` → matches

## Hard Constraints

- No frozen-artifact mutation at retry/replay time.
- No async/IPFS/TinyDB patterns.
- No Stargazer async patterns in ported code.
- Do not implement `merge_bam_alignment` or interval-scoped HaplotypeCaller.

## Out of Scope (this milestone)

- `merge_bam_alignment` — deferred.
- Interval-scoped HaplotypeCaller — deferred.
- Downloading the NA12878 chr20 BAM — user-supplied via SCP.
- `CalculateGenotypePosteriors` — deferred.
