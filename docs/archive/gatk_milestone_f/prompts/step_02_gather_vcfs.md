# Step 02 — `gather_vcfs` Task

## Model

**Sonnet 4.6** (`claude-sonnet-4-6`). `GatherVcfs` is a Picard tool
(bundled in GATK4) that requires inputs to be in genomic order and
non-overlapping. The ordering invariant must be documented in
`composition_constraints` so the calling workflow enforces it.

## Goal

Add `gather_vcfs` to `src/flytetest/tasks/variant_calling.py`, its registry
entry, and unit tests. Add it to `_VARIANT_CALLING_TASK_NAMES` in the
contract test.

## Context

- Milestone F plan §4: `docs/gatk_milestone_f/milestone_f_plan.md`.
- No Stargazer reference — design from GATK docs (GatherVcfs is standard
  Picard, bundled in the GATK4 SIF).
- Pattern: `mark_duplicates` (Milestone B: `str` paths, no decorator, return
  `dict` manifest).

## What to build

### `src/flytetest/tasks/variant_calling.py`

Append after `apply_vqsr`. Signature:

```python
def gather_vcfs(
    gvcf_paths: list[str],
    sample_id: str,
    results_dir: str,
    sif_path: str = "",
) -> dict:
    """Merge ordered per-interval GVCFs into a single GVCF using GATK GatherVcfs."""
```

Validate: raise `ValueError` if `gvcf_paths` is empty.

Command:

```
gatk GatherVcfs \
  -I <gvcf1> -I <gvcf2> ... \
  -O <results_dir>/<sample_id>_gathered.g.vcf.gz \
  --CREATE_INDEX true
```

Build `-I` flags in a loop (one per path, in the same order as `gvcf_paths`
— ordering is caller's responsibility).

Output: `<sample_id>_gathered.g.vcf.gz` with companion `.tbi` (written by
`--CREATE_INDEX true`). Raise `FileNotFoundError` if absent after run.

Manifest:
```python
{"gathered_gvcf": str(out_vcf)}
```

### `MANIFEST_OUTPUT_KEYS` extension

Append `"gathered_gvcf"` to `MANIFEST_OUTPUT_KEYS`.

### Registry entry

- `name`: `"gather_vcfs"`, `category`: `"task"`, `pipeline_stage_order`: `15`
- `inputs`: `gvcf_paths` (list[str]), `sample_id`, `results_dir`, `sif_path`
- `outputs`: `gathered_gvcf` (str)
- `slurm_resource_hints`: `{"cpu": "2", "memory": "8Gi", "walltime": "01:00:00"}`
- `accepted_planner_types`: `("VariantCallSet",)`
- `produced_planner_types`: `("VariantCallSet",)`
- `composition_constraints`:
  - `"gvcf_paths must be in genomic interval order; GatherVcfs requires non-overlapping inputs."`
  - `"All input GVCFs must be indexed (.tbi or .idx next to each file)."`

### Add to `_VARIANT_CALLING_TASK_NAMES` in `tests/test_registry_manifest_contract.py`

### Tests (`tests/test_variant_calling.py`)

`GatherVcfsTests`:

- `test_gather_vcfs_runs` — patches `run_tool`, creates dummy output; asserts
  manifest has `gathered_gvcf` ending in `_gathered.g.vcf.gz`.
- `test_gather_vcfs_builds_I_flags` — captures cmd; asserts `-I` appears
  once per input path in the correct order.
- `test_gather_vcfs_empty_list_raises` — asserts `ValueError` for empty
  `gvcf_paths`.
- `test_gather_vcfs_missing_output_raises` — no output created; asserts
  `FileNotFoundError`.

## CHANGELOG

```
### GATK Milestone F Step 02 — gather_vcfs task (YYYY-MM-DD)
- [x] YYYY-MM-DD added gather_vcfs task (stage 15).
- [x] YYYY-MM-DD added registry entry.
- [x] YYYY-MM-DD added 4 unit tests in GatherVcfsTests.
- [x] YYYY-MM-DD extended MANIFEST_OUTPUT_KEYS with gathered_gvcf.
```

## Verification

```bash
VIRTUAL_ENV=.venv PATH=".venv/bin:$PATH" PYTHONPATH=src pytest tests/test_variant_calling.py -xvs -k "GatherVcfs"
VIRTUAL_ENV=.venv PATH=".venv/bin:$PATH" PYTHONPATH=src pytest tests/test_registry_manifest_contract.py -xvs
```

## Commit message

```
variant_calling: add gather_vcfs task + registry entry
```

## Checklist

- [ ] `-I` flags emitted in `gvcf_paths` order.
- [ ] `"gathered_gvcf"` in `MANIFEST_OUTPUT_KEYS`.
- [ ] Registry at `pipeline_stage_order=15`.
- [ ] `gather_vcfs` in `_VARIANT_CALLING_TASK_NAMES`.
- [ ] 4 tests passing.
- [ ] Step 02 marked Complete in checklist.
