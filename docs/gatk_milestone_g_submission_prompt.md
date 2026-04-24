# GATK Milestone G — Submission Prompt

Branch: `gatkport-g`

**Phase 3 GATK pipeline: complete.**

Milestone G closes the GATK germline variant calling pipeline by adding
`calculate_genotype_posteriors` (CGP) — a GATK4 task that refines genotype
posteriors using optional population-frequency priors — and wires it into a
thin `post_genotyping_refinement` workflow. A new end-to-end pipeline overview
document (`docs/gatk_pipeline_overview.md`) provides a single reference for
all 16 tasks and 7 workflows implemented across Milestones A through G.

## What Was Built

| Item | Stage | Tests |
|---|---|---|
| `calculate_genotype_posteriors` task | task stage 16 | 5 unit tests |
| `post_genotyping_refinement` workflow | workflow stage 7 | 3 unit tests |
| `docs/gatk_pipeline_overview.md` | — | 89 lines |

- `calculate_genotype_posteriors` — GATK4 CGP with no `-R` flag; optional
  `--supporting-callsets` per population VCF; raises `FileNotFoundError` if
  output absent.
- `post_genotyping_refinement` — single-task workflow wrapping CGP; composable
  after `genotype_refinement` (VQSR) or directly after `joint_call_gvcfs`.
- `MANIFEST_OUTPUT_KEYS` extended with `cgp_vcf` (tasks) and `refined_vcf_cgp`
  (workflows).
- `docs/tool_refs/gatk4.md` updated with full CGP section.

## Key Files

| File | Role |
|---|---|
| `src/flytetest/tasks/variant_calling.py` | `calculate_genotype_posteriors` task |
| `src/flytetest/workflows/variant_calling.py` | `post_genotyping_refinement` + updated `MANIFEST_OUTPUT_KEYS` |
| `src/flytetest/registry/_variant_calling.py` | Registry entries (task stage 16, workflow stage 7) |
| `tests/test_variant_calling.py` | 5 new CGP tests |
| `tests/test_variant_calling_workflows.py` | 3 new PostGenotypingRefinement tests |
| `tests/test_registry_manifest_contract.py` | `calculate_genotype_posteriors` added |
| `docs/gatk_pipeline_overview.md` | End-to-end pipeline DAG, task/workflow inventory |
| `docs/tool_refs/gatk4.md` | `calculate_genotype_posteriors` reference section |

## Verification

```bash
VIRTUAL_ENV=.venv PATH=".venv/bin:$PATH" PYTHONPATH=src python -m compileall src/flytetest/
VIRTUAL_ENV=.venv PATH=".venv/bin:$PATH" PYTHONPATH=src pytest
rg "async def|await |asyncio\.gather|\.cid\b|IPFS|Pinata|TinyDB" \
  src/flytetest/tasks/variant_calling.py src/flytetest/workflows/variant_calling.py
rg "calculate_genotype_posteriors|post_genotyping_refinement" src/flytetest/registry/_variant_calling.py
wc -l docs/gatk_pipeline_overview.md
```

## Scope Boundaries

- Job arrays / parallel scatter — deferred; scatter is synchronous `for` loop.
- `VariantFiltration` (hard-filtering) — deferred; user-composable.
- VQSR on CGP output — user-composable; out of scope.
- `SplitIntervals` — out of scope; users supply interval lists directly.

## Phase 3 Summary (Milestones A–G)

16 tasks · 7 workflows · 2 fixture bundles · end-to-end pipeline from FASTQ/uBAM
to a final optionally CGP-refined VCF. All tests green; no async/IPFS/TinyDB patterns.
