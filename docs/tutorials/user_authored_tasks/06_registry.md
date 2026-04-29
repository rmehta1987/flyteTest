# Chapter 6: Registry entry deep-dive

The `RegistryEntry` is the contract between your task code and the rest of
flyteTest. The planner reads it to decide if your stage fits a request, MCP
reads it to decide whether to expose your task to clients, and the test suite
reads it to enforce that declared outputs match what the task actually writes.

This chapter walks every load-bearing field of the `my_custom_filter` entry:
the actual value, what it controls, and what breaks if you get it wrong. The
dataclasses live at `src/flytetest/registry/_types.py:13` (`InterfaceField`),
`src/flytetest/registry/_types.py:31` (`RegistryCompatibilityMetadata`), and
`src/flytetest/registry/_types.py:53` (`RegistryEntry`). The full entry runs
about 35 lines starting at `src/flytetest/registry/_variant_calling.py:1312`.

## `name` — the registry key

`src/flytetest/registry/_variant_calling.py:1313`

```python
name="my_custom_filter",
```

Unique key used by `get_entry(...)` and visible to MCP clients in
`list_entries`. Convention: snake_case, matching the task function name at
`src/flytetest/tasks/variant_calling.py:1278`. Drift breaks `run_task`
target resolution.

## `category` — task or workflow

`src/flytetest/registry/_variant_calling.py:1314`

```python
category="task",
```

Type-narrowed `"task" | "workflow"`. Drives whether the entry shows up
under `SUPPORTED_TASK_NAMES` or `SUPPORTED_WORKFLOW_NAMES`
(`src/flytetest/mcp_contract.py:506`). Tasks also need a `TASK_PARAMETERS`
entry; workflows do not.

## `description`

`src/flytetest/registry/_variant_calling.py:1315`

```python
description=(
    "Pure-Python QUAL threshold filter for plain-text VCFs. "
    "On-ramp reference example for user-authored tasks: no container, "
    "no external binary, invoked via run_tool Python-callable mode."
),
```

One sentence or short paragraph; surfaces in `list_entries` and in prompt
context. Vague descriptions cause the planner to skip your task even when
it would fit.

## `inputs` — mirror the task signature

`src/flytetest/registry/_variant_calling.py:1320`

```python
inputs=(
    InterfaceField("input_vcf", "File", "Input VCF (uncompressed plain text)."),
    InterfaceField("min_qual", "float", "Minimum QUAL to retain a record (inclusive). Default 30.0."),
),
```

One `InterfaceField` per parameter. `name` MUST match the task signature
exactly. `type` is a hint string (`"File"`, `"Dir"`, `"int"`, `"float"`,
`"str"`, `"list[File]"`). Note `input_vcf`, not `vcf_path` — see
[Chapter 5](05_bindings.md) for the planner-field naming-collision rule.

## `outputs` — must subset `MANIFEST_OUTPUT_KEYS`

`src/flytetest/registry/_variant_calling.py:1324`

```python
outputs=(
    InterfaceField("my_filtered_vcf", "File", "QUAL-filtered output VCF."),
),
```

Every name listed here MUST appear in the module-level
`MANIFEST_OUTPUT_KEYS` tuple at `src/flytetest/tasks/variant_calling.py:29`
(`"my_filtered_vcf"` is at line 74). The registry-manifest contract test
asserts the subset relation; forgetting to append fails before any task runs.

## `tags`

`src/flytetest/registry/_variant_calling.py:1327`

```python
tags=("variant_calling", "filter", "pure-python", "on-ramp"),
```

Free-form, kebab-case. Used for catalog discovery; not load-bearing for
execution.

## `compatibility` — planner and pipeline metadata

A `RegistryCompatibilityMetadata` block carrying planner-graph edges and
execution defaults:

```python
compatibility=RegistryCompatibilityMetadata(
    biological_stage="custom QUAL filter",                       # line 1329
    accepted_planner_types=("VariantCallSet",),                  # line 1330
    produced_planner_types=("VariantCallSet",),                  # line 1331
    reusable_as_reference=False,                                 # line 1332
    execution_defaults={...},                                    # line 1333
    supported_execution_profiles=("local", "slurm"),             # line 1342
    synthesis_eligible=True,                                     # line 1343
    composition_constraints=(),                                  # line 1344
    pipeline_family="variant_calling",                           # line 1345
    pipeline_stage_order=22,                                     # line 1346
),
```

Field-by-field:

- **`biological_stage`** — short label returned by `get_pipeline_stages(family)`
  at `src/flytetest/registry/__init__.py:76`.
- **`accepted_planner_types`** — typed dataclass names from
  `src/flytetest/planner_types.py` the planner can resolve into your `File`/`Dir`
  inputs. `VariantCallSet.vcf_path` flows into the `input_vcf` parameter.
  Reread [Chapter 5](05_bindings.md): a task parameter MUST NOT collide with
  any field name on a dataclass listed here.
- **`produced_planner_types`** — what the task contributes back. The filter
  consumes a `VariantCallSet` and produces another (smaller) `VariantCallSet`,
  letting downstream stages chain off it.
- **`reusable_as_reference`** — `True` only for outputs reusable as upstream
  reference artifacts (e.g. an indexed reference genome). Sample-specific
  outputs stay `False`.
- **`supported_execution_profiles`** — which profiles this entry can run
  under. Restrict to `("local",)` if Slurm makes no sense.
- **`synthesis_eligible`** — `True` lets the planner include this entry in
  synthesized plans. `False` for manual-only building blocks.
- **`composition_constraints`** — prose strings shown when the planner
  proposes a plan with this entry. Empty here; entries needing staged
  databases (e.g. `snpeff_data_dir`) use it to flag the requirement.
- **`pipeline_family` / `pipeline_stage_order`** — group and sort key.
  `get_pipeline_stages("variant_calling")` returns entries sorted by stage
  order. Use sparse integers so new stages can be inserted without
  renumbering. Stage 22 places this filter at the end of the family.

### `execution_defaults` (the dict)

`src/flytetest/registry/_variant_calling.py:1333`

```python
execution_defaults={
    "profile": "local",
    "result_manifest": "run_manifest.json",
    "resources": {"cpu": "1", "memory": "4Gi", "execution_class": "local"},
    "slurm_resource_hints": {"cpu": "1", "memory": "4Gi", "walltime": "00:30:00"},
    "runtime_images": {},
    "tool_databases": {},
    "module_loads": ("python/3.11.9",),
},
```

- **`runtime_images`** — empty `{}` for python-callable tasks. SIF tasks map
  `<tool>_sif` parameter names to default container paths
  ([Chapter 3](03_execution_modes.md)). `check_offline_staging` blocks Slurm
  submission if a declared image is unreachable, so an empty dict here is
  what makes pure-Python tasks freely Slurm-runnable.
- **`module_loads`** — a FULL REPLACEMENT of `DEFAULT_SLURM_MODULE_LOADS`,
  not an append. The variant-calling default is `python/3.11.9`,
  `apptainer/1.4.1`, `gatk/4.5.0`, `samtools/1.22.1`; this entry drops
  apptainer/gatk/samtools because the task starts no subprocess.
- `queue` and `account` are NEVER seeded here — always user-supplied at
  submission time.

## `showcase_module` — the MCP discovery switch

`src/flytetest/registry/_variant_calling.py:1348`

```python
showcase_module="flytetest.tasks.variant_calling",
```

The single field that controls MCP exposure. `SHOWCASE_TARGETS` at
`src/flytetest/mcp_contract.py:493` iterates `REGISTRY_ENTRIES` and yields
one target per entry with a non-empty `showcase_module`. Empty string =
catalog-only (visible in `list_entries`, not callable through `run_task`).
For tasks you ALSO need a `TASK_PARAMETERS` entry at
`src/flytetest/server.py:310` — see [Chapter 9](09_mcp_exposure.md).

## Minimal entry template

The smallest valid `RegistryEntry` for a new python-callable task:

```python
RegistryEntry(
    name="your_task",
    category="task",
    description="One sentence describing what this does.",
    inputs=(InterfaceField("input_file", "File", "Input."),),
    outputs=(InterfaceField("output_file", "File", "Output."),),
    tags=("your_family", "verb"),
    compatibility=RegistryCompatibilityMetadata(
        biological_stage="short label",
        accepted_planner_types=("YourPlannerType",),
        produced_planner_types=("YourPlannerType",),
        execution_defaults={
            "profile": "local",
            "result_manifest": "run_manifest.json",
            "resources": {"cpu": "1", "memory": "4Gi", "execution_class": "local"},
            "slurm_resource_hints": {"cpu": "1", "memory": "4Gi", "walltime": "00:30:00"},
            "runtime_images": {},
            "module_loads": ("python/3.11.9",),
        },
        supported_execution_profiles=("local", "slurm"),
        synthesis_eligible=True,
        pipeline_family="your_family",
        pipeline_stage_order=10,
    ),
    showcase_module="flytetest.tasks.your_family",
),
```

Other `RegistryCompatibilityMetadata` defaults (`reusable_as_reference=False`,
`composition_constraints=()`, `runtime_image_policy=...`) can be omitted.

## Where to next

- [Chapter 7: Testing your task](07_testing.md) — `RegistryEntryShapeTests`
  enforces the shape rules above with one targeted test class.
- [Chapter 9: MCP exposure](09_mcp_exposure.md) — what `showcase_module`
  unlocks, plus the `TASK_PARAMETERS` companion entry tasks need.

---

[← Prev: The binding contract](05_bindings.md) · [Next: Testing your task →](07_testing.md)
