Use this prompt when starting Step 24 or when handing it off to another session.

```text
You are continuing the FLyteTest scientist-centered MCP surface reshape under the rules in:

- /home/rmeht/Projects/flyteTest/AGENTS.md
- /home/rmeht/Projects/flyteTest/DESIGN.md  (§6.2 lists validate_run_recipe as part of the MCP surface)
- /home/rmeht/Projects/flyteTest/docs/mcp_reshape/checklist.md
- /home/rmeht/Projects/flyteTest/docs/mcp_reshape/mcp_reshape_plan.md  (§11 — validate_run_recipe)

Context:

- This is Step 24. Depends on Steps 04 (bundles), 05 (staging), 06
  (tool_databases on WorkflowSpec), 14 ($ref binding grammar), 21 + 22 (the
  reshaped run tools). DESIGN §6.2 lists `validate_run_recipe` but it has
  never been implemented; this step adds it.

Key decisions already made (do not re-litigate):

- The tool validates a FROZEN artifact — it takes `artifact_path`, not a
  fresh planning request. Nothing is re-planned; nothing is mutated.
- Validation = (a) every binding resolves through the existing
  `LocalManifestAssetResolver` (including `$ref` via the durable asset
  index), and (b) `check_offline_staging` returns no findings for the
  supplied `shared_fs_roots`.
- This is an INSPECT-BEFORE-EXECUTE tool (§6 reframe) — advertise that way
  in `mcp_contract.py`. It is safe to call as many times as the scientist
  wants; it never submits, never writes, never mutates.

Task:

1. Add `validate_run_recipe(artifact_path: str,
   execution_profile: Literal["local", "slurm"] = "local",
   shared_fs_roots: list[str] | None = None) -> dict` to `server.py`,
   matching the §11 snippet:
   - `load_workflow_spec_artifact(Path(artifact_path))`.
   - Iterate `artifact.bindings` and call `resolver.resolve(binding,
     durable_index=_load_durable_index())` on each; catch exceptions into a
     `findings` list with `kind="binding"`, `key=<binding_name>`, and the
     `reason` message.
   - Run `check_offline_staging(artifact, tuple(Path(r) for r in
     (shared_fs_roots or [])))` and fold each `StagingFinding` into
     `findings` as a dict `{kind, key, path, reason}`.
   - Return `ValidateRecipeReply` (asdict) with `supported=(not findings)`,
     `recipe_id=artifact.recipe_id`, `execution_profile`, and `findings`.

2. Register the tool in `create_mcp_server()` alongside the other tools.

3. Update `mcp_contract.py` tool descriptions so `validate_run_recipe`
   appears in the inspect-before-execute group (§6). (The full reframe
   lands in Step 27 — this step only adds the new entry so
   `list_tools()` is honest.)

Tests to add (tests/test_server.py):

- Happy-path artifact (all bindings resolve, staging clean) returns
  `supported=True` with empty `findings`.
- Artifact with a `$ref` to an unknown run_id returns `supported=False`;
  the corresponding finding has `kind="binding"` and names the offending
  `run_id` in `reason`.
- Artifact with an unreachable container returns `supported=False`; the
  finding has `kind="container"` and the container path.
- Artifact with a missing `tool_databases` path returns a finding with
  `kind="tool_database"`.
- Calling `validate_run_recipe` twice in a row against the same artifact
  yields byte-identical findings (no hidden mutation).
- `execution_profile="local"` without `shared_fs_roots` does not flag
  on-shared-fs issues but DOES flag missing paths.
- `execution_profile="slurm"` with an empty `shared_fs_roots` flags every
  staged path as not-on-shared-fs (no false negatives).

Verification:

- `python -m compileall src/flytetest/server.py`
- `pytest tests/test_server.py`

Commit message: "server: add validate_run_recipe MCP tool (inspect-before-execute)".

Then mark Step 24 Complete in docs/mcp_reshape/checklist.md.
```
