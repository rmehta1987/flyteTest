# GATK4 Variant Calling — Milestone A Checklist

Tracks Milestone A of the Phase 3 GATK port described in
`docs/gatk_milestone_a/milestone_a_plan.md`. Separate from:

- `docs/realtime_refactor_checklist.md` (platform architecture milestones)
- `docs/mcp_reshape/checklist.md` (MCP surface reshape — complete)
- `docs/dataserialization/checklist.md` (serialization + registry restructure — complete)

Master plan: `docs/gatk_milestone_a/milestone_a_plan.md`
Per-step submission prompts: `docs/gatk_milestone_a/prompts/`

Use this file as the canonical shared tracker for Milestone A. Future
sessions mark steps Complete, record partial progress, and note blockers
here. Keep entries scannable.

## Branch

All Milestone A work lands on branch `gatkport`. Check it out before
starting a step (`git checkout gatkport`) and commit each step there
using the commit message specified in the step's prompt file.

## Status Labels

- `Not started`
- `In progress`
- `Blocked`
- `Complete`

## Steps

Ordering groups foundation work first (planner types, env, registry
skeleton), then the seven task ports in biological dependency order,
then closure (contract tests, tool-ref doc, agent-context refresh).

### Foundation

| # | Step | Plan section | Prompt | Status |
|---|------|--------------|--------|--------|
| 01 | Add `AlignmentSet`, `VariantCallSet`, `KnownSites` planner types | §6.1 | `prompts/step_01_planner_types.md` | Complete |
| 02 | Add `variant_calling_env` + `_variant_calling.py` skeleton | §6.2 | `prompts/step_02_env_and_registry_skeleton.md` | Not started |

### Tasks (each: task impl + registry entry + unit test + CHANGELOG line)

| # | Step | Plan section | Prompt | Status |
|---|------|--------------|--------|--------|
| 03 | `create_sequence_dictionary` — reference prep | §6.3 (stage 1) | `prompts/step_03_create_sequence_dictionary.md` | Not started |
| 04 | `index_feature_file` — known-sites indexer | §6.3 (stage 2) | `prompts/step_04_index_feature_file.md` | Not started |
| 05 | `base_recalibrator` — BQSR report | §6.3 (stage 3) | `prompts/step_05_base_recalibrator.md` | Not started |
| 06 | `apply_bqsr` — apply BQSR | §6.3 (stage 4) | `prompts/step_06_apply_bqsr.md` | Not started |
| 07 | `haplotype_caller` — per-sample GVCF | §6.3 (stage 5) | `prompts/step_07_haplotype_caller.md` | Not started |
| 08 | `combine_gvcfs` — merge per-sample GVCFs | §6.3 (stage 6) | `prompts/step_08_combine_gvcfs.md` | Not started |
| 09 | `joint_call_gvcfs` — GenomicsDBImport + GenotypeGVCFs | §6.3 (stage 7) | `prompts/step_09_joint_call_gvcfs.md` | Not started |

### Closure

| # | Step | Plan section | Prompt | Status |
|---|------|--------------|--------|--------|
| 10 | Manifest contract tests + tool-ref doc + agent-context sweep | §6.4 | `prompts/step_10_closure.md` | Not started |

## Verification Gates

Before marking Milestone A Complete, the plan's §8 Verification block
must pass. Summary:

- `python -m compileall src/flytetest/`
- `pytest tests/test_variant_calling.py -xvs`
- `pytest tests/test_registry_manifest_contract.py -xvs`
- `pytest tests/test_planner_types.py -xvs` (or equivalent round-trip
  coverage file)
- `pytest` full suite green
- `rg "async def|await |asyncio\.gather|\.cid\b|IPFS|Pinata|TinyDB" src/flytetest/tasks/variant_calling.py` → zero hits
- `rg "variant_calling" src/flytetest/registry/__init__.py` → matches
- `python -c "import flytetest.server"` clean on a fresh clone with no
  Milestone B fixture data on disk

## Hard Constraints

- Do not modify frozen saved artifacts at retry/replay time (AGENTS.md).
- Do not submit a Slurm job without a frozen run record.
- Do not change `classify_slurm_failure()` semantics without a decision record.
- Do not copy Stargazer async / IPFS patterns (`async def`, `await
  asset.fetch()`, `asyncio.gather`, `.cid`, `_storage.default_client`).

## Out of Scope (this milestone)

See master plan §7. Highlights:

- Workflow compositions — Milestone B.
- Alignment / dedup preprocessing — Milestone B.
- VQSR — deferred.
- Bundles, minimal fixtures, container-pull script extensions — Milestone B.
- Cluster validation prompts — Milestone C.
