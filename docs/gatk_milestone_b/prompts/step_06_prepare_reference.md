# Step 06 — `prepare_reference` Workflow

## Goal

Create `src/flytetest/workflows/variant_calling.py` with the
`prepare_reference` workflow and add a registry entry for it.

## Context

- Plan §4: `docs/gatk_milestone_b/milestone_b_plan.md`.
- Stargazer reference (step ordering):
  `stargazer/src/stargazer/workflows/gatk_data_preprocessing.py` — `prepare_reference`.
- Existing workflow pattern: `src/flytetest/workflows/transcript_evidence.py`.
- All sub-tasks already implemented (Steps 01–02 of Milestone A provided
  `create_sequence_dictionary` and `index_feature_file`; Step 02 of Milestone B
  provided `bwa_mem2_index`).
- Workflow file: `src/flytetest/workflows/variant_calling.py`.
- Workflow tests file: `tests/test_variant_calling_workflows.py` (new file).

## What to build

### `src/flytetest/workflows/variant_calling.py`

```python
from flytetest.config import variant_calling_env
from flytetest.tasks.variant_calling import (
    create_sequence_dictionary,
    index_feature_file,
    bwa_mem2_index,
)
from flytetest.manifest_io import _write_json
from flytetest.manifest_envelope import build_manifest_envelope

MANIFEST_OUTPUT_KEYS: tuple[str, ...] = (
    "prepared_ref",
)

@variant_calling_env.task
def prepare_reference(
    ref_path: str,
    known_sites: list[str],
    results_dir: str,
    sif_path: str = "",
) -> dict:
    """
    Prepare a reference genome for GATK germline variant calling.

    Steps:
    1. CreateSequenceDictionary — produces .dict file.
    2. IndexFeatureFile — indexes each known-sites VCF.
    3. bwa_mem2_index — creates BWA-MEM2 index files.
    """
    create_sequence_dictionary(ref_path=ref_path, results_dir=results_dir, sif_path=sif_path)
    for vcf in known_sites:
        index_feature_file(vcf_path=vcf, results_dir=results_dir, sif_path=sif_path)
    bwa_mem2_index(ref_path=ref_path, results_dir=results_dir, sif_path=sif_path)

    manifest = build_manifest_envelope(
        task_name="prepare_reference",
        results_dir=results_dir,
        outputs={"prepared_ref": ref_path},
    )
    _write_json(manifest, results_dir, "run_manifest.json")
    return manifest
```

### `MANIFEST_OUTPUT_KEYS`

`MANIFEST_OUTPUT_KEYS = ("prepared_ref",)` is defined in the workflow module.

### Registry entry in `_variant_calling.py`

Add to `VARIANT_CALLING_ENTRIES`:

```python
RegistryEntry(
    name="prepare_reference",
    category="workflow",
    description="Prepare a reference genome for GATK germline variant calling (dict + known-sites index + BWA-MEM2 index).",
    pipeline_family="variant_calling",
    pipeline_stage_order=1,
    showcase_module="",
    accepted_planner_types=("ReferenceGenome", "KnownSites"),
    produced_planner_types=("ReferenceGenome",),
    inputs=[
        InterfaceField("ref_path", "str", "Absolute path to reference FASTA."),
        InterfaceField("known_sites", "list[str]", "List of known-sites VCF paths."),
        InterfaceField("results_dir", "str", "Output directory."),
        InterfaceField("sif_path", "str", "Optional GATK4 SIF image path."),
    ],
    outputs=[
        InterfaceField("prepared_ref", "str", "Reference path (with all indices in results_dir)."),
    ],
    compatibility=RegistryCompatibilityMetadata(
        local_resources={"cpu": "4", "memory": "16Gi"},
        slurm_hints={"cpus_per_task": 8, "mem": "32G", "time": "04:00:00"},
    ),
)
```

### Tests (`tests/test_variant_calling_workflows.py`)

Create this file. Add `PrepareReferenceRegistryTests`,
`PrepareReferenceInvocationTests`, `PrepareReferenceManifestTests`:

- Registry entry shape (category="workflow", stage_order=1).
- When mocking sub-tasks, the workflow calls them in order:
  `create_sequence_dictionary`, then `index_feature_file` per known-site,
  then `bwa_mem2_index`.
- `index_feature_file` is called once per entry in `known_sites`.
- Manifest emits `"prepared_ref"`.
- `MANIFEST_OUTPUT_KEYS` in workflow module contains `"prepared_ref"`.

### `CHANGELOG.md`

```
### GATK Milestone B Step 06 — prepare_reference workflow (YYYY-MM-DD)
- [x] YYYY-MM-DD created `src/flytetest/workflows/variant_calling.py` with `prepare_reference`.
- [x] YYYY-MM-DD added `prepare_reference` registry entry (category=workflow, stage_order 1).
- [x] YYYY-MM-DD created `tests/test_variant_calling_workflows.py`.
- [x] YYYY-MM-DD added N tests; all tests passing.
```

## Commit message

```
variant_calling: add prepare_reference workflow + registry entry
```

## Checklist

- [ ] `src/flytetest/workflows/variant_calling.py` created.
- [ ] `MANIFEST_OUTPUT_KEYS = ("prepared_ref",)` in workflow module.
- [ ] Sub-tasks called in order: dict → index_feature_file (per VCF) → bwa_mem2_index.
- [ ] Registry entry category="workflow", stage_order=1.
- [ ] `tests/test_variant_calling_workflows.py` created.
- [ ] Tests: registry shape, sub-task call order, per-VCF indexing, manifest.
- [ ] `pytest tests/test_variant_calling_workflows.py -xvs` green.
- [ ] `pytest tests/test_registry_manifest_contract.py -xvs` green.
- [ ] CHANGELOG updated.
- [ ] Step 06 marked Complete in checklist.
