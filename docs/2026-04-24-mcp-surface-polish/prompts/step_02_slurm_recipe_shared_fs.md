# Step 02 — Add shared_fs_roots to run_slurm_recipe

`validate_run_recipe` accepts `shared_fs_roots` and runs `check_offline_staging`
with those roots. But `run_slurm_recipe` takes only `artifact_path` and calls
`_run_slurm_recipe_impl` without any roots, so the staging preflight is silently
skipped at actual submission time. A scientist who validates before submitting
gets a stronger guarantee than what actually fires on submit.

File: `src/flytetest/server.py`

---

## Changes

### 1. `run_slurm_recipe` (line ~2853)

Add `shared_fs_roots` parameter with default `None`:

```python
def run_slurm_recipe(
    artifact_path: str,
    shared_fs_roots: list[str] | None = None,
) -> dict[str, object]:
    """Submit a previously frozen workflow-spec recipe artifact to Slurm.

    Args:
        artifact_path: Path to the frozen recipe artifact to submit.
        shared_fs_roots: Filesystem prefixes visible to compute nodes. When
            provided, runs check_offline_staging before sbatch to verify
            containers, tool databases, and input paths are reachable from
            compute nodes. Omit to skip staging preflight.
    """
    return _run_slurm_recipe_impl(artifact_path, shared_fs_roots=shared_fs_roots)
```

### 2. `_run_slurm_recipe_impl` (line ~2788)

Add `shared_fs_roots` parameter and pass it to `.submit()`:

```python
def _run_slurm_recipe_impl(
    artifact_path: str | Path,
    *,
    run_dir: Path | None = None,
    sbatch_runner: Any = subprocess.run,
    command_available: Any = None,
    resume_from_local_record: str | Path | None = None,
    shared_fs_roots: list[str] | None = None,   # ← add
) -> dict[str, object]:
```

Then pass it to `.submit()`:
```python
result = SlurmWorkflowSpecExecutor(...).submit(
    Path(artifact_path),
    resume_from_local_record=...,
    shared_fs_roots=tuple(Path(r) for r in (shared_fs_roots or [])),   # ← add
)
```

Check `SlurmWorkflowSpecExecutor.submit` signature in `src/flytetest/spec_executor.py`
to confirm it accepts `shared_fs_roots` — it should, since `run_task` and
`run_workflow` already pass it through (lines ~1947 and ~2232 in server.py).

---

## Backwards compatibility

`shared_fs_roots=None` (the default) must preserve existing behaviour: staging
preflight is skipped, same as before this change.

---

## Tests to add

Add a test that when `shared_fs_roots` is provided to `run_slurm_recipe`, it is
passed through to the executor's `.submit()` call. Use the same injection pattern
used for `sbatch_runner` in existing `run_slurm_recipe` tests.

---

## Verification

```bash
# Confirm the new parameter is accepted
PYTHONPATH=src python -c "
import inspect
from flytetest.server import run_slurm_recipe
print(inspect.signature(run_slurm_recipe))
# must show shared_fs_roots parameter
"

PYTHONPATH=src python -m pytest tests/ -q 2>&1 | tail -5
```
