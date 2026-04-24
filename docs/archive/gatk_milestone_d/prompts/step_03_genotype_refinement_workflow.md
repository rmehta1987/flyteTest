# Step 03 — `genotype_refinement` Workflow

## Model

**Sonnet 4.6** (`claude-sonnet-4-6`). The two-pass VQSR structure (SNP → INDEL
on SNP-filtered VCF) is subtle: the INDEL pass must consume the SNP-filtered
VCF, not the original joint VCF. Getting the pass ordering wrong produces a
valid-looking but incorrect pipeline.

## Goal

Add `genotype_refinement` to `src/flytetest/workflows/variant_calling.py`,
its registry entries to `src/flytetest/registry/_variant_calling.py`, and
unit tests to `tests/test_variant_calling_workflows.py`.

## Context

- Milestone D plan §4: `docs/gatk_milestone_d/milestone_d_plan.md`.
- Depends on Steps 01 and 02 (both tasks Complete).
- Existing workflow pattern to mirror: `preprocess_sample` in
  `src/flytetest/workflows/variant_calling.py` (sequential task calls,
  manifest emission, `@variant_calling_env.task` decorator).
- `MANIFEST_OUTPUT_KEYS` in `src/flytetest/workflows/variant_calling.py`
  must be extended with `"refined_vcf"`.

## What to build

### `src/flytetest/workflows/variant_calling.py`

Add after `germline_short_variant_discovery`. Function signature:

```python
def genotype_refinement(
    ref_path: str,
    joint_vcf: str,
    snp_resources: list[str],           # VCF paths for SNP VQSR
    snp_resource_flags: list[dict],     # parallel flag dicts per SNP resource
    indel_resources: list[str],         # VCF paths for INDEL VQSR
    indel_resource_flags: list[dict],   # parallel flag dicts per INDEL resource
    cohort_id: str,
    results_dir: str,
    snp_filter_level: float = 0.0,      # 0.0 → use apply_vqsr default (99.5)
    indel_filter_level: float = 0.0,    # 0.0 → use apply_vqsr default (99.0)
    sif_path: str = "",
) -> str:
    """Return path to VQSR-refined VCF."""
```

Two-pass execution (order is mandatory):

```python
# Pass 1 — SNP
snp_recal, snp_tranches = variant_recalibrator(
    ref_path, joint_vcf, snp_resources, snp_resource_flags,
    "SNP", cohort_id, results_dir, sif_path)
snp_vcf = apply_vqsr(
    ref_path, joint_vcf, snp_recal, snp_tranches,
    "SNP", cohort_id, results_dir, snp_filter_level, sif_path)

# Pass 2 — INDEL (input is the SNP-filtered VCF, not joint_vcf)
indel_recal, indel_tranches = variant_recalibrator(
    ref_path, snp_vcf, indel_resources, indel_resource_flags,
    "INDEL", cohort_id, results_dir, sif_path)
refined_vcf = apply_vqsr(
    ref_path, snp_vcf, indel_recal, indel_tranches,
    "INDEL", cohort_id, results_dir, indel_filter_level, sif_path)
```

Emit manifest:

```python
build_manifest_envelope(results_dir, stage="genotype_refinement", outputs={
    "refined_vcf": str(refined_vcf),
})
```

### `MANIFEST_OUTPUT_KEYS` extension — workflows module

Append `"refined_vcf"` to `MANIFEST_OUTPUT_KEYS` in
`src/flytetest/workflows/variant_calling.py`.

### `src/flytetest/registry/_variant_calling.py`

Add a `RegistryEntry` for `genotype_refinement` after `germline_short_variant_discovery`:

- `name`: `"genotype_refinement"`
- `category`: `"workflow"`
- `pipeline_stage_order`: `4`
- `pipeline_family`: `"variant_calling"`
- `inputs`: `ref_path`, `joint_vcf`, `snp_resources`, `snp_resource_flags`,
  `indel_resources`, `indel_resource_flags`, `cohort_id`, `results_dir`,
  `snp_filter_level` (optional), `indel_filter_level` (optional).
- `outputs`: `refined_vcf` (File).
- `slurm_resource_hints`: `{"cpu": "8", "memory": "32Gi", "walltime": "08:00:00"}`.
- `runtime_images`: `{"gatk_sif": "data/images/gatk4.sif"}`.
- `accepted_planner_types`: `("ReferenceGenome", "VariantCallSet", "KnownSites")`.
- `produced_planner_types`: `("VariantCallSet",)`.
- `composition_constraints`:
  `("Requires a joint-called VCF with sufficient variant count for VQSR training (chr20 slice is too small; use full chr20 WGS at ≥30x).",)`.

### `tests/test_variant_calling_workflows.py`

Add a `GenotypeRefinementWorkflowTests` class with:

- `test_genotype_refinement_runs` — patches `variant_recalibrator` and
  `apply_vqsr` so each returns dummy paths; asserts the workflow returns a
  path string and emits `run_manifest.json` with `"refined_vcf"` key.
- `test_genotype_refinement_indel_uses_snp_vcf` — captures the second
  `variant_recalibrator` call's `vcf_path` argument; asserts it equals the
  return value of the first `apply_vqsr` call (not `joint_vcf`).
- `test_genotype_refinement_manifest_key` — asserts `run_manifest.json`
  contains key `"refined_vcf"` pointing at a path ending in
  `_vqsr_indel.vcf.gz`.

### `CHANGELOG.md`

```
### GATK Milestone D Step 03 — genotype_refinement workflow (YYYY-MM-DD)
- [x] YYYY-MM-DD added genotype_refinement workflow to src/flytetest/workflows/variant_calling.py.
- [x] YYYY-MM-DD added genotype_refinement registry entry (workflow stage 4).
- [x] YYYY-MM-DD added 3 unit tests in GenotypeRefinementWorkflowTests.
- [x] YYYY-MM-DD extended workflows MANIFEST_OUTPUT_KEYS with refined_vcf.
```

## Verification

```bash
VIRTUAL_ENV=.venv PATH=".venv/bin:$PATH" PYTHONPATH=src python -m compileall src/flytetest/workflows/variant_calling.py
VIRTUAL_ENV=.venv PATH=".venv/bin:$PATH" PYTHONPATH=src pytest tests/test_variant_calling_workflows.py -xvs -k "GenotypeRefinement"
VIRTUAL_ENV=.venv PATH=".venv/bin:$PATH" PYTHONPATH=src pytest tests/test_registry_manifest_contract.py -xvs
rg "async def|await |asyncio\.gather|\.cid\b|IPFS|Pinata|TinyDB" src/flytetest/workflows/variant_calling.py
rg "genotype_refinement" src/flytetest/registry/_variant_calling.py
```

## Commit message

```
variant_calling: add genotype_refinement workflow + registry entry
```

## Checklist

- [ ] Workflow added to `variant_calling.py` after `germline_short_variant_discovery`.
- [ ] INDEL pass consumes SNP-filtered VCF, not the original `joint_vcf`.
- [ ] `MANIFEST_OUTPUT_KEYS` in workflows module extended with `"refined_vcf"`.
- [ ] Registry entry at `pipeline_stage_order=4`, `category="workflow"`.
- [ ] `composition_constraints` notes the chr20 slice limitation.
- [ ] 3 unit tests passing, including the INDEL-uses-SNP-VCF assertion.
- [ ] Registry-manifest contract test green.
- [ ] Grep gate passes.
- [ ] CHANGELOG updated.
- [ ] Step 03 marked Complete in `docs/gatk_milestone_d/checklist.md`.
