# Step 02 — Composed Workflow + Registry Entry

_Resolve the open questions in `user_authored_workflows_plan.md` before starting.
The exact workflow name, input surface, and pipeline_stage_order must be confirmed._

Read before starting:
- `src/flytetest/workflows/variant_calling.py` — `annotate_variants_snpeff` at line 603
  (the closest composition reference for a terminal task applied to an existing VCF)
- `src/flytetest/registry/_variant_calling.py` — last `RegistryEntry` block
- `src/flytetest/tasks/variant_calling.py:1272` — `my_custom_filter` task signature

Do NOT touch `planning.py`, `mcp_contract.py`, `bundles.py`, `spec_executor.py`,
or `planner_types.py`.

---

## Change 1 — `src/flytetest/workflows/variant_calling.py`

Append after `annotate_variants_snpeff`. The workflow takes an existing VCF
(already called, stored as a `VariantCallSet`) and applies `my_custom_filter`:

```python
@variant_calling_env.task
def germline_short_variant_discovery_filtered(
    vcf_path: File,
    min_qual: float = 30.0,
) -> File:
    """Apply QUAL threshold filtering to an existing variant call set.

    This is the on-ramp reference composition: it demonstrates how to wire a
    user-authored Python-callable task (`my_custom_filter`) into the variant
    calling pipeline without re-running upstream GATK steps.

    Use this workflow when you already have a joint-called or VQSR-filtered VCF
    and want to apply a custom quality threshold before downstream analysis.
    """
    return my_custom_filter(vcf_path=vcf_path, min_qual=min_qual)
```

Add the import for `my_custom_filter` at the top of the workflows file if not
already present.

---

## Change 2 — `src/flytetest/registry/_variant_calling.py`

Append after the `my_custom_filter` entry:

```python
    RegistryEntry(
        name="germline_short_variant_discovery_filtered",
        category="workflow",
        description=(
            "Apply QUAL threshold filtering to an existing variant call set. "
            "On-ramp reference composition: wires my_custom_filter into the "
            "pipeline without re-running upstream GATK steps."
        ),
        inputs=(
            InterfaceField("vcf_path", "File", "Input VCF (joint-called or VQSR-filtered, plain text)."),
            InterfaceField("min_qual", "float", "Minimum QUAL threshold (inclusive). Default 30.0."),
        ),
        outputs=(
            InterfaceField("my_filtered_vcf", "File", "QUAL-filtered output VCF."),
        ),
        tags=("variant_calling", "filter", "pure-python", "on-ramp", "composition"),
        compatibility=RegistryCompatibilityMetadata(
            biological_stage="custom QUAL filter (composed)",
            accepted_planner_types=("VariantCallSet",),
            produced_planner_types=("VariantCallSet",),
            reusable_as_reference=False,
            execution_defaults={
                "profile": "local",
                "result_manifest": "run_manifest.json",
                "resources": {"cpu": "1", "memory": "4Gi", "execution_class": "local"},
                "slurm_resource_hints": {"cpu": "1", "memory": "4Gi", "walltime": "00:30:00"},
                "runtime_images": {},
                "tool_databases": {},
                "module_loads": ("python/3.11.9",),
            },
            supported_execution_profiles=("local", "slurm"),
            synthesis_eligible=True,
            composition_constraints=(),
            pipeline_family="variant_calling",
            pipeline_stage_order=23,
        ),
        showcase_module="flytetest.workflows.variant_calling",
    ),
```

---

## Verification

```bash
python3 -m compileall \
    src/flytetest/workflows/variant_calling.py \
    src/flytetest/registry/_variant_calling.py

PYTHONPATH=src python3 -c "
from flytetest.registry import get_entry
e = get_entry('germline_short_variant_discovery_filtered')
print('OK:', e.name, e.category)
print('  accepted:', e.compatibility.accepted_planner_types)
print('  stage_order:', e.compatibility.pipeline_stage_order)
"
```
