Use this prompt when starting Step 21 or when handing it off to another session.

Model: Opus recommended — this is the BC break; missteps cascade into Step 22 (symmetric reshape) and the Step 26 call-site sweep.

```text
You are continuing the FLyteTest scientist-centered MCP surface reshape under the rules in:

- /home/rmeht/Projects/flyteTest/AGENTS.md  (hard constraints: freeze before execute; never modify frozen artifacts)
- /home/rmeht/Projects/flyteTest/DESIGN.md  (§8.7 coordinated migration)
- /home/rmeht/Projects/flyteTest/docs/mcp_reshape/checklist.md
- /home/rmeht/Projects/flyteTest/docs/mcp_reshape/mcp_reshape_plan.md  (§2, §3b, §3g, §3i — run_task reshape)

Context:

- This is Step 21. Depends on Steps 01-20 (foundation, registry, resolver,
  planner, wrappers). Reshapes `run_task` from the M21 flat `inputs` shape
  to `bindings + inputs + resources + execution_profile + runtime_images +
  tool_databases + source_prompt + dry_run`. This is the BC break.

Key decisions already made (do not re-litigate):

- Freeze transparently via `artifact_from_typed_plan` +
  `save_workflow_spec_artifact` before execute.
- Return a `RunReply` (asdict at boundary) with named `outputs`,
  `execution_status`, `exit_status`, `recipe_id`, `run_record_path`,
  `artifact_path`.
- Empty `source_prompt` appends a non-fatal advisory to `limitations`.
- Wrap the body in `_execute_run_tool(...)` (Step 19) so typed resolver
  exceptions translate to `PlanDecline`.
- `dry_run=True` executes steps 1-5 of the flow and skips executor dispatch;
  returns `DryRunReply` with the fully-resolved state. The artifact IS
  written to disk so it can be chained to `run_slurm_recipe(artifact_path=...)`.

Task:

1. Rewrite the body at `server.py:995` matching §2 of the master plan.

2. Derive scalar parameters via `_scalar_params_for_task(task_name, bindings)`
   — scalars are TASK_PARAMETERS entries NOT covered by typed bindings.

3. Named outputs via `_collect_named_outputs(entry, run_record_path)`
   (projects `manifest["outputs"]` onto `entry.outputs[*].name`; handles
   required-vs-optional advisories per §3b).

4. Execution status: local run → populate `execution_status` +
   `exit_status` from the run record; slurm submit → `execution_status =
   "success"`, `exit_status = None` (terminal state surfaces via
   monitor_slurm_job).

Tests to add (tests/test_server.py):

- Bundle-spread call succeeds.
- Unknown bindings decline.
- Missing scalar decline.
- Freeze happens: `.runtime/specs/<id>.json` exists.
- Outputs dict keyed by registry (names only, no paths list).
- Empty source_prompt → advisory in limitations.
- dry_run=True → artifact exists, no run_record, returns DryRunReply.
- chained dry_run → run_slurm_recipe(artifact_path=...) executes with
  unchanged artifact bytes.
- Local executor non-zero exit → supported=True, execution_status="failed".

Verification:

- `python -m compileall src/flytetest/server.py`
- `pytest tests/test_server.py`

Commit message: "server: reshape run_task (bindings+inputs+resources; freeze, named outputs, dry_run)".

Then mark Step 21 Complete in docs/mcp_reshape/checklist.md.
```
