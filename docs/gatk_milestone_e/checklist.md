# GATK4 Germline Variant Calling — Milestone E Checklist

Master plan: `docs/gatk_milestone_e/milestone_e_plan.md`
Per-step prompts: `docs/gatk_milestone_e/prompts/`

## Branch

`git checkout -b gatkport-e`

## Status Labels

`Not started` · `In progress` · `Blocked` · `Complete`

## Steps

| # | Step | Prompt | Status |
|---|------|--------|--------|
| 01 | `UnmappedBAM` planner type | `prompts/step_01_unmapped_bam_type.md` | Complete |
| 02 | `merge_bam_alignment` task | `prompts/step_02_merge_bam_alignment.md` | Complete |
| 03 | `preprocess_sample_from_ubam` workflow | `prompts/step_03_preprocess_sample_from_ubam.md` | Not started |
| 04 | Closure | `prompts/step_04_closure.md` | Not started |

## Verification Gates

- `python -m compileall src/flytetest/`
- `pytest tests/test_variant_calling.py -xvs`
- `pytest tests/test_variant_calling_workflows.py -xvs`
- `pytest tests/test_registry_manifest_contract.py -xvs`
- `pytest tests/test_planner_types.py -xvs`
- `pytest` full suite green
- `rg "async def|await |asyncio\.gather|\.cid\b|IPFS|Pinata|TinyDB" src/flytetest/tasks/variant_calling.py src/flytetest/workflows/variant_calling.py` → zero hits
- `rg "merge_bam_alignment|preprocess_sample_from_ubam" src/flytetest/registry/_variant_calling.py` → matches

## Hard Constraints

- No `RevertSam`, `SamToFastq`, or async/IPFS patterns.
- Milestone E is purely additive — no changes to existing tasks or workflows.
