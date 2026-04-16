# Milestone 0 Compatibility Inventory

Date: 2026-04-06

Related checklist milestone:
- `docs/realtime_refactor_checklist.md` Milestone 0

## Current State

- The repo already has a narrow planner, static registry, compatibility
  `flyte_rnaseq_workflow.py` shim, and a small MCP showcase.
- The compatibility guardrails were described at a high level in the checklist
  and README, but the exact externally visible behaviors were not yet recorded
  in one slice-focused plan.
- `tests/test_server.py` already covered MCP tool names and resource URIs, but
  there was no dedicated planner contract test module and no direct
  compatibility-export coverage for `flyte_rnaseq_workflow.py`.
- `tests/test_registry.py` covered specific entries, but not the current
  `list_entries()` behavior that later registry work must preserve.

## Target State

- Milestone 0 records which planner, registry, server, and workflow-export
  behaviors are compatibility-critical versus safe to refactor internally.
- The checklist carries a short stop-rule note for Milestones 1 through 8.
- Acceptance checks cover:
  - planner output shape and supported-entry grouping
  - registry listing behavior
  - MCP tool names and resource URIs
  - `flyte_rnaseq_workflow.py` compatibility exports

## Implementation Steps

1. Inspect `src/flytetest/planning.py`, `src/flytetest/registry.py`,
   `src/flytetest/server.py`, `flyte_rnaseq_workflow.py`, and the current tests
   to identify externally visible compatibility seams.
2. Add `tests/test_planning.py` to freeze the current showcase planner subset.
3. Extend `tests/test_registry.py` to cover `list_entries()` behavior directly.
4. Add `tests/test_compatibility_exports.py` to guard the `flyte run`
   compatibility entrypoint.
5. Update `docs/realtime_refactor_checklist.md` with the compatibility
   inventory, stop-rule note, acceptance evidence, and completed Milestone 0
   items.

## Validation Steps

- Run:
  `.venv/bin/python -m unittest tests.test_planning tests.test_registry tests.test_server tests.test_compatibility_exports`
- Run:
  `.venv/bin/python -m py_compile tests/test_planning.py tests/test_registry.py tests/test_server.py tests/test_compatibility_exports.py`

## Blockers Or Assumptions

- This slice intentionally freezes the current narrow planner/MCP subset; it
  does not start Milestone 1 biology-facing type work.
- The compatibility-export test relies on the repo's Flyte test stub because
  the real Flyte SDK is not required in the default local test environment.
