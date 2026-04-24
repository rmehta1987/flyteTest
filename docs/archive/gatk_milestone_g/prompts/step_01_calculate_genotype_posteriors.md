# Step 01 — `calculate_genotype_posteriors` Task

## Model

**Sonnet 4.6** (`claude-sonnet-4-6`). No Stargazer reference — command must
be derived from GATK Best Practices documentation. The optional
`--supporting-callsets` flag requires careful handling: omit the flag
entirely when `supporting_callsets` is empty/None (not pass an empty string).

## Goal

Add `calculate_genotype_posteriors` to `src/flytetest/tasks/variant_calling.py`,
its registry entry, and unit tests.

## Context

- Milestone G plan §4: `docs/gatk_milestone_g/milestone_g_plan.md`.
- No Stargazer reference for this task.
- GATK doc: `CalculateGenotypePosteriors` (bundled in GATK4 SIF).
- Pattern: `apply_vqsr` (same str-path, no-decorator, return dict style).
- Branch: `gatkport-g` (`git checkout -b gatkport-g`).

## What to build

### `src/flytetest/tasks/variant_calling.py`

Append after `apply_vqsr`. Signature:

```python
def calculate_genotype_posteriors(
    ref_path: str,
    vcf_path: str,
    cohort_id: str,
    results_dir: str,
    supporting_callsets: list[str] | None = None,
    sif_path: str = "",
) -> dict:
    """Refine genotype posteriors using population priors (GATK4 CGP)."""
```

Command:

```
gatk CalculateGenotypePosteriors \
  -V <vcf_path> \
  -O <results_dir>/<cohort_id>_cgp.vcf.gz \
  --create-output-variant-index true \
  [--supporting-callsets <vcf>]   # one flag per entry in supporting_callsets
```

`-R` is not required by CGP. Omit the `-R` flag entirely.
Emit `--supporting-callsets <vcf>` once per entry in `supporting_callsets`
when non-empty; omit the flag when `supporting_callsets` is `None` or `[]`.

Check for companion `.tbi` after run; record in manifest as
`"cgp_vcf_index"` (empty string if absent, consistent with `apply_vqsr`).

Raise `FileNotFoundError` if `<cohort_id>_cgp.vcf.gz` is absent after run.

Manifest:
```python
{
    "cgp_vcf": str(output_vcf),
    "cgp_vcf_index": str(tbi) if tbi.exists() else "",
}
```

### `MANIFEST_OUTPUT_KEYS` extension

Append `"cgp_vcf"` to `MANIFEST_OUTPUT_KEYS`.

### Registry entry

- `name`: `"calculate_genotype_posteriors"`, `category`: `"task"`,
  `pipeline_stage_order`: `16`
- `inputs`: `ref_path` (unused by CGP but kept for consistency), `vcf_path`,
  `cohort_id`, `results_dir`, `supporting_callsets` (optional), `sif_path`
- `outputs`: `cgp_vcf` (str)
- `slurm_resource_hints`: `{"cpu": "4", "memory": "16Gi", "walltime": "02:00:00"}`
- `accepted_planner_types`: `("VariantCallSet",)`
- `produced_planner_types`: `("VariantCallSet",)`
- `composition_constraints`:
  - `"Input VCF should be joint-called (joint_call_gvcfs) or VQSR-filtered (genotype_refinement)."`
  - `"supporting_callsets VCFs must be indexed (.tbi or .idx present)."`

### Add to `_VARIANT_CALLING_TASK_NAMES` in `tests/test_registry_manifest_contract.py`

### Tests (`tests/test_variant_calling.py`)

`CalculateGenotypePosteriorTests`:

- `test_cgp_runs_without_supporting_callsets` — no `--supporting-callsets`
  in cmd when `supporting_callsets=None`.
- `test_cgp_runs_with_supporting_callsets` — asserts `--supporting-callsets`
  appears once per entry when list is non-empty.
- `test_cgp_output_filename` — manifest `cgp_vcf` ends in `_cgp.vcf.gz`.
- `test_cgp_missing_output_raises` — `FileNotFoundError` when output absent.
- `test_cgp_no_R_flag` — asserts `-R` does **not** appear in the cmd.

## CHANGELOG

```
### GATK Milestone G Step 01 — calculate_genotype_posteriors task (YYYY-MM-DD)
- [x] YYYY-MM-DD added calculate_genotype_posteriors (stage 16).
- [x] YYYY-MM-DD added 5 unit tests.
- [x] YYYY-MM-DD extended MANIFEST_OUTPUT_KEYS with cgp_vcf.
```

## Verification

```bash
VIRTUAL_ENV=.venv PATH=".venv/bin:$PATH" PYTHONPATH=src pytest tests/test_variant_calling.py -xvs -k "CalculateGenotype"
VIRTUAL_ENV=.venv PATH=".venv/bin:$PATH" PYTHONPATH=src pytest tests/test_registry_manifest_contract.py -xvs
```

## Commit message

```
variant_calling: add calculate_genotype_posteriors task + registry entry
```

## Checklist

- [ ] `--supporting-callsets` omitted when `supporting_callsets` is None/[].
- [ ] No `-R` flag in command.
- [ ] `"cgp_vcf"` in `MANIFEST_OUTPUT_KEYS`.
- [ ] Registry at `pipeline_stage_order=16`.
- [ ] 5 tests passing.
- [ ] Step 01 marked Complete in checklist.
