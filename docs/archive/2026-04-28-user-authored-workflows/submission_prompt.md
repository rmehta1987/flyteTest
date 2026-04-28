# Submission Prompt — User-Authored Workflow Composition

Execute the prompts in `docs/2026-04-28-user-authored-workflows/prompts/` in order:

```
step_01_flat_tool_task.md
step_02_composed_workflow.md
step_03_flat_tool_workflow.md
step_04_tests.md
step_05_docs_update.md
step_06_closure.md
```

## Pre-conditions

- On branch `main`; 942 tests collected (1 pre-existing error in
  `test_compatibility_exports.py` — ignore it throughout)
- `my_custom_filter` task exists at `src/flytetest/tasks/variant_calling.py:1272`
- `my_custom_filter` registry entry at `src/flytetest/registry/_variant_calling.py:1312`
- `TASK_PARAMETERS["my_custom_filter"]` at `src/flytetest/server.py:308`
- `mcp_tools.py` has no flat tool for `my_custom_filter` yet
- Last workflow: `annotate_variants_snpeff` at
  `src/flytetest/workflows/variant_calling.py:603`
- Read `docs/2026-04-28-user-authored-workflows/user_authored_workflows_plan.md`
  before starting; resolve all open questions with the user first

## Success criterion

Full suite green (minus the pre-existing error), all checklist gates ticked,
milestone archived to `docs/archive/`.
