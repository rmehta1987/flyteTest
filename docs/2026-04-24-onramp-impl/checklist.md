# On-Ramp Implementation Milestone Checklist

## Steps

| Step | Name | Status |
|---|---|---|
| 01 | Extend `run_tool` (python_callable mode + tests) | [ ] |
| 02 | Pure-Python filter logic (`_filter_helpers.py` + `test_my_filter.py`) | [ ] |
| 03 | Task, registry entry, `TASK_PARAMETERS` append | [ ] |
| 04 | Test classes in `test_variant_calling.py` (Layers 2–4) | [ ] |
| 05 | Doc updates (`user_tasks.md`, `scaffold.md`) | [ ] |
| 06 | Closure (CHANGELOG, full suite, commit) | [ ] |

## Verification gates

- [ ] `python3 -m compileall` passes on all touched files
- [ ] `pytest tests/test_run_tool.py tests/test_my_filter.py -x` — pure-layer green
- [ ] `pytest tests/test_variant_calling.py::MyCustomFilterInvocationTests -x` — Layer 2
- [ ] `pytest tests/test_variant_calling.py::MyCustomFilterRegistryTests -x` — Layer 3
- [ ] `pytest tests/test_variant_calling.py::MyCustomFilterMCPExposureTests -x` — Layer 4
- [ ] `pytest tests/test_registry.py tests/test_registry_manifest_contract.py -x`
- [ ] Full suite green (no regressions)
- [ ] `rg "my_custom_filter"` appears in task def, registry, `TASK_PARAMETERS`, tests, CHANGELOG — nowhere else
- [ ] `git diff --name-only` contains no `planning.py`, `mcp_contract.py`, `bundles.py`, `spec_executor.py`, `planner_types.py`

## Hard constraints

- `run_tool` extension must be backward compatible — all existing call sites use
  positional args and must continue working without any changes
- Task parameter must be `vcf_path: File`, not `vcf: File`
- Output file must use `.vcf` extension (uncompressed)
- Missing QUAL (`.`) must be treated as below threshold (dropped)
- `_filter_helpers.py` lives inside `src/flytetest/tasks/`, not a new top-level package
- `TASK_PARAMETERS` append is the only allowed `server.py` edit
