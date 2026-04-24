# GATK4 Germline Variant Calling — Milestone B Checklist

Tracks Milestone B of the Phase 3 GATK port described in
`docs/gatk_milestone_b/milestone_b_plan.md`.

Master plan: `docs/gatk_milestone_b/milestone_b_plan.md`
Per-step submission prompts: `docs/gatk_milestone_b/prompts/`

Use this file as the canonical shared tracker for Milestone B. Future
sessions mark steps Complete, record partial progress, and note blockers
here.

## Branch

Create a new branch `gatkport-b` before starting:
`git checkout -b gatkport-b`

Merge into `main` after all steps are complete and verification gates pass.

## Status Labels

- `Not started`
- `In progress`
- `Blocked`
- `Complete`

## Steps

### Foundation

| # | Step | Prompt | Status |
|---|------|--------|--------|
| 01 | Add `ReadPair` planner type | `prompts/step_01_read_pair_type.md` | Complete |

### Preprocessing Tasks (each: task impl + registry entry + unit test + CHANGELOG line)

| # | Step | Prompt | Status |
|---|------|--------|--------|
| 02 | `bwa_mem2_index` — index reference for BWA-MEM2 | `prompts/step_02_bwa_mem2_index.md` | Complete |
| 03 | `bwa_mem2_mem` — align paired reads → unsorted BAM | `prompts/step_03_bwa_mem2_mem.md` | Complete |
| 04 | `sort_sam` — coordinate-sort BAM | `prompts/step_04_sort_sam.md` | Complete |
| 05 | `mark_duplicates` — mark PCR/optical duplicates | `prompts/step_05_mark_duplicates.md` | Complete |

### Workflow Compositions (each: workflow impl + registry entries + unit test + CHANGELOG line)

| # | Step | Prompt | Status |
|---|------|--------|--------|
| 06 | `prepare_reference` workflow | `prompts/step_06_prepare_reference.md` | Complete |
| 07 | `preprocess_sample` workflow | `prompts/step_07_preprocess_sample.md` | Complete |
| 08 | `germline_short_variant_discovery` workflow | `prompts/step_08_germline_short_variant_discovery.md` | Complete |

### Closure

| # | Step | Prompt | Status |
|---|------|--------|--------|
| 09 | Fixture bundle + container script + agent-context sweep | `prompts/step_09_closure.md` | Complete |

## Verification Gates

Before marking Milestone B Complete, all gates in the plan's §8 must pass:

- `python -m compileall src/flytetest/`
- `pytest tests/test_variant_calling.py -xvs`
- `pytest tests/test_variant_calling_workflows.py -xvs`
- `pytest tests/test_registry_manifest_contract.py -xvs`
- `pytest tests/test_planner_types.py -xvs`
- `pytest` full suite green
- `rg "async def|await |asyncio\.gather|\.cid\b|IPFS|Pinata|TinyDB" src/flytetest/tasks/variant_calling.py src/flytetest/workflows/variant_calling.py` → zero hits
- `rg "bwa_mem2_index|sort_sam|mark_duplicates|prepare_reference|preprocess_sample|germline_short_variant_discovery" src/flytetest/registry/_variant_calling.py` → matches

## Hard Constraints

- Do not copy Stargazer async/IPFS patterns.
- Do not implement `merge_bam_alignment` (uBAM path) — out of scope.
- Do not implement VQSR — still deferred.
- Do not modify frozen saved artifacts at retry/replay time.

## Out of Scope (this milestone)

- `merge_bam_alignment` — deferred.
- VQSR (`variant_recalibrator`, `apply_vqsr`) — deferred.
- Interval-scoped HaplotypeCaller — deferred.
- `docs/mcp_full_pipeline_prompt_tests.md` refresh — Milestone C.
- Actual fixture data in the repo — bundle is documentation-only.
