# GATK4 Germline Variant Calling — Milestone G Checklist

Master plan: `docs/gatk_milestone_g/milestone_g_plan.md`
Per-step prompts: `docs/gatk_milestone_g/prompts/`

## Branch

`git checkout -b gatkport-g`

## Status Labels

`Not started` · `In progress` · `Blocked` · `Complete`

## Steps

| # | Step | Prompt | Status |
|---|------|--------|--------|
| 01 | `calculate_genotype_posteriors` task | `prompts/step_01_calculate_genotype_posteriors.md` | Complete |
| 02 | `post_genotyping_refinement` workflow | `prompts/step_02_post_genotyping_refinement.md` | Complete |
| 03 | End-to-end pipeline reference + GATK closure | `prompts/step_03_closure.md` | Not started |

## Verification Gates

- `python -m compileall src/flytetest/`
- `pytest` full suite green
- `rg "async def|await |asyncio\.gather|\.cid\b|IPFS|Pinata|TinyDB" src/flytetest/tasks/variant_calling.py src/flytetest/workflows/variant_calling.py` → zero hits
- `rg "calculate_genotype_posteriors|post_genotyping_refinement" src/flytetest/registry/_variant_calling.py` → matches
- `wc -l docs/gatk_pipeline_overview.md` ≤150 lines

## Hard Constraints

- No Stargazer reference for CGP — design from GATK docs only.
- No modification of `genotype_refinement` — CGP is a separate composable workflow.
- Milestone G is purely additive.
