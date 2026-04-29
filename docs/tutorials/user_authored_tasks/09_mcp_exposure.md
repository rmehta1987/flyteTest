# Chapter 9: MCP exposure

Three things make a registered task or workflow callable from an MCP client:

1. The `showcase_module` field on the `RegistryEntry` — discovery.
2. A flat-tool wrapper in `mcp_tools.py` — the JSON surface clients see.
3. A `TASK_PARAMETERS` row in `server.py` — scalar-input validation
   (tasks only).

Workflows skip the third piece. This chapter walks through both, using
`my_custom_filter` (task) and `apply_custom_filter` (workflow).

## Piece 1: `showcase_module` in the registry entry

`SHOWCASE_TARGETS` — the canonical list of MCP-callable names — is *derived*
from any `RegistryEntry` whose `showcase_module` is set. Set the field, your
entry shows up; leave it `None`, it stays internal.

`src/flytetest/mcp_contract.py:483`

```python
SHOWCASE_TARGETS = tuple(
    ShowcaseTarget(
        name=entry.name,
        category=entry.category,
        module_name=entry.showcase_module,
        source_path=_resolve_source_path(entry.showcase_module),
    )
    for entry in REGISTRY_ENTRIES
    if entry.showcase_module
)
```

The on-ramp task points at the tasks file, the workflow points at the
workflows file:

`src/flytetest/registry/_variant_calling.py:1348`

```python
showcase_module="flytetest.tasks.variant_calling",
```

`src/flytetest/registry/_variant_calling.py:1391`

```python
showcase_module="flytetest.workflows.variant_calling",
```

That single field is enough to make the entry visible through
`list_entries`, `SUPPORTED_TASK_NAMES` / `SUPPORTED_WORKFLOW_NAMES`, and the
bundle/recipe resolvers.

## Piece 2: The flat tool

A flat tool is a Python function with **only scalar parameters** (string
paths, ints, floats, bools, optional list-of-str). MCP clients see those
parameters directly in their JSON schema. The body assembles the two-layer
`bindings` / `inputs` dict from [Chapter 5](05_bindings.md) and delegates
to `run_task` (or `run_workflow`).

`src/flytetest/mcp_tools.py:948`

```python
def vc_custom_filter(
    input_vcf: str,
    min_qual: float = 30.0,
    partition: str = "",
    account: str = "",
    cpu: int = 0,
    memory: str = "",
    walltime: str = "",
    shared_fs_roots: list[str] | None = None,
    module_loads: list[str] | None = None,
    dry_run: bool = False,
) -> dict:
    """Apply a pure-Python QUAL threshold filter to a plain-text VCF.
    ...
    Example
    -------
    >>> vc_custom_filter(
    ...     input_vcf="/data/results/joint_called.vcf",
    ...     min_qual=50.0,
    ... )

    All paths must be absolute.
    """
    return _run_task(
        task_name="my_custom_filter",
        bindings={"VariantCallSet": {"vcf_path": input_vcf}},
        inputs={"input_vcf": input_vcf, "min_qual": min_qual},
        resource_request=_resource_request(
            partition, account, cpu, memory, walltime, shared_fs_roots, module_loads
        ),
        dry_run=dry_run,
    )
```

Things to notice:

- **Signature.** Only scalars. Absolute paths arrive as plain `str`, not
  `flyte.io.File` — the MCP boundary translates them into typed bindings.
- **Body.** `bindings` keys on the planner type and its field name
  (`VariantCallSet` → `vcf_path`); `inputs` keys on the task parameter
  name (`input_vcf`). The naming-collision rule from Chapter 5 lives
  inside this dict.
- **Delegation through a deferred import.** `_run_task` lazy-imports
  `flytetest.server.run_task` at call time:

  `src/flytetest/mcp_tools.py:31`

  ```python
  def _run_task(*args, **kwargs):
      from flytetest.server import run_task
      return run_task(*args, **kwargs)
  ```

  `server.py` registers these flat tools, so a top-level
  `from flytetest.server import run_task` here would create an import
  cycle.

The docstring is the only prose the MCP client sees — see
[The MCP docstring standard](#the-mcp-docstring-standard) below.

## Piece 3: `TASK_PARAMETERS` in `server.py` (tasks only)

`TASK_PARAMETERS` tells `run_task` which **scalar** (non-`File`, non-`Dir`)
inputs the task accepts and which are required.

`src/flytetest/server.py:310`

```python
"my_custom_filter": (
    ("input_vcf", True),
    ("min_qual", False),
),
```

Rules:

- Each entry is `(parameter_name, required)`. `True` for parameters with
  no default; `False` otherwise.
- `File` and `Dir` parameters are handled by typed bindings and do
  **not** appear here.
- Forgetting this row is the most common cause of a flat tool that
  imports cleanly but rejects valid calls at runtime.

Workflows skip this — `showcase_module` alone is sufficient.

## Workflow flat tools — same shape

Workflow flat tools follow the same template; the only difference is the
delegate function and the absence of a `TASK_PARAMETERS` row.

`src/flytetest/mcp_tools.py:1009`

```python
def vc_apply_custom_filter(
    input_vcf: str,
    min_qual: float = 30.0,
    ...
) -> dict:
    """Apply a user-authored QUAL filter to an existing variant call set.
    ...
    """
    return _run_workflow(
        workflow_name="apply_custom_filter",
        bindings={"VariantCallSet": {"vcf_path": input_vcf}},
        inputs={"input_vcf": input_vcf, "min_qual": min_qual},
        resource_request=_resource_request(
            partition, account, cpu, memory, walltime, shared_fs_roots, module_loads
        ),
        dry_run=dry_run,
    )
```

Both flat tools are registered side-by-side in `create_mcp_server()`:

`src/flytetest/server.py:4571`

```python
mcp.tool(description=TOOL_DESCRIPTIONS[VC_CUSTOM_FILTER_TOOL_NAME])(_mcp_tools.vc_custom_filter)
mcp.tool(description=TOOL_DESCRIPTIONS[VC_APPLY_CUSTOM_FILTER_TOOL_NAME])(_mcp_tools.vc_apply_custom_filter)
```

Their tool-name constants are also added to the `FLAT_TOOLS` tuple in
`mcp_contract.py` so they appear in `MCP_TOOL_NAMES`.

## The MCP docstring standard

The flat-tool docstring is the only prose an MCP client ever sees about
the tool. The repo standard (`AGENTS.md` under *Prompt / MCP / Slurm*,
with broader documentation guidance in `.codex/documentation.md`) requires
every `@mcp.tool` docstring to:

- name the valid parameter keys (matching the function signature),
- include a concrete invocation example, and
- state that all paths must be absolute.

`vc_custom_filter` above hits all three: parameter list, a `>>>` block
with a real path, and the trailing `All paths must be absolute.` line.
Keep this template when you add your own.

## What's next

[Chapter 10](10_verification.md) walks through verifying a new flat
tool: `python -m compileall`, the importable-flat-tool smoke check
(`from flytetest.mcp_tools import <your_tool>`), and the registry
contract tests reviewers will look for.
