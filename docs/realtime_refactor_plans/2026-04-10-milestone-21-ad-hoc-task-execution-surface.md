# Milestone 21 Ad Hoc Task Execution Surface

Date: 2026-04-10
Status: Proposed

Related checklist milestone:
- `docs/realtime_refactor_checklist.md` Milestone 21

Implementation note:
- This slice should broaden the current one-task ad hoc execution boundary into
  a deliberate, explicit task-execution surface.
- It should keep ad hoc task execution distinct from saved workflow recipe
  execution rather than turning the MCP layer into a second workflow engine.
- It should prefer direct Python task execution over brittle CLI serialization
  paths when task signatures include Flyte `File`, `Dir`, or collection-shaped
  values.

## Current State

- The MCP recipe surface is still workflow-first and recipe-first.
- `src/flytetest/server.py` currently supports one ad hoc task target:
  `exonerate_align_chunk`.
- Local workflow execution already uses explicit handler routing and now has a
  direct-Python fallback for collection-shaped workflow inputs when the current
  Flyte CLI serialization path is insufficient.
- There is no general policy yet for which registered tasks may be exposed for
  user-facing ad hoc execution.

## Target State

- FLyteTest exposes a bounded, documented set of registered tasks that can run
  ad hoc for experimentation, boundary debugging, or stage-focused validation.
- The task-execution surface keeps input binding explicit for scalar values and
  Flyte `File` / `Dir` shapes, including collection-shaped inputs when a task
  signature requires them.
- Ad hoc task results return structured, machine-readable summaries with stable
  output paths and clear limitations.
- Saved workflow recipe execution remains the primary reproducible path for
  multi-stage biology requests.

## Scope

In scope:

- Define the eligibility rules for user-facing ad hoc task execution.
- Extend the MCP/server task runner beyond the current single-task boundary.
- Add explicit coercion rules for scalar, `Path`, `File`, `Dir`, `list[File]`,
  and similar registered task inputs when needed.
- Keep task execution results inspectable and consistent with the current
  server result-summary style.
- Add tests for supported tasks, unsupported tasks, input coercion, and task
  result reporting.
- Update docs once the behavior lands.

Out of scope:

- Automatically exposing every registered task.
- Replacing frozen workflow recipe execution with task chaining.
- Changing the biological workflow boundaries or supported workflow families.
- Broader remote execution or backend-deployed orchestration.

## Implementation Steps

1. Audit `src/flytetest/server.py`, `src/flytetest/mcp_contract.py`,
   `src/flytetest/registry.py`, and current task modules to identify which
   registered tasks are safe to expose as ad hoc execution targets.
2. Define a small eligibility policy for user-facing tasks:
   clear biological boundary, explicit inputs, inspectable outputs, and no
   hidden dependence on prior shell-side setup.
3. Extend the task runner to coerce explicit task inputs into the Python object
   shapes expected by the selected task implementation.
4. Preserve a structured task execution result contract with output paths,
   limitations, and typed failure reporting.
5. Add tests covering supported task selection, task-input coercion,
   unsupported-task declines, and successful direct execution.
6. Update README, `docs/mcp_showcase.md`, `docs/capability_maturity.md`, and
   the checklist once the behavior lands.

## Validation Steps

- Run `python3 -m py_compile` on touched Python files if code changes land.
- Run focused tests:
  - `python3 -m unittest tests.test_server`
  - `python3 -m unittest tests.test_planning`
  - `python3 -m unittest tests.test_registry`
- Run `git diff --check`.
- Expand coverage if the work touches shared result-summary or contract logic.

## Blockers or Assumptions

- This milestone assumes the MCP/server task surface should stay explicit and
  bounded rather than discoverable from every registered task automatically.
- It assumes ad hoc task execution should remain a stage-debugging and
  experimentation tool, not a substitute for frozen workflow recipes.
- If a task requires non-obvious prior assets or hidden runtime context, it
  should remain ineligible until that contract can be made explicit.
