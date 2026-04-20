Use this prompt when starting Step 19 or when handing it off to another session.

```text
You are continuing the FLyteTest scientist-centered MCP surface reshape under the rules in:

- /home/rmeht/Projects/flyteTest/AGENTS.md
- /home/rmeht/Projects/flyteTest/docs/mcp_reshape/checklist.md
- /home/rmeht/Projects/flyteTest/docs/mcp_reshape/mcp_reshape_plan.md  (§3g — exception-to-decline translation)

Context:

- This is Step 19. Depends on Step 03 (errors.py), Step 02 (mcp_replies.py),
  Step 13/14 (resolver raises typed exceptions). The run-tool bodies (Step
  21/22) will be wrapped with this helper so scientist-addressable failures
  land in a typed `PlanDecline` with actionable `next_steps` rather than
  opaque FastMCP 500s.

Task:

1. Add `_execute_run_tool(fn, *, target_name, pipeline_family) -> dict`
   in `server.py` matching the code in §3g. Translates each
   `PlannerResolutionError` subclass into a `PlanDecline` with
   exception-type-aware `next_steps`:
   - `UnknownRunIdError` → point at `list_available_bindings`, durable asset
     index.
   - `UnknownOutputNameError` → name the known outputs.
   - `ManifestNotFoundError` / `BindingPathMissingError` → point at
     `list_available_bindings`.

2. Infrastructure / unknown failures propagate (logged per Step 18 ERROR
   path). Do NOT swallow.

3. The wrapper returns `asdict(PlanDecline(...))` for JSON wire compatibility
   — see §3d.

Tests to add (tests/test_server.py — `_execute_run_tool` block):

- Each typed exception → corresponding decline shape with expected
  `next_steps`.
- Non-resolution exception propagates (and emits the ERROR log line per
  Step 18).

Verification:

- `python -m compileall src/flytetest/server.py`
- `pytest tests/test_server.py`

Commit message: "server: add _execute_run_tool wrapper (typed exception to decline)".

Then mark Step 19 Complete in docs/mcp_reshape/checklist.md.
```
