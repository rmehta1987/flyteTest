# Step 05 — Milestone H Closure

## Model

**Sonnet 4.6** (`claude-sonnet-4-6`). The submission prompt must narrate
four cross-cutting changes accurately. Haiku risks omitting or
misstating pieces.

## Goal

1. Write the milestone CHANGELOG entry consolidating Steps 01–04.
2. Write `docs/gatk_milestone_h_submission_prompt.md` (≤100 lines).
3. Run an end-to-end smoke through the newly wired MCP surface.
4. Full verification gate (see plan §8) must pass.
5. Merge `gatkport-h` → `main`.

## Context

- Milestone H plan §6 and §8.
- Precedent: `docs/gatk_milestone_g_submission_prompt.md` (≤100 lines).
- Branch: `gatkport-h`.

## What to build

### Milestone CHANGELOG entry (prepend under `## Unreleased`)

```
### GATK Milestone H — Complete (YYYY-MM-DD)

GATK production wiring: MCP surface exposure, P0 fixes, signature and
idempotency cleanups. Closes the claim-vs-reality gap from the
2026-04-23 review — GATK is now reachable through the experiment loop.

- [x] YYYY-MM-DD Step 01: bwa_mem2_mem shell quoting + per-stage manifest filenames.
- [x] YYYY-MM-DD Step 02: 14 showcase_module assignments + 7 TASK_PARAMETERS entries + README update.
- [x] YYYY-MM-DD Step 03: variant_calling planning intent + bundle integrity + stale-assumption sweep.
- [x] YYYY-MM-DD Step 04: post_genotyping_refinement ref_path drop + prepare_reference idempotency + GenomicsDB doc.
- [x] YYYY-MM-DD full pytest green (<count> passed, <count> skipped).
- Breaking: task-level manifests moved from run_manifest.json to run_manifest_<stage>.json.
- Breaking: post_genotyping_refinement no longer accepts ref_path.
- Deferred to Milestone I: port 9 plain-Python helpers to Flyte task pattern; biology gaps (hard-filtering, variant annotation, post-call stats, pre-call coverage QC); true scatter parallelism; VQSR annotation parameterization; read-group parameterization.
```

### `docs/gatk_milestone_h_submission_prompt.md`

Target ≤100 lines. Structure mirrors the Milestone G submission prompt:

```markdown
# GATK Milestone H — Submission Prompt

Branch: `gatkport-h`

**GATK MCP surface wired; claim-vs-reality gap closed.**

Milestone H lands the four cross-cutting changes from the 2026-04-23
principal-bioinformatician review: the MCP surface now reaches every
GATK workflow and every Milestone A task; `bwa_mem2_mem` no longer
shell-interpolates user paths; per-stage manifests preserve per-task
provenance inside multi-task workflows; and three smaller cleanups
(post_genotyping_refinement signature, prepare_reference idempotency,
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
| `prepare_reference` idempotency | force=False default; skip-if-present for each inner step |
| GenomicsDB ephemeral-only doc | docs/gatk_pipeline_overview.md deferred-items |

## Key Files

| File | Role |
|---|---|
| `src/flytetest/tasks/variant_calling.py` | Shell quoting + per-stage manifests |
| `src/flytetest/workflows/variant_calling.py` | post_genotyping_refinement + prepare_reference |
| `src/flytetest/registry/_variant_calling.py` | 14 showcase_module assignments |
| `src/flytetest/server.py` | TASK_PARAMETERS entries for 7 tasks |
| `src/flytetest/planning.py` | variant_calling intent branch |
| `src/flytetest/bundles.py` | variant_calling_germline_minimal KnownSites cleanup |
| `README.md` | Current local MCP execution list + biological scope |
| `docs/gatk_pipeline_overview.md` | Deferred-items GenomicsDB note |
| `tests/test_variant_calling.py` | ShellQuoting + PerStageManifest (4 tests) |
| `tests/test_variant_calling_workflows.py` | Idempotency + Signature (6 tests) |
| `tests/test_planning.py` | VariantCallingIntent (4 tests) |
| `tests/test_bundles.py` | Bundle consistency (1 test) |
| `tests/test_mcp_contract.py` | Supported-names assertions (3 tests) |
| `tests/test_server.py` | run_workflow / run_task dispatch (2 tests) |

## Verification

```bash
VIRTUAL_ENV=.venv PATH=".venv/bin:$PATH" PYTHONPATH=src python -m compileall src/flytetest/
VIRTUAL_ENV=.venv PATH=".venv/bin:$PATH" PYTHONPATH=src pytest
rg "async def|await |asyncio\.gather|\.cid\b|IPFS|Pinata|TinyDB" src/flytetest/tasks/variant_calling.py src/flytetest/workflows/variant_calling.py
rg "shell=True" src/flytetest/tasks/variant_calling.py
rg "out of scope for Milestone A" src/flytetest/
rg "showcase_module" src/flytetest/registry/_variant_calling.py | grep -v '""' | wc -l
VIRTUAL_ENV=.venv PATH=".venv/bin:$PATH" PYTHONPATH=src python -c \
  "from flytetest.mcp_contract import SUPPORTED_WORKFLOW_NAMES, SUPPORTED_TASK_NAMES
assert 'germline_short_variant_discovery' in SUPPORTED_WORKFLOW_NAMES
assert 'haplotype_caller' in SUPPORTED_TASK_NAMES
print('mcp surface ok')"
```

## Scope Boundaries

- Plain-Python helpers (bwa_mem2_*, sort_sam, mark_duplicates,
  variant_recalibrator, apply_vqsr, merge_bam_alignment, gather_vcfs,
  calculate_genotype_posteriors) remain workflow-internal. Full Flyte
  task-pattern port is Milestone I.
- Biology additions (VariantFiltration hard-filtering, SnpEff/VEP
  annotation, bcftools-stats / MultiQC post-call, Picard
  CollectWgsMetrics pre-call) are deferred to Milestone I.
- scattered_haplotype_caller remains synchronous; true scatter is
  Milestone I.

## Phase 3 Status

Phase 3 GATK germline variant calling pipeline is now **reachable end-to-end
through the MCP experiment loop**. Remaining Phase 3 work (scope
completeness, scientific QC, parallelism) moves to Milestone I.
```

### Smoke test

Before merging, run a manual smoke through the MCP surface with a
dry-run:

```bash
VIRTUAL_ENV=.venv PATH=".venv/bin:$PATH" PYTHONPATH=src python -c "
from flytetest.server import _run_workflow_impl
result = _run_workflow_impl(
    workflow_name='germline_short_variant_discovery',
    bindings={},
    inputs={
        'ref_path': '/tmp/nonexistent/ref.fa',
        'sample_ids': ['demo'],
        'r1_paths': ['/tmp/nonexistent/r1.fq.gz'],
        'known_sites': ['/tmp/nonexistent/dbsnp.vcf'],
        'intervals': ['chr20'],
        'results_dir': '/tmp/h_smoke',
    },
    dry_run=True,
)
print('supported:', result.get('supported'))
assert result.get('supported') is True, result
"
```

This confirms `run_workflow` dispatches correctly without needing real
GATK binaries.

### Merge

```bash
git checkout main && git merge --no-ff gatkport-h && git branch -d gatkport-h
```

Do not push to remote without explicit user instruction.

## CHANGELOG

Covered by the milestone CHANGELOG block above.

## Verification

```bash
wc -l docs/gatk_milestone_h_submission_prompt.md
# expected: ≤100
VIRTUAL_ENV=.venv PATH=".venv/bin:$PATH" PYTHONPATH=src pytest
rg "### GATK Milestone H — Complete" CHANGELOG.md
```

## Commit message

```
variant_calling: close Milestone H — GATK MCP surface wiring + P0 fixes + cleanups
```

## Checklist

- [ ] Milestone CHANGELOG entry prepended under `## Unreleased`.
- [ ] `docs/gatk_milestone_h_submission_prompt.md` written, ≤100 lines.
- [ ] Full pytest suite green; count recorded in CHANGELOG.
- [ ] All §8 verification gates pass.
- [ ] Manual MCP smoke succeeds for `germline_short_variant_discovery`.
- [ ] Breaking changes called out explicitly (manifest filenames,
      `post_genotyping_refinement` signature).
- [ ] Deferred-to-Milestone-I items enumerated in both submission prompt
      and CHANGELOG.
- [ ] Branch merged with `--no-ff`; `gatkport-h` deleted.
- [ ] Checklist fully Complete (all 5 steps).
