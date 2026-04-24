# Plan — End-to-End Test of the User-Authoring On-Ramp

## Context

Earlier in this session we built a user-authoring on-ramp (`.codex/user_tasks.md`)
and a unified scaffolding agent prompt (`.codex/agent/scaffold.md`). Those
artifacts describe how a user wraps a custom Python function as a registered
flyteTest task, and how the scaffolding agent mechanically produces the patch.

The on-ramp has not yet been exercised against a real task. The worked example
in `.codex/user_tasks.md` — a pure-Python variant filter that consumes a
`VariantCallSet` and produces a filtered VCF — has never been implemented, and
the repo has no pure-Python tasks today (every existing task shells out via
`run_tool`). This creates two risks:

1. The on-ramp / scaffold agent may contain a latent mistake (wrong Read First
   order, missing step, incorrect SIF handling) that only surfaces when
   someone actually tries to follow it.
2. Future edits to `server.py`, the registry types, or the MCP surface could
   silently break the scaffolding contract, with no guard test catching it.

We will land a minimal pure-Python reference task (`my_custom_filter`),
scaffolded by following the on-ramp exactly as a user would, and ship it with
tests at every layer the user guide promises. That gives us:

- a first pure-Python task, establishing that pattern cleanly in the repo,
- a living regression guard for the on-ramp,
- a copyable template that future users can point to.

## Deliverables

All files land in a single commit on the current branch.

### New files

- **`src/flytetest/filtering/__init__.py`** — empty.
- **`src/flytetest/filtering/my_filter.py`** — pure-Python `filter_vcf(in_path: Path, out_path: Path, min_qual: float) -> None`. Plain-text VCF I/O (no `pysam` — the repo has no VCF-parsing dep per `pyproject.toml:11-15`). Pass-through for header lines (`#`-prefixed); for data lines, parse column 6 (QUAL) as float and skip rows below `min_qual`. ~25 lines.
- **`tests/test_my_filter.py`** — pure-logic unit tests for `filter_vcf` against an inline synthetic VCF built with `tmp_path` (pattern per `tests/test_variant_calling.py:265-276`). Assert header preserved, low-QUAL records dropped, high-QUAL records kept.

### Edited files (following `.codex/agent/scaffold.md` Generation Order exactly)

1. **`src/flytetest/tasks/variant_calling.py`** — append `my_custom_filter` task (pure-Python mode: no `_sif` param, calls `filter_vcf` directly, writes `run_manifest_my_custom_filter.json`). Append `"my_filtered_vcf"` to `MANIFEST_OUTPUT_KEYS` at line 25.
2. **`src/flytetest/registry/_variant_calling.py`** — append `RegistryEntry` with `accepted_planner_types=("VariantCallSet",)`, `produced_planner_types=("VariantCallSet",)`, `runtime_images={}`, `module_loads=("python/3.11.9",)`, `pipeline_stage_order=22`, `showcase_module="flytetest.tasks.variant_calling"`.
3. **`src/flytetest/server.py`** — append to `TASK_PARAMETERS` at line 164: `"my_custom_filter": (("min_qual", False),)`. Only the non-`File`/non-`Dir` scalar.
4. **`tests/test_variant_calling.py`** — add three test classes (see Testing Strategy below).
5. **`CHANGELOG.md`** — one dated `[x]` entry under `## Unreleased` describing the reference example.

## Implementation steps (execute the scaffolding agent's Generation Order as self-demonstration)

Order matters — each step checks the previous one's consistency:

1. Write `src/flytetest/filtering/my_filter.py` and its unit test. Validate with `pytest tests/test_my_filter.py` before touching any task wiring. If pure logic isn't right, fix it here.
2. Append `my_custom_filter` task to `src/flytetest/tasks/variant_calling.py`. Import `filter_vcf` from `flytetest.filtering.my_filter`. Use `project_mkdtemp`, `require_path`, `build_manifest_envelope`, `_write_json` — the same helpers the reference task at `src/flytetest/tasks/variant_calling.py:72` uses. Append `"my_filtered_vcf"` to `MANIFEST_OUTPUT_KEYS`.
3. Append the `RegistryEntry` to `VARIANT_CALLING_ENTRIES` at `src/flytetest/registry/_variant_calling.py:11`. `inputs`/`outputs` must mirror the task signature exactly.
4. Append to `TASK_PARAMETERS` at `src/flytetest/server.py:164`. Only `("min_qual", False)` — `vcf` is a `File` binding, not a scalar.
5. Add test classes to `tests/test_variant_calling.py` (see below).
6. Add CHANGELOG entry dated 2026-04-24 (or current day).

## Testing strategy — five layers, cheapest first

The layers match the three-layer testing model in `.codex/user_tasks.md` plus two registry/MCP guards the on-ramp implicitly promises.

### Layer 1 — pure Python unit test
`tests/test_my_filter.py`. Construct a 5-line synthetic VCF in `tmp_path` (two header lines, three data lines at QUAL values 10, 50, 100). Call `filter_vcf(in, out, min_qual=30.0)`. Assert two data lines remain and all header lines preserved. No Flyte, no harness.

### Layer 2 — task invocation via `flyte_stub`
New class `MyCustomFilterInvocationTests` in `tests/test_variant_calling.py`. `install_flyte_stub()` at module load already makes `@variant_calling_env.task` a pass-through (`tests/flyte_stub.py:92-94`). Call `my_custom_filter(vcf=File(path=str(vcf_path)), min_qual=30.0)` directly on a synthetic VCF. Assert:
- returned `File` exists
- `run_manifest_my_custom_filter.json` written next to output
- manifest contains `outputs["my_filtered_vcf"]` pointing at the returned path
- filtered content is correct (low-QUAL record dropped)

This is the pattern at `tests/test_variant_calling.py:75-99` minus the `patch.object(..., "run_tool", ...)` since there is no `run_tool` call — the first pure-Python task in the repo.

### Layer 3 — registry shape
New class `MyCustomFilterRegistryTests` in `tests/test_variant_calling.py`, mirroring `RegistryEntryShapeTests` at `tests/test_variant_calling.py:52-72`. Assert:
- `get_entry("my_custom_filter")` returns non-None
- `entry.category == "task"`
- `entry.compatibility.pipeline_family == "variant_calling"`
- `entry.compatibility.accepted_planner_types == ("VariantCallSet",)`
- `entry.compatibility.produced_planner_types == ("VariantCallSet",)`
- `"my_filtered_vcf"` in output names and in `MANIFEST_OUTPUT_KEYS`
- `entry.showcase_module == "flytetest.tasks.variant_calling"`

### Layer 4 — MCP discovery + `TASK_PARAMETERS`
New class `MyCustomFilterMCPExposureTests` in `tests/test_variant_calling.py`. Assert:
- `"my_custom_filter"` in `flytetest.mcp_contract.SUPPORTED_TASK_NAMES` (derived from `showcase_module` at `src/flytetest/mcp_contract.py:253-266`)
- `flytetest.server.TASK_PARAMETERS["my_custom_filter"] == (("min_qual", False),)`
- `flytetest.server._scalar_params_for_task("my_custom_filter")` returns `("min_qual",)` after typed bindings are subtracted (pattern at `src/flytetest/server.py:1704-1717`)

### Layer 5 (optional) — end-to-end `run_task` smoke
If Layer 4 passes, add one smoke test that patches the task handler and calls `run_task` with a `VariantCallSet`-shaped binding, following the pattern at `tests/test_server.py:3065-3124`. Not strictly required — Layer 2 already exercises the callable — but it's the only way to exercise the resolver that turns a typed binding into the `vcf: File` parameter.

## Critical files referenced (read-only — plan does not modify these)

- `.codex/user_tasks.md` — worked example the plan implements
- `.codex/agent/scaffold.md` — Generation Order the plan follows step-by-step
- `tests/flyte_stub.py:67-94` — `File.download_sync()` passthrough and the `@task` pass-through decorator that makes Layer 2 possible
- `src/flytetest/tasks/variant_calling.py:25` — `MANIFEST_OUTPUT_KEYS`
- `src/flytetest/tasks/variant_calling.py:72` — reference task pattern
- `src/flytetest/registry/_variant_calling.py:11-45` — reference `RegistryEntry` including `showcase_module`
- `src/flytetest/planner_types.py:221` — `VariantCallSet`
- `src/flytetest/server.py:164` — `TASK_PARAMETERS`
- `src/flytetest/server.py:1704-1717` — `_scalar_params_for_task`
- `src/flytetest/mcp_contract.py:253-266` — `SHOWCASE_TARGETS` / `SUPPORTED_TASK_NAMES` derivation
- `tests/test_variant_calling.py:52-72` — `RegistryEntryShapeTests` template
- `tests/test_variant_calling.py:75-99` — task invocation test template (without the `run_tool` patch, since this task has none)
- `tests/test_registry_manifest_contract.py:88-100` — MANIFEST_OUTPUT_KEYS subset assertion pattern

## Verification (exact commands)

Run in this order; each must pass before the next.

1. `python3 -m compileall src/flytetest/filtering/ src/flytetest/tasks/variant_calling.py src/flytetest/registry/_variant_calling.py src/flytetest/server.py` — syntax check every touched module.
2. `PYTHONPATH=src pytest tests/test_my_filter.py -x` — Layer 1 passes alone before integration wiring is exercised.
3. `PYTHONPATH=src pytest tests/test_variant_calling.py::MyCustomFilterInvocationTests tests/test_variant_calling.py::MyCustomFilterRegistryTests tests/test_variant_calling.py::MyCustomFilterMCPExposureTests -x` — Layers 2–4.
4. `PYTHONPATH=src pytest tests/test_registry.py tests/test_registry_manifest_contract.py -x` — confirm the existing registry guards still pass (declared outputs subset check, etc.).
5. `PYTHONPATH=src pytest -x` — full suite; expect 858 + new tests, all green.
6. `rg -n "my_custom_filter" src/ tests/` — confirm the name appears exactly in: task def, registry entry, `TASK_PARAMETERS`, test file, CHANGELOG. Zero stray references.
7. `git diff --stat` — confirm only these files changed: the three `src/flytetest/filtering/*` files, `src/flytetest/tasks/variant_calling.py`, `src/flytetest/registry/_variant_calling.py`, `src/flytetest/server.py`, `tests/test_my_filter.py`, `tests/test_variant_calling.py`, `CHANGELOG.md`. No edits to `planning.py`, `mcp_contract.py`, `bundles.py`, `spec_executor.py`, or `planner_types.py` — that's the scaffold agent's Decline Condition boundary holding.

## Rollback plan

If Layer 4 reveals the on-ramp is wrong (e.g. the task doesn't appear in `SUPPORTED_TASK_NAMES`, or `_scalar_params_for_task` returns the wrong tuple), the fix goes into `.codex/user_tasks.md` and `.codex/agent/scaffold.md` first, then the reference task is re-scaffolded against the corrected guide. The test artifacts stay as the regression guard.
