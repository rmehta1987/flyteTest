# Step 01 — Flat MCP Tool for `my_custom_filter`

Read `src/flytetest/mcp_tools.py` — specifically `vc_annotate_variants_snpeff`
(the task-level flat tool closest in shape to what we need) before writing.

---

## Context

`my_custom_filter` is registered in the registry and in `TASK_PARAMETERS`, but has
no flat tool in `mcp_tools.py`. MCP clients that only navigate flat tools cannot
call it. This step adds `vc_custom_filter`.

---

## Change — `src/flytetest/mcp_tools.py`

Append after `annotation_exonerate_chunk`. Follow the shape of
`vc_annotate_variants_snpeff` (task-level flat tool, `run_task` delegate):

```python
def vc_custom_filter(
    vcf_path: str,
    min_qual: float = 30.0,
    dry_run: bool = False,
    partition: str = "",
    account: str = "",
    cpu: int = 1,
    memory: str = "4Gi",
    walltime: str = "00:30:00",
    shared_fs_roots: list[str] | None = None,
    module_loads: list[str] | None = None,
) -> dict:
    """Apply a pure-Python QUAL threshold filter to a plain-text VCF.

    Drops records with QUAL below ``min_qual`` or with missing QUAL (``.``).
    Header lines are always preserved. No container required.

    Required parameters:
      vcf_path   Absolute path to input VCF (uncompressed plain text).

    Optional parameters:
      min_qual   Minimum QUAL threshold (inclusive). Default 30.0.
      dry_run    If true, plan but do not execute.

    Resource parameters (Slurm only):
      partition, account, cpu, memory (e.g. "4Gi"), walltime (HH:MM:SS),
      shared_fs_roots (list of absolute path prefixes), module_loads.

    Example:
      vc_custom_filter(
          vcf_path="/data/results/joint_called.vcf",
          min_qual=50.0,
      )

    All paths must be absolute.
    """
    from flytetest.planner_types import VariantCallSet

    bindings = {
        "VariantCallSet": {"vcf_path": vcf_path},
    }
    inputs: dict[str, object] = {
        "min_qual": min_qual,
    }
    resource_request = _resource_request(
        partition=partition,
        account=account,
        cpu=cpu,
        memory=memory,
        walltime=walltime,
        shared_fs_roots=shared_fs_roots,
        module_loads=module_loads,
    )
    return _run_task(
        task_name="my_custom_filter",
        bindings=bindings,
        inputs=inputs,
        resource_request=resource_request,
        dry_run=dry_run,
    )
```

---

## Verification

```bash
python3 -m compileall src/flytetest/mcp_tools.py

PYTHONPATH=src python3 -c "
from flytetest.mcp_tools import vc_custom_filter
result = vc_custom_filter(vcf_path='/data/test.vcf', dry_run=True)
print('dry_run result:', result)
"
```
