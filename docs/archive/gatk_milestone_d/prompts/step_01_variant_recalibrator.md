# Step 01 — `variant_recalibrator` Task

## Model

**Sonnet 4.6** (`claude-sonnet-4-6`). Requires careful adaptation of the
Stargazer reference (async/IPFS) into the synchronous FLyteTest task pattern.
The per-resource flag construction and the SNP vs INDEL annotation list branch
are non-trivial and need to match the GATK CLI contract exactly.

## Goal

Add `variant_recalibrator` to `src/flytetest/tasks/variant_calling.py`, its
registry entry to `src/flytetest/registry/_variant_calling.py`, and unit tests
to `tests/test_variant_calling.py`.

## Context

- Milestone D plan §3 and §4: `docs/gatk_milestone_d/milestone_d_plan.md`.
- Stargazer reference (read-only, command shape only):
  `stargazer/src/stargazer/tasks/gatk/variant_recalibrator.py`.
- Existing task pattern to mirror: `base_recalibrator` in
  `src/flytetest/tasks/variant_calling.py` (manifest envelope, `run_tool`,
  `sif_path` handling).
- `KnownSites` planner type (already has `training`, `truth`, `prior`,
  `vqsr_mode` fields): `src/flytetest/planner_types.py`.
- Registry pattern: `src/flytetest/registry/_variant_calling.py` —
  match the `RegistryEntry` shape of the nearest existing task entry.
- Branch: `gatkport-d`. Create with `git checkout -b gatkport-d` if not
  already on it.

## What to build

### `src/flytetest/tasks/variant_calling.py`

Add after `joint_call_gvcfs`. Function signature:

```python
def variant_recalibrator(
    ref_path: str,
    vcf_path: str,
    known_sites: list[str],           # list of VCF paths
    known_sites_flags: list[dict],    # parallel list of flag dicts per site
    mode: str,                        # "SNP" or "INDEL"
    cohort_id: str,
    results_dir: str,
    sif_path: str = "",
) -> tuple[str, str]:
    """Return (recal_file, tranches_file) paths."""
```

`known_sites_flags` entries are dicts with keys `resource_name`, `known`,
`training`, `truth`, `prior` matching the `KnownSites` planner fields.
Passing as parallel lists (rather than dataclasses) keeps the task signature
JSON-serialisable without importing planner types into the task layer.

GATK command:

```
gatk VariantRecalibrator
    -R <ref_path>
    -V <vcf_path>
    -mode <mode>
    -O <results_dir>/<cohort_id>_<mode.lower()>.recal
    --tranches-file <results_dir>/<cohort_id>_<mode.lower()>.tranches
    --resource:<name>,known=<known>,training=<training>,truth=<truth>,prior=<prior> <vcf_path>
        (one flag per entry in known_sites / known_sites_flags)
    -an QD -an MQ -an MQRankSum -an ReadPosRankSum -an FS -an SOR   (if mode == "SNP")
    -an QD -an FS -an SOR                                            (if mode == "INDEL")
```

Boolean fields must be lowercased strings (`"true"` / `"false"`) — GATK
rejects Python booleans. `prior` defaults to `"10"` if `None`.

Container invocation: when `sif_path` is non-empty, wrap via `run_tool` with
`sif_path` — same pattern as `base_recalibrator`.

Raise `FileNotFoundError` if `output_recal` does not exist after the command.

Emit manifest with `build_manifest_envelope`:

```python
{
    "recal_file": str(output_recal),
    "tranches_file": str(output_tranches),
}
```

### `MANIFEST_OUTPUT_KEYS` extension

Append `"recal_file"` and `"tranches_file"` to the module-level
`MANIFEST_OUTPUT_KEYS` tuple (do not remove existing keys).

### `src/flytetest/registry/_variant_calling.py`

Add a `RegistryEntry` for `variant_recalibrator` after `joint_call_gvcfs`:

- `name`: `"variant_recalibrator"`
- `category`: `"task"`
- `pipeline_stage_order`: `12`
- `pipeline_family`: `"variant_calling"`
- `inputs`: `ref_path`, `vcf_path`, `known_sites`, `known_sites_flags`,
  `mode`, `cohort_id`, `results_dir` (all typed `InterfaceField`).
- `outputs`: `recal_file` (File), `tranches_file` (File).
- `slurm_resource_hints`: `{"cpu": "4", "memory": "16Gi", "walltime": "04:00:00"}`.
- `runtime_images`: `{"gatk_sif": "data/images/gatk4.sif"}`.
- `accepted_planner_types`: `("ReferenceGenome", "VariantCallSet", "KnownSites")`.
- `produced_planner_types`: `()`.

### `tests/test_variant_calling.py`

Add a `VariantRecalibratorTests` class with:

- `test_variant_recalibrator_snp_runs` — patches `run_tool` / `subprocess.run`
  to return success; creates dummy `<cohort_id>_snp.recal` and `.tranches`
  files in a `tmp_path`; asserts task returns `(recal_path, tranches_path)`,
  both exist, and manifest contains `"recal_file"` and `"tranches_file"`.
- `test_variant_recalibrator_indel_runs` — same for `mode="INDEL"`.
- `test_variant_recalibrator_invalid_mode` — asserts `ValueError` for
  `mode="MIXED"`.
- `test_variant_recalibrator_resource_flags_snp` — captures the `cmd` list
  passed to `run_tool`; asserts `-an MQ` is present (SNP-only annotation)
  and `-an MQRankSum` is present; asserts `-mode SNP`.
- `test_variant_recalibrator_resource_flags_indel` — same but asserts
  `-an MQ` is NOT present and `-mode INDEL`.

### `CHANGELOG.md`

```
### GATK Milestone D Step 01 — variant_recalibrator task (YYYY-MM-DD)
- [x] YYYY-MM-DD added variant_recalibrator to src/flytetest/tasks/variant_calling.py.
- [x] YYYY-MM-DD added variant_recalibrator registry entry (stage 12).
- [x] YYYY-MM-DD added 5 unit tests in VariantRecalibratorTests.
- [x] YYYY-MM-DD extended MANIFEST_OUTPUT_KEYS with recal_file, tranches_file.
```

## Verification

```bash
VIRTUAL_ENV=.venv PATH=".venv/bin:$PATH" PYTHONPATH=src python -m compileall src/flytetest/tasks/variant_calling.py
VIRTUAL_ENV=.venv PATH=".venv/bin:$PATH" PYTHONPATH=src pytest tests/test_variant_calling.py -xvs -k "VariantRecalibrator"
VIRTUAL_ENV=.venv PATH=".venv/bin:$PATH" PYTHONPATH=src pytest tests/test_registry_manifest_contract.py -xvs
rg "async def|await |asyncio\.gather|\.cid\b|IPFS|Pinata|TinyDB" src/flytetest/tasks/variant_calling.py
```

All must pass; grep gate returns zero hits.

## Commit message

```
variant_calling: add variant_recalibrator task + registry entry
```

## Checklist

- [ ] Task added after `joint_call_gvcfs` in `variant_calling.py`.
- [ ] `MANIFEST_OUTPUT_KEYS` extended with `"recal_file"`, `"tranches_file"`.
- [ ] Registry entry at `pipeline_stage_order=12`.
- [ ] SNP annotation list includes MQ, MQRankSum, ReadPosRankSum; INDEL list omits them.
- [ ] Resource flag format: `--resource:{name},known=...,training=...,truth=...,prior=...`.
- [ ] Boolean fields are lowercased strings, not Python booleans.
- [ ] 5 unit tests passing.
- [ ] Registry-manifest contract test green.
- [ ] Grep gate passes.
- [ ] CHANGELOG updated.
- [ ] Step 01 marked Complete in `docs/gatk_milestone_d/checklist.md`.
