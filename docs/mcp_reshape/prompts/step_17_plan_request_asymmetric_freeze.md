Use this prompt when starting Step 17 or when handing it off to another session.

```text
You are continuing the FLyteTest scientist-centered MCP surface reshape under the rules in:

- /home/rmeht/Projects/flyteTest/AGENTS.md
- /home/rmeht/Projects/flyteTest/docs/mcp_reshape/checklist.md
- /home/rmeht/Projects/flyteTest/docs/mcp_reshape/mcp_reshape_plan.md  (§3j — plan_request asymmetric freeze)

Context:

- This is Step 17. Depends on Step 02 (PlanSuccess has `artifact_path` +
  `suggested_next_call` + `composition_stages`) and Step 16 (prose heuristics
  gone). Differentiates the two cases `plan_request` handles:
  - Single-entry structured match → do NOT freeze; return
    `suggested_next_call` that re-issues the matching `run_workflow` /
    `run_task` call with structured kwargs.
  - Composition fallback → DO freeze to `artifact_path` so
    `run_local_recipe` / `run_slurm_recipe` have something to execute
    against (composed novel DAGs don't correspond to a single `run_*` call).

Key decisions already made (do not re-litigate):

- Single-entry no-freeze avoids orphaned-artifact churn when the scientist
  commits via `run_workflow` immediately after.
- M15 P2 approval gate: composed DAGs set `requires_user_approval=True` in
  the frozen artifact; `plan_request` surfaces this as a `limitations`
  advisory pointing at `approve_composed_recipe`.

Task:

1. Branch in `plan_typed_request` (or a thin wrapper the `plan_request`
   tool calls): single-entry vs composed.

2. Single-entry branch:
   - Fill `suggested_next_call = {"tool": "run_workflow",
     "kwargs": {...structured kwargs, including source_prompt echo}}`.
   - `artifact_path = ""`, `composition_stages = ()`.

3. Composed branch:
   - Call `artifact_from_typed_plan(...)` + `save_workflow_spec_artifact(...)`.
   - `artifact_path` populated, `composition_stages` lists the assembled
     stage names, `requires_user_approval = True`.
   - `suggested_next_call = {"tool": "approve_composed_recipe",
     "kwargs": {"artifact_path": artifact_path}}`.

4. Both branches return a `PlanSuccess`. Both declines return a `PlanDecline`
   with §10's three recovery channels.

Tests to add (tests/test_planning.py):

- Single-entry NL goal → `artifact_path == ""` AND no file under
  `.runtime/specs/` AND `suggested_next_call["tool"] == "run_workflow"`.
- Composed NL goal → `artifact_path` populated, file exists,
  `requires_user_approval=True`, `suggested_next_call["tool"] ==
  "approve_composed_recipe"`.
- Both-fail NL goal → `PlanDecline` with `suggested_bundles` populated.

Verification:

- `python -m compileall src/flytetest/planning.py`
- `pytest tests/test_planning.py`

Commit message: "planning: plan_request asymmetric freeze (single-entry no-op, composed freeze)".

Then mark Step 17 Complete in docs/mcp_reshape/checklist.md.
```
