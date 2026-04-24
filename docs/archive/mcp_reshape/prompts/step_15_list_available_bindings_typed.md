Use this prompt when starting Step 15 or when handing it off to another session.

```text
You are continuing the FLyteTest scientist-centered MCP surface reshape under the rules in:

- /home/rmeht/Projects/flyteTest/AGENTS.md
- /home/rmeht/Projects/flyteTest/docs/mcp_reshape/checklist.md
- /home/rmeht/Projects/flyteTest/docs/mcp_reshape/mcp_reshape_plan.md  (§3f)

Context:

- This is Step 15. Additive — no BC break. Adds a `typed_bindings` field
  alongside the existing `bindings` field in
  `list_available_bindings`'s reply.

Key decisions already made (do not re-litigate):

- Existing `bindings` field (keyed by scalar parameter name) stays unchanged.
- `typed_bindings` is keyed by planner-type name (from
  `entry.compatibility.accepted_planner_types`). Inner dicts are keyed by
  `Path`-annotated field names discovered via
  `get_type_hints(planner_type)` — NOT by a `_path` naming convention.

Task:

1. Add a helper `_path_fields_for(planner_type)` that returns field names
   whose annotation is `Path` or `Path | None` / `Optional[Path]`.

2. Extend the `list_available_bindings` implementation at
   `server.py:2513` to also populate `typed_bindings` keyed by
   planner-type name, with inner dicts of `field_name -> [candidate_paths]`.

3. The discovery logic for candidate paths is the same as today (scan the
   workspace for matching files); only the grouping key changes.

Tests to add (tests/test_server.py — list_available_bindings block):

- `typed_bindings` keys equal
  `entry.compatibility.accepted_planner_types`.
- Inner dicts match `_path_fields_for(planner_type)` for the registry type.
- An entry with a new planner type (simulate by injecting a synthetic
  registry entry in a fixture) surfaces in `typed_bindings` without
  MCP-layer edits.

Verification:

- `python -m compileall src/flytetest/server.py`
- `pytest tests/test_server.py`

Commit message: "server: list_available_bindings exposes typed_bindings".

Then mark Step 15 Complete in docs/mcp_reshape/checklist.md.
```
