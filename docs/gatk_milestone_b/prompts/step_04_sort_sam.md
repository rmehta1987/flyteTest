# Step 04 — `sort_sam` Task

## Goal

Add the `sort_sam` task to `src/flytetest/tasks/variant_calling.py`
and register it in `src/flytetest/registry/_variant_calling.py`.

## Context

- Plan §4: `docs/gatk_milestone_b/milestone_b_plan.md`.
- Stargazer reference (command args):
  `stargazer/src/stargazer/tasks/gatk/sort_sam.py`.
- Consumes the unsorted BAM from `bwa_mem2_mem` (Step 03).
- Uses `run_tool`, `require_path`, `build_manifest_envelope`, `_write_json`.

## Command shape

```
gatk SortSam \
  -I <aligned.bam> \
  -O <sample_id>_sorted.bam \
  --SORT_ORDER coordinate \
  --CREATE_INDEX true
```

`--CREATE_INDEX true` writes `<output>.bam.bai` alongside the BAM.

## What to build

### Task signature

```python
def sort_sam(
    bam_path: str,
    sample_id: str,
    results_dir: str,
    sif_path: str = "",
) -> dict:
```

### Output

- `<results_dir>/<sample_id>_sorted.bam`.
- Index: check both `<output>.bai` and `<output>.bam.bai` (consistent with
  `apply_bqsr` pattern in Milestone A).
- Manifest key: `"sorted_bam"`.

### `MANIFEST_OUTPUT_KEYS` addition

```python
MANIFEST_OUTPUT_KEYS: tuple[str, ...] = (
    ...,
    "aligned_bam",
    "sorted_bam",  # ← new
)
```

### Registry entry

```python
RegistryEntry(
    name="sort_sam",
    category="task",
    description="Coordinate-sort a BAM file using GATK SortSam.",
    pipeline_family="variant_calling",
    pipeline_stage_order=10,
    showcase_module="",
    accepted_planner_types=("AlignmentSet",),
    produced_planner_types=("AlignmentSet",),
    inputs=[
        InterfaceField("bam_path", "str", "Absolute path to input BAM."),
        InterfaceField("sample_id", "str", "Sample identifier."),
        InterfaceField("results_dir", "str", "Output directory."),
        InterfaceField("sif_path", "str", "Optional GATK4 SIF image path."),
    ],
    outputs=[
        InterfaceField("sorted_bam", "str", "Path to coordinate-sorted BAM."),
    ],
    compatibility=RegistryCompatibilityMetadata(
        local_resources={"cpu": "4", "memory": "16Gi"},
        slurm_hints={"cpus_per_task": 8, "mem": "32G", "time": "04:00:00"},
    ),
)
```

### Tests (`tests/test_variant_calling.py`)

Add `SortSamRegistryTests`, `SortSamInvocationTests`, `SortSamManifestTests`:

- Registry entry shape (stage_order=10).
- Command contains `"SortSam"`, `"-I"`, `"-O"`, `"--SORT_ORDER"`,
  `"coordinate"`, `"--CREATE_INDEX"`, `"true"`.
- Output path ends with `_sorted.bam`.
- Manifest emits `"sorted_bam"`.
- `FileNotFoundError` if output BAM absent.

### `CHANGELOG.md`

```
### GATK Milestone B Step 04 — sort_sam task (YYYY-MM-DD)
- [x] YYYY-MM-DD added `sort_sam` to `variant_calling.py`.
- [x] YYYY-MM-DD added `sort_sam` registry entry (stage_order 10).
- [x] YYYY-MM-DD extended MANIFEST_OUTPUT_KEYS with `"sorted_bam"`.
- [x] YYYY-MM-DD added N tests; all tests passing.
```

## Commit message

```
variant_calling: add sort_sam task + registry entry
```

## Checklist

- [ ] `sort_sam` function in `variant_calling.py`.
- [ ] `--CREATE_INDEX true` in command.
- [ ] Index file existence checked (both naming conventions).
- [ ] `MANIFEST_OUTPUT_KEYS` extended with `"sorted_bam"`.
- [ ] Registry entry at stage_order=10.
- [ ] Tests: registry shape, cmd shape, manifest emission, missing-file error.
- [ ] `pytest tests/test_variant_calling.py -xvs` green.
- [ ] CHANGELOG updated.
- [ ] Step 04 marked Complete in checklist.
