# Milestone 8 MCP Typed Planning Preview

Date: 2026-04-07

Related checklist milestone:
- `docs/realtime_refactor_checklist.md` Milestone 8

## Current State

- `src/flytetest/server.py` exposed the stable MCP tools:
  `list_entries`, `plan_request`, and `prompt_and_run`.
- The server used the narrow explicit-path showcase planner for runnable
  targets.
- The typed planner, resolver, saved spec artifacts, and local saved-spec
  executor existed, but MCP did not expose typed planning preview data.

## Target State

- Keep current MCP tool names and old showcase response fields stable.
- Add typed planning preview data to `plan_request(...)` and
  `prompt_and_run(...)` responses.
- Keep `prompt_and_run(...)` execution limited to the current runnable showcase
  targets until a later explicit migration broadens execution behavior.
- Expose whether typed planning/spec-preview data is available in
  `result_summary`.

## Implementation Steps

1. Route server-side planning through both the old showcase planner and the
   additive typed planner.
2. Add `typed_planning` metadata to MCP planning and prompt-and-run responses.
3. Add `typed_planning_available` to the prompt-and-run summary contract.
4. Keep direct execution through the existing workflow/task runners.
5. Add server tests for old showcase prompts and broader typed planning
   previews.
6. Update README, capability maturity notes, and the realtime checklist.

## Validation Steps

- Run server tests.
- Run planner, registry, resolver, spec, artifact, executor, and compatibility
  export suites.
- Compile touched Python modules and tests.

## Blockers Or Assumptions

- Broader typed planning previews are visible through MCP, but MCP execution
  still only runs the current showcase targets.
- The server does not yet expose a tool that saves spec artifacts or runs the
  local saved-spec executor directly.
- Typed planning metadata is additive and should not remove old response keys.
