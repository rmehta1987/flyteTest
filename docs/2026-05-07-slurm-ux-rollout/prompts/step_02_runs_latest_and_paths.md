# Step 02 — runs/latest symlink + monitor_slurm_job paths-in-response

## Context

After Step 01, every artifact for a run lives under `.runtime/runs/<recipe_id>/`. This step adds two complementary UX wins:

1. **`runs/latest` symlink** — `cd .runtime/runs/latest` always lands on the most recent submission. No need to type or paste a long timestamped recipe_id.
2. **`monitor_slurm_job` paths-in-response** — the structured response carries every relevant absolute path so the user can copy directly without reconstructing.

Inputs and outputs physically live on cluster scratch (shared FS roots) and can't move into the run dir, so `inputs/` and `outputs/` stay as named symlinks within the run dir.

## Files to read before editing

- `src/flytetest/spec_executor.py` `_submit_saved_artifact` (~line 2127, post-Step 01) — find the post-submission write hook
- `src/flytetest/server.py:3204` — current `monitor_slurm_job` response shape
- Slide image 4 in `Bioinformatics_Agentic_AI.pptx` — `show_run` already returns paths; align `monitor_slurm_job` to match

## Files to create / edit

| Action | File |
|---|---|
| Edit | `src/flytetest/spec_executor.py` |
| Edit | `src/flytetest/server.py` |
| Edit | `tests/test_spec_executor.py` (or matching test file) |
| Edit | `tests/test_server.py` (or wherever `monitor_slurm_job` is tested) |
| Edit | `CHANGELOG.md` |

## Implementation instructions

### `src/flytetest/spec_executor.py` — `_submit_saved_artifact` post-write hook

After the run record is written and sbatch returns the jobid, create three things in the run dir:

```python
def _create_run_dir_links(run_dir: Path, *, jobid: str, shared_fs_roots: tuple[Path, ...]) -> None:
    """Create user-facing convenience links inside the run dir.

    - inputs/  → first declared shared FS root (or named per-root symlinks if multi-root)
    - outputs/ → run output root (assumed conventional location relative to run_dir)
    - stdout.log / stderr.log: NOT created here — Slurm controls slurm-<jobid>.out
      naming, and we keep those filenames as-is. Users can `cat slurm-*.out` directly.

    Idempotent: existing symlinks are removed and recreated to point at the
    most recent attempt.
    """
    inputs_link = run_dir / "inputs"
    outputs_link = run_dir / "outputs"
    if inputs_link.is_symlink() or inputs_link.exists():
        inputs_link.unlink()
    if outputs_link.is_symlink() or outputs_link.exists():
        outputs_link.unlink()
    if shared_fs_roots:
        # Single-root case: a flat `inputs/` symlink. Multi-root: per-root named links.
        if len(shared_fs_roots) == 1:
            inputs_link.symlink_to(shared_fs_roots[0])
        else:
            inputs_link.mkdir()
            for root in shared_fs_roots:
                (inputs_link / root.name).symlink_to(root)
    # outputs_link target convention TBD — likely the run dir itself or a
    # subdirectory; consult `run_local_recipe` / `run_slurm_recipe` for where
    # outputs actually land. If outputs are scattered, this may be a no-op.
```

Then update `.runtime/runs/latest`:

```python
def _update_latest_symlink(runs_root: Path, recipe_id: str) -> None:
    """Point .runtime/runs/latest at <recipe_id>. Idempotent on retry."""
    latest = runs_root / "latest"
    if latest.is_symlink() or latest.exists():
        latest.unlink()
    latest.symlink_to(recipe_id)  # relative target — within runs_root
```

Both helpers run after `save_slurm_run_record(record)` succeeds. If sbatch fails, neither is updated — the symlinks always reflect the most recent successful submission.

### `src/flytetest/server.py:3204` — `monitor_slurm_job` response

Audit the current response. Ensure the dict carries (in addition to whatever's already there):

```python
{
    ...,
    "spec_path": "/abs/path/to/.runtime/runs/<recipe_id>/spec.json",
    "run_record_path": "/abs/path/to/.runtime/runs/<recipe_id>/slurm_run_record.json",
    "stdout_path": "/abs/path/to/.runtime/runs/<recipe_id>/slurm-<jobid>.out",
    "stderr_path": "/abs/path/to/.runtime/runs/<recipe_id>/slurm-<jobid>.err",
    "outputs_dir": "/abs/path/to/.runtime/runs/<recipe_id>/outputs/" | None,
    "inputs_dir":  "/abs/path/to/.runtime/runs/<recipe_id>/inputs/"  | None,
}
```

All paths absolute. `outputs_dir` and `inputs_dir` may be `None` if the symlinks weren't created (e.g., no shared_fs_roots declared).

### Tests

- After `_submit_saved_artifact` succeeds (mocked sbatch), assert `.runtime/runs/latest` is a symlink resolving to `<recipe_id>`.
- After a retry (second `_submit_saved_artifact` call with a new recipe_id), assert `.runtime/runs/latest` now points at the new dir.
- `monitor_slurm_job(...)` response includes all 6 path fields as absolute strings.
- `monitor_slurm_job(...)` on a record where shared_fs_roots was empty returns `inputs_dir: None` (or omits the field cleanly).

## Acceptance criteria

- After `_submit_saved_artifact` returns: `readlink .runtime/runs/latest` resolves to `<recipe_id>`
- `cd .runtime/runs/<recipe_id>` shows: `spec.json`, `slurm_run_record.json`, `slurm-<jobid>.out`, `slurm-<jobid>.err`, `inputs` (symlink), `outputs` (symlink — may be empty if outputs land elsewhere)
- `monitor_slurm_job(...)` response carries `spec_path`, `run_record_path`, `stdout_path`, `stderr_path`, `outputs_dir`, `inputs_dir` as absolute paths
- Tests pass

## CHANGELOG entry template

```
## Unreleased

### Slurm UX rollout — Phase 0 step 02 (2026-05-07)

- [x] 2026-05-07 `spec_executor.py` `_submit_saved_artifact`: creates `.runtime/runs/latest` symlink to most recent recipe_id, plus `inputs/` and `outputs/` named symlinks within each run dir. Idempotent on retry.
- [x] 2026-05-07 `server.py:3204` `monitor_slurm_job`: response now carries `spec_path`, `run_record_path`, `stdout_path`, `stderr_path`, `outputs_dir`, `inputs_dir` as absolute paths. User can copy any path directly from the response without reconstruction.
```
