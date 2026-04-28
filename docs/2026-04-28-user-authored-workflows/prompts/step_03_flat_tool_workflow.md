# Step 03 — Flat MCP Tool for Composed Workflow

Read `src/flytetest/mcp_tools.py` — specifically `vc_annotate_variants_snpeff`
(the workflow-level flat tool closest in shape) before writing.

---

## Context

`germline_short_variant_discovery_filtered` is now registered as a workflow but
has no flat tool. This step adds `vc_germline_filtered` following the established
`vc_*` naming convention for workflow flat tools.

---

## Change — `src/flytetest/mcp_tools.py`

Append after `vc_custom_filter` (from Step 01):

```python
def vc_germline_filtered(
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
    """Apply QUAL threshold filtering to an existing variant call set.

    On-ramp reference composition: wires ``my_custom_filter`` into the pipeline
    without re-running upstream GATK steps.

    Required parameters:
      vcf_path   Absolute path to a joint-called or VQSR-filtered plain-text VCF.

    Optional parameters:
      min_qual   Minimum QUAL threshold (inclusive). Default 30.0.
      dry_run    If true, plan but do not execute.

    Resource parameters (Slurm only):
      partition, account, cpu, memory (e.g. "4Gi"), walltime (HH:MM:SS),
      shared_fs_roots (list of absolute path prefixes), module_loads.

    Example:
      vc_germline_filtered(
          vcf_path="/data/results/joint_called.vcf",
          min_qual=50.0,
      )

    All paths must be absolute.
    """
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
    return _run_workflow(
        workflow_name="germline_short_variant_discovery_filtered",
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
from flytetest.mcp_tools import vc_germline_filtered
result = vc_germline_filtered(vcf_path='/data/test.vcf', dry_run=True)
print('dry_run result:', result)
"
```
