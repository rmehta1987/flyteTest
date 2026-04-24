Use this prompt when starting Step 06 or when handing it off to another session.

```text
You are continuing the FLyteTest scientist-centered MCP surface reshape under the rules in:

- /home/rmeht/Projects/flyteTest/AGENTS.md (hard constraint: never modify frozen artifacts)
- /home/rmeht/Projects/flyteTest/DESIGN.md
- /home/rmeht/Projects/flyteTest/docs/mcp_reshape/checklist.md
- /home/rmeht/Projects/flyteTest/docs/mcp_reshape/mcp_reshape_plan.md  (§8 — WorkflowSpec grows tool_databases)

Context:

- This is Step 06. Field addition on `WorkflowSpec` with a default so existing
  frozen artifacts on disk keep loading. The hard constraint from AGENTS.md is
  that we never rewrite existing frozen artifacts — the read path must cope
  with a missing key by defaulting to an empty dict.

Key decisions already made (do not re-litigate):

- `tool_databases: dict[str, str]` — analogous shape to `runtime_images`:
  `{logical_name: filesystem_path}`. Resolution order mirrors §3c
  (entry defaults → bundle override → explicit kwarg).

Task:

1. Add `tool_databases: dict[str, str] = field(default_factory=dict)` to
   `WorkflowSpec` in `src/flytetest/spec_artifacts.py`.

2. Wire through `artifact_from_typed_plan(plan, ...)` — read from the plan
   (see §3c resolution order; the plan dict already carries the resolved
   value).

3. Round-trip via `save_workflow_spec_artifact` + `load_workflow_spec_artifact`:
   when serializing, include the dict; when loading an old artifact missing
   the key, default to `{}`.

Tests to add (tests/test_spec_artifacts.py):

- Round-trip with `tool_databases={"busco_lineage_dir": "/x/y"}`.
- Load an artifact JSON without the key → `tool_databases == {}` (no raise).
- `artifact_from_typed_plan` with a plan carrying the field populates the
  artifact.

Verification:

- `python -m compileall src/flytetest/spec_artifacts.py`
- `pytest tests/test_spec_artifacts.py`
- `pytest tests/` (no regression from the default-value migration)

Commit message: "spec_artifacts: WorkflowSpec grows tool_databases (read-path BC)".

Then mark Step 06 Complete in docs/mcp_reshape/checklist.md.
```
