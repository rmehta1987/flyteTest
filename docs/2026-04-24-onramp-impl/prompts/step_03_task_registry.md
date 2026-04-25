# Step 03 — Task Wrapper, Registry Entry, and TASK_PARAMETERS Append

Read the following before starting:
- `src/flytetest/tasks/variant_calling.py` — full file (for `MANIFEST_OUTPUT_KEYS` and the `create_sequence_dictionary` reference pattern at line ~72)
- `src/flytetest/registry/_variant_calling.py` — the last `RegistryEntry` block (to find the insertion point and copy the shape)
- `src/flytetest/server.py` lines ~160-175 — `TASK_PARAMETERS` dict

Do not touch `planning.py`, `mcp_contract.py`, `bundles.py`, `spec_executor.py`,
or `planner_types.py`.

---

## Edit 1 — `src/flytetest/tasks/variant_calling.py`

### 1a. Add import for `_filter_helpers`

At the top of the file, alongside the other local imports, add:

```python
from flytetest.tasks._filter_helpers import filter_vcf
```

### 1b. Append to `MANIFEST_OUTPUT_KEYS`

Find `MANIFEST_OUTPUT_KEYS` (line ~25). Append `"my_filtered_vcf"` at the end of
the tuple, inside the closing parenthesis. Add a comment marking the on-ramp slice:

```python
    # On-ramp reference task
    "my_filtered_vcf",
```

### 1c. Append the task function

Append at the **end** of the file (after all existing tasks):

```python
@variant_calling_env.task
def my_custom_filter(
    vcf_path: File,
    min_qual: float = 30.0,
) -> File:
    """Apply a pure-Python QUAL threshold filter to a plain-text VCF.

    Records with QUAL below ``min_qual`` or with missing QUAL (``.``) are
    dropped. Header lines are always preserved. This task is the on-ramp
    reference example for user-authored pure-Python logic; it goes through
    ``run_tool`` in Python-callable mode so the execution pattern is uniform
    across all task families.
    """
    in_vcf = require_path(Path(vcf_path.download_sync()), "Input VCF")
    out_dir = project_mkdtemp("my_custom_filter_")
    out_vcf = out_dir / "my_filtered.vcf"

    run_tool(
        python_callable=filter_vcf,
        callable_kwargs={
            "in_path": in_vcf,
            "out_path": out_vcf,
            "min_qual": min_qual,
        },
    )

    require_path(out_vcf, "Filtered VCF output")

    manifest = build_manifest_envelope(
        stage="my_custom_filter",
        assumptions=[
            "Input VCF is uncompressed plain text.",
            "QUAL field is numeric or '.' (missing QUAL treated as below threshold).",
        ],
        inputs={"vcf_path": str(in_vcf), "min_qual": min_qual},
        outputs={"my_filtered_vcf": str(out_vcf)},
    )
    _write_json(out_dir / "run_manifest_my_custom_filter.json", manifest)
    return File(path=str(out_vcf))
```

---

## Edit 2 — `src/flytetest/registry/_variant_calling.py`

Append a new `RegistryEntry` to `VARIANT_CALLING_ENTRIES` (the list at line ~11).
Add it **after** the last existing entry. Copy the shape of a nearby task entry
(e.g. `variant_filtration` at line ~634) and adjust:

```python
    RegistryEntry(
        name="my_custom_filter",
        category="task",
        description=(
            "Pure-Python QUAL threshold filter for plain-text VCFs. "
            "On-ramp reference example for user-authored tasks."
        ),
        inputs=[
            InterfaceField("vcf_path", "File", "Input VCF (uncompressed plain text)."),
            InterfaceField("min_qual", "float", "Minimum QUAL to retain a record (inclusive)."),
        ],
        outputs=[
            InterfaceField("my_filtered_vcf", "File", "QUAL-filtered output VCF."),
        ],
        compatibility=RegistryCompatibilityMetadata(
            pipeline_family="variant_calling",
            biological_stage="custom_qual_filter",
            accepted_planner_types=("VariantCallSet",),
            produced_planner_types=("VariantCallSet",),
            pipeline_stage_order=22,
            execution_defaults={
                "runtime_images": {},
                "module_loads": ("python/3.11.9",),
            },
        ),
        showcase_module="flytetest.tasks.variant_calling",
    ),
```

---

## Edit 3 — `src/flytetest/server.py`

Find `TASK_PARAMETERS` (line ~164). It is a `dict` mapping task names to tuples of
`(name, required)` scalar parameter pairs. Append one entry:

```python
    "my_custom_filter": (
        ("min_qual", False),
    ),
```

**Only `min_qual` goes here.** `vcf_path` is a `File` binding resolved through the
typed-binding path, not a scalar — it must not appear in `TASK_PARAMETERS`.

---

## Verification

```bash
python3 -m compileall \
    src/flytetest/tasks/_filter_helpers.py \
    src/flytetest/tasks/variant_calling.py \
    src/flytetest/registry/_variant_calling.py \
    src/flytetest/server.py

# Quick smoke: confirm name resolution
PYTHONPATH=src python3 -c "
from flytetest.registry import get_entry
e = get_entry('my_custom_filter')
print('OK entry:', e.name, e.category)
print('  accepted:', e.compatibility.accepted_planner_types)
print('  stage_order:', e.compatibility.pipeline_stage_order)

from flytetest.server import TASK_PARAMETERS
assert 'my_custom_filter' in TASK_PARAMETERS
assert TASK_PARAMETERS['my_custom_filter'] == (('min_qual', False),)
print('OK TASK_PARAMETERS:', TASK_PARAMETERS['my_custom_filter'])

from flytetest.tasks.variant_calling import MANIFEST_OUTPUT_KEYS
assert 'my_filtered_vcf' in MANIFEST_OUTPUT_KEYS
print('OK MANIFEST_OUTPUT_KEYS: my_filtered_vcf present')
"
```
