# Chapter 8: Composing a workflow

A workflow in flyteTest is a Python function that calls tasks and returns their
outputs. In this Flyte v2 codebase, workflows are decorated with
`@<family>_env.task` — *not* `@workflow`. This is non-obvious and deliberate:
the SDK version pinned in this repo exposes `env.task` but does not yet expose
a separate `env.workflow` decorator, so composition is done by calling tasks
from a task. The wrapper is the same shape; the body is what differs.

This chapter walks two real examples: the minimal one-task `apply_custom_filter`
that wires the user-authored filter from chapters 1–7 onto an existing VCF, and
the four-stage `rnaseq_qc_quant` pipeline.

## Why `@env.task` for workflows

The repo note is short and load-bearing — see
`src/flytetest/workflows/rnaseq_qc_quant.py:21`:

```python
# Flyte 2.0.10 in this repo exposes env.task but not env.workflow, so this
# workflow entrypoint remains a composed task to preserve current behavior.
```

Treat workflows as tasks that happen to call other tasks. The registry entry's
`category="workflow"` field (chapter 6) is what distinguishes them at the MCP
layer; the decorator itself is identical.

## Example A — minimal composition: `apply_custom_filter`

This is the on-ramp reference workflow. It takes a VCF, runs your custom filter
task, writes a workflow-level manifest, and returns the filtered VCF. One stage,
one call, one return.

`src/flytetest/workflows/variant_calling.py:645`

```python
@variant_calling_env.task
def apply_custom_filter(
    input_vcf: File,
    min_qual: float = 30.0,
) -> File:
    """Apply a user-authored QUAL filter to an existing variant call set.

    On-ramp reference composition: wires ``my_custom_filter`` into the variant
    calling pipeline without re-running upstream GATK steps. ...
    """
    from flytetest.config import project_mkdtemp

    filtered_vcf = my_custom_filter(input_vcf=input_vcf, min_qual=min_qual)
    out_dir = project_mkdtemp("apply_custom_filter_")
    manifest = build_manifest_envelope(
        stage="apply_custom_filter",
        assumptions=[
            "Input VCF is uncompressed plain text (no companion index needed).",
            "Filtering is QUAL-threshold only; no model-based filtering applied.",
        ],
        inputs={
            "input_vcf": input_vcf.download_sync(),
            "min_qual": min_qual,
        },
        outputs={"my_filtered_vcf": filtered_vcf.path},
    )
    _write_json(out_dir / "run_manifest.json", manifest)
    return filtered_vcf
```

Walk through the four pieces:

- **Decorator.** `@variant_calling_env.task` ties the workflow to the
  variant-calling task environment defined in `src/flytetest/config.py:165`.
  The family environment carries default container, module, and resource
  defaults so every task it decorates inherits a consistent runtime. Use the
  same family environment that the tasks you compose live under.
- **Signature.** Plain `flyte.io.File` and scalar inputs only — no planner
  dataclasses. The MCP resolver materializes typed bindings into these
  arguments before the workflow ever runs (see chapter 5). The
  `min_qual` default carries through from the task signature.
- **Body.** A single call to `my_custom_filter(...)`. The returned `File` is
  bound to `filtered_vcf` and used twice: once to write the workflow's own
  manifest, once as the return value. The workflow does not re-stage the
  input or recompute anything the task already did.
- **Return.** Pass the upstream task output through unchanged. No wrapping,
  no path extraction, no reconstruction.

## Example B — multi-stage: `rnaseq_qc_quant`

`src/flytetest/workflows/rnaseq_qc_quant.py:23`

```python
@rnaseq_qc_quant_env.task
def rnaseq_qc_quant(
    ref: File,
    left: File,
    right: File,
    salmon_sif: str = "",
    fastqc_sif: str = "",
) -> Dir:
    """Run the compatibility RNA-seq QC and Salmon quantification boundary."""
    index = salmon_index(ref=ref, salmon_sif=salmon_sif)
    qc = fastqc(left=left, right=right, fastqc_sif=fastqc_sif)
    quant = salmon_quant(index=index, left=left, right=right, salmon_sif=salmon_sif)
    return collect_results(qc=qc, quant=quant)
```

Same shape, four stages:

1. `salmon_index` builds a transcriptome index from `ref`. The returned `Dir`
   is bound to `index`.
2. `fastqc` runs in parallel-friendly fashion against the raw reads. It does
   not depend on `index`, so the engine is free to schedule it independently.
3. `salmon_quant` consumes both `index` (from stage 1) and the raw `left`/
   `right` reads (workflow inputs). This is where the wiring matters: the
   `index=index` keyword arg passes the upstream `Dir` directly.
4. `collect_results(qc=qc, quant=quant)` receives both upstream outputs and
   produces the final `Dir` the workflow returns.

## The wiring rule

Pass upstream `flyte.io.File` and `flyte.io.Dir` outputs *directly* as inputs
to downstream tasks. Do not extract `.path` and pass the string. Do not call
`download_sync()` at the workflow layer to re-stage the file. The Flyte
runtime tracks the typed handle through the dependency graph; reducing it to a
string at composition time defeats that. The workflow only ever reaches into
`.path` or `download_sync()` when it is writing its own manifest — never to
hand to another task.

This is also why the workflow's signature uses `File` rather than `str`: the
binding contract (chapter 5) terminates at the function boundary, and inside
the body you stay in typed-handle land.

## Workflow registry entry

Workflows have registry entries too. The shape is identical to a task entry
except for `category`, which is set to `"workflow"`.

`src/flytetest/registry/_variant_calling.py:1350`

```python
RegistryEntry(
    name="apply_custom_filter",
    category="workflow",
    description=(
        "Apply a user-authored QUAL filter to an existing variant call set. ..."
    ),
    inputs=(
        InterfaceField("input_vcf", "File", "Input VCF (joint-called or VQSR-filtered, plain text)."),
        InterfaceField("min_qual", "float", "Minimum QUAL to retain a record (inclusive). Default 30.0."),
    ),
    outputs=(
        InterfaceField("my_filtered_vcf", "File", "QUAL-filtered output VCF."),
    ),
    ...
    showcase_module="flytetest.workflows.variant_calling",
),
```

Two differences from the task entry of the same name's underlying task:

- `category="workflow"` routes the entry into `SUPPORTED_WORKFLOW_NAMES` and
  through `run_workflow` rather than `run_task`. See chapter 6 for the full
  field-by-field deep dive.
- `showcase_module="flytetest.workflows.variant_calling"` — point at the
  workflow module, not the tasks module, so MCP can resolve the callable.

Workflows do *not* need a `TASK_PARAMETERS` entry in `server.py`. That table is
for tasks only; `showcase_module` plus `category="workflow"` is enough to
expose a workflow through the MCP surface.

## Common pitfalls

- **Using `@workflow`.** Flyte v1 idiom; this codebase does not have it.
  Decorate workflows with `@<family>_env.task`.
- **Calling tasks with raw paths.** Passing `index.path` (a string) instead
  of `index` (a `Dir`) breaks the dependency tracking and forces the
  downstream task's signature to take `str`, which conflicts with the
  binding contract.
- **Forgetting to register.** A workflow function that has no
  `RegistryEntry` is invisible to MCP and to the planner. Add the entry in
  `src/flytetest/registry/_<family>.py` as part of the same patch.
- **Wrong `showcase_module`.** Pointing at the tasks module for a workflow
  entry (or vice versa) makes the MCP resolver fail to find the callable.

## What's next

- Chapter 9 covers MCP exposure: how a workflow with `category="workflow"`
  becomes a flat tool a client can call.
- Chapter 10 is the verification recipe — compileall, pytest, and the PR
  checklist that catches the pitfalls above before review.
