# Step 02 — `post_genotyping_refinement` Workflow

## Model

**Haiku 4.5** (`claude-haiku-4-5-20251001`). The workflow is a single task
call with a manifest wrapper — the thinnest workflow in the codebase. All
field values and the exact structure are given explicitly below.

## Goal

Add `post_genotyping_refinement` to `src/flytetest/workflows/variant_calling.py`,
its registry entry, and unit tests.

## Context

- Milestone G plan §4: `docs/gatk_milestone_g/milestone_g_plan.md`.
- Depends on Step 01 (`calculate_genotype_posteriors`).
- Pattern: `genotype_refinement` workflow in same file (thinnest workflow
  pattern available — one or two task calls + manifest emit).

## What to build

### `src/flytetest/workflows/variant_calling.py`

Import `calculate_genotype_posteriors`. Append after `scattered_haplotype_caller`
(or after `genotype_refinement` if Milestone F hasn't landed). Signature:

```python
@variant_calling_env.task
def post_genotyping_refinement(
    ref_path: str,
    vcf_path: str,
    cohort_id: str,
    results_dir: str,
    supporting_callsets: list[str] | None = None,
    sif_path: str = "",
) -> dict:
    """Apply CalculateGenotypePosteriors to a joint-called or VQSR-filtered VCF."""
    cgp = calculate_genotype_posteriors(
        ref_path=ref_path,
        vcf_path=vcf_path,
        cohort_id=cohort_id,
        results_dir=results_dir,
        supporting_callsets=supporting_callsets,
        sif_path=sif_path,
    )
    out_dir = Path(results_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest = build_manifest_envelope(
        stage="post_genotyping_refinement",
        assumptions=[
            "vcf_path is a joint-called or VQSR-filtered cohort VCF.",
            "supporting_callsets VCFs are indexed when provided.",
        ],
        inputs={"vcf_path": vcf_path, "cohort_id": cohort_id},
        outputs={"refined_vcf_cgp": cgp["outputs"]["cgp_vcf"]},
    )
    _write_json(out_dir / "run_manifest.json", manifest)
    return manifest
```

### `MANIFEST_OUTPUT_KEYS` extension — workflows module

Append `"refined_vcf_cgp"` to `MANIFEST_OUTPUT_KEYS`.

### Registry entry

- `name`: `"post_genotyping_refinement"`, `category`: `"workflow"`,
  `pipeline_stage_order`: `7`
- `inputs`: `ref_path`, `vcf_path`, `cohort_id`, `results_dir`,
  `supporting_callsets` (optional), `sif_path`
- `outputs`: `refined_vcf_cgp` (str)
- `slurm_resource_hints`: `{"cpu": "4", "memory": "16Gi", "walltime": "02:00:00"}`
- `accepted_planner_types`: `("ReferenceGenome", "VariantCallSet")`
- `produced_planner_types`: `("VariantCallSet",)`
- `reusable_as_reference`: `True`
- `composition_constraints`:
  - `"Composable after genotype_refinement (VQSR) or directly after joint_call_gvcfs."`
  - `"supporting_callsets VCFs must be indexed when provided."`

### Tests (`tests/test_variant_calling_workflows.py`)

`PostGenotypingRefinementTests`:

- `test_post_genotyping_refinement_runs` — patches `calculate_genotype_posteriors`;
  asserts manifest has `refined_vcf_cgp` key.
- `test_registry_entry_shape` — entry at workflow stage 7 with
  `refined_vcf_cgp` output.
- `test_supporting_callsets_forwarded` — asserts that when
  `supporting_callsets=["s.vcf"]` is passed, `calculate_genotype_posteriors`
  mock receives it.

## CHANGELOG

```
### GATK Milestone G Step 02 — post_genotyping_refinement workflow (YYYY-MM-DD)
- [x] YYYY-MM-DD added post_genotyping_refinement workflow (stage 7).
- [x] YYYY-MM-DD added 3 unit tests.
- [x] YYYY-MM-DD extended workflows MANIFEST_OUTPUT_KEYS with refined_vcf_cgp.
```

## Verification

```bash
VIRTUAL_ENV=.venv PATH=".venv/bin:$PATH" PYTHONPATH=src pytest tests/test_variant_calling_workflows.py -xvs -k "PostGenotypingRefinement"
VIRTUAL_ENV=.venv PATH=".venv/bin:$PATH" PYTHONPATH=src pytest -q
```

## Commit message

```
variant_calling: add post_genotyping_refinement workflow + registry entry
```

## Checklist

- [ ] `calculate_genotype_posteriors` imported in workflow module.
- [ ] `"refined_vcf_cgp"` in workflows `MANIFEST_OUTPUT_KEYS`.
- [ ] Registry at `pipeline_stage_order=7`, `reusable_as_reference=True`.
- [ ] 3 tests passing.
- [ ] Full suite green.
- [ ] Step 02 marked Complete in checklist.
