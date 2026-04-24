# GATK4 Germline Variant Calling — Milestone I Checklist

Master plan: `docs/gatk_milestone_i/milestone_i_plan.md`
Per-step prompts: `docs/gatk_milestone_i/prompts/`

## Branch

`git checkout -b gatkport-i`

Milestone H must be merged first.

## Status Labels

`Not started` · `In progress` · `Blocked` · `Complete`

## Steps

| # | Step | Prompt | Status |
|---|------|--------|--------|
| 01 | Port preprocessing helpers + read-group params + adapt preprocess_sample | `prompts/step_01_port_preprocessing.md` | Complete |
| 02 | Port remaining 5 helpers + adapt 4 workflows | `prompts/step_02_port_remaining_helpers.md` | Complete |
| 03 | VQSR parameterization + honest scatter rename | `prompts/step_03_parameter_cleanups.md` | Complete |
| 04 | `variant_filtration` + `small_cohort_filter` workflow | `prompts/step_04_hard_filtering.md` | Complete |
| 05 | QC bookends — Picard + bcftools + MultiQC | `prompts/step_05_qc_bookends.md` | Complete |
| 06 | Variant annotation via SnpEff | `prompts/step_06_variant_annotation.md` | Complete |
| 07 | Closure — MCP re-wire, CHANGELOG, submission prompt, merge | `prompts/step_07_closure.md` | Complete |

## Verification Gates (milestone-level)

All gates passed on 2026-04-24:

- [x] `python -m compileall src/flytetest/` — clean
- [x] `pytest` — 858 passed, 1 skipped
- [x] no async/IPFS/TinyDB patterns in tasks/workflows
- [x] `rg "results_dir" src/flytetest/tasks/variant_calling.py` → zero hits
- [x] `rg "scattered_haplotype_caller" src/flytetest/` → zero hits (test assertion only)
- [x] `rg "showcase_module" ...` → 32 entries (≥20 gate met)
- [x] Every module-level `def` in tasks/variant_calling.py is `@variant_calling_env.task`-decorated

## Hard Constraints

- Milestone H must be landed on `main` before starting.
- Hard-filter expressions must come verbatim from GATK Best Practices; do not invent thresholds.
- SnpEff is the chosen annotation tool for this milestone; VEP is Milestone K.
- Real scheduler-level scatter is Milestone K; `scattered_haplotype_caller` gets renamed, not reimplemented.
- No plain-Python task helpers remain after Step 02 — every task is `@variant_calling_env.task`-decorated.
- Every new task cites its tool manual section or GATK Best Practices article in the registry entry.
- Preserve the registry-manifest contract test (`test_registry_manifest_contract.py`): new `MANIFEST_OUTPUT_KEYS` must appear on both the task-module and workflow-module constant tuples and be exercised by at least one test.
