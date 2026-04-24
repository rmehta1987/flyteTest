# Step 02 — `bwa_mem2_index` Task

## Goal

Add the `bwa_mem2_index` task to `src/flytetest/tasks/variant_calling.py`
and register it in `src/flytetest/registry/_variant_calling.py`.

## Context

- Plan §4: `docs/gatk_milestone_b/milestone_b_plan.md`.
- Stargazer reference (read-only, argument ordering only):
  `stargazer/src/stargazer/tasks/general/bwa_mem2.py` — `bwa_mem2_index`.
- Existing task pattern: `create_sequence_dictionary` in `variant_calling.py`.
- Uses `run_tool`, `require_path`, `build_manifest_envelope`, `_write_json`.

## Command shape

```
bwa-mem2 index -p <results_dir>/<ref_basename> <ref.fa>
```

Creates index files with extensions `.0123`, `.amb`, `.ann`, `.bwt.2bit.64`,
`.pac` next to the prefix in `results_dir`.

## What to build

### Task signature

```python
def bwa_mem2_index(
    ref_path: str,
    results_dir: str,
    sif_path: str = "",
) -> dict:
```

- `ref_path` — absolute path to reference FASTA.
- `results_dir` — directory where index files are written.
- `sif_path` — optional SIF image path (passed to `run_tool`).
- Returns the `run_manifest.json` dict.

### Output

- Index prefix: `<results_dir>/<ref_basename>` (no extension).
- All five index files must exist after the command or raise `FileNotFoundError`.
- Manifest key: `"bwa_index_prefix"` — the string prefix path.

### `MANIFEST_OUTPUT_KEYS` addition

Extend the tuple in `variant_calling.py`:

```python
MANIFEST_OUTPUT_KEYS: tuple[str, ...] = (
    "sequence_dict", "feature_index", "bqsr_report",
    "recalibrated_bam", "gvcf", "combined_gvcf", "joint_vcf",
    "bwa_index_prefix",  # ← new
)
```

### Registry entry

Add to `VARIANT_CALLING_ENTRIES` in `_variant_calling.py`:

```python
RegistryEntry(
    name="bwa_mem2_index",
    category="task",
    description="Index a reference FASTA for BWA-MEM2 alignment.",
    pipeline_family="variant_calling",
    pipeline_stage_order=8,
    showcase_module="",
    accepted_planner_types=("ReferenceGenome",),
    produced_planner_types=("ReferenceGenome",),
    inputs=[
        InterfaceField("ref_path", "str", "Absolute path to reference FASTA."),
        InterfaceField("results_dir", "str", "Directory for index output."),
        InterfaceField("sif_path", "str", "Optional GATK4 SIF image path."),
    ],
    outputs=[
        InterfaceField("bwa_index_prefix", "str", "Path prefix for BWA-MEM2 index files."),
    ],
    compatibility=RegistryCompatibilityMetadata(
        local_resources={"cpu": "4", "memory": "16Gi"},
        slurm_hints={"cpus_per_task": 8, "mem": "32G", "time": "02:00:00"},
    ),
)
```

### Tests (`tests/test_variant_calling.py`)

Add `BwaMem2IndexRegistryTests`, `BwaMem2IndexInvocationTests`,
`BwaMem2IndexManifestTests` covering:

- Registry entry shape (name, stage_order=8, pipeline_family).
- Command contains `"bwa-mem2"`, `"index"`, `"-p"`, and `ref_path`.
- Manifest emits `"bwa_index_prefix"`.
- `FileNotFoundError` if index files are absent after the run.

### `CHANGELOG.md`

```
### GATK Milestone B Step 02 — bwa_mem2_index task (YYYY-MM-DD)
- [x] YYYY-MM-DD added `bwa_mem2_index` to `variant_calling.py`.
- [x] YYYY-MM-DD added `bwa_mem2_index` registry entry (stage_order 8).
- [x] YYYY-MM-DD extended MANIFEST_OUTPUT_KEYS with `"bwa_index_prefix"`.
- [x] YYYY-MM-DD added N tests; all tests passing.
```

## Commit message

```
variant_calling: add bwa_mem2_index task + registry entry
```

## Checklist

- [ ] `bwa_mem2_index` function in `variant_calling.py`.
- [ ] Five index file extensions verified post-run.
- [ ] `MANIFEST_OUTPUT_KEYS` extended with `"bwa_index_prefix"`.
- [ ] Registry entry at stage_order=8.
- [ ] Tests: registry shape, cmd shape, manifest emission, missing-file error.
- [ ] `pytest tests/test_variant_calling.py -xvs` green.
- [ ] CHANGELOG updated.
- [ ] Step 02 marked Complete in checklist.
