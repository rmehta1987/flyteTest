# Submission Prompt — On-Ramp Implementation

Execute the prompts in `docs/2026-04-24-onramp-impl/prompts/` in order:

```
step_01_run_tool_extend.md
step_02_filter_logic.md
step_03_task_registry.md
step_04_tests.md
step_05_docs_update.md
step_06_closure.md
```

## Pre-conditions

- On branch `main`; 862 tests pass, 1 skipped
- `src/flytetest/config.py:245` — `run_tool` signature before this milestone:
  `run_tool(cmd: list[str], sif: str, bind_paths: list[Path], cwd=None, stdout_path=None)`
- `MANIFEST_OUTPUT_KEYS` at `src/flytetest/tasks/variant_calling.py:25`
- `TASK_PARAMETERS` at `src/flytetest/server.py:164`
- `VariantCallSet.vcf_path` at `src/flytetest/planner_types.py:221`
- Read `docs/2026-04-24-onramp-impl/onramp_impl_plan.md` before starting

## Success criterion

Full suite green, all checklist gates ticked, milestone archived to `docs/archive/`.
