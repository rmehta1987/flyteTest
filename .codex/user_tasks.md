# User-Authored Tasks and Workflows

For a hands-on walkthrough see `docs/tutorials/user_authored_tasks/`.

This guide is for users who want to add their own first-class task or workflow
to FLyteTest — for example, plugging a custom Python variant-filter module into
the existing `variant_calling` pipeline.

It is a condensed, user-facing walkthrough. For depth, follow the cross-links:

- `.codex/tasks.md` — full task-authoring guide (signatures, manifests, hardware)
- `.codex/workflows.md` — workflow composition rules and stage boundaries
- `.codex/registry.md` — registry-entry field semantics end-to-end
- `.codex/testing.md` — fixture conventions and MCP reshape test shapes
- `.codex/agent/scaffold.md` — delegate the mechanical patch generation

## When to read this

Read this when you have an existing Python function or tool invocation you want
to land inside `src/flytetest/` as a registered, composable step. If you are
already comfortable with the registry contract and just need style rules, go
straight to the specialist guides above.

## Where your module lives

Keep two layers:

1. **Pure logic** under `src/flytetest/<your_area>/<your_module>.py`. No Flyte
   decorators, no `flyte.io` types — just functions that take paths/values and
   produce files. This lets you unit-test with plain `pytest` and no harness.
2. **A thin task wrapper** appended to the relevant
   `src/flytetest/tasks/<family>.py` (e.g. `variant_calling.py`). The wrapper
   handles `File.download_sync()`, output staging, manifest writing, and calls
   into your pure function.

The reference wrapper pattern is `create_sequence_dictionary` at
`src/flytetest/tasks/variant_calling.py:72` — follow its shape.

## Defining inputs (bindings)

Task function signatures use `flyte.io.File`, `flyte.io.Dir`, and scalars only.
Never put a planner dataclass directly in the signature — the MCP resolver does
that translation for you.

The *binding contract* is set in two places that must stay consistent:

- The **function signature** lists the concrete Flyte inputs (`reference_fasta: File`, `vcf: File`, scalars like `min_qual: float = 30.0`).
- The registry entry's **`accepted_planner_types`** names the planner dataclass
  the resolver will materialize into those inputs. The resolver matches
  dataclass field names to task parameter names.

Example: a task that takes a joint-called VCF should accept the planner type
`VariantCallSet` (defined at `src/flytetest/planner_types.py`). That
dataclass's `vcf_path` field flows into a task parameter named `input_vcf`,
`vcf`, or similar.

### Naming-collision gotcha (must read)

**Task / workflow parameter names must NOT collide with planner-type field
names.** If your `accepted_planner_types` includes `VariantCallSet` (which
has fields `vcf_path`, `variant_type`, `caller`, ...), do *not* name your
task parameter `vcf_path`. The resolver classifies any parameter whose
name matches a binding inner-key as "covered by the typed binding" and
strips it from `TASK_PARAMETERS`-style scalar validation, but the local
execution path still needs the parameter present in `inputs`. The two
checks disagree, the dry-run plans, and the real run fails with confusing
"Unknown scalar inputs" / "Missing required workflow inputs" errors.

Use `input_vcf`, `joint_vcf`, `vcf_in`, etc. — *not* `vcf_path`. The
established convention across the codebase is `input_vcf` for typed File
parameters at every layer (task signature, workflow signature, flat-tool
user-facing parameter). The binding inner key still carries the
planner-field name (`vcf_path`), since that is what the planner type
itself defines:

```python
# task / workflow signature
def apply_custom_filter(input_vcf: File, min_qual: float = 30.0) -> File:
    ...

# flat tool — user-facing param matches the function signature; the
# planner-type field name (vcf_path) appears only inside the binding dict.
def vc_apply_custom_filter(input_vcf: str, min_qual: float = 30.0, ...):
    return _run_workflow(
        workflow_name="apply_custom_filter",
        bindings={"VariantCallSet": {"vcf_path": input_vcf}},  # planner field
        inputs={"input_vcf": input_vcf, "min_qual": min_qual}, # function param
        ...
    )
```

## Manifests and `MANIFEST_OUTPUT_KEYS`

Every key a task writes under `manifest["outputs"]` must appear in the
module-level `MANIFEST_OUTPUT_KEYS` tuple at the top of the tasks file
(`src/flytetest/tasks/variant_calling.py:25` is the variant-calling tuple).
Append your new output names to that tuple — a registry-manifest contract
test asserts declared registry outputs are a subset.

Use `build_manifest_envelope(...)` + `_write_json(...)` to produce the
manifest; do not hand-roll the dict. Manifest filenames follow
`run_manifest_<stage>.json` (see the reference task at
`src/flytetest/tasks/variant_calling.py:99`).

## The registry entry

Every task needs a `RegistryEntry` in `src/flytetest/registry/_<family>.py`
(e.g. `_variant_calling.py`). Append to the family's tuple — for variant
calling that's `VARIANT_CALLING_ENTRIES` at
`src/flytetest/registry/_variant_calling.py:11`, and the reference entry is
`create_sequence_dictionary` at
`src/flytetest/registry/_variant_calling.py:12`.

Three load-bearing fields:

- **`inputs` / `outputs`**: one `InterfaceField` per parameter, mirroring your
  function signature exactly. Name, type-string, and short description.
- **`accepted_planner_types` / `produced_planner_types`** inside
  `RegistryCompatibilityMetadata`: the planner-graph edges. Names must exist
  in `src/flytetest/planner_types.py`.
- **`execution_defaults.runtime_images`** and
  **`execution_defaults.module_loads`**: default SIF paths and environment
  modules. Drop `apptainer/1.4.1` from `module_loads` if your task has no SIF.

Also set `showcase_module="flytetest.tasks.<family>"` so MCP surfaces can
resolve the callable. Setting `showcase_module` is what makes a task
(or workflow) auto-appear in MCP `list_entries`, `SUPPORTED_TASK_NAMES`,
and `SHOWCASE_TARGETS` — those are derived from the registry at
`src/flytetest/mcp_contract.py:253`.

## `TASK_PARAMETERS` — the one required `server.py` touch

For tasks only (not workflows), you also need to append an entry to the
`TASK_PARAMETERS` dict at `src/flytetest/server.py:164`. This is a pure
metadata declaration that tells `run_task` at the MCP boundary which
scalar inputs the task accepts:

```python
TASK_PARAMETERS: dict[str, tuple[tuple[str, bool], ...]] = {
    ...
    "my_custom_filter": (
        ("min_qual", False),    # has a default
        ("min_depth", False),   # has a default
    ),
    ...
}
```

Rules: list only the **non-`File` / non-`Dir`** parameters from the
function signature (`File`/`Dir` inputs are typed bindings, handled by the
planner); mark `required=True` for params without a default and `False`
otherwise. Workflows do not need this — `showcase_module` alone is
sufficient to expose them through MCP.

## Execution modes — choosing the right `run_tool` path

`run_tool` in `src/flytetest/config.py` supports three modes. Pick exactly one.

| Mode | When to use | Call shape |
|---|---|---|
| **SIF / container** | tool ships in a container (GATK, bwa-mem2, SnpEff, BRAKER3) | `run_tool(cmd, sif_path, bind_paths)` |
| **Native executable** | binary on PATH or at an explicit path (Rscript, compiled C++, samtools) | `run_tool(cmd, sif="", bind_paths=[])` |
| **Python callable** | pure-Python logic, no external binary | `run_tool(python_callable=fn, callable_kwargs={...})` |

**SIF mode:** declare a `<tool>_sif: str = ""` parameter and register the
default path under `runtime_images` in the registry entry (e.g.
`{"gatk_sif": "data/images/gatk4.sif"}`). Pass the parameter into
`run_tool(cmd, sif, bind_paths)`.

**Native executable mode:** omit the `_sif` parameter or keep it as an
optional fallback. Pass `sif=""` to `run_tool` — it calls the binary directly
via `subprocess.run`. Use for system binaries (`Rscript`, compiled C++,
`samtools`) or any binary available as a cluster module. Declare the relevant
`module_loads` in the registry entry.

**Python callable mode:** import your pure-Python function and pass it to
`run_tool(python_callable=fn, callable_kwargs={...})`. No subprocess is
started. Use this for threshold filters, format converters, statistics
aggregations, or any logic with no external binary dependency. In the registry
entry: `"runtime_images": {}` and `"module_loads": ("python/3.11.9",)`.
`check_offline_staging` will not block Slurm submission on a missing image.

The reference implementation of the Python-callable pattern is `my_custom_filter`
in `src/flytetest/tasks/variant_calling.py`. Read it before writing your own
pure-Python task — it is the copyable template.

## Testing — no-SIF workflow integration

Three layers, cheapest first:

1. **Unit-test the pure-Python module** directly with `pytest` against a tiny
   fixture (a hand-written VCF/BED/BAM header). No Flyte, no containers.
2. **Call the task function directly** with a fixture `File`.
   - *SIF/native tasks*: patch `run_tool` with a fake that captures the command
     and writes a synthetic output — pattern at `tests/test_variant_calling.py:78`
     (`patch.object(variant_calling, "run_tool", side_effect=fake_run_tool)`).
   - *Python-callable tasks*: no patch needed. `run_tool` calls your function
     in-process, so just call the task with a `File` stub and assert on the
     output file and manifest. See `MyCustomFilterInvocationTests` in
     `tests/test_variant_calling.py` for this simpler pattern.
3. **Run the task standalone via the MCP surface** by freezing a prior run's
   output into a bundle and calling `load_bundle` → `run_task`. You iterate on
   the downstream step without re-running upstream GATK. See `.codex/testing.md`
   for fixture conventions and bundle shapes.

For the registry entry itself, mirror `RegistryEntryShapeTests` at
`tests/test_variant_calling.py:52` — check `get_entry(...)` returns your
entry, `pipeline_family` is correct, and declared output names are in
`MANIFEST_OUTPUT_KEYS`.

## Wiring into a workflow

Workflow entrypoints live in `src/flytetest/workflows/<family>.py`. For
variant calling, `prepare_reference` at
`src/flytetest/workflows/variant_calling.py:54` is the composition reference.

Workflows are also decorated with `@<family>_env.task` (Flyte v2 composes
tasks by calling them from other tasks — there is no separate `@workflow`
decorator here). Bind a downstream task by passing the upstream task's
returned `File`/`Dir` directly. The minimal copyable template — applying a
user-authored task to an existing VCF — is `apply_custom_filter` in
`src/flytetest/workflows/variant_calling.py`:

```python
@variant_calling_env.task
def apply_custom_filter(
    input_vcf: File,
    min_qual: float = 30.0,
) -> File:
    filtered_vcf = my_custom_filter(input_vcf=input_vcf, min_qual=min_qual)
    # ... write workflow-level run_manifest.json ...
    return filtered_vcf
```

Read it before writing your own composed workflow. To re-run upstream
discovery and then filter, take a FASTQ-shaped input surface and call
`germline_short_variant_discovery(...)` first, then your custom task — the
same composition pattern, just with more inputs.

## Worked example — custom Python variant filter

Scenario: you have `src/flytetest/filtering/my_filter.py` with a
`filter_vcf(in_path, out_path, min_qual, min_depth)` function, and you want
to apply it to a joint-called or VQSR-filtered VCF. (Note: GATK's
`variant_filtration` already exists — this example is deliberately a
*different* filter with your own statistical criteria, illustrating the
pattern.)

### 1. Task wrapper (append to `src/flytetest/tasks/variant_calling.py`)

```python
from flytetest.filtering.my_filter import filter_vcf

@variant_calling_env.task
def my_custom_filter(
    vcf: File,
    min_qual: float = 30.0,
    min_depth: int = 10,
) -> File:
    """Apply a custom Python variant filter to a joint-called VCF."""
    in_vcf = require_path(Path(vcf.download_sync()), "Input VCF")
    out_dir = project_mkdtemp("custom_filter_")
    out_vcf = out_dir / f"{in_vcf.stem}.customfiltered.vcf.gz"

    filter_vcf(in_vcf, out_vcf, min_qual=min_qual, min_depth=min_depth)
    require_path(out_vcf, "Custom-filtered VCF")

    manifest = build_manifest_envelope(
        stage="my_custom_filter",
        assumptions=["Input VCF is joint-called or VQSR-filtered."],
        inputs={"vcf": str(in_vcf), "min_qual": min_qual, "min_depth": min_depth},
        outputs={"my_filtered_vcf": str(out_vcf)},
    )
    _write_json(out_dir / f"run_manifest_{manifest['stage']}.json", manifest)
    return File(path=str(out_vcf))
```

Then add `"my_filtered_vcf"` to `MANIFEST_OUTPUT_KEYS` at the top of the file.

### 2. Registry entry (append to `VARIANT_CALLING_ENTRIES`)

```python
RegistryEntry(
    name="my_custom_filter",
    category="task",
    description="Apply a custom Python variant filter to a joint-called or VQSR-filtered VCF.",
    inputs=(
        InterfaceField("vcf", "File", "Input VCF (joint-called or VQSR-filtered)."),
        InterfaceField("min_qual", "float", "Minimum QUAL threshold."),
        InterfaceField("min_depth", "int", "Minimum DP threshold."),
    ),
    outputs=(
        InterfaceField("my_filtered_vcf", "File", "Custom-filtered VCF (.vcf.gz)."),
    ),
    tags=("variant_calling", "filtering", "custom"),
    compatibility=RegistryCompatibilityMetadata(
        biological_stage="Custom Python variant filtering",
        accepted_planner_types=("VariantCallSet",),
        produced_planner_types=("VariantCallSet",),
        reusable_as_reference=False,
        execution_defaults={
            "profile": "local",
            "result_manifest": "run_manifest.json",
            "resources": {"cpu": "2", "memory": "8Gi", "execution_class": "local"},
            "slurm_resource_hints": {"cpu": "2", "memory": "8Gi", "walltime": "01:00:00"},
            "runtime_images": {},
            "module_loads": ("python/3.11.9",),
        },
        supported_execution_profiles=("local", "slurm"),
        synthesis_eligible=True,
        composition_constraints=(
            "Input VCF must be joint-called (joint_call_gvcfs) or VQSR-filtered (apply_vqsr).",
        ),
        pipeline_family="variant_calling",
        pipeline_stage_order=22,
    ),
    showcase_module="flytetest.tasks.variant_calling",
),
```

### 3. Test stub (new class in `tests/test_variant_calling.py`)

```python
class MyCustomFilterRegistryTests(TestCase):
    def test_my_custom_filter_registry_entry_shape(self) -> None:
        from flytetest.registry import get_entry
        entry = get_entry("my_custom_filter")
        self.assertIsNotNone(entry)
        self.assertEqual(entry.compatibility.pipeline_family, "variant_calling")
        self.assertEqual(entry.compatibility.accepted_planner_types, ("VariantCallSet",))
        output_names = tuple(f.name for f in entry.outputs)
        self.assertIn("my_filtered_vcf", output_names)
        self.assertIn("my_filtered_vcf", MANIFEST_OUTPUT_KEYS)
```

Plus a direct-invocation test mirroring
`tests/test_variant_calling.py:78` if you want to guard the manifest shape
without running the real filter.

### 4. CHANGELOG entry

Add one dated `[x]` line under `## Unreleased` in `CHANGELOG.md`.

## Real on-ramp artifacts (callable today)

After the user-authored-workflows milestone the following are all real,
registered entries callable via MCP. Use them as copy-paste templates:

| Name | Type | Flat tool | Description |
|---|---|---|---|
| `my_custom_filter` | task | `vc_custom_filter` | QUAL filter via Python-callable mode (no SIF, no subprocess) |
| `apply_custom_filter` | workflow | `vc_apply_custom_filter` | Composed: existing VCF → `my_custom_filter` → filtered VCF |

The task shows Python-callable mode end-to-end. The workflow shows how to
wire a custom task into a new end-to-end entry without touching upstream
GATK steps — apply this pattern when you already have a joint-called VCF
and want to tack a user-authored step onto the end.

## Hand-off to the scaffolding agent

`.codex/agent/scaffold.md` is the specialist role prompt that turns the
intent — "a custom variant filter after `joint_call_gvcfs`, pure Python,
reusing `VariantCallSet`" — into the exact patch set above. Use it instead
of hand-writing the four pieces whenever your change fits the supported
shape (one new task + registry entry + test stub, inside an existing
pipeline family, no new planner dataclass).

## Escalate, don't improvise

Stop and ask for review if your change needs any of:

- a new planner dataclass in `src/flytetest/planner_types.py`
- a task that crosses pipeline families
- a new MCP surface, or any change to `server.py`, `planning.py`,
  `mcp_contract.py`, or `bundles.py`

Those are architecture-critical and sit under `.codex/agent/architecture.md`.
