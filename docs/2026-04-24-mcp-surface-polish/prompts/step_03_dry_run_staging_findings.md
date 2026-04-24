# Step 03 — Populate staging_findings in dry_run

`run_task` and `run_workflow` both return `DryRunReply` with `staging_findings=()`
hardcoded when `dry_run=True`. The user must separately call `validate_run_recipe`
to see staging issues. This defeats the purpose of dry_run as an inspect-before-
submit tool — staging findings should surface in the dry_run reply itself.

File: `src/flytetest/server.py`

There are two dry_run blocks to fix — one in `run_task` (~line 1923) and one in
`run_workflow` (~line 2203). Both are structurally identical.

---

## What staging_findings should contain

`staging_findings` is a `tuple[str, ...]` of human-readable finding strings from
`check_offline_staging` in `src/flytetest/staging.py`. Read that function before
implementing to understand what it returns and what arguments it needs.

The findings come from `check_offline_staging(runtime_images, tool_databases,
resolved_input_paths, shared_fs_roots)`. During dry_run, `shared_fs_roots` may
not be provided — in that case run the check with an empty tuple (local path
existence check only, no compute-node reachability check).

---

## Change pattern (apply to BOTH dry_run blocks)

Before (current):
```python
if dry_run:
    return asdict(
        DryRunReply(
            ...
            staging_findings=(),
            ...
        )
    )
```

After:
```python
if dry_run:
    from flytetest.staging import check_offline_staging
    _findings = check_offline_staging(
        runtime_images=runtime_images or {},
        tool_databases=tool_databases or {},
        resolved_input_paths=[],   # bindings not yet resolved at plan stage
        shared_fs_roots=tuple(
            Path(r) for r in (
                (resources or {}).get("shared_fs_roots") or []
            )
        ),
    )
    return asdict(
        DryRunReply(
            ...
            staging_findings=tuple(_findings),
            ...
        )
    )
```

Read the existing `run_task` and `run_workflow` non-dry_run paths to confirm how
`runtime_images`, `tool_databases`, and `resources` are named in each block —
the variable names may differ slightly.

---

## Important constraint

`staging_findings` is informational in dry_run — it must NOT block or raise even
if findings are non-empty. The dry_run reply is still returned with `supported=True`
and the frozen artifact. The scientist decides whether to proceed. Only actual
submission (`run_slurm_recipe`) should ever block on staging failures.

---

## Tests to add

Add tests for both `run_task` and `run_workflow` dry_run paths:
- When `runtime_images` contains a path to a non-existent SIF, `staging_findings`
  in the reply must be non-empty.
- When all paths exist, `staging_findings` must be empty.
- `supported` must be `True` in both cases (findings don't block the dry_run).

---

## Verification

```python
# Smoke test via Python (no MCP server needed)
import os, tempfile
os.chdir("/home/rmeht/Projects/flyteTest")
import sys; sys.path.insert(0, "src")

from flytetest.server import run_task
reply = run_task(
    task_name="create_sequence_dictionary",
    inputs={"reference_fasta": "/nonexistent/ref.fa"},
    runtime_images={"gatk_sif": "/nonexistent/gatk4.sif"},
    dry_run=True,
)
print("supported:", reply["supported"])           # must be True
print("staging_findings:", reply["staging_findings"])  # must be non-empty
```

```bash
PYTHONPATH=src python -m pytest tests/ -q 2>&1 | tail -5
```
