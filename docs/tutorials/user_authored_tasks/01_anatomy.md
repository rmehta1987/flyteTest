# Chapter 01 — Anatomy of a task

A flyteTest task is three files. Once you internalise that shape, every later
chapter is filling in details. This chapter walks the three layers using the
`my_custom_filter` reference task already in the repo — a pure-Python QUAL
filter for VCFs, deliberately small so the structure stays visible.

The three layers, top to bottom:

1. **Pure logic** — a standard-library Python module under
   `src/flytetest/tasks/_*_helpers.py` (or, when the logic is large enough,
   `src/flytetest/<area>/`). No Flyte imports. Unit-testable with plain
   `pytest`.
2. **Thin task wrapper** — a function in `src/flytetest/tasks/<family>.py`
   decorated with `@<family>_env.task`. Owns I/O staging, manifest writing, and
   delegates the actual work to layer 1 via `run_tool`.
3. **Registry entry** — a `RegistryEntry` appended to the family tuple in
   `src/flytetest/registry/_<family>.py`. Metadata that exposes the task to MCP
   clients and the planner.

Each layer has one job. Mixing them is the most common author mistake.

## Layer 1 — Pure logic

`src/flytetest/tasks/_filter_helpers.py:12`

```python
def filter_vcf(
    in_path: Path,
    out_path: Path,
    min_qual: float,
    stats: dict[str, int] | None = None,
) -> None:
    """Write a QUAL-filtered copy of a plain-text VCF."""
    counts = {"malformed_lines_dropped": 0, "low_qual_dropped": 0,
              "missing_qual_dropped": 0, "records_kept": 0}
    with in_path.open() as fh_in, out_path.open("w") as fh_out:
        for line in fh_in:
            if line.startswith("#"):
                fh_out.write(line)
                continue
            ...
```

What is *not* here:

- No `flyte.io.File`. Just `pathlib.Path` in, file written to disk.
- No `@task` decorator, no `run_tool`, no manifest envelope.
- No third-party imports — only the standard library.

That separation is the point. You can run this against a tiny on-disk VCF
fixture under plain `pytest` without spinning up Flyte, a SIF, or a Flyte
storage stub. The module-level docstring at
`src/flytetest/tasks/_filter_helpers.py:1` enforces the contract:

```python
"""Pure-Python VCF filtering helpers.

Intentionally dependency-free: no pysam, no htslib, no external packages.
Import only from the standard library.
"""
```

When you write your own task, start here. Get the function right and tested,
*then* wrap it.

## Layer 2 — Thin task wrapper

`src/flytetest/tasks/variant_calling.py:1272`

```python
@variant_calling_env.task
def my_custom_filter(
    input_vcf: File,
    min_qual: float = 30.0,
) -> File:
    """Apply a pure-Python QUAL threshold filter to a plain-text VCF."""
    in_vcf = require_path(Path(input_vcf.download_sync()), "Input VCF")
    out_dir = project_mkdtemp("my_custom_filter_")
    out_vcf = out_dir / "my_filtered.vcf"

    stats: dict[str, int] = {}
    run_tool(
        python_callable=filter_vcf,
        callable_kwargs={"in_path": in_vcf, "out_path": out_vcf,
                         "min_qual": min_qual, "stats": stats},
    )
    require_path(out_vcf, "Filtered VCF output")

    manifest = build_manifest_envelope(
        stage="my_custom_filter",
        ...
        outputs={"my_filtered_vcf": str(out_vcf)},
    )
    _write_json(out_dir / "run_manifest_my_custom_filter.json", manifest)
    return File(path=str(out_vcf))
```

The wrapper does five things, in order:

1. **Resolve inputs to a local `Path`.** `download_sync()` brings the blob to
   disk; `require_path` fails fast with a readable message if staging didn't
   produce a real file.
2. **Create a deterministic output directory** with `project_mkdtemp` so retries
   and parallel runs don't trample each other.
3. **Delegate to layer 1 via `run_tool`.** Python-callable mode means no
   subprocess and no container — `run_tool` calls `filter_vcf(**callable_kwargs)`
   in-process. Going through `run_tool` even here is deliberate: every task in
   the codebase reaches its tool through the same entry point.
4. **Write a manifest** with `build_manifest_envelope`. Every key under
   `manifest["outputs"]` (here, `"my_filtered_vcf"`) must already appear in the
   module's `MANIFEST_OUTPUT_KEYS` tuple at
   `src/flytetest/tasks/variant_calling.py:26`, or a registry-manifest contract
   test fails.
5. **Return `flyte.io.File`** wrapping the local output path.

The wrapper does not implement filtering. It stages, runs, records, returns.

## Layer 3 — Registry entry

`src/flytetest/registry/_variant_calling.py:1312`

```python
RegistryEntry(
    name="my_custom_filter",
    category="task",
    description="Pure-Python QUAL threshold filter for plain-text VCFs. ...",
    inputs=(
        InterfaceField("input_vcf", "File", "Input VCF (uncompressed plain text)."),
        InterfaceField("min_qual", "float", "Minimum QUAL to retain a record ..."),
    ),
    outputs=(
        InterfaceField("my_filtered_vcf", "File", "QUAL-filtered output VCF."),
    ),
    tags=("variant_calling", "filter", "pure-python", "on-ramp"),
    compatibility=RegistryCompatibilityMetadata(
        accepted_planner_types=("VariantCallSet",),
        produced_planner_types=("VariantCallSet",),
        execution_defaults={
            "profile": "local",
            "resources": {"cpu": "1", "memory": "4Gi", "execution_class": "local"},
            "runtime_images": {},
            "module_loads": ("python/3.11.9",),
            ...
        },
        pipeline_family="variant_calling",
        pipeline_stage_order=22,
        ...
    ),
    showcase_module="flytetest.tasks.variant_calling",
),
```

The registry entry is metadata only. It does not run code. It:

- Names and describes the task for `list_entries`.
- Mirrors the wrapper signature one-for-one in `inputs` / `outputs`.
- Declares planner-graph edges via `accepted_planner_types` /
  `produced_planner_types` — names must exist in
  `src/flytetest/planner_types.py`.
- Supplies execution defaults: `runtime_images` is empty (pure Python has no
  SIF) and `apptainer/1.4.1` is absent from `module_loads` for the same reason.
- Sets `showcase_module="flytetest.tasks.variant_calling"`, which is what makes
  the task auto-appear in MCP `list_entries` and `SHOWCASE_TARGETS`.

Every field is covered field-by-field in [chapter 06 — registry entry
deep-dive](./06_registry.md).

## How the three layers connect

Walk one MCP call through the layers. A scientist invokes the
`vc_custom_filter` flat tool with an input VCF path and a `min_qual` threshold:

1. The flat tool in `mcp_tools.py` builds typed `bindings` and scalar `inputs`,
   then delegates to `run_task`.
2. `run_task` looks up the `my_custom_filter` registry entry, validates the
   planner types, and resolves the `VariantCallSet` binding into the
   `input_vcf: File` parameter.
3. The Flyte runtime invokes the layer 2 wrapper. The wrapper calls
   `download_sync`, `project_mkdtemp`, then `run_tool(python_callable=...)`.
4. `run_tool` invokes layer 1 — `filter_vcf` — directly in-process.
5. The wrapper writes the manifest and returns a `File` pointing at the new VCF.
6. `run_task` packages the result into a `RunReply` for MCP.

Three layers, three responsibilities, one call path. If something breaks, you
know which layer to open.

## Forward pointers

- [Chapter 02 — End-to-end walkthrough](./02_walkthrough.md) opens these three
  files in sequence and changes a real value, end to end.
- [Chapter 06 — Registry entry deep-dive](./06_registry.md) covers every
  `RegistryEntry` field, including the planner-type fields and execution
  defaults skipped here.
- For the authoritative reference on layer boundaries, naming, and gotchas, see
  `.codex/user_tasks.md`.
