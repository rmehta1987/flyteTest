# Step 01 — P0 Security + Provenance Fixes

## Model

**Sonnet 4.6** (`claude-sonnet-4-6`). Two small, mechanical fixes across a
single module plus focused tests. Opus is overkill.

## Goal

1. Fix the shell-injection hole in `bwa_mem2_mem`
   (`src/flytetest/tasks/variant_calling.py:450-506`) by quoting every
   user-supplied path.
2. Stop the per-task `run_manifest.json` overwrite inside multi-task
   workflows by switching every variant_calling *task* to a per-stage
   filename (`run_manifest_<stage>.json`). Workflow-level manifests stay
   at `run_manifest.json`.
3. Add regression tests for both.

## Context

- Milestone H plan §1, §4 Step 01:
  `docs/gatk_milestone_h/milestone_h_plan.md`.
- Branch: `gatkport-h` (`git checkout -b gatkport-h`).
- Pattern reference: existing Milestone A tasks already emit manifests;
  only the filename shape changes.

## What to build

### `src/flytetest/tasks/variant_calling.py`

**Shell quoting in `bwa_mem2_mem` (line ~450-506):**

```python
import shlex

rg = f"@RG\\tID:{sample_id}\\tSM:{sample_id}\\tLB:lib\\tPL:ILLUMINA"
pipeline = (
    f"bwa-mem2 mem -R {shlex.quote(rg)} -t {threads} "
    f"{shlex.quote(ref_path)} {shlex.quote(r1_path)}"
    + (f" {shlex.quote(r2_path)}" if r2_path else "")
    + f" | samtools view -bS -o {shlex.quote(str(output_bam))} -"
)
```

Keep the existing `if sif_path: apptainer exec ... bash -c <quoted
pipeline>` path. The outer `shlex.quote(pipeline)` wrapping is already
present for the container case; preserve it.

**Per-stage manifest filenames — all 16 tasks:**

Every occurrence of

```python
_write_json(out_dir / "run_manifest.json", manifest)
```

becomes

```python
_write_json(out_dir / f"run_manifest_{manifest['stage']}.json", manifest)
```

Sites (by `def` name, in file order): `create_sequence_dictionary`,
`index_feature_file`, `base_recalibrator`, `apply_bqsr`,
`haplotype_caller`, `joint_call_gvcfs`, `combine_gvcfs`, `bwa_mem2_index`,
`bwa_mem2_mem`, `sort_sam`, `mark_duplicates`, `variant_recalibrator`,
`apply_vqsr`, `merge_bam_alignment`, `gather_vcfs`,
`calculate_genotype_posteriors`. 16 sites total.

Do **not** change the workflow-level emits in
`src/flytetest/workflows/variant_calling.py` — those stay at
`run_manifest.json`.

### Tests (`tests/test_variant_calling.py`)

Add two test classes (or extend existing ones):

**`BwaMem2MemShellQuotingTests`:**

- `test_bwa_mem2_mem_handles_path_with_space` — create a tempdir with
  `" my reads "` in the path, pass to `bwa_mem2_mem`, assert the
  subprocess command string contains the quoted form and that the
  function does not raise before invoking the tool. Mock `subprocess.run`
  with `returncode=0` and a writable `output_bam` to satisfy the
  post-check.
- `test_bwa_mem2_mem_rejects_unquoted_metacharacters` — assert that a
  reads path ending in `;echo pwned` appears *inside quotes* in the
  captured command string, not as a separate shell token. Mock
  `subprocess.run` as above.

**`PerStageManifestFilenameTests`:**

- `test_each_task_writes_namespaced_manifest` — parametrize over the 16
  task names; for each, mock `run_tool` and assert the call to
  `_write_json` (or resulting file path) ends in
  `run_manifest_<stage>.json`, not `run_manifest.json`.
- `test_preprocess_sample_preserves_all_stage_manifests` — use the
  existing `preprocess_sample` workflow test fixture; after run, assert
  that `run_manifest_bwa_mem2_mem.json`,
  `run_manifest_sort_sam.json`, `run_manifest_mark_duplicates.json`,
  `run_manifest_base_recalibrator.json`, and
  `run_manifest_apply_bqsr.json` all exist in the results directory.

Reuse existing mocking patterns from current `test_variant_calling.py`
tests (they already mock `run_tool` and the GATK SIF).

## Backward Compatibility

Per-stage manifest filenames break any external consumer reading
`{results_dir}/run_manifest.json` directly from a task's output directory.
No in-repo consumer does this (workflows use return values and the
workflow-level `run_manifest.json`). Note explicitly in the CHANGELOG
that the change affects task-level manifest filenames only.

## CHANGELOG

```
### GATK Milestone H Step 01 — P0 security + provenance fixes (YYYY-MM-DD)
- [x] YYYY-MM-DD bwa_mem2_mem: shlex.quote on ref_path, r1_path, r2_path, rg, output_bam.
- [x] YYYY-MM-DD per-stage manifest filenames (run_manifest_<stage>.json) on all 16 variant_calling tasks.
- [x] YYYY-MM-DD added BwaMem2MemShellQuotingTests (2 tests) and PerStageManifestFilenameTests (2 tests).
- [!] Breaking: task-level manifests moved from {results_dir}/run_manifest.json to
      {results_dir}/run_manifest_<stage>.json. Workflow-level manifests unchanged.
```

## Verification

```bash
VIRTUAL_ENV=.venv PATH=".venv/bin:$PATH" PYTHONPATH=src \
  pytest tests/test_variant_calling.py -xvs -k "ShellQuoting or PerStageManifest"
VIRTUAL_ENV=.venv PATH=".venv/bin:$PATH" PYTHONPATH=src \
  pytest tests/test_variant_calling.py tests/test_variant_calling_workflows.py -xvs
rg "run_manifest\.json" src/flytetest/tasks/variant_calling.py
# expected: zero hits
rg "run_manifest_" src/flytetest/tasks/variant_calling.py | wc -l
# expected: 16
rg "shell=True" src/flytetest/tasks/variant_calling.py
# expected: ≤1 hit, inside bwa_mem2_mem
```

## Commit message

```
variant_calling: fix shell injection in bwa_mem2_mem + per-stage manifest filenames
```

## Checklist

- [ ] `shlex.quote` applied to `ref_path`, `r1_path`, `r2_path`, `rg`, `output_bam` in `bwa_mem2_mem`.
- [ ] All 16 task sites switched to `run_manifest_<stage>.json`.
- [ ] Workflow-level manifests (`workflows/variant_calling.py`) unchanged.
- [ ] 4 new tests passing.
- [ ] Existing `test_variant_calling*.py` suites still green.
- [ ] CHANGELOG entry includes the breaking-change note.
- [ ] Step 01 marked Complete in checklist.
