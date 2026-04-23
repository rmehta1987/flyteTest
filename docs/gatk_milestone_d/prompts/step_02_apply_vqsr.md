# Step 02 — `apply_vqsr` Task

## Model

**Sonnet 4.6** (`claude-sonnet-4-6`). Simpler than Step 01 but has a subtle
companion-index check (`.vcf.gz.tbi` vs `.vcf.gz.idx`) and the
`truth_sensitivity_filter_level` default logic that must match the GATK Best
Practices values exactly.

## Goal

Add `apply_vqsr` to `src/flytetest/tasks/variant_calling.py`, its registry
entry to `src/flytetest/registry/_variant_calling.py`, and unit tests to
`tests/test_variant_calling.py`.

## Context

- Milestone D plan §4: `docs/gatk_milestone_d/milestone_d_plan.md`.
- Stargazer reference (read-only):
  `stargazer/src/stargazer/tasks/gatk/apply_vqsr.py`.
- Depends on Step 01 (`variant_recalibrator`) being Complete — `apply_vqsr`
  consumes the `recal_file` and `tranches_file` emitted by it.
- Pattern to mirror: `apply_bqsr` in `src/flytetest/tasks/variant_calling.py`
  (manifest envelope, companion-index detection, `run_tool`, `sif_path`).

## What to build

### `src/flytetest/tasks/variant_calling.py`

Add after `variant_recalibrator`. Function signature:

```python
def apply_vqsr(
    ref_path: str,
    vcf_path: str,
    recal_file: str,
    tranches_file: str,
    mode: str,                              # "SNP" or "INDEL"
    cohort_id: str,
    results_dir: str,
    truth_sensitivity_filter_level: float = 0.0,   # 0.0 means "use default"
    sif_path: str = "",
) -> str:
    """Return path to the VQSR-filtered VCF."""
```

Default filter levels (applied when `truth_sensitivity_filter_level == 0.0`):
- SNP: `99.5`
- INDEL: `99.0`

These match Stargazer's `_DEFAULT_FILTER_LEVEL` and GATK Best Practices.

GATK command:

```
gatk ApplyVQSR
    -R <ref_path>
    -V <vcf_path>
    --recal-file <recal_file>
    --tranches-file <tranches_file>
    --truth-sensitivity-filter-level <level>
    --create-output-variant-index true
    -mode <mode>
    -O <results_dir>/<cohort_id>_vqsr_<mode.lower()>.vcf.gz
```

Output is always `.vcf.gz`. `--create-output-variant-index true` writes a
companion `.vcf.gz.tbi`. Check for the `.tbi` after the command and record
its path in the manifest as `"vqsr_vcf_index"` (empty string if absent).

Container invocation: same `sif_path` / `run_tool` pattern as `apply_bqsr`.

Raise `FileNotFoundError` if the output VCF does not exist after the command.

Emit manifest with `build_manifest_envelope`:

```python
{
    "vqsr_vcf": str(output_vcf),
    "vqsr_vcf_index": str(tbi_path) if tbi_path.exists() else "",
}
```

### `MANIFEST_OUTPUT_KEYS` extension

Append `"vqsr_vcf"` to the module-level `MANIFEST_OUTPUT_KEYS` tuple.
(Do not add `"vqsr_vcf_index"` — it is a companion file, not a primary
output key; consistent with how `apply_bqsr` omits the `.bai` key.)

### `src/flytetest/registry/_variant_calling.py`

Add a `RegistryEntry` for `apply_vqsr` after `variant_recalibrator`:

- `name`: `"apply_vqsr"`
- `category`: `"task"`
- `pipeline_stage_order`: `13`
- `pipeline_family`: `"variant_calling"`
- `inputs`: `ref_path`, `vcf_path`, `recal_file`, `tranches_file`, `mode`,
  `cohort_id`, `results_dir`, `truth_sensitivity_filter_level` (optional).
- `outputs`: `vqsr_vcf` (File).
- `slurm_resource_hints`: `{"cpu": "4", "memory": "16Gi", "walltime": "02:00:00"}`.
- `runtime_images`: `{"gatk_sif": "data/images/gatk4.sif"}`.
- `accepted_planner_types`: `("ReferenceGenome", "VariantCallSet")`.
- `produced_planner_types`: `("VariantCallSet",)`.
- `composition_constraints`:
  `("recal_file and tranches_file must come from variant_recalibrator for the same mode.",)`.

### `tests/test_variant_calling.py`

Add an `ApplyVQSRTests` class with:

- `test_apply_vqsr_snp_runs` — patches `run_tool`; creates dummy
  `<cohort_id>_vqsr_snp.vcf.gz` and `.vcf.gz.tbi` in `tmp_path`; asserts
  task returns the VCF path and manifest contains `"vqsr_vcf"`.
- `test_apply_vqsr_indel_runs` — same for `mode="INDEL"`.
- `test_apply_vqsr_default_filter_level_snp` — captures the cmd; asserts
  `--truth-sensitivity-filter-level` is `"99.5"` when
  `truth_sensitivity_filter_level=0.0`.
- `test_apply_vqsr_default_filter_level_indel` — asserts default is `"99.0"`.
- `test_apply_vqsr_custom_filter_level` — asserts `"99.0"` passed explicitly
  for SNP is used verbatim (overrides default).
- `test_apply_vqsr_invalid_mode` — asserts `ValueError` for `mode="BOTH"`.
- `test_apply_vqsr_missing_output_raises` — patches `run_tool` to succeed
  but does not create the output file; asserts `FileNotFoundError`.

### `CHANGELOG.md`

```
### GATK Milestone D Step 02 — apply_vqsr task (YYYY-MM-DD)
- [x] YYYY-MM-DD added apply_vqsr to src/flytetest/tasks/variant_calling.py.
- [x] YYYY-MM-DD added apply_vqsr registry entry (stage 13).
- [x] YYYY-MM-DD added 7 unit tests in ApplyVQSRTests.
- [x] YYYY-MM-DD extended MANIFEST_OUTPUT_KEYS with vqsr_vcf.
```

## Verification

```bash
VIRTUAL_ENV=.venv PATH=".venv/bin:$PATH" PYTHONPATH=src python -m compileall src/flytetest/tasks/variant_calling.py
VIRTUAL_ENV=.venv PATH=".venv/bin:$PATH" PYTHONPATH=src pytest tests/test_variant_calling.py -xvs -k "ApplyVQSR"
VIRTUAL_ENV=.venv PATH=".venv/bin:$PATH" PYTHONPATH=src pytest tests/test_registry_manifest_contract.py -xvs
rg "async def|await |asyncio\.gather|\.cid\b|IPFS|Pinata|TinyDB" src/flytetest/tasks/variant_calling.py
```

## Commit message

```
variant_calling: add apply_vqsr task + registry entry
```

## Checklist

- [ ] Task added after `variant_recalibrator` in `variant_calling.py`.
- [ ] `MANIFEST_OUTPUT_KEYS` extended with `"vqsr_vcf"`.
- [ ] Default filter levels: SNP 99.5, INDEL 99.0.
- [ ] Output filename: `<cohort_id>_vqsr_<mode.lower()>.vcf.gz`.
- [ ] `--create-output-variant-index true` in command.
- [ ] Registry entry at `pipeline_stage_order=13`.
- [ ] 7 unit tests passing.
- [ ] Registry-manifest contract test green.
- [ ] Grep gate passes.
- [ ] CHANGELOG updated.
- [ ] Step 02 marked Complete in `docs/gatk_milestone_d/checklist.md`.
