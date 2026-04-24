# GATK Milestone H — Submission Prompt

Branch: `gatkport-h`

**GATK MCP surface wired; claim-vs-reality gap closed.**

Milestone H lands four cross-cutting changes from the 2026-04-23 review:
MCP surface now reaches every GATK workflow and every Milestone A task;
`bwa_mem2_mem` no longer shell-interpolates user paths; per-stage manifests
preserve per-task provenance inside multi-task workflows; and three smaller
cleanups (post_genotyping_refinement signature, prepare_reference idempotency,
GenomicsDB ephemeral-only doc) close the drift items.

## What Was Built

| Item | Scope |
|---|---|
| `showcase_module` on 14 registry entries | 7 workflows + 7 Milestone A tasks |
| `TASK_PARAMETERS` for 7 exposed tasks | server.py dispatch surface |
| `variant_calling` planning intent branch | planning.py natural-language matching |
| P0 shell-injection fix | bwa_mem2_mem shlex.quote on all user paths |
| P0 manifest collision fix | run_manifest_<stage>.json per-task naming |
| `post_genotyping_refinement` signature | unused ref_path dropped |
| `prepare_reference` idempotency | force=False default; skip-if-present |
| GenomicsDB ephemeral-only doc | docs/gatk_pipeline_overview.md |
| Resolver safety | unregistered planner types return graceful miss |

## Key Files

| File | Role |
|---|---|
| `src/flytetest/tasks/variant_calling.py` | Shell quoting + per-stage manifests |
| `src/flytetest/workflows/variant_calling.py` | post_genotyping_refinement + prepare_reference |
| `src/flytetest/registry/_variant_calling.py` | 14 showcase_module assignments |
| `src/flytetest/server.py` | TASK_PARAMETERS + GATK dispatch branches |
| `src/flytetest/planning.py` | variant_calling intent branch |
| `src/flytetest/bundles.py` | variant_calling_germline_minimal KnownSites cleanup |
| `src/flytetest/resolver.py` | Graceful miss for unregistered planner types |
| `README.md` | Current local MCP execution list + biological scope |
| `docs/gatk_pipeline_overview.md` | Deferred-items GenomicsDB note |

## Verification

```bash
VIRTUAL_ENV=.venv PATH=".venv/bin:$PATH" PYTHONPATH=src python -m compileall src/flytetest/
VIRTUAL_ENV=.venv PATH=".venv/bin:$PATH" PYTHONPATH=src pytest
rg "shell=True" src/flytetest/tasks/variant_calling.py
rg "out of scope for Milestone A" src/flytetest/
rg 'showcase_module="flytetest' src/flytetest/registry/_variant_calling.py | wc -l
# expected: 14
```

## Scope Boundaries

- Plain-Python helpers (bwa_mem2_*, sort_sam, mark_duplicates, etc.) remain
  workflow-internal. Full Flyte task-pattern port is Milestone I.
- Biology additions (VariantFiltration, SnpEff/VEP, bcftools-stats, etc.) deferred.
- scattered_haplotype_caller remains synchronous; true scatter is Milestone I.

## Phase 3 Status

Phase 3 GATK germline variant calling pipeline is now **reachable end-to-end
through the MCP experiment loop**. Remaining Phase 3 work (scope completeness,
scientific QC, parallelism) moves to Milestone I.
