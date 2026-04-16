# Milestone 5 Typed Planner Preview

Date: 2026-04-06

Related checklist milestone:
- `docs/realtime_refactor_checklist.md` Milestone 5

## Current State

- `src/flytetest/planning.py` preserved the narrow MCP showcase planner through
  `plan_request(...)`.
- Planner-facing biology types, the local manifest-backed resolver, normalized
  spec dataclasses, and registry compatibility metadata already existed.
- The older prompt path still started with explicit local path extraction and
  did not consume the resolver or registry compatibility metadata.

## Target State

- Add an additive typed planning path without changing the showcase planner
  payload.
- Map prompts into a small set of biology-level goals before resolving inputs.
- Use resolver results and registry compatibility metadata to report whether a
  prompt maps to:
  - direct registered workflow selection
  - registered-stage composition
  - a metadata-only generated `WorkflowSpec` preview
  - honest decline for unsupported or underspecified biology
- Return assumptions, missing typed inputs, runtime requirements, a
  metadata-only `WorkflowSpec`, and a metadata-only `BindingPlan`.

## Implementation Steps

1. Add `plan_typed_request(...)` and typed planning helpers in
   `src/flytetest/planning.py`.
2. Keep `plan_request(...)` unchanged as the current MCP compatibility subset.
3. Build small `WorkflowSpec` and `BindingPlan` previews from registry entries
   and resolver outputs.
4. Add tests covering current showcase prompts plus all new typed planning
   outcomes.
5. Update README, capability maturity notes, and the realtime checklist.

## Validation Steps

- Run planner tests plus compatibility suites.
- Run Python compilation for touched modules and tests.

## Blockers Or Assumptions

- Generated `WorkflowSpec` outputs are metadata-only previews in this
  milestone; they are not persisted or executed yet.
- The typed goal classifier intentionally recognizes a small starting set of
  planning goals rather than claiming broad natural-language coverage.
- The MCP server still uses the older `plan_request(...)` compatibility path
  until a deliberate Milestone 8 migration.
