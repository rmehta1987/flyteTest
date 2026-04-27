# Step 01 — Choose one MCP entry point

## Goal

Decide whether `prompt_and_run` / `plan_request` (LIFECYCLE_TOOLS) or the
`list_entries → list_bundles → load_bundle → run_task / run_workflow`
experiment loop is the canonical scientist start path. Both currently exist
as registered MCP tools and overlap in role.

## Why

`CRITIQUE_REPORT.md` ENG-01: two registered ways to start a run; users
cannot tell which is canonical. `prompt_and_run` is named PRIMARY_TOOL_NAME
in `src/flytetest/mcp_contract.py:43` but is *not* in the documented
experiment loop in `AGENTS.md`.

## Files to read

- `src/flytetest/mcp_contract.py:70–103` — the three tool tuples.
- `src/flytetest/server.py:992` (`plan_request`), `:3492` (`_prompt_and_run_impl`),
  `:3579` (`prompt_and_run`), `:4417–4438` (`mcp.tool` registrations).
- `AGENTS.md` — "Scientist's experiment loop" paragraph.
- `tests/test_server.py` — tests for `plan_request` and `prompt_and_run`
  (search for `def test_plan_request` and `def test_prompt_and_run`).

## Output

A short decision document (in this prompt's reply, or as a comment on the
checklist):

1. Which path is canonical going forward?
2. What evidence supports the choice (telemetry, real client behavior,
   maintainer recall)?
3. What happens to the loser — un-register from `MCP_TOOL_NAMES` (preferred,
   keeps the Python function for tests / scripts) or full deletion?

## Do not

Touch any code in this step. The implementation is step 02.
