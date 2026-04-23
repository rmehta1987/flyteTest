# Step 07 — `preprocess_sample` Workflow

## Goal

Add the `preprocess_sample` workflow to
`src/flytetest/workflows/variant_calling.py` and register it.

## Context

- Plan §4: `docs/gatk_milestone_b/milestone_b_plan.md`.
- Stargazer reference:
  `stargazer/src/stargazer/workflows/gatk_data_preprocessing.py` — `preprocess_sample`.
- All sub-tasks already exist: `bwa_mem2_mem` (Step 03), `sort_sam` (Step 04),
  `mark_duplicates` (Step 05), `base_recalibrator` (Milestone A Step 05),
  `apply_bqsr` (Milestone A Step 06).
- Extend `src/flytetest/workflows/variant_calling.py` (created in Step 06).

## What to build

### Workflow function

```python
@variant_calling_env.task
def preprocess_sample(
    ref_path: str,
    r1_path: str,
    sample_id: str,
    known_sites: list[str],
    results_dir: str,
    r2_path: str = "",
    sif_path: str = "",
) -> dict:
    """
    Preprocess a single sample from raw reads to BQSR-recalibrated BAM.

    Steps:
    1. bwa_mem2_mem   — align reads → unsorted BAM
    2. sort_sam        — coordinate sort
    3. mark_duplicates — mark PCR/optical duplicates
    4. base_recalibrator — generate BQSR table
    5. apply_bqsr      — apply recalibration
    """
    aligned   = bwa_mem2_mem(ref_path, r1_path, sample_id, results_dir, r2_path, sif_path=sif_path)
    sorted_m  = sort_sam(aligned["aligned_bam"], sample_id, results_dir, sif_path=sif_path)
    deduped   = mark_duplicates(sorted_m["sorted_bam"], sample_id, results_dir, sif_path=sif_path)
    bqsr_tbl  = base_recalibrator(ref_path, deduped["dedup_bam"], known_sites, sample_id, results_dir, sif_path=sif_path)
    recal     = apply_bqsr(ref_path, deduped["dedup_bam"], bqsr_tbl["bqsr_report"], sample_id, results_dir, sif_path=sif_path)

    manifest = build_manifest_envelope(
        task_name="preprocess_sample",
        results_dir=results_dir,
        outputs={"preprocessed_bam": recal["recalibrated_bam"]},
    )
    _write_json(manifest, results_dir, "run_manifest.json")
    return manifest
```

### `MANIFEST_OUTPUT_KEYS` update

Extend the workflow module tuple:

```python
MANIFEST_OUTPUT_KEYS: tuple[str, ...] = (
    "prepared_ref",
    "preprocessed_bam",  # ← new
)
```

### Registry entry

```python
RegistryEntry(
    name="preprocess_sample",
    category="workflow",
    description="Preprocess one sample from paired-end FASTQs to BQSR-recalibrated BAM.",
    pipeline_family="variant_calling",
    pipeline_stage_order=2,
    showcase_module="",
    accepted_planner_types=("ReferenceGenome", "ReadPair", "KnownSites"),
    produced_planner_types=("AlignmentSet",),
    inputs=[
        InterfaceField("ref_path", "str", "Absolute path to reference FASTA."),
        InterfaceField("r1_path", "str", "Absolute path to R1 FASTQ."),
        InterfaceField("sample_id", "str", "Sample identifier."),
        InterfaceField("known_sites", "list[str]", "List of indexed known-sites VCF paths."),
        InterfaceField("results_dir", "str", "Output directory."),
        InterfaceField("r2_path", "str", "Optional R2 FASTQ path."),
        InterfaceField("sif_path", "str", "Optional GATK4/BWA SIF image path."),
    ],
    outputs=[
        InterfaceField("preprocessed_bam", "str", "Path to BQSR-recalibrated BAM."),
    ],
    compatibility=RegistryCompatibilityMetadata(
        local_resources={"cpu": "8", "memory": "32Gi"},
        slurm_hints={"cpus_per_task": 16, "mem": "64G", "time": "12:00:00"},
    ),
)
```

### Tests (`tests/test_variant_calling_workflows.py`)

Add `PreprocessSampleRegistryTests`, `PreprocessSampleInvocationTests`,
`PreprocessSampleManifestTests`:

- Registry entry shape (category="workflow", stage_order=2).
- With mocked sub-tasks: calls occur in order — `bwa_mem2_mem`, `sort_sam`,
  `mark_duplicates`, `base_recalibrator`, `apply_bqsr`.
- Each sub-task receives the correct output from the previous step.
- Manifest emits `"preprocessed_bam"` equal to `recal["recalibrated_bam"]`.
- `MANIFEST_OUTPUT_KEYS` in workflow module contains `"preprocessed_bam"`.

### `CHANGELOG.md`

```
### GATK Milestone B Step 07 — preprocess_sample workflow (YYYY-MM-DD)
- [x] YYYY-MM-DD added `preprocess_sample` to `src/flytetest/workflows/variant_calling.py`.
- [x] YYYY-MM-DD added `preprocess_sample` registry entry (category=workflow, stage_order 2).
- [x] YYYY-MM-DD extended workflow MANIFEST_OUTPUT_KEYS with `"preprocessed_bam"`.
- [x] YYYY-MM-DD added N tests; all tests passing.
```

## Commit message

```
variant_calling: add preprocess_sample workflow + registry entry
```

## Checklist

- [ ] `preprocess_sample` in workflow module; sub-tasks called in order.
- [ ] `MANIFEST_OUTPUT_KEYS` extended with `"preprocessed_bam"`.
- [ ] Registry entry category="workflow", stage_order=2.
- [ ] Tests: call order, manifest, sub-task data threading.
- [ ] `pytest tests/test_variant_calling_workflows.py -xvs` green.
- [ ] `pytest tests/test_registry_manifest_contract.py -xvs` green.
- [ ] CHANGELOG updated.
- [ ] Step 07 marked Complete in checklist.
