Use this prompt when starting Step 10 or when handing it off to another session.

```text
You are continuing the FLyteTest scientist-centered MCP surface reshape under the rules in:

- /home/rmeht/Projects/flyteTest/AGENTS.md
- /home/rmeht/Projects/flyteTest/docs/mcp_reshape/checklist.md
- /home/rmeht/Projects/flyteTest/docs/mcp_reshape/mcp_reshape_plan.md  (§3b — MANIFEST_OUTPUT_KEYS convention)

Context:

- This is Step 10. Mechanical: export a module-level
  `MANIFEST_OUTPUT_KEYS: tuple[str, ...]` on every task module under
  `src/flytetest/tasks/` listing the keys the task writes under
  `manifest["outputs"]`. This is the source of truth that Step 11's
  contract test asserts against.

Task:

1. For each task module under `src/flytetest/tasks/`:
   - Identify `manifest["outputs"]` write sites (usually a dict literal
     immediately before `write_json(...)`).
   - Add `MANIFEST_OUTPUT_KEYS: tuple[str, ...] = ("a", "b", ...)` near the
     top of the module with every key the task writes.
   - Include internal audit keys (BUSCO's `summary_notation`) — extras not
     declared on the registry entry are allowed; Step 11's test only flags
     *missing* keys.

2. Module docstring / neighboring comment explains the role of this constant
   as the registry-manifest contract source of truth.

Tests:

- Step 11 adds the cross-module contract test; no per-task tests here.

Verification:

- `python -m compileall src/flytetest/tasks/`
- `rg -n "^MANIFEST_OUTPUT_KEYS" src/flytetest/tasks/` — one line per task
  module.

Commit message: "tasks: export MANIFEST_OUTPUT_KEYS on every task module".

Then mark Step 10 Complete in docs/mcp_reshape/checklist.md.
```
