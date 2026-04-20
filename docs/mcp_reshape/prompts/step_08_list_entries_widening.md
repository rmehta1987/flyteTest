Use this prompt when starting Step 08 or when handing it off to another session.

```text
You are continuing the FLyteTest scientist-centered MCP surface reshape under the rules in:

- /home/rmeht/Projects/flyteTest/AGENTS.md
- /home/rmeht/Projects/flyteTest/DESIGN.md
- /home/rmeht/Projects/flyteTest/docs/mcp_reshape/checklist.md
- /home/rmeht/Projects/flyteTest/docs/mcp_reshape/mcp_reshape_plan.md  (§1 — list_entries widening)

Context:

- This is Step 08. Reshape `list_entries` + `_entry_payload` so the catalog
  reads as a pipeline map. This changes the reply shape from
  `{"entries": [...], "server_tools": [...], "limitations": [...]}` to
  `list[dict]`, which is a coordinated BC break per DESIGN §8.7.
- `resource_scope()` and `resource_supported_targets()` still call
  `_supported_entry_payloads()` — decide whether to keep them on the old
  shape (add a thin wrapper that wraps the new list into the old dict) or
  update them to the new shape. Default: keep the resource functions on the
  old shape; the reshape targets the MCP tool only.

Key decisions already made (do not re-litigate):

- `pipeline_family` is a cosmetic filter layered on top of
  `registry.list_entries(category)`.
- Filter to entries with non-empty `showcase_module` (only entries actually
  wired through the runtime path).

Task:

1. Rewrite `_entry_payload(entry: RegistryEntry) -> dict[str, object]` to
   take a `RegistryEntry` directly (not a name). Return the fields listed in
   §1: `name`, `category`, `description`, `pipeline_family`,
   `pipeline_stage_order`, `biological_stage`, `accepted_planner_types`,
   `produced_planner_types`, `supported_execution_profiles`,
   `slurm_resource_hints`, `local_resource_defaults`, full `inputs` +
   `outputs` InterfaceField lists (pass through `required`), `tags`, and
   the full `execution_defaults` dict (§3c extras ride along).

2. `list_entries(category=None, pipeline_family=None) -> list[dict]`:
   - Call `registry.list_entries(category)`.
   - If `pipeline_family`: filter by it.
   - Filter to `entry.showcase_module` non-empty.
   - Map through `_entry_payload`.
   - Return the list.

3. Update tests to assert the new list shape and the new fields.

4. `resource_scope()` / `resource_supported_targets()` keep their current
   wrapper shape OR migrate cleanly — pick one and apply consistently.

Tests to update (tests/test_server.py):

- `test_list_entries_exposes_only_the_supported_targets` — assert list
  shape; still asserts category coverage.
- `test_list_entries_exposes_slurm_resource_hints_for_slurm_capable_workflows`
  — assert `slurm_resource_hints` still present per entry.
- New tests: category filter returns only tasks (or workflows); pipeline_family
  filter returns only matching entries; non-showcased entries are excluded.

Verification:

- `python -m compileall src/flytetest/server.py`
- `pytest tests/test_server.py`

Commit message: "server: widen list_entries payload + pipeline_family filter".

Then mark Step 08 Complete in docs/mcp_reshape/checklist.md.
```
