# Step 03 — `scattered_haplotype_caller` Workflow

## Model

**Sonnet 4.6** (`claude-sonnet-4-6`). The per-interval subdirectory naming
(`interval_0000/`, `interval_0001/`) is critical — without it, parallel calls
overwrite each other's output files. Also verify that GVCFs are passed to
`gather_vcfs` in interval order, not dict-iteration order.

## Goal

Add `scattered_haplotype_caller` to `src/flytetest/workflows/variant_calling.py`,
its registry entry, and unit tests.

## Context

- Milestone F plan §4: `docs/gatk_milestone_f/milestone_f_plan.md`.
- Depends on Steps 01 + 02 (intervals in haplotype_caller + gather_vcfs).
- Import `gather_vcfs` in the workflow module.
- `haplotype_caller` in the workflow module is the `File`-based Milestone A
  task — it returns a `File` object; extract `.path` for the gather step.

## What to build

### `src/flytetest/workflows/variant_calling.py`

Import `gather_vcfs`. Append after `preprocess_sample_from_ubam`. Signature:

```python
def scattered_haplotype_caller(
    ref_path: str,
    bam_path: str,
    sample_id: str,
    intervals: list[str],
    results_dir: str,
    sif_path: str = "",
) -> dict:
    """Call per-sample GVCFs scattered across intervals, then gather."""
```

Validate: raise `ValueError` if `intervals` is empty.

Body:

```python
interval_gvcfs: list[str] = []
for i, interval in enumerate(intervals):
    interval_dir = str(Path(results_dir) / f"interval_{i:04d}")
    gvcf_file = haplotype_caller(
        reference_fasta=File(path=ref_path),
        aligned_bam=File(path=bam_path),
        sample_id=sample_id,
        intervals=[interval],
        gatk_sif=sif_path,
    )
    # haplotype_caller returns File; move it to interval subdir via manifest
    interval_gvcfs.append(gvcf_file.path)

gathered = gather_vcfs(
    gvcf_paths=interval_gvcfs,
    sample_id=sample_id,
    results_dir=results_dir,
    sif_path=sif_path,
)
emit manifest: scattered_gvcf = gathered["outputs"]["gathered_gvcf"]
```

Note: `haplotype_caller` is the Milestone A `File`-returning task. Pass
`intervals=[interval]` using the new parameter from Milestone F Step 01.
`results_dir` is not accepted by the Milestone A task — it uses
`project_mkdtemp` internally. The per-interval subdirectory isolation comes
from each `haplotype_caller` call getting its own temp dir.

### `MANIFEST_OUTPUT_KEYS` extension — workflows module

Append `"scattered_gvcf"` to `MANIFEST_OUTPUT_KEYS`.

### Registry entry

- `name`: `"scattered_haplotype_caller"`, `category`: `"workflow"`,
  `pipeline_stage_order`: `6`
- `inputs`: `ref_path`, `bam_path`, `sample_id`, `intervals` (list[str]),
  `results_dir`, `sif_path`
- `outputs`: `scattered_gvcf` (str)
- `slurm_resource_hints`: `{"cpu": "16", "memory": "64Gi", "walltime": "24:00:00"}`
- `accepted_planner_types`: `("ReferenceGenome", "AlignmentSet")`
- `produced_planner_types`: `("VariantCallSet",)`
- `reusable_as_reference`: `True`
- `composition_constraints`:
  - `"intervals must be non-empty and in genomic order for GatherVcfs."`
  - `"Scatter is synchronous (Python for loop); no job arrays."`
  - `"BAM must be BQSR-recalibrated (preprocess_sample or preprocess_sample_from_ubam must have run first)."`

### Tests (`tests/test_variant_calling_workflows.py`)

`ScatteredHaplotypeCallerTests`:

- `test_scattered_haplotype_caller_runs` — patches `haplotype_caller` and
  `gather_vcfs`; asserts manifest has `scattered_gvcf` key.
- `test_haplotype_caller_called_once_per_interval` — 3 intervals → asserts
  `haplotype_caller` mock called exactly 3 times.
- `test_gather_vcfs_receives_gvcfs_in_interval_order` — captures
  `gather_vcfs` call's `gvcf_paths` argument; asserts it equals
  `[mock_hc_return.path, mock_hc_return.path, mock_hc_return.path]` in
  iteration order (not shuffled).
- `test_empty_intervals_raises` — asserts `ValueError` for `intervals=[]`.
- `test_registry_entry_shape` — entry at workflow stage 6, `scattered_gvcf`
  output.

## CHANGELOG

```
### GATK Milestone F Step 03 — scattered_haplotype_caller workflow (YYYY-MM-DD)
- [x] YYYY-MM-DD added scattered_haplotype_caller workflow (stage 6).
- [x] YYYY-MM-DD added registry entry.
- [x] YYYY-MM-DD added 5 unit tests.
- [x] YYYY-MM-DD extended workflows MANIFEST_OUTPUT_KEYS with scattered_gvcf.
```

## Verification

```bash
VIRTUAL_ENV=.venv PATH=".venv/bin:$PATH" PYTHONPATH=src pytest tests/test_variant_calling_workflows.py -xvs -k "ScatteredHaplotypeCaller"
VIRTUAL_ENV=.venv PATH=".venv/bin:$PATH" PYTHONPATH=src pytest -q
rg "scattered_haplotype_caller" src/flytetest/registry/_variant_calling.py
```

## Commit message

```
variant_calling: add scattered_haplotype_caller workflow + registry entry
```

## Checklist

- [ ] `ValueError` raised for empty `intervals`.
- [ ] `haplotype_caller` called once per interval.
- [ ] `gather_vcfs` receives GVCFs in interval iteration order.
- [ ] `"scattered_gvcf"` in workflows `MANIFEST_OUTPUT_KEYS`.
- [ ] Registry at `pipeline_stage_order=6`, `reusable_as_reference=True`.
- [ ] 5 tests passing.
- [ ] Full suite green.
- [ ] Step 03 marked Complete in checklist.
