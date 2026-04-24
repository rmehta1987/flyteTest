# Step 05 — `mark_duplicates` Task

## Goal

Add the `mark_duplicates` task to `src/flytetest/tasks/variant_calling.py`
and register it in `src/flytetest/registry/_variant_calling.py`.

## Context

- Plan §4: `docs/gatk_milestone_b/milestone_b_plan.md`.
- Stargazer reference (command args):
  `stargazer/src/stargazer/tasks/gatk/mark_duplicates.py`.
- Consumes the coordinate-sorted BAM from `sort_sam` (Step 04).
- Uses `run_tool`, `require_path`, `build_manifest_envelope`, `_write_json`.

## Command shape

```
gatk MarkDuplicates \
  -I <sorted.bam> \
  -O <sample_id>_marked_duplicates.bam \
  -M <sample_id>_duplicate_metrics.txt \
  --CREATE_INDEX true
```

## What to build

### Task signature

```python
def mark_duplicates(
    bam_path: str,
    sample_id: str,
    results_dir: str,
    sif_path: str = "",
) -> dict:
```

### Output

- `<results_dir>/<sample_id>_marked_duplicates.bam` — deduped BAM.
- `<results_dir>/<sample_id>_duplicate_metrics.txt` — metrics file.
- Index: `--CREATE_INDEX true` writes BAI; check both naming conventions.
- Manifest keys: `"dedup_bam"` (BAM path), `"duplicate_metrics"` (metrics path).

### `MANIFEST_OUTPUT_KEYS` addition

```python
MANIFEST_OUTPUT_KEYS: tuple[str, ...] = (
    "sequence_dict", "feature_index", "bqsr_report",
    "recalibrated_bam", "gvcf", "combined_gvcf", "joint_vcf",
    "bwa_index_prefix", "aligned_bam", "sorted_bam",
    "dedup_bam", "duplicate_metrics",  # ← new
)
```

### Registry entry

```python
RegistryEntry(
    name="mark_duplicates",
    category="task",
    description="Mark PCR and optical duplicate reads using GATK MarkDuplicates.",
    pipeline_family="variant_calling",
    pipeline_stage_order=11,
    showcase_module="",
    accepted_planner_types=("AlignmentSet",),
    produced_planner_types=("AlignmentSet",),
    inputs=[
        InterfaceField("bam_path", "str", "Absolute path to coordinate-sorted BAM."),
        InterfaceField("sample_id", "str", "Sample identifier."),
        InterfaceField("results_dir", "str", "Output directory."),
        InterfaceField("sif_path", "str", "Optional GATK4 SIF image path."),
    ],
    outputs=[
        InterfaceField("dedup_bam", "str", "Path to duplicate-marked BAM."),
        InterfaceField("duplicate_metrics", "str", "Path to duplicate metrics file."),
    ],
    compatibility=RegistryCompatibilityMetadata(
        local_resources={"cpu": "4", "memory": "16Gi"},
        slurm_hints={"cpus_per_task": 8, "mem": "32G", "time": "04:00:00"},
    ),
)
```

### Tests (`tests/test_variant_calling.py`)

Add `MarkDuplicatesRegistryTests`, `MarkDuplicatesInvocationTests`,
`MarkDuplicatesManifestTests`:

- Registry entry shape (stage_order=11, two outputs).
- Command contains `"MarkDuplicates"`, `"-I"`, `"-O"`, `"-M"`,
  `"--CREATE_INDEX"`, `"true"`.
- Output BAM name contains `_marked_duplicates`.
- Metrics filename contains `_duplicate_metrics`.
- Manifest emits both `"dedup_bam"` and `"duplicate_metrics"`.
- `FileNotFoundError` if output BAM absent.

### `CHANGELOG.md`

```
### GATK Milestone B Step 05 — mark_duplicates task (YYYY-MM-DD)
- [x] YYYY-MM-DD added `mark_duplicates` to `variant_calling.py`.
- [x] YYYY-MM-DD added `mark_duplicates` registry entry (stage_order 11).
- [x] YYYY-MM-DD extended MANIFEST_OUTPUT_KEYS with `"dedup_bam"`, `"duplicate_metrics"`.
- [x] YYYY-MM-DD added N tests; all tests passing.
```

## Commit message

```
variant_calling: add mark_duplicates task + registry entry
```

## Checklist

- [ ] `mark_duplicates` function in `variant_calling.py`.
- [ ] `--CREATE_INDEX true` in command.
- [ ] Both BAM and metrics paths in manifest.
- [ ] `MANIFEST_OUTPUT_KEYS` extended with `"dedup_bam"` and `"duplicate_metrics"`.
- [ ] Registry entry at stage_order=11 with two output fields.
- [ ] Tests: registry shape, cmd shape, manifest emission (both keys), missing-file error.
- [ ] `pytest tests/test_variant_calling.py -xvs` green.
- [ ] `pytest tests/test_registry_manifest_contract.py -xvs` green.
- [ ] CHANGELOG updated.
- [ ] Step 05 marked Complete in checklist.
