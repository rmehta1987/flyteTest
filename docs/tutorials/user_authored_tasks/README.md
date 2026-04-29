# Tutorial: Adding Your Own Task and Workflow

A hands-on walkthrough for new contributors who want to land a custom task and
workflow in flyteTest. Each chapter builds on the previous one; by the end you
will have re-derived the on-ramp reference example (`my_custom_filter` task and
`apply_custom_filter` workflow, shipped in commit `ad1ccef`) from first
principles and know where to plug your own logic in.

If you already know the registry contract and just want the rules-of-thumb,
skip the tutorial and read `.codex/user_tasks.md` directly.

## Who this is for

You are comfortable writing Python and have a function — a filter, a format
converter, a small statistics step — that you want to run as a registered,
composable stage inside the existing variant-calling or annotation pipelines.
You do not need prior Flyte v2 experience; the chapters introduce the framework
concepts as they appear.

## Prerequisites

- A working local checkout with the dev environment installed
  (`pip install -r requirements-cluster.txt`, see top-level `README.md`).
- `PYTHONPATH=src python3 -m pytest tests/ -q` passes on `main`.
- You have read the top-level `README.md` and skimmed `AGENTS.md` for the
  hard constraints and registry-first rules.

## Chapter list

Read these in order the first time through. Each chapter is roughly one PR's
worth of reading and produces one slice of the worked example.

1. [Anatomy of a task](01_anatomy.md) — the three-part structure (pure logic,
   task wrapper, registry entry) and why each layer exists.
2. [Your first task](02_first_task.md) — full walkthrough of
   `my_custom_filter`, end to end.
3. [Execution modes](03_execution_modes.md) — choosing between SIF, native
   executable, and python-callable invocation through `run_tool`.
4. [Manifests and outputs](04_manifests.md) — how `build_manifest_envelope`
   and `MANIFEST_OUTPUT_KEYS` enforce the output contract.
5. [The binding contract](05_bindings.md) — how planner-type fields map to
   task parameters, and the naming-collision gotcha to avoid.
6. [Registry entry deep-dive](06_registry.md) — every load-bearing field on
   `RegistryEntry` and `RegistryCompatibilityMetadata`.
7. [Testing your task](07_testing.md) — three test layers, with the
   `count_vcf_records` toy example for end-to-end demos.
8. [Composing a workflow](08_workflow_composition.md) — wiring tasks together
   with the `@<family>_env.task` decorator pattern.
9. [MCP exposure](09_mcp_exposure.md) — flat tools, `TASK_PARAMETERS`, and how
   your task becomes callable from an MCP client.
10. [Verification and PR checklist](10_verification.md) — the full local
    validation recipe plus what reviewers look for.

## Where to look in the codebase

The worked example is real, registered, and callable today. Open these files
alongside the chapters:

| Concept | File | Anchor |
|---|---|---|
| Pure-logic example | `src/flytetest/tasks/_filter_helpers.py` | `filter_vcf` (top of file) |
| Task wrapper example | `src/flytetest/tasks/variant_calling.py` | `my_custom_filter` at line 1278 |
| Workflow composition example | `src/flytetest/workflows/variant_calling.py` | `apply_custom_filter` at line 646 |
| Registry entries | `src/flytetest/registry/_variant_calling.py` | `my_custom_filter` at line 1313, `apply_custom_filter` at line 1351 |
| MCP flat tools | `src/flytetest/mcp_tools.py` | `vc_custom_filter` at line 948, `vc_apply_custom_filter` at line 1009 |
| Test patterns | `tests/test_variant_calling.py` | `MyCustomFilterInvocationTests` at line 2757, `MyCustomFilterRegistryTests` at line 2828, `MyCustomFilterMCPExposureTests` at line 2875 |
| Reference guide (deeper) | `.codex/user_tasks.md` | top of file |

## What you will produce

Following the tutorial end to end yields, in your own branch:

- one new pure-logic helper module under `src/flytetest/tasks/`,
- one new task in `src/flytetest/tasks/<family>.py`,
- one new workflow in `src/flytetest/workflows/<family>.py`,
- two new `RegistryEntry` records in `src/flytetest/registry/_<family>.py`,
- two new flat tools in `src/flytetest/mcp_tools.py`,
- a `TASK_PARAMETERS` entry in `src/flytetest/server.py`,
- a small new test class in `tests/test_<family>.py`,
- a dated `[x]` line under `## Unreleased` in `CHANGELOG.md`.

That set is the smallest patch that satisfies every contract test in the
suite. The chapters walk through each piece in order.

## A note on scope

Stop and ask for review (do not improvise) if your change needs any of:

- a new planner dataclass in `src/flytetest/planner_types.py`,
- a task that crosses pipeline families,
- a new MCP surface, or any change to `server.py` (beyond `TASK_PARAMETERS`),
  `planning.py`, `mcp_contract.py`, or `bundles.py`.

Those are architecture-critical and live under `.codex/agent/architecture.md`.
The tutorial assumes your change fits inside an existing pipeline family and
reuses an existing planner dataclass — the same shape as the worked example.

## Conventions used in this tutorial

- Code blocks are real snippets from the repo. The source `path:line` appears
  immediately above each block; if the line drifts as the codebase evolves,
  the file path is still the source of truth.
- Cross-links between chapters are relative markdown.
- Reader-facing voice ("you write...", "your task..."). No emojis.

Start with [Chapter 1: Anatomy of a task](01_anatomy.md).
