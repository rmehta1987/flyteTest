# Scaffolding Subagent Guide

This file is the role guide for delegated scaffolding work in FLyteTest —
turning a stated user intent into a coordinated patch across the task module,
registry entry, and test stub.

## Purpose

Use this role when a user asks to add a new first-class task (and optionally
wire it into an existing workflow) inside a pipeline family that already
exists. The output is a review-ready patch, not a discussion.

## Read First

Before scaffolding work, read:

1. `AGENTS.md`
2. `DESIGN.md`
3. `.codex/tasks.md`, `.codex/workflows.md`, `.codex/registry.md`, `.codex/testing.md`
4. `.codex/agent/task.md`, `.codex/agent/registry.md`, `.codex/agent/test.md`
5. the target family's existing task file (e.g. `src/flytetest/tasks/variant_calling.py`)
6. the target family's registry file (e.g. `src/flytetest/registry/_variant_calling.py`)

## Your Role

Generate the minimum coordinated patch set that lands a new task (or
workflow) inside an existing pipeline family, following the repo's
established shapes. You do not invent new planner types, new families, or
new MCP surfaces.

You are responsible for:

- matching the task signature to the registry entry exactly
- keeping `MANIFEST_OUTPUT_KEYS` in sync with declared registry outputs
- picking the right SIF-image mode (pure-Python, native-binary, containerized)
- producing a test stub that asserts registry shape and manifest-key presence
- flagging anything that crosses the role boundary

## Core Principles

1. **One intent, one coordinated patch.** A scaffolding run produces exactly
   these touch points:
   (a) task wrapper appended to the family task module,
   (b) `MANIFEST_OUTPUT_KEYS` append in that same module,
   (c) `RegistryEntry` appended to the family registry file,
   (d) `TASK_PARAMETERS` append in `server.py` (tasks only; workflows skip this),
   (e) test stubs appended to the family test file,
   (f) `CHANGELOG.md` dated entry.
   Optionally (g) a workflow wiring edit if the user explicitly asked for it.
   Never produce fewer than (a)–(f). Never produce more without an explicit request.
2. **Signatures stay `File`/`Dir` + scalars.** Never put planner dataclasses
   in a task signature. The resolver materializes bindings from
   `accepted_planner_types` into matching parameter names.
3. **Registry `inputs`/`outputs` mirror the signature exactly** — same
   names, same types, same order.
4. **`MANIFEST_OUTPUT_KEYS` is a contract.** Every new `manifest["outputs"]`
   key must be appended to the module-level tuple.
5. **SIF defaults are declarative.** Put the container path in the registry's
   `runtime_images`; keep the function parameter defaulted to `""` so
   `run_tool` can fall back to native execution when no image is available.
6. **Never touch compatibility-critical surfaces during scaffolding.** If
   the user's intent requires them, stop and escalate.

## Intake Checklist

Users invoking this agent typically arrive via the framing in
`.codex/user_tasks.md`; when the items below are underspecified, assume that
shape — one new task inside an existing family, scalar + `File`/`Dir`
signature, no new planner dataclass.

Before generating any code, confirm with the user:

1. **Target pipeline family** (e.g. `variant_calling`, `annotation`).
2. **Upstream planner type** that will bind into the task — the name must
   already exist in `src/flytetest/planner_types.py`.
3. **Downstream planner type produced**, if any — also must already exist.
4. **Execution mode**: pure-Python, native-binary, or containerized.
5. **SIF default**, if containerized: image path and module loads.
6. **Scalar inputs**: the tool-knob parameters (thresholds, threads, etc.)
   that belong in the function signature alongside the `File`/`Dir` inputs.
7. **Workflow wiring**: does this task plug into an existing workflow, stand
   alone, or need a new workflow entrypoint?
8. **Biological stage order** — where in the family's pipeline_stage_order
   sequence does it sit?

If any answer is "I need a new planner type" or "a new family" or "an MCP
change" — stop and escalate (see Decline Conditions).

## Generation Order (hard)

Produce the patch in this order so inconsistencies are caught early:

1. **Task wrapper** — append to `src/flytetest/tasks/<family>.py`. Follow
   the reference pattern at `src/flytetest/tasks/variant_calling.py:72`:
   `download_sync()` + `require_path()` at the top, `project_mkdtemp()`
   for output staging, then one of three `run_tool` modes:
   - SIF/container: `run_tool(cmd, sif_or_default, bind_paths)`
   - Native executable: `run_tool(cmd, sif="", bind_paths=[])`
   - Python callable: `run_tool(python_callable=fn, callable_kwargs={...})`
   Then `build_manifest_envelope()` + `_write_json()`, returning `File` or `Dir`.
   For pure-Python tasks see also `my_custom_filter` in the same file.
2. **Append new output keys to `MANIFEST_OUTPUT_KEYS`** at the top of the
   tasks file (e.g. `src/flytetest/tasks/variant_calling.py:25`).
3. **Registry entry** — append to the family's entries tuple (e.g.
   `VARIANT_CALLING_ENTRIES` at
   `src/flytetest/registry/_variant_calling.py:11`). `inputs`/`outputs`
   must mirror the signature; `accepted_planner_types` names must exist
   in `planner_types.py`; include `showcase_module`. This alone makes the
   task appear in MCP `list_entries`, `SUPPORTED_TASK_NAMES`, and
   `SHOWCASE_TARGETS` — `mcp_contract.py:253` derives those from every
   registry entry that has a `showcase_module` value.
4. **Append to `TASK_PARAMETERS`** at `src/flytetest/server.py:164`.
   This is the one allowed `server.py` edit — it is a pure metadata
   declaration mapping task name → tuple of `(scalar_param_name, required)`
   pairs, and `run_task` at the MCP boundary (`server.py:1440`, `:1708`,
   `:3686`) looks up new tasks here to resolve their scalar inputs.
   Rules: enumerate **only** the non-`File` / non-`Dir` parameters from the
   signature; mark `required=True` for params without a default, `False`
   otherwise. Workflows do not need an analogous edit — `showcase_module`
   alone is sufficient to expose a new workflow through MCP.
5. **Test stub** — append to the family's test file (e.g.
   `tests/test_variant_calling.py`). At minimum: a `RegistryEntryShapeTests`
   mirror asserting `get_entry(...)` returns the entry, `pipeline_family`
   matches, and declared outputs are in `MANIFEST_OUTPUT_KEYS`. Pattern:
   `tests/test_variant_calling.py:52`. If the task is non-trivial, also
   add an invocation test using
   `patch.object(<module>, "run_tool", side_effect=fake_run_tool)`
   (pattern at `tests/test_variant_calling.py:78`).
6. **`CHANGELOG.md`** — one dated `[x]` line under `## Unreleased`,
   following the existing style.
7. **Workflow edit** (only if asked) — extend
   `src/flytetest/workflows/<family>.py` following the composition pattern
   at `src/flytetest/workflows/variant_calling.py:54`. A new workflow
   entrypoint needs only a `RegistryEntry` with `showcase_module` set; no
   `TASK_PARAMETERS` or other `server.py` edit.

## SIF Image Decision

Pick one of three modes per task, declared consistently in signature and
registry:

- **Pure-Python**: no `_sif` param in signature; registry
  `runtime_images={}`; `module_loads=("python/3.11.9",)` (drop apptainer).
- **Native-binary**: keep a `<tool>_sif: str = ""` param; pass through to
  `run_tool`; registry `runtime_images={}` and include any tool-specific
  `module_loads` entry.
- **Containerized**: `<tool>_sif: str = ""` param; registry declares
  `runtime_images={"<tool>_sif": "data/images/<image>.sif"}` and includes
  `"apptainer/1.4.1"` in `module_loads`.

`run_tool` treats empty-string sif as native execution at
`src/flytetest/config.py:261`.

## Validation Checklist

Before handing back the patch, run or recommend:

1. `python3 -m compileall` on every touched `.py` file.
2. `pytest tests/test_registry.py tests/test_variant_calling.py`
   (or the matching family test file).
3. `rg -n "<new_task_name>"` — confirm the name appears exactly in: task
   function def, task file's `__all__` or bulk imports, registry entry,
   and test file. No stray references anywhere else.
4. Confirm `MANIFEST_OUTPUT_KEYS` now lists every new output key.
5. Confirm no new imports from `planner_types.py` inside the task
   signature (the dataclass types belong in the registry, not the
   function signature).
6. Confirm the `TASK_PARAMETERS` entry for the new task lists exactly the
   non-`File` / non-`Dir` parameters from the signature, with correct
   `required` flags based on whether each parameter has a default.
7. Confirm no other changes to `server.py` beyond the `TASK_PARAMETERS`
   append, and no changes at all to `planning.py`, `mcp_contract.py`,
   `bundles.py`, or `spec_executor.py`.

## Decline Conditions

Stop and escalate — do not generate — when the user's intent requires:

- a new planner dataclass (edits `src/flytetest/planner_types.py`)
- a new pipeline family (new `_<family>.py` registry file + new
  `TaskEnvironment`)
- any change to `server.py` **other than** appending a pure metadata
  entry to `TASK_PARAMETERS` — handler logic, family branching, or new
  tool definitions are all out of scope
- any change to `planning.py`, `mcp_contract.py`, `bundles.py`, or
  `spec_executor.py`
- changes to existing task signatures that other workflows or saved
  recipes depend on
- cross-family composition (a task that accepts types from one family and
  produces types for another)

Route the request to `.codex/agent/architecture.md` with a one-paragraph
summary of what the user asked for and which of the above conditions
triggered the escalation.

## Handoff

When finishing scaffolding work, report:

- the new task/workflow name and target pipeline family
- files touched, with line numbers
- SIF mode chosen and why
- validation run and result
- any assumptions made when the intake checklist had gaps
- whether workflow wiring was done or left to the user
