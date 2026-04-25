# Step 04 — Test Classes in `tests/test_variant_calling.py`

Read the following before starting:
- `tests/test_variant_calling.py` lines 52-99 — `RegistryEntryShapeTests` and the
  first invocation test (for the reference task pattern, including `File` stub usage)
- `tests/flyte_stub.py` lines 67-94 — `File.download_sync()` passthrough and the
  `@task` no-op decorator
- `tests/test_my_filter.py` (written in Step 02) — the synthetic VCF fixture shape

Add three test classes to `tests/test_variant_calling.py`. Append them after the
existing classes.

---

## Class 1 — `MyCustomFilterInvocationTests` (Layer 2)

This is the first pure-Python task in the repo: **no `run_tool` subprocess, no
`patch.object(config, "run_tool", ...)`**. Call the task directly with a `File`
stub and assert outputs and manifest.

```python
class MyCustomFilterInvocationTests(TestCase):
    """Layer 2: invoke my_custom_filter directly via flyte_stub File."""

    _SYNTHETIC_VCF = (
        "##fileformat=VCFv4.2\n"
        "#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\n"
        "chr20\t100\t.\tA\tT\t10.0\tPASS\t.\n"
        "chr20\t200\t.\tC\tG\t50.0\tPASS\t.\n"
        "chr20\t300\t.\tT\tA\t.\tPASS\t.\n"
    )

    def _run(self, min_qual: float = 30.0):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            vcf_file = tmp_path / "input.vcf"
            vcf_file.write_text(self._SYNTHETIC_VCF)

            from flytetest.tasks.variant_calling import my_custom_filter
            result = my_custom_filter(
                vcf_path=File(path=str(vcf_file)),
                min_qual=min_qual,
            )
            # Capture output before tempdir is cleaned up
            out_path = Path(result.path)
            out_content = out_path.read_text()
            manifest_path = out_path.parent / "run_manifest_my_custom_filter.json"
            manifest = json.loads(manifest_path.read_text())
        return out_content, manifest, str(out_path)

    def test_returns_file(self):
        _, _, out_path = self._run()
        self.assertTrue(Path(out_path).name.endswith(".vcf"))

    def test_low_qual_record_filtered_out(self):
        content, _, _ = self._run(min_qual=30.0)
        self.assertNotIn("\t10.0\t", content)

    def test_high_qual_record_retained(self):
        content, _, _ = self._run(min_qual=30.0)
        self.assertIn("\t50.0\t", content)

    def test_missing_qual_filtered_out(self):
        content, _, _ = self._run(min_qual=30.0)
        # chr20 pos 300 has QUAL=.
        data_lines = [l for l in content.splitlines() if not l.startswith("#")]
        self.assertFalse(any("\t.\t" in l for l in data_lines))

    def test_headers_preserved(self):
        content, _, _ = self._run()
        header_lines = [l for l in content.splitlines() if l.startswith("#")]
        self.assertGreater(len(header_lines), 0)

    def test_manifest_written(self):
        _, manifest, _ = self._run()
        self.assertEqual(manifest["stage"], "my_custom_filter")

    def test_manifest_contains_output_key(self):
        _, manifest, out_path = self._run()
        self.assertIn("my_filtered_vcf", manifest["outputs"])
        self.assertEqual(manifest["outputs"]["my_filtered_vcf"], out_path)
```

---

## Class 2 — `MyCustomFilterRegistryTests` (Layer 3)

Mirror the shape of `RegistryEntryShapeTests` at `tests/test_variant_calling.py:52`.

```python
class MyCustomFilterRegistryTests(TestCase):
    """Layer 3: assert RegistryEntry shape and manifest-output consistency."""

    def setUp(self):
        from flytetest.registry import get_entry
        self.entry = get_entry("my_custom_filter")

    def test_entry_exists(self):
        self.assertIsNotNone(self.entry)

    def test_category_is_task(self):
        self.assertEqual(self.entry.category, "task")

    def test_pipeline_family(self):
        self.assertEqual(self.entry.compatibility.pipeline_family, "variant_calling")

    def test_accepted_planner_types(self):
        self.assertEqual(
            self.entry.compatibility.accepted_planner_types, ("VariantCallSet",)
        )

    def test_produced_planner_types(self):
        self.assertEqual(
            self.entry.compatibility.produced_planner_types, ("VariantCallSet",)
        )

    def test_showcase_module(self):
        self.assertEqual(self.entry.showcase_module, "flytetest.tasks.variant_calling")

    def test_output_key_in_manifest_output_keys(self):
        from flytetest.tasks.variant_calling import MANIFEST_OUTPUT_KEYS
        output_names = {f.name for f in self.entry.outputs}
        self.assertIn("my_filtered_vcf", output_names)
        self.assertIn("my_filtered_vcf", MANIFEST_OUTPUT_KEYS)

    def test_input_names_match_task_signature(self):
        input_names = {f.name for f in self.entry.inputs}
        self.assertIn("vcf_path", input_names)
        self.assertIn("min_qual", input_names)

    def test_runtime_images_empty_for_pure_python(self):
        images = self.entry.compatibility.execution_defaults.get("runtime_images", {})
        self.assertEqual(images, {})
```

---

## Class 3 — `MyCustomFilterMCPExposureTests` (Layer 4)

```python
class MyCustomFilterMCPExposureTests(TestCase):
    """Layer 4: MCP discovery and scalar-parameter subtraction."""

    def test_appears_in_supported_task_names(self):
        from flytetest.mcp_contract import SUPPORTED_TASK_NAMES
        self.assertIn("my_custom_filter", SUPPORTED_TASK_NAMES)

    def test_task_parameters_entry_exact(self):
        from flytetest.server import TASK_PARAMETERS
        self.assertIn("my_custom_filter", TASK_PARAMETERS)
        self.assertEqual(
            TASK_PARAMETERS["my_custom_filter"],
            (("min_qual", False),),
        )

    def test_scalar_params_excludes_file_binding(self):
        """vcf_path is a File binding — it must not appear in scalar params."""
        from flytetest.server import _scalar_params_for_task
        # With no typed bindings provided, only min_qual should appear.
        params = _scalar_params_for_task("my_custom_filter", bindings={})
        param_names = [name for name, _ in params]
        self.assertIn("min_qual", param_names)
        self.assertNotIn("vcf_path", param_names)

    def test_min_qual_is_not_required(self):
        """min_qual has a default — it should not be marked required."""
        from flytetest.server import TASK_PARAMETERS
        for name, required in TASK_PARAMETERS["my_custom_filter"]:
            if name == "min_qual":
                self.assertFalse(required, "min_qual has a default and should not be required")
```

---

## Verification

```bash
PYTHONPATH=src python3 -m pytest \
    tests/test_variant_calling.py::MyCustomFilterInvocationTests \
    tests/test_variant_calling.py::MyCustomFilterRegistryTests \
    tests/test_variant_calling.py::MyCustomFilterMCPExposureTests \
    -v

# Registry contract guards
PYTHONPATH=src python3 -m pytest \
    tests/test_registry.py \
    tests/test_registry_manifest_contract.py \
    -x -q
```

If `MyCustomFilterMCPExposureTests::test_appears_in_supported_task_names` fails,
check that `showcase_module="flytetest.tasks.variant_calling"` is set in the
`RegistryEntry` from Step 03. That field is what `SHOWCASE_TARGETS` in
`mcp_contract.py` uses to derive `SUPPORTED_TASK_NAMES`.
