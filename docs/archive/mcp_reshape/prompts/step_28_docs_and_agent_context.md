Use this prompt when starting Step 28 or when handing it off to another session.

```text
You are continuing the FLyteTest scientist-centered MCP surface reshape under the rules in:

- /home/rmeht/Projects/flyteTest/AGENTS.md
- /home/rmeht/Projects/flyteTest/DESIGN.md
- /home/rmeht/Projects/flyteTest/docs/mcp_reshape/checklist.md
- /home/rmeht/Projects/flyteTest/docs/mcp_reshape/mcp_reshape_plan.md  (§14, §15 — documentation refresh)

Context:

- This is Step 28. Depends on Steps 21-27 (the code surface is stable;
  descriptions are canonical). Refreshes every context-load file that
  downstream Claude sessions and contributors read first. If this step is
  skipped, future sessions propose the old patterns from stale `.codex/`
  guidance.

Key decisions already made (do not re-litigate):

- `.codex/` specialist guides are context-load files, not end-user docs.
  User-facing rewrites (`docs/mcp_showcase.md`, `docs/tutorial_context.md`)
  happen in Step 29.
- Archive superseded milestone plans under
  `docs/realtime_refactor_plans/archive/` per AGENTS.md §Behavior Changes;
  leave active plans in place.
- CHANGELOG entry includes a short before/after migration example for the
  flat-`inputs` → `bindings`+`inputs` reshape.

Task:

1. **Top-level**
   - `AGENTS.md` — add `bundles.py`, `staging.py`, `errors.py`,
     `mcp_replies.py`, `validate_run_recipe` to the Project Structure
     orientation block. Update the Prompt/MCP/Slurm section to mention the
     scientist's experiment loop (`list_entries → list_bundles →
     load_bundle → run_task/run_workflow`) and the preflight staging
     invariant.
   - `CLAUDE.md` — no structural change; verify the @AGENTS.md include
     still pulls updated content.
   - `DESIGN.md` — §6.2: add `list_bundles`, `load_bundle`,
     `validate_run_recipe`; note `prepare_*` are inspect-before-execute
     power tools. Opening: add a sentence that new pipeline families plug
     in without MCP-layer edits. §7.5: reference the preflight staging
     check by name. §6.2 or §7.5: one-line note on the new `recipe_id`
     format (`<YYYYMMDDThhmmss.mmm>Z-<target_name>`, §3h).
   - `CHANGELOG.md` — dated entry covering: heuristic removal, MCP reshape
     (with BC-break call-out), bundles, staging preflight,
     `validate_run_recipe`, `$ref` bindings, decline-to-bundles routing,
     resource-hint handoff docs. Include a short before/after migration
     example for the `inputs` reshape.
   - `README.md` — update "Current Status" to note the experiment loop is
     the primary scientist entrypoint; `prepare_*` are inspect-before-
     execute power-user tools.

2. **`.codex/` specialist guides**
   - `.codex/registry.md` — add an "Adding a Pipeline Family" walkthrough
     (`_<family>.py` + planner types + tasks + workflows + optional
     bundle, nothing else). Link the GATK placeholder as the worked
     example.
   - `.codex/tasks.md` — document `bindings` vs `inputs` split; show how
     `TASK_PARAMETERS` entries map to scalar inputs once typed bindings
     cover the rest.
   - `.codex/workflows.md` — document that workflows receive scalar
     `inputs` only at the MCP boundary and own their internal assembly.
   - `.codex/testing.md` — add patterns for `_check_bundle_availability`
     with `tmp_path`-rooted fixtures (runtime, not import-time — §13);
     testing `$ref` resolution; `$ref` / `$manifest` type-compatibility
     declines (§7); preflight staging findings and the
     `RunReply(execution_status="failed")` reply shape (§8); decline-to-
     bundles shape.
   - `.codex/code-review.md` — add: MCP-layer PRs must not introduce
     family-specific branches; families live in `registry/_<family>.py` +
     `tasks/` + `workflows/` + optional `bundles.py`.
   - `.codex/documentation.md`, `.codex/comments.md` — only touch if a
     grep surfaces stale examples referencing the old flat shape.

3. **`.codex/agent/` role prompts**
   - `.codex/agent/registry.md` — mirror `.codex/registry.md` updates.
   - `.codex/agent/task.md`, `.codex/agent/workflow.md` — reflect new
     run-tool shapes so specialist agents propose bindings/scalar-input
     code, not flat-dict code.
   - `.codex/agent/test.md` — mirror `.codex/testing.md` additions.
   - `.codex/agent/code-review.md` — mirror the MCP-layer-branch-free
     checklist.
   - `.codex/agent/architecture.md` — note the scientist's experiment
     loop and the family-extensibility contract as load-bearing
     constraints; add `mcp_replies.py` and `errors.py` to the MCP
     wire-format + error-translation layer description.

4. **Realtime refactor docs**
   - `docs/realtime_refactor_checklist.md` — tick off items this
     milestone closes; add any items promoted from OOS.
   - `docs/realtime_refactor_milestone_*_submission_prompt.md` — update
     the active milestone's prompt if it references the old MCP surface.
   - Archive the superseded planning doc to
     `docs/realtime_refactor_plans/archive/` if this milestone supersedes
     an M21-era plan.

5. **Docstrings (§15 — touched in-module, not pure-docs)**. If touched
   during prior steps' implementations, confirm they are accurate:
   - `server.py`: `run_task`, `run_workflow`, `list_entries`,
     `list_bundles`, `load_bundle`, `validate_run_recipe`,
     `_entry_payload`, `_scalar_params_for_task`,
     `_collect_named_outputs`, `_execute_run_tool`, `_limitation_reply`,
     `_unsupported_target_reply`.
   - `planning.py`: `plan_typed_request`, `plan_request`.
   - `mcp_contract.py`: module docstring adds cross-reference to
     `mcp_replies.py`.
   - `bundles.py`, `staging.py`, `mcp_replies.py`, `errors.py`: module
     docstrings + per-symbol docstrings.
   - `resolver.py::_materialize_bindings`: expanded to cover the three
     binding forms (§7).
   - `spec_artifacts.py::artifact_from_typed_plan`: notes
     `tool_databases` / `runtime_images` resolution order (§3c) and new
     `recipe_id` format (§3h).
   - `spec_executor.py::SlurmWorkflowSpecExecutor.submit`: notes
     preflight staging check + short-circuit on findings (§8).

Verification:

- `rg -n 'run_task\(|run_workflow\(|plan_typed_request\(|_extract_prompt_paths|_classify_target' docs/ .codex/ AGENTS.md CLAUDE.md DESIGN.md` → zero stale hits.
- `rg -n "inputs\s*=\s*\{" docs/ .codex/` cross-checked against call-site
  snippets — zero stale old-shape executable examples.
- `rg -n '_validate_bundles' docs/ .codex/` → zero hits (§13 rewrite).
- `python -m compileall src/flytetest/` (docstrings parse).

Commit message: "docs: refresh AGENTS/DESIGN/CHANGELOG/.codex for MCP reshape".

Then mark Step 28 Complete in docs/mcp_reshape/checklist.md.
```
