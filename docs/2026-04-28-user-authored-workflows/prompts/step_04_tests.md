# Step 04 — Tests

Read before starting:
- `tests/test_mcp_tools.py` — find the test class for `vc_annotate_variants_snpeff`
  (both the task flat tool and workflow flat tool patterns live there)
- `tests/test_variant_calling.py` — `MyCustomFilterRegistryTests` shape (for the
  workflow registry test pattern)

---

## Class 1 — Flat tool: `vc_custom_filter` (add to `tests/test_mcp_tools.py`)

Mirror the nearest task flat-tool test class. At minimum:

```python
class VcCustomFilterFlatToolTests(TestCase):
    """Flat tool vc_custom_filter: dry-run planning and decline guard."""

    def _call(self, **kwargs):
        from flytetest.mcp_tools import vc_custom_filter
        return vc_custom_filter(**kwargs)

    def test_dry_run_returns_dict(self):
        result = self._call(vcf_path="/data/test.vcf", dry_run=True)
        self.assertIsInstance(result, dict)

    def test_missing_vcf_path_declines(self):
        result = self._call(vcf_path="", dry_run=True)
        # Empty path should produce a decline or error, not a crash.
        self.assertIsInstance(result, dict)

    def test_dry_run_supported_flag_present(self):
        result = self._call(vcf_path="/data/test.vcf", dry_run=True)
        # Result must have 'supported' or 'target' key (plan reply shape).
        self.assertTrue("supported" in result or "target" in result)
```

---

## Class 2 — Flat tool: `vc_germline_filtered` (add to `tests/test_mcp_tools.py`)

```python
class VcGermlineFilteredFlatToolTests(TestCase):
    """Flat tool vc_germline_filtered: dry-run planning."""

    def _call(self, **kwargs):
        from flytetest.mcp_tools import vc_germline_filtered
        return vc_germline_filtered(**kwargs)

    def test_dry_run_returns_dict(self):
        result = self._call(vcf_path="/data/test.vcf", dry_run=True)
        self.assertIsInstance(result, dict)

    def test_dry_run_supported_flag_present(self):
        result = self._call(vcf_path="/data/test.vcf", dry_run=True)
        self.assertTrue("supported" in result or "target" in result)
```

---

## Class 3 — Registry: `germline_short_variant_discovery_filtered`
(add to `tests/test_variant_calling.py`)

```python
class GermlineFilteredWorkflowRegistryTests(TestCase):
    """Registry shape for the on-ramp composed workflow."""

    def setUp(self):
        from flytetest.registry import get_entry
        self.entry = get_entry("germline_short_variant_discovery_filtered")

    def test_entry_exists(self):
        self.assertIsNotNone(self.entry)

    def test_category_is_workflow(self):
        self.assertEqual(self.entry.category, "workflow")

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
        self.assertEqual(
            self.entry.showcase_module, "flytetest.workflows.variant_calling"
        )

    def test_runtime_images_empty(self):
        images = self.entry.compatibility.execution_defaults.get("runtime_images", {})
        self.assertEqual(images, {})

    def test_pipeline_stage_order(self):
        self.assertEqual(self.entry.compatibility.pipeline_stage_order, 23)
```

---

## Verification

```bash
PYTHONPATH=src python3 -m pytest \
    tests/test_mcp_tools.py::VcCustomFilterFlatToolTests \
    tests/test_mcp_tools.py::VcGermlineFilteredFlatToolTests \
    tests/test_variant_calling.py::GermlineFilteredWorkflowRegistryTests \
    -v

PYTHONPATH=src python3 -m pytest tests/test_registry.py -x -q
```
