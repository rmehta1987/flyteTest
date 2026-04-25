# Plan — On-Ramp Implementation: run_tool Extension + my_custom_filter Reference Task

_Created 2026-04-24._

## Motivation

`PLAN_onramp_test.md` calls for a pure-Python reference task (`my_custom_filter`)
that exercises the user-authoring on-ramp end to end. Before implementing that task,
we are extending `run_tool` in `src/flytetest/config.py` so that all three execution
modes a user might need live in a single, testable place:

| Mode | When to use | How invoked |
|---|---|---|
| **SIF/container** | tool requires a containerized binary (GATK, bwa-mem2, SnpEff) | `run_tool(cmd, sif_path, bind_paths)` |
| **Native executable** | binary available on `PATH` or at an explicit path (Rscript, compiled C++, samtools) | `run_tool(cmd, sif="", bind_paths=[])` — already works |
| **Python callable** | pure-Python logic with no subprocess overhead | `run_tool(python_callable=fn, callable_kwargs={...})` — **new** |

The native executable mode already works today — `sif=""` falls through to a bare
`subprocess.run`. This plan documents it explicitly in the guide and adds a test, but
requires no code change for that path. The Python callable mode requires a backward-
compatible extension to `run_tool`.

## Scope

Touch only these files:
- `src/flytetest/config.py` — extend `run_tool` signature
- `src/flytetest/tasks/variant_calling.py` — add task + `MANIFEST_OUTPUT_KEYS` append
- `src/flytetest/tasks/_filter_helpers.py` — new pure-Python logic module
- `src/flytetest/registry/_variant_calling.py` — new `RegistryEntry`
- `src/flytetest/server.py` — `TASK_PARAMETERS` append only
- `tests/test_run_tool.py` — new config-layer tests for all three modes
- `tests/test_my_filter.py` — pure-logic unit tests
- `tests/test_variant_calling.py` — three new test classes
- `.codex/user_tasks.md` — update to document three modes + point to real implementation
- `.codex/agent/scaffold.md` — fix Core Principle 1 wording
- `CHANGELOG.md` — dated entry

Do NOT touch: `planning.py`, `mcp_contract.py`, `bundles.py`, `spec_executor.py`,
`planner_types.py`, `server.py` handler logic, any workflow file.

## Key design decisions (settled)

- `run_tool` gets a **keyword-only** `python_callable` + `callable_kwargs` pair.
  When `python_callable` is provided the subprocess path is skipped entirely.
  `cmd` becomes optional (`None` default) so pure-Python callers need not pass a
  dummy list. Existing positional call sites (`run_tool(cmd, sif, bind_paths)`)
  continue to work unchanged.
- The reference task parameter is **`vcf_path: File`** (not `vcf`) to match the
  `VariantCallSet.vcf_path` field name that the resolver uses for binding wiring.
- Output file uses **`.vcf`** extension (uncompressed plain text).
- Missing QUAL (`.`) is treated as **below threshold** — the record is dropped.
- Pure-Python logic lives in **`src/flytetest/tasks/_filter_helpers.py`**, not in
  a new top-level `filtering/` package. Import path stays inside the tasks layer.
- `my_custom_filter` calls `run_tool(python_callable=filter_vcf, callable_kwargs=...)`
  — it goes through `run_tool` exactly like SIF tasks, preserving the single
  execution entry point for all task families.

## Milestone H/I / current-state constraints

- 862 tests pass today (baseline after mcp-surface-polish); treat "full suite green"
  as the target, not a hardcoded count.
- `MANIFEST_OUTPUT_KEYS` is at `variant_calling.py:25`; append `"my_filtered_vcf"`.
- `TASK_PARAMETERS` is in `server.py`; append only the scalar entry — `vcf_path` is
  a `File` binding and must not appear there.
- `pipeline_stage_order=22` is the next free slot after the 21 existing GATK tasks.
- `variant_filtration` already exists at `registry/_variant_calling.py:634`.
  `my_custom_filter` is additive / alternative, not a replacement.

## Verification gates (all must pass before merge)

```bash
# Syntax
python3 -m compileall src/flytetest/config.py \
    src/flytetest/tasks/_filter_helpers.py \
    src/flytetest/tasks/variant_calling.py \
    src/flytetest/registry/_variant_calling.py \
    src/flytetest/server.py

# Pure-logic layer
PYTHONPATH=src pytest tests/test_run_tool.py tests/test_my_filter.py -x

# Task + registry + MCP layers
PYTHONPATH=src pytest \
    tests/test_variant_calling.py::MyCustomFilterInvocationTests \
    tests/test_variant_calling.py::MyCustomFilterRegistryTests \
    tests/test_variant_calling.py::MyCustomFilterMCPExposureTests -x

# Registry guards
PYTHONPATH=src pytest tests/test_registry.py tests/test_registry_manifest_contract.py -x

# Full suite
PYTHONPATH=src pytest -x

# Name consistency
rg -n "my_custom_filter|my_filtered_vcf|filter_vcf" src/ tests/ CHANGELOG.md

# Scope guard — none of these should appear in diff
git diff --name-only | grep -E "planning\.py|mcp_contract\.py|bundles\.py|\
spec_executor\.py|planner_types\.py"
```
