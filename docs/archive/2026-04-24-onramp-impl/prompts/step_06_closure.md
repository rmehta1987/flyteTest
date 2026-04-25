# Step 06 — Closure

Run all verification gates, update CHANGELOG.md, commit, and archive.

---

## Verification gates (all must pass)

### Syntax
```bash
python3 -m compileall \
    src/flytetest/config.py \
    src/flytetest/tasks/_filter_helpers.py \
    src/flytetest/tasks/variant_calling.py \
    src/flytetest/registry/_variant_calling.py \
    src/flytetest/server.py
```

### Pure-layer tests
```bash
PYTHONPATH=src python3 -m pytest tests/test_run_tool.py tests/test_my_filter.py -v
```

### Task + registry + MCP layers
```bash
PYTHONPATH=src python3 -m pytest \
    tests/test_variant_calling.py::MyCustomFilterInvocationTests \
    tests/test_variant_calling.py::MyCustomFilterRegistryTests \
    tests/test_variant_calling.py::MyCustomFilterMCPExposureTests \
    -v
```

### Registry contract guards
```bash
PYTHONPATH=src python3 -m pytest \
    tests/test_registry.py \
    tests/test_registry_manifest_contract.py \
    -x -q
```

### Full suite
```bash
PYTHONPATH=src python3 -m pytest --ignore=tests/test_compatibility_exports.py -q
# Expected: 862 + new tests, all green. Record the actual count.
```

### Name consistency
```bash
rg -n "my_custom_filter|my_filtered_vcf|filter_vcf" src/ tests/ CHANGELOG.md
# Must appear in: task def, MANIFEST_OUTPUT_KEYS, registry entry,
# TASK_PARAMETERS, test classes, CHANGELOG. Nowhere else.
```

### Scope guard
```bash
git diff --name-only | grep -E \
    "planning\.py|mcp_contract\.py|bundles\.py|spec_executor\.py|planner_types\.py"
# Must return nothing.
```

---

## CHANGELOG.md entry

Add immediately below `## Unreleased`, above all existing sections:

```markdown
### On-ramp implementation — run_tool extension + my_custom_filter (2026-04-24)

- [x] 2026-04-24 `config.py`: extended `run_tool` with `python_callable` +
  `callable_kwargs` keyword-only parameters; Python-callable mode invokes a
  function in-process with no subprocess overhead; native executable mode
  (Rscript, compiled C++, system binary) now explicitly documented alongside
  the existing SIF/container path; all three modes tested in `tests/test_run_tool.py`.
- [x] 2026-04-24 `tasks/_filter_helpers.py` (new): pure-Python `filter_vcf`
  function — plain-text VCF QUAL threshold filter; no external dependencies;
  missing QUAL (`.`) treated as below threshold; 7 unit tests in
  `tests/test_my_filter.py`.
- [x] 2026-04-24 `tasks/variant_calling.py`: added `my_custom_filter` task
  (pure-Python callable mode, `vcf_path: File → File`, `min_qual: float = 30.0`);
  appended `"my_filtered_vcf"` to `MANIFEST_OUTPUT_KEYS`; manifest written as
  `run_manifest_my_custom_filter.json`.
- [x] 2026-04-24 `registry/_variant_calling.py`: added `RegistryEntry` for
  `my_custom_filter` (`pipeline_stage_order=22`, `accepted/produced=VariantCallSet`,
  `runtime_images={}`, `module_loads=("python/3.11.9",)`).
- [x] 2026-04-24 `server.py`: appended `"my_custom_filter": (("min_qual", False),)`
  to `TASK_PARAMETERS`; no other server changes.
- [x] 2026-04-24 Tests: `MyCustomFilterInvocationTests` (Layer 2 — direct task
  call with File stub), `MyCustomFilterRegistryTests` (Layer 3 — entry shape +
  manifest-key consistency), `MyCustomFilterMCPExposureTests` (Layer 4 — MCP
  discovery + scalar parameter contract); all in `tests/test_variant_calling.py`.
- [x] 2026-04-24 `.codex/user_tasks.md`: updated to document all three execution
  modes (SIF, native, Python callable) and linked to the real `my_custom_filter`
  implementation as the copyable template.
- [x] 2026-04-24 `.codex/agent/scaffold.md`: corrected Core Principle 1 from
  "four file edits" to the accurate six touch points; added Python-callable mode
  to the Execution Mode section.
```

---

## Commit

```bash
git add \
    src/flytetest/config.py \
    src/flytetest/tasks/_filter_helpers.py \
    src/flytetest/tasks/variant_calling.py \
    src/flytetest/registry/_variant_calling.py \
    src/flytetest/server.py \
    tests/test_run_tool.py \
    tests/test_my_filter.py \
    tests/test_variant_calling.py \
    .codex/user_tasks.md \
    .codex/agent/scaffold.md \
    CHANGELOG.md

git commit -m "onramp-impl: run_tool callable mode + my_custom_filter reference task"
```

## Archive

```bash
git mv docs/2026-04-24-onramp-impl docs/archive/2026-04-24-onramp-impl
git commit -m "archive: onramp-impl milestone"
```
