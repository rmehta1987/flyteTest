# Step 02 — `merge_bam_alignment` Task

## Model

**Sonnet 4.6** (`claude-sonnet-4-6`). The command has several non-obvious
flags (`--PRIMARY_ALIGNMENT_STRATEGY MostDistant`, `--ATTRIBUTES_TO_RETAIN X0`)
whose inclusion must exactly match the Stargazer reference. Minor flag
differences produce subtly incorrect output that won't fail unit tests.

## Goal

Add `merge_bam_alignment` to `src/flytetest/tasks/variant_calling.py`, its
registry entry, and unit tests.

## Context

- Milestone E plan §4: `docs/gatk_milestone_e/milestone_e_plan.md`.
- Stargazer reference (command flags only — ignore async/IPFS):
  `stargazer/src/stargazer/tasks/gatk/merge_bam_alignment.py`.
- Pattern: `mark_duplicates` in `src/flytetest/tasks/variant_calling.py`
  (Milestone B task: `str` paths, no decorator, return `dict` manifest).
- Depends on Step 01 (`UnmappedBAM`) being Complete.

## What to build

### `src/flytetest/tasks/variant_calling.py`

Add after `variant_recalibrator` / `apply_vqsr` (end of file). Signature:

```python
def merge_bam_alignment(
    ref_path: str,
    aligned_bam: str,
    ubam_path: str,
    sample_id: str,
    results_dir: str,
    sif_path: str = "",
) -> dict:
    """Merge aligned BAM with unmapped BAM using GATK4 MergeBamAlignment."""
```

GATK command (all flags from Stargazer reference):

```
gatk MergeBamAlignment \
  -R <ref_path> \
  -ALIGNED <aligned_bam> \
  -UNMAPPED <ubam_path> \
  -O <results_dir>/<sample_id>_merged.bam \
  --SORT_ORDER coordinate \
  --ADD_MATE_CIGAR true \
  --CLIP_ADAPTERS false \
  --CLIP_OVERLAPPING_READS true \
  --INCLUDE_SECONDARY_ALIGNMENTS true \
  --MAX_INSERTIONS_OR_DELETIONS -1 \
  --PRIMARY_ALIGNMENT_STRATEGY MostDistant \
  --ATTRIBUTES_TO_RETAIN X0 \
  --CREATE_INDEX true
```

`--CREATE_INDEX true` writes `<sample_id>_merged.bai` alongside the BAM.
Check for `.bai` or `.bam.bai` companion (same pattern as `apply_bqsr`).

Raise `FileNotFoundError` if `<sample_id>_merged.bam` is absent after run.

Manifest outputs:
```python
{
    "merged_bam": str(out_bam),
    "merged_bam_index": str(bai) if bai.exists() else "",
}
```

### `MANIFEST_OUTPUT_KEYS` extension

Append `"merged_bam"` to `MANIFEST_OUTPUT_KEYS` in
`src/flytetest/tasks/variant_calling.py`.

### Registry entry

- `name`: `"merge_bam_alignment"`, `category`: `"task"`, `pipeline_stage_order`: `14`
- `inputs`: `ref_path`, `aligned_bam`, `ubam_path`, `sample_id`, `results_dir`, `sif_path`
- `outputs`: `merged_bam` (str)
- `slurm_resource_hints`: `{"cpu": "4", "memory": "16Gi", "walltime": "02:00:00"}`
- `accepted_planner_types`: `("ReferenceGenome", "AlignmentSet", "UnmappedBAM")`
- `produced_planner_types`: `("AlignmentSet",)`
- `composition_constraints`: `("ubam_path must be queryname-sorted (GATK requirement for MergeBamAlignment).",)`

### Add to `_VARIANT_CALLING_TASK_NAMES` in `tests/test_registry_manifest_contract.py`

### Tests (`tests/test_variant_calling.py`)

`MergeBamAlignmentTests` class:

- `test_merge_bam_alignment_runs` — patches `run_tool`, creates dummy
  `<sample_id>_merged.bam` in `tmp_path`; asserts manifest has `merged_bam`.
- `test_merge_bam_alignment_command_shape` — captures cmd; asserts
  `-ALIGNED`, `-UNMAPPED`, `--SORT_ORDER coordinate`,
  `--PRIMARY_ALIGNMENT_STRATEGY MostDistant`,
  `--ATTRIBUTES_TO_RETAIN X0` all present.
- `test_merge_bam_alignment_missing_output_raises` — no output file created;
  asserts `FileNotFoundError`.
- `test_merge_bam_alignment_manifest_key` — manifest contains `merged_bam`
  ending in `_merged.bam`.

## CHANGELOG

```
### GATK Milestone E Step 02 — merge_bam_alignment task (YYYY-MM-DD)
- [x] YYYY-MM-DD added merge_bam_alignment to src/flytetest/tasks/variant_calling.py.
- [x] YYYY-MM-DD added registry entry (stage 14).
- [x] YYYY-MM-DD added 4 unit tests in MergeBamAlignmentTests.
- [x] YYYY-MM-DD extended MANIFEST_OUTPUT_KEYS with merged_bam.
```

## Verification

```bash
VIRTUAL_ENV=.venv PATH=".venv/bin:$PATH" PYTHONPATH=src python -m compileall src/flytetest/tasks/variant_calling.py
VIRTUAL_ENV=.venv PATH=".venv/bin:$PATH" PYTHONPATH=src pytest tests/test_variant_calling.py -xvs -k "MergeBamAlignment"
VIRTUAL_ENV=.venv PATH=".venv/bin:$PATH" PYTHONPATH=src pytest tests/test_registry_manifest_contract.py -xvs
rg "async def|await |asyncio\.gather|\.cid\b|IPFS|Pinata|TinyDB" src/flytetest/tasks/variant_calling.py
```

## Commit message

```
variant_calling: add merge_bam_alignment task + registry entry
```

## Checklist

- [ ] All 9 `MergeBamAlignment` flags present in command.
- [ ] `MANIFEST_OUTPUT_KEYS` extended with `"merged_bam"`.
- [ ] Registry entry at `pipeline_stage_order=14`.
- [ ] `merge_bam_alignment` added to `_VARIANT_CALLING_TASK_NAMES`.
- [ ] 4 unit tests passing.
- [ ] Contract test green.
- [ ] Step 02 marked Complete in checklist.
