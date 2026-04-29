# Chapter 02 — Your first task: walkthrough

This chapter is a linear, top-to-bottom tour of the existing `my_custom_filter`
task. Every later chapter zooms into one piece of what you see here. Read this
once with the four real source files open in another pane and you will know
what an end-to-end user-authored task looks like in this repo.

You will not write any code in this chapter. You will read four files in a
specific order, then run the existing tests to confirm your environment is
working.

## Open these files alongside this chapter

Open these four paths in your editor before you start. The chapter walks them
in order:

1. `src/flytetest/tasks/_filter_helpers.py` — pure logic, no Flyte
2. `src/flytetest/tasks/variant_calling.py` — the Flyte task wrapper
3. `src/flytetest/registry/_variant_calling.py` — the registry entry
4. `src/flytetest/mcp_tools.py` — the MCP flat tool

Background reading: [`.codex/user_tasks.md`](../../../.codex/user_tasks.md)
covers the same shape as a condensed reference. This chapter is the
walkthrough; that file is the spec.

## Step 1 — The pure function

Start at the bottom of the stack. The actual filter logic lives in a
dependency-free helper module: standard-library only, no `flyte`, no `pysam`,
no containers. That property is what lets you unit-test it with plain
`pytest`.

`src/flytetest/tasks/_filter_helpers.py:12`

```python
def filter_vcf(
    in_path: Path,
    out_path: Path,
    min_qual: float,
    stats: dict[str, int] | None = None,
) -> None:
```

The signature takes paths and scalars and returns nothing — it writes to
`out_path`. The optional `stats` mapping is populated with per-run counts
(`malformed_lines_dropped`, `low_qual_dropped`, `missing_qual_dropped`,
`records_kept`) so the caller can record them in a manifest.

The body is plain text I/O: header lines starting with `#` pass through, data
lines are split on tab up to the QUAL column (index 5), and each record is
kept or dropped against `min_qual`. Missing QUAL (`.`), unparseable QUAL, and
malformed lines are all dropped — a "filtered" VCF must remain readable by
downstream tools.

Why a separate module? Two reasons:

- It can be imported and unit-tested without any Flyte machinery.
- It is reused inside `run_tool(python_callable=...)` mode without forcing the
  task wrapper to inline business logic.

Chapter 03 covers writing pure-logic helpers in detail.

## Step 2 — The task wrapper

Now move up one layer. The Flyte task is a thin wrapper that handles file
staging, calls the pure function through `run_tool`, and writes a manifest.
All the heavy lifting from Step 1 is reused — the wrapper adds nothing
biological.

The relevant imports at the top of the file:

`src/flytetest/tasks/variant_calling.py:14`

```python
from flytetest.config import (
    variant_calling_env,
    project_mkdtemp,
    require_path,
    run_tool,
)
from flytetest.tasks._filter_helpers import filter_vcf
from flytetest.manifest import build_manifest_envelope, write_json as _write_json
```

Note `_filter_helpers.filter_vcf` is imported here — the wrapper passes it
into `run_tool` as `python_callable`. Also note the `MANIFEST_OUTPUT_KEYS`
contract:

`src/flytetest/tasks/variant_calling.py:26`

```python
MANIFEST_OUTPUT_KEYS: tuple[str, ...] = (
    "sequence_dict",
    ...
)
```

`my_filtered_vcf` lives inside that tuple at line 71. A registry-manifest
contract test asserts that every output your registry entry declares appears
in `MANIFEST_OUTPUT_KEYS`. If you forget to append, the test fails loudly.

Now the task itself. Read the whole thing once:

`src/flytetest/tasks/variant_calling.py:1272`

```python
@variant_calling_env.task
def my_custom_filter(
    input_vcf: File,
    min_qual: float = 30.0,
) -> File:
    """Apply a pure-Python QUAL threshold filter to a plain-text VCF.
    ...
    """
    in_vcf = require_path(Path(input_vcf.download_sync()), "Input VCF")
    out_dir = project_mkdtemp("my_custom_filter_")
    out_vcf = out_dir / "my_filtered.vcf"

    stats: dict[str, int] = {}
    run_tool(
        python_callable=filter_vcf,
        callable_kwargs={
            "in_path": in_vcf,
            "out_path": out_vcf,
            "min_qual": min_qual,
            "stats": stats,
        },
    )

    require_path(out_vcf, "Filtered VCF output")
    ...
    manifest = build_manifest_envelope(
        stage="my_custom_filter",
        ...
        inputs={"input_vcf": str(in_vcf), "min_qual": min_qual},
        outputs={"my_filtered_vcf": str(out_vcf)},
    )
    manifest["filter_stats"] = stats
    _write_json(out_dir / "run_manifest_my_custom_filter.json", manifest)
    return File(path=str(out_vcf))
```

Walk it block by block:

- **`@variant_calling_env.task`** — the Flyte v2 task decorator for this
  pipeline family. Every task in `variant_calling.py` uses the same
  decorator; it carries the family's resource defaults and image hints.
- **Signature** — `input_vcf: File` is a typed Flyte file binding (the
  resolver hands it in from the planner). `min_qual: float = 30.0` is a
  scalar with a default. Notice the parameter is named `input_vcf`, not
  `vcf_path`. That is deliberate — see the naming-collision section in
  [`.codex/user_tasks.md`](../../../.codex/user_tasks.md). Chapter 06 covers
  the rule.
- **`download_sync()`** — `flyte.io.File` is a remote handle until you call
  this. After it, `in_vcf` is a real local `Path`.
- **`project_mkdtemp(...)`** — creates a scratch directory under the project
  results tree. Use this instead of `tempfile.mkdtemp()` so outputs survive
  inspection.
- **`run_tool(python_callable=filter_vcf, callable_kwargs={...})`** —
  Python-callable mode. No subprocess is started; the helper from Step 1 is
  invoked in-process. Compare with SIF mode (used by the GATK tasks) and
  native-executable mode in [`.codex/user_tasks.md`](../../../.codex/user_tasks.md).
- **`require_path(out_vcf, ...)`** — defensive existence check; raises
  immediately with a useful message if the helper failed to write the file.
- **`build_manifest_envelope(...)` + `_write_json(...)`** — the canonical way
  to produce a manifest. Do not hand-roll the dict. The output filename
  follows the `run_manifest_<stage>.json` convention.
- **Return value** — `File(path=str(out_vcf))` wraps the local path back into
  a Flyte `File` so downstream tasks can consume it.

Chapter 04 covers task wrappers in depth.

## Step 3 — The registry entry

The registry is what makes this task discoverable. Without an entry, MCP
clients cannot see it, the planner cannot route to it, and `list_entries`
will not return it. The entry lives next to all the other variant-calling
entries:

`src/flytetest/registry/_variant_calling.py:1312`

```python
RegistryEntry(
    name="my_custom_filter",
    category="task",
    description=(
        "Pure-Python QUAL threshold filter for plain-text VCFs. "
        "On-ramp reference example for user-authored tasks: no container, "
        "no external binary, invoked via run_tool Python-callable mode."
    ),
    inputs=(
        InterfaceField("input_vcf", "File", "Input VCF (uncompressed plain text)."),
        InterfaceField("min_qual", "float", "Minimum QUAL to retain a record (inclusive). Default 30.0."),
    ),
    outputs=(
        InterfaceField("my_filtered_vcf", "File", "QUAL-filtered output VCF."),
    ),
    tags=("variant_calling", "filter", "pure-python", "on-ramp"),
    compatibility=RegistryCompatibilityMetadata(
        biological_stage="custom QUAL filter",
        accepted_planner_types=("VariantCallSet",),
        produced_planner_types=("VariantCallSet",),
        ...
        execution_defaults={
            "profile": "local",
            "result_manifest": "run_manifest.json",
            "resources": {"cpu": "1", "memory": "4Gi", "execution_class": "local"},
            "slurm_resource_hints": {"cpu": "1", "memory": "4Gi", "walltime": "00:30:00"},
            "runtime_images": {},
            "tool_databases": {},
            "module_loads": ("python/3.11.9",),
        },
        ...
        pipeline_family="variant_calling",
        pipeline_stage_order=22,
    ),
    showcase_module="flytetest.tasks.variant_calling",
),
```

There are many fields. Four of them carry most of the weight:

- **`inputs` / `outputs`** — one `InterfaceField` per parameter. Each name
  must mirror the function signature exactly. The output name `my_filtered_vcf`
  must also appear in `MANIFEST_OUTPUT_KEYS` (see Step 2).
- **`accepted_planner_types`** — the planner-graph edges. `VariantCallSet`
  comes from `src/flytetest/planner_types.py`. The resolver matches the
  dataclass's `vcf_path` field into the task's `input_vcf` parameter.
- **`showcase_module="flytetest.tasks.variant_calling"`** — this single field
  is what makes the task auto-appear in MCP `list_entries`,
  `SUPPORTED_TASK_NAMES`, and `SHOWCASE_TARGETS`. Without it, the entry
  exists but no MCP surface knows how to call it.

Chapter 06 is the deep-dive on every field, the planner-type contract, and
the naming-collision gotcha. For now, keep moving.

## Step 4 — The MCP flat tool

The final layer is the MCP-facing wrapper. Flat tools are the user-friendly
surface — instead of asking a scientist to construct a `bindings + inputs`
dict, the flat tool exposes a flat keyword argument list and assembles the
dict internally:

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

Three things to notice:

- The user-facing parameter is named `input_vcf` — same name as the task
  signature. The planner-field name `vcf_path` only appears inside the
  `bindings` dict, where it must, because that is what `VariantCallSet`
  itself defines.
- The flat tool delegates to `_run_task("my_custom_filter", ...)`. The
  `task_name` here is the registry entry name from Step 3.
- Slurm parameters (`partition`, `account`, ...) are wired through
  `_resource_request(...)`. This is uniform across every flat tool in the
  file.

`vc_custom_filter` is also registered in the `FLAT_TOOLS` tuple at
`src/flytetest/mcp_tools.py:2127` — that is what surfaces the function to
MCP clients. Chapter 08 covers flat tools end-to-end, including the
docstring style requirements.

## Step 5 — Run the tests

You have now read the four files. Confirm the environment is wired correctly
by running the existing tests for this task. From the project root, with
your venv active and `PYTHONPATH=src`:

```bash
pytest -k "MyCustomFilter" -q
```

Expected output (final line):

```
23 passed, 128 deselected in 0.18s
```

The 23 tests are spread across three classes in
`tests/test_variant_calling.py`:

- `MyCustomFilterInvocationTests` (line 2757) — call the task directly with
  a fixture VCF and assert outputs and manifest contents
- `MyCustomFilterRegistryTests` (line 2828) — assert the `RegistryEntry`
  shape from Step 3
- `MyCustomFilterMCPExposureTests` (line 2875) — assert MCP discovery and
  `TASK_PARAMETERS` wiring

Then confirm registry discovery directly:

```bash
python -c "from flytetest.registry import REGISTRY_ENTRIES; print([e.name for e in REGISTRY_ENTRIES if e.name == 'my_custom_filter'])"
```

Expected output:

```
['my_custom_filter']
```

If both commands produce the expected output, your environment is correct and
the existing reference task is fully wired.

## What you have now seen

End-to-end, top to bottom: a pure helper, a task wrapper, a registry entry,
a flat MCP tool, and the tests that hold them together. That is the entire
shape of a user-authored task in this repo.

Chapters 03 through 10 each zoom into one of those pieces:

- Chapter 03 — pure helpers (`_filter_helpers.py` style)
- Chapter 04 — task wrappers (`@variant_calling_env.task`,
  `download_sync`, manifest envelope)
- Chapter 05 — `run_tool` modes (SIF, native, Python-callable)
- Chapter 06 — registry entries, planner types, naming collisions
- Chapter 07 — `MANIFEST_OUTPUT_KEYS` and the registry-manifest contract
- Chapter 08 — MCP flat tools and `FLAT_TOOLS` registration
- Chapter 09 — workflows that compose user-authored tasks
  (the `apply_custom_filter` reference)
- Chapter 10 — testing patterns for each of the above

Move on to Chapter 03 when you are ready.
