# GATK4 Germline Variant Calling — Milestone F Checklist

Master plan: `docs/gatk_milestone_f/milestone_f_plan.md`
Per-step prompts: `docs/gatk_milestone_f/prompts/`

## Branch

`git checkout -b gatkport-f`

## Status Labels

`Not started` · `In progress` · `Blocked` · `Complete`

## Steps

| # | Step | Prompt | Status |
|---|------|--------|--------|
| 01 | Extend `haplotype_caller` with optional intervals | `prompts/step_01_haplotype_caller_intervals.md` | Not started |
| 02 | `gather_vcfs` task | `prompts/step_02_gather_vcfs.md` | Not started |
| 03 | `scattered_haplotype_caller` workflow | `prompts/step_03_scattered_haplotype_caller.md` | Not started |
| 04 | Closure | `prompts/step_04_closure.md` | Not started |

## Verification Gates

- `python -m compileall src/flytetest/`
- `pytest tests/test_variant_calling.py -xvs`
- `pytest tests/test_variant_calling_workflows.py -xvs`
- `pytest tests/test_registry_manifest_contract.py -xvs`
- `pytest` full suite green
- `rg "async def|await |asyncio\.gather|\.cid\b|IPFS|Pinata|TinyDB" src/flytetest/tasks/variant_calling.py src/flytetest/workflows/variant_calling.py` → zero hits
- `rg "gather_vcfs|scattered_haplotype_caller" src/flytetest/registry/_variant_calling.py` → matches
- Existing `HaplotypeCallerInvocationTests` still pass

## Hard Constraints

- `haplotype_caller` extension must be backward compatible (`intervals=None`
  produces identical output to pre-Milestone-F).
- Sequential Python for loop only — no asyncio, no job arrays.
- `SplitIntervals` is out of scope; user supplies intervals.
