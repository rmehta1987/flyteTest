# Chapter 4: Manifests and outputs

Every task emits a JSON manifest next to its output file. Downstream stages,
retry logic, and the MCP result viewer read this manifest instead of guessing
at file paths or re-running the planner. Two helpers and one tuple keep the
contract tight: `MANIFEST_OUTPUT_KEYS`, `build_manifest_envelope()`, and
`write_json()` (imported as `_write_json` by task modules). This chapter walks
through them using `my_custom_filter` from [Chapter 2](02_first_task.md) as
the worked example.

## The output keys declaration

Every key the module writes under `manifest["outputs"]` must appear in the
module-level `MANIFEST_OUTPUT_KEYS` tuple at the top of the tasks file. A
registry-manifest contract test asserts that every output name declared in a
`RegistryEntry` is also present in this tuple.

`src/flytetest/tasks/variant_calling.py:29`

```python
MANIFEST_OUTPUT_KEYS: tuple[str, ...] = (
    "sequence_dict",
    "feature_index",
    ...
    # On-ramp reference task
    "my_filtered_vcf",
)
```

Three rules:

- Declare the tuple at **module scope**, not inside a task body. It is read
  during import by registry contract tests.
- Names must match the keys passed to `outputs={...}` in
  `build_manifest_envelope`.
- When you add a new task with a new output, append the name here. This is
  the easy-to-miss cross-cutting edit reviewers always look for.

## Building the envelope

`build_manifest_envelope()` assembles the shared skeleton. Do not hand-roll
the dict — the helper enforces the four required fields (`stage`,
`assumptions`, `inputs`, `outputs`) and optional `code_reference` /
`tool_ref` slots so every manifest in the repo has the same shape. See the
signature and docstring at `src/flytetest/manifest.py:22`.

The call inside `my_custom_filter`:

`src/flytetest/tasks/variant_calling.py:1311`

```python
manifest = build_manifest_envelope(
    stage="my_custom_filter",
    assumptions=[
        "Input VCF is uncompressed plain text.",
        "QUAL field is numeric or '.' (missing QUAL treated as below threshold).",
        "Malformed lines (<6 tab fields, blank, or unparseable QUAL) are dropped.",
    ],
    inputs={"input_vcf": str(in_vcf), "min_qual": min_qual},
    outputs={"my_filtered_vcf": str(out_vcf)},
)
manifest["filter_stats"] = stats
```

Argument by argument:

- `stage` — the task function name, written verbatim. Self-identifying when
  the manifest is read outside a running workflow.
- `assumptions` — ordered notes about what the task assumed of its inputs.
  Useful when a downstream stage breaks and you need to reconstruct decisions.
- `inputs` — paths and scalars the task received. Always coerce `Path` to
  `str` here; `as_json_compatible()` does it for you on write, but explicit
  is cleaner.
- `outputs` — the keys must be a subset of `MANIFEST_OUTPUT_KEYS`. Values are
  the on-disk paths the task produced.

After the envelope is built you can attach extra task-specific provenance —
`my_custom_filter` records its `filter_stats` (how many records passed,
failed, were malformed) before writing.

## Writing the manifest

`write_json()` (imported as `_write_json`) serializes the dict with
2-space indentation, normalizing `Path` and `tuple` payloads via
`as_json_compatible()`. It also creates the parent directory if needed, so
tasks do not have to `mkdir` first.

`src/flytetest/manifest.py:108`

The call from `my_custom_filter`:

`src/flytetest/tasks/variant_calling.py:1322`

```python
_write_json(out_dir / "run_manifest_my_custom_filter.json", manifest)
```

The file lands **next to the task output** in the same `project_mkdtemp`
directory. The naming convention is `run_manifest_<stage>.json` for
individual variant-calling tasks (and `run_manifest.json` at the workflow
level — see Chapter 8).

## Staging inputs with `download_sync`

A `flyte.io.File` is a remote handle, not a local path. The first thing a
task does is materialize each input file onto the worker filesystem with
`download_sync()`, then wrap the result with `require_path()` so a missing
or zero-byte file fails fast with a clear message.

`src/flytetest/tasks/variant_calling.py:1285`

```python
in_vcf = require_path(Path(input_vcf.download_sync()), "Input VCF")
```

Always call `download_sync()` before passing the file to `run_tool`, the
filter helper, or any other consumer. Reading `input_vcf.path` directly
works in some local-stub test paths but fails on real Flyte workers where
the file has not been staged yet.

## Sample manifest JSON shape

Running `my_custom_filter` on a small synthetic VCF produces a manifest
that looks like this (paths shortened for readability):

```json
{
  "stage": "my_custom_filter",
  "assumptions": [
    "Input VCF is uncompressed plain text.",
    "QUAL field is numeric or '.' (missing QUAL treated as below threshold).",
    "Malformed lines (<6 tab fields, blank, or unparseable QUAL) are dropped."
  ],
  "inputs": {
    "input_vcf": "/tmp/.../input.vcf",
    "min_qual": 30.0
  },
  "outputs": {
    "my_filtered_vcf": "/tmp/.../my_custom_filter_xxxx/my_filtered.vcf"
  },
  "filter_stats": {
    "records_kept": 1,
    "records_filtered": 2,
    "malformed_lines_dropped": 0
  }
}
```

The first four keys are the envelope; anything below them (`filter_stats`
here) is task-specific provenance attached after the envelope is built.

## Common pitfalls

- **`MANIFEST_OUTPUT_KEYS` declared inside a task body.** It must live at
  module scope so registry import-time contract tests can read it.
- **Adding a new return value but forgetting the key.** The registry will
  define an output with no matching entry in the tuple; the contract test in
  `tests/test_variant_calling.py` (see `MyCustomFilterRegistryTests` at
  line 2828) fails with a clear message. Append the new name to the tuple.
- **Skipping `download_sync()` and using `flyte.io.File.path` directly.** Works
  in some local stubs, fails on real workers where the file is not yet on
  disk. Always materialize first, then `require_path()`.

## What's next

- [Chapter 5: The binding contract](05_bindings.md) — how planner-type fields
  reach the task parameters you saw in the `inputs={...}` dict above.
- [Chapter 6: Registry entry deep-dive](06_registry.md) — where the registry
  validates declared outputs against `MANIFEST_OUTPUT_KEYS`.
- [Chapter 7: Testing your task](07_testing.md) — asserting manifest shape and
  `outputs` keys in unit tests.

---

[← Prev: Execution modes](03_execution_modes.md) · [Next: The binding contract →](05_bindings.md)
