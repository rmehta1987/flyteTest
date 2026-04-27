# Step 02 — Apply the entry-point decision

## Goal

Eliminate the duplication identified in step 01. After this step, exactly
one of the two start paths is the canonical scientist surface; the other is
either un-registered or removed.

## Files to touch (default case: keep the experiment loop, drop `prompt_and_run` / `plan_request` from MCP)

- `src/flytetest/mcp_contract.py:70–103` — remove `"plan_request"` and
  `PRIMARY_TOOL_NAME` from `LIFECYCLE_TOOLS`. Update
  `MCP_TOOL_NAMES` if it doesn't auto-derive.
- `src/flytetest/mcp_contract.py:116+` — remove the corresponding
  `TOOL_DESCRIPTIONS` entries.
- `src/flytetest/server.py:4417–4438` — delete the two `mcp.tool(...)`
  registration lines for `plan_request` and `prompt_and_run`.
  Keep the Python function definitions (`def plan_request`, `def prompt_and_run`)
  intact — internal callers and tests still use them.
- `tests/test_server.py` — any test that asserts the registered tool list
  includes `plan_request` / `prompt_and_run` needs the assertion removed
  (e.g., `test_create_mcp_server_registers_only_the_required_tools` at
  `tests/test_server.py:365`).
- `tests/test_mcp_contract.py` — remove asserts that count
  `LIFECYCLE_TOOLS` length, if any.

## Files to touch (alternative: keep `prompt_and_run`, drop the experiment-loop language)

- `AGENTS.md` — replace the "Scientist's experiment loop" bullet with a
  single line pointing at `prompt_and_run`.
- `README.md` — update the Quick Start.
- `SCIENTIST_GUIDE.md` — update first-run guidance.
- No code changes.

## Acceptance

- `rg 'plan_request|prompt_and_run' src/flytetest/mcp_contract.py` returns
  zero hits (default case), or the AGENTS.md change is present
  (alternative case).
- All 887 tests pass: `PYTHONPATH=src python3 -m pytest tests/ -q`.
- The `CHANGELOG.md` has one dated entry under today's date describing the
  decision and the change.

## Commit

`critique-followup: collapse MCP entry points to <chosen path>`
