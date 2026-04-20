Use this prompt when starting Step 12 or when handing it off to another session.

```text
You are continuing the FLyteTest scientist-centered MCP surface reshape under the rules in:

- /home/rmeht/Projects/flyteTest/AGENTS.md
- /home/rmeht/Projects/flyteTest/DESIGN.md  (§7.5 offline-compute; §6.2 MCP tool surface)
- /home/rmeht/Projects/flyteTest/docs/mcp_reshape/checklist.md
- /home/rmeht/Projects/flyteTest/docs/mcp_reshape/mcp_reshape_plan.md  (§3c — expanded execution_defaults)

Context:

- This is Step 12. `RegistryCompatibilityMetadata.execution_defaults` grows
  four documented optional keys: `runtime_images`, `module_loads`, `env_vars`,
  `tool_databases`. No standalone `environment_profiles.py` module — registry
  is the single source of truth for environment metadata.

Key decisions already made (do not re-litigate):

- Schema-only expansion: no new fields on `RegistryCompatibilityMetadata`.
  The existing `execution_defaults: dict[str, object]` holds the new keys.
- Per-call override surface is narrow: only `runtime_images` and
  `tool_databases` get explicit kwargs on `run_task`/`run_workflow`.
  `module_loads` is already reachable via `resource_request.module_loads`.
  `env_vars` has no per-call kwarg (bundle-level override covers planned
  variation).
- `env_vars` is for non-secret tool configuration only. Credentials stay in
  the MCP server's own environment and inherit via subprocess; no credential
  management in this milestone.

Task:

1. Populate `execution_defaults` on showcased entries where appropriate:
   BRAKER3 annotation, BUSCO QC, Exonerate — add the relevant
   `runtime_images` / `tool_databases` / `module_loads` / `env_vars`
   defaults. Do not invent values: copy from existing bundle seeds or
   explicit scientist-supplied paths.

2. In `src/flytetest/planning.py::plan_typed_request`, implement the
   resolution order per key:
   - `runtime_images`: entry default → bundle override → kwarg.
   - `tool_databases`: entry default → bundle override → kwarg.
   - `module_loads`: entry default → bundle override → `resource_request.module_loads`.
   - `env_vars`: entry default → bundle override.

3. Freeze the resolved values into `WorkflowSpec` (tool_databases uses Step
   06's new field; runtime_images is existing).

Tests to add (tests/test_planning.py):

- Entry-only defaults → frozen values come from the registry.
- Bundle override → bundle wins over entry.
- Kwarg override → kwarg wins over both.
- All layered simultaneously → kwarg wins; absent key falls back to next
  layer.

Verification:

- `python -m compileall src/flytetest/planning.py`
- `pytest tests/test_planning.py`

Commit message: "planning: resolve execution_defaults (entry → bundle → kwarg)".

Then mark Step 12 Complete in docs/mcp_reshape/checklist.md.
```
