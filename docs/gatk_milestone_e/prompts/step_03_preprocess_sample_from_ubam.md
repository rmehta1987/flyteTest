# Step 03 — `preprocess_sample_from_ubam` Workflow

## Model

**Sonnet 4.6** (`claude-sonnet-4-6`). Subtle structural difference from
`preprocess_sample`: no `sort_sam` step (MergeBamAlignment handles sorting),
and the aligned BAM from `bwa_mem2_mem` is passed to `merge_bam_alignment`
before `mark_duplicates`. Getting the step order wrong produces a valid-looking
but biologically incorrect BAM.

## Goal

Add `preprocess_sample_from_ubam` to `src/flytetest/workflows/variant_calling.py`,
its registry entry, and unit tests.

## Context

- Milestone E plan §4: `docs/gatk_milestone_e/milestone_e_plan.md`.
- Pattern: `preprocess_sample` in `src/flytetest/workflows/variant_calling.py`
  — sequential task calls, manifest emission, `@variant_calling_env.task`.
- Depends on Steps 01 + 02 (UnmappedBAM type + merge_bam_alignment task).
- Import `merge_bam_alignment` alongside existing task imports in the workflow
  module.

## What to build

### `src/flytetest/workflows/variant_calling.py`

Add `merge_bam_alignment` to the import block. Append workflow after
`genotype_refinement`. Signature:

```python
def preprocess_sample_from_ubam(
    ref_path: str,
    r1_path: str,
    ubam_path: str,
    sample_id: str,
    known_sites: list[str],
    results_dir: str,
    r2_path: str = "",
    threads: int = 4,
    sif_path: str = "",
) -> dict:
    """Preprocess a sample using the uBAM path (align → merge → dedup → BQSR)."""
```

Step order (no `sort_sam`):

```python
aligned = bwa_mem2_mem(ref_path, r1_path, sample_id, results_dir,
                       r2_path, threads, sif_path)
merged  = merge_bam_alignment(ref_path,
                               aligned["outputs"]["aligned_bam"],
                               ubam_path, sample_id, results_dir, sif_path)
deduped = mark_duplicates(merged["outputs"]["merged_bam"],
                          sample_id, results_dir, sif_path)
bqsr_tbl = base_recalibrator(ref_path, deduped["outputs"]["dedup_bam"],
                              known_sites, sample_id, sif_path)
recal_bam = apply_bqsr(ref_path, deduped["outputs"]["dedup_bam"],
                        bqsr_tbl, sample_id, sif_path)
emit manifest: preprocessed_bam_from_ubam = recal_bam
```

`base_recalibrator` and `apply_bqsr` use the Milestone A `File`-based
signatures — wrap path strings in `File(path=...)` as in `preprocess_sample`.

### `MANIFEST_OUTPUT_KEYS` extension — workflows module

Append `"preprocessed_bam_from_ubam"` to `MANIFEST_OUTPUT_KEYS` in
`src/flytetest/workflows/variant_calling.py`.

### Registry entry

- `name`: `"preprocess_sample_from_ubam"`, `category`: `"workflow"`,
  `pipeline_stage_order`: `5`
- `inputs`: `ref_path`, `r1_path`, `ubam_path`, `sample_id`, `known_sites`,
  `results_dir`, `r2_path` (optional), `threads` (optional), `sif_path`
- `outputs`: `preprocessed_bam_from_ubam` (str)
- `slurm_resource_hints`: `{"cpu": "16", "memory": "64Gi", "walltime": "04:00:00"}`
- `accepted_planner_types`: `("ReferenceGenome", "ReadPair", "UnmappedBAM", "KnownSites")`
- `produced_planner_types`: `("AlignmentSet",)`
- `reusable_as_reference`: `True`
- `composition_constraints`:
  - `"ubam_path must be queryname-sorted."`
  - `"No sort_sam step — MergeBamAlignment --SORT_ORDER coordinate handles sorting."`
  - `"Reference must be prepared (prepare_reference must have run first)."`

### Tests (`tests/test_variant_calling_workflows.py`)

`PreprocessSampleFromUbamWorkflowTests`:

- `test_preprocess_sample_from_ubam_runs` — patches all 5 sub-tasks; asserts
  manifest has `preprocessed_bam_from_ubam` key.
- `test_no_sort_sam_called` — patches sub-tasks; asserts `sort_sam` is
  **never** called (MergeBamAlignment handles ordering).
- `test_merge_bam_alignment_receives_aligned_bam` — asserts
  `merge_bam_alignment` is called with `aligned_bam` from `bwa_mem2_mem`
  output, not a raw path.
- `test_registry_entry_shape` — entry exists at workflow stage 5 with
  `preprocessed_bam_from_ubam` output.

## CHANGELOG

```
### GATK Milestone E Step 03 — preprocess_sample_from_ubam workflow (YYYY-MM-DD)
- [x] YYYY-MM-DD added preprocess_sample_from_ubam workflow.
- [x] YYYY-MM-DD added registry entry (workflow stage 5).
- [x] YYYY-MM-DD added 4 unit tests.
- [x] YYYY-MM-DD extended workflows MANIFEST_OUTPUT_KEYS with preprocessed_bam_from_ubam.
```

## Verification

```bash
VIRTUAL_ENV=.venv PATH=".venv/bin:$PATH" PYTHONPATH=src python -m compileall src/flytetest/workflows/variant_calling.py
VIRTUAL_ENV=.venv PATH=".venv/bin:$PATH" PYTHONPATH=src pytest tests/test_variant_calling_workflows.py -xvs -k "PreprocessSampleFromUbam"
VIRTUAL_ENV=.venv PATH=".venv/bin:$PATH" PYTHONPATH=src pytest -q
rg "preprocess_sample_from_ubam" src/flytetest/registry/_variant_calling.py
```

## Commit message

```
variant_calling: add preprocess_sample_from_ubam workflow + registry entry
```

## Checklist

- [ ] No `sort_sam` call in the workflow body.
- [ ] `merge_bam_alignment` receives `aligned["outputs"]["aligned_bam"]`.
- [ ] `MANIFEST_OUTPUT_KEYS` extended with `"preprocessed_bam_from_ubam"`.
- [ ] Registry entry at `pipeline_stage_order=5`, `reusable_as_reference=True`.
- [ ] 4 unit tests passing including the `sort_sam`-never-called assertion.
- [ ] Full suite green.
- [ ] Step 03 marked Complete in checklist.
