# Chapter 07: Testing your task

A flyteTest task is tested in three places. Catch logic bugs in the pure
function, manifest-shape bugs in direct task invocation, and contract bugs in
the registry / MCP layer. Each layer is cheap to run, fast to fail, and
catches a different class of mistake.

This chapter walks the ladder using a brand-new toy task added alongside the
chapter: `count_vcf_records`. It is the simplest possible end-to-end example
the codebase contains — one `File` input, one JSON `File` output, no scalars,
no SIF, no subprocess. Open the four `CountVcfRecords*` test classes in
`tests/test_variant_calling.py` and follow along.

## The task you are testing

`src/flytetest/tasks/_filter_helpers.py:90`
```python
def count_vcf_records(vcf_path: Path) -> dict:
    counts = {"header_lines": 0, "data_lines": 0}
    with vcf_path.open() as fh:
        for line in fh:
            if line.startswith("#"):
                counts["header_lines"] += 1
                continue
            if not line.strip():
                continue
            counts["data_lines"] += 1
    return counts
```

`src/flytetest/tasks/variant_calling.py:1331`
```python
@variant_calling_env.task
def count_vcf_records(vcf: File) -> File:
    in_vcf = require_path(Path(vcf.download_sync()), "Input VCF")
    out_dir = project_mkdtemp("count_vcf_records_")
    out_json = out_dir / "vcf_record_counts.json"
    captured: dict[str, int] = {}

    def _capture(vcf_path: Path) -> None:
        captured.update(count_vcf_records_pure(vcf_path=vcf_path))

    run_tool(python_callable=_capture, callable_kwargs={"vcf_path": in_vcf})
    _write_json(out_json, captured)
    ...
```

## Layer 1 — unit tests on the pure function

The pure function has no Flyte imports and no I/O beyond reading the input
file. Test it like any other Python function: build a tiny synthetic VCF in
a `tempfile.TemporaryDirectory`, call the function, assert on the return
dict.

`tests/test_variant_calling.py` — class `CountVcfRecordsUnitTests`
```python
def test_counts_header_and_data_lines(self):
    from flytetest.tasks._filter_helpers import count_vcf_records as count_pure
    counts = count_pure(self._write(_COUNT_RECORDS_SYNTHETIC_VCF))
    self.assertEqual(counts["header_lines"], 3)
    self.assertEqual(counts["data_lines"], 3)
```

Other tests in the class cover blank-line handling, data-only files, and the
empty-file boundary case.

What this layer catches: logic bugs. Off-by-one. Wrong handling of blank
lines. Misclassifying header lines. These are the bugs you will introduce
most often, and they are nearly free to test here — milliseconds per test.

## Layer 2 — direct task invocation

The thin wrapper has its own bugs to catch: did `download_sync` succeed, did
the output JSON land where the wrapper says it does, is the manifest envelope
shaped correctly. Build a `flyte.io.File` against a real path on disk and
call the task function directly — no scheduler, no executor.

`tests/test_variant_calling.py` — class `CountVcfRecordsInvocationTests`
```python
def _run(self) -> tuple[dict, dict, str]:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        vcf_file = tmp_path / "input.vcf"
        vcf_file.write_text(_COUNT_RECORDS_SYNTHETIC_VCF)

        result = count_vcf_records(vcf=File(path=str(vcf_file)))
        out_path = Path(result.path)
        counts = json.loads(out_path.read_text())
        manifest_path = out_path.parent / "run_manifest_count_vcf_records.json"
        manifest = json.loads(manifest_path.read_text())
    return counts, manifest, str(out_path)
```

The class then asserts each property the wrapper promises:
- the returned `File.path` ends in `.json`
- the JSON's counts match what was in the synthetic input
- `manifest["stage"] == "count_vcf_records"`
- `manifest["outputs"]["vcf_record_counts"]` equals the output path
- the manifest file exists alongside the output
- `manifest["record_counts"]` carries the count dict

What this layer catches: missing `download_sync`, wrong `MANIFEST_OUTPUT_KEYS`
declaration, output keys that disagree between `outputs={...}` and what the
manifest envelope ends up with, files written to the wrong directory.

## Layer 3 — registry shape

Layer 3 is fast and stateless: import the registry entry and assert its
fields. No file I/O. This is where you catch contract drift: the task added
a new output but its registry entry doesn't list it; the planner-type
declaration disagrees with the binding; the `showcase_module` points at the
wrong module.

`tests/test_variant_calling.py` — class `CountVcfRecordsRegistryTests`
```python
def setUp(self) -> None:
    from flytetest.registry import get_entry
    self.entry = get_entry("count_vcf_records")

def test_output_key_in_manifest_output_keys(self):
    output_names = {f.name for f in self.entry.outputs}
    self.assertIn("vcf_record_counts", output_names)
    self.assertIn("vcf_record_counts", MANIFEST_OUTPUT_KEYS)
```

Other tests in the class assert `category="task"`, the pipeline family,
accepted planner types, the showcase module path, exact input names, and
that `runtime_images` is empty (no SIF needed for a pure-Python task).

What this layer catches: a new output you added to the task wrapper that you
forgot to declare in the registry entry; mismatched planner-type
declarations; a typo in `showcase_module` that breaks MCP discovery.

## Layer 4 — MCP exposure

The fourth class asserts the flat tool is importable and registered. This
is the layer that catches "I added the task and tests, but forgot to wire it
up for MCP clients."

`tests/test_variant_calling.py` — class `CountVcfRecordsMCPExposureTests`
```python
def test_appears_in_supported_task_names(self):
    from flytetest.mcp_contract import SUPPORTED_TASK_NAMES
    self.assertIn("count_vcf_records", SUPPORTED_TASK_NAMES)

def test_flat_tool_importable_with_docstring(self):
    from flytetest.mcp_tools import vc_count_records
    self.assertTrue(callable(vc_count_records))
    self.assertTrue(vc_count_records.__doc__)

def test_task_parameters_entry_exact(self):
    from flytetest.server import TASK_PARAMETERS
    self.assertEqual(
        TASK_PARAMETERS["count_vcf_records"],
        (("vcf", True),),
    )
```

What this layer catches: `vc_<name>` not exported from `mcp_tools.py`; tool
name constant missing from `FLAT_TOOLS`; `TASK_PARAMETERS` not updated to
list the scalar param schema.

## Running the ladder

```
PYTHONPATH=src .venv/bin/python -m pytest tests/test_variant_calling.py -k "CountVcfRecords" -q
```

Expected output:
```
.....................                                                  [100%]
21 passed, ... deselected in 0.2s
```

If layer 1 fails, fix the pure function. If layer 2 fails but layer 1
passes, the bug is in the wrapper or the manifest envelope. If only
layer 3 or 4 fails, the code is correct but the contract surface — registry
entry, flat tool, `TASK_PARAMETERS` — is out of sync.

## What's next

[Chapter 08](08_workflow_composition.md) shows how to compose a task into a
workflow. [Chapter 10](10_verification.md) is the pre-PR checklist that
runs all four layers plus a `compileall` and a registry-presence smoke test.

---

[← Prev: Registry entry deep-dive](06_registry.md) · [Next: Composing a workflow →](08_workflow_composition.md)
