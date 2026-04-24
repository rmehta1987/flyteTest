# GATK4 Germline Variant Calling — Milestone H Checklist

Master plan: `docs/gatk_milestone_h/milestone_h_plan.md`
Per-step prompts: `docs/gatk_milestone_h/prompts/`

## Branch

`git checkout -b gatkport-h`

## Status Labels

`Not started` · `In progress` · `Blocked` · `Complete`

## Steps

| # | Step | Prompt | Status |
|---|------|--------|--------|
| 01 | P0 fixes — shell quoting + per-stage manifest filenames | `prompts/step_01_p0_fixes.md` | Complete |
| 02 | MCP surface wiring — `showcase_module` + `TASK_PARAMETERS` + README | `prompts/step_02_mcp_surface_wiring.md` | Complete |
| 03 | Planning intent + bundle integrity + stale-assumption sweep | `prompts/step_03_planning_and_bundles.md` | Complete |
| 04 | Workflow cleanups — `post_genotyping_refinement`, idempotency, docs | `prompts/step_04_cleanups.md` | Complete |
| 05 | Closure — CHANGELOG, submission prompt, smoke, merge | `prompts/step_05_closure.md` | Complete |

## Verification Gates (milestone-level)

- `python -m compileall src/flytetest/` ✓
- `pytest` full suite green — 808 passed, 1 skipped ✓
- `rg "async def|await |asyncio\.gather|\.cid\b|IPFS|Pinata|TinyDB" ...` → zero hits ✓
- `rg "shell=True" src/flytetest/tasks/variant_calling.py` → 1 hit (bwa_mem2_mem only) ✓
- `rg "out of scope for Milestone A" src/flytetest/tasks/variant_calling.py` → zero hits ✓
- `rg "showcase_module" src/flytetest/registry/_variant_calling.py` → 14 non-empty assignments ✓
- `python -c "from flytetest.mcp_contract import SUPPORTED_WORKFLOW_NAMES; assert 'germline_short_variant_discovery' in SUPPORTED_WORKFLOW_NAMES"` → exits 0 ✓

## Hard Constraints

- No porting of plain-Python helper tasks to the Flyte pattern — deferred to Milestone I.
- No new biology (hard-filtering, annotation, stats) — deferred to Milestone I.
- Per-stage manifest filename change is a breaking change for external manifest readers; document in CHANGELOG.
- `showcase_module` is the only wiring knob needed; do not duplicate target lists in `server.py` or `mcp_contract.py`.
- Preserve existing output file layouts (BAM/VCF/index paths) so smoke tests and downstream workflows keep working.
