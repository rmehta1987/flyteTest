# Milestone 9 MCP Spec Cutover

Date: 2026-04-07

Related checklist milestone:
- `docs/realtime_refactor_checklist.md` Milestone 9

## Current State

- `src/flytetest/server.py` still exposes the narrow showcase flow with
  `list_entries`, `plan_request`, and `prompt_and_run`.
- `prompt_and_run(...)` still routes through the old prompt-path planning and
  CLI-oriented execution helpers.
- `src/flytetest/planning.py` already exposes typed-planning previews and saved
  spec generation helpers, but MCP does not yet use them as the primary
  execution path.
- `src/flytetest/spec_artifacts.py` and `src/flytetest/spec_executor.py` exist
  and can support a recipe-first execution model.

## Target State

- The MCP server becomes spec-backed instead of showcase-backed.
- Prompt interpretation happens through `plan_typed_request(...)`.
- Supported plans are frozen into saved `WorkflowSpec` artifacts before
  execution.
- `LocalWorkflowSpecExecutor` executes the saved recipe through explicit local
  handlers.
- `prompt_and_run(...)` remains as a compatibility alias, but it now delegates
  to the recipe flow.
- MCP exposes `prepare_run_recipe(...)` and `run_local_recipe(...)` for
  inspectable, replayable execution.

## Day One Scope

Keep the first cutover intentionally small:

- `ab_initio_annotation_braker3`
- `protein_evidence_alignment`
- `exonerate_align_chunk`

The server can broaden the runnable set later by extending the handler map and
MCP contract after the recipe path is proven.

## Implementation Steps

1. Update `src/flytetest/mcp_contract.py` so the contract reflects the recipe
   flow rather than the old showcase blocklist.
2. Update `src/flytetest/planning.py` so the recipe path is the source of truth
   for supported requests.
3. Add a small handler map in `src/flytetest/server.py` for the day-one
   executable targets.
4. Add `prepare_run_recipe(...)` to persist a frozen artifact under
   `.runtime/specs/`.
5. Add `run_local_recipe(...)` to load and execute a saved artifact directly.
6. Rewrite `_prompt_and_run_impl(...)` so it uses the typed plan, saved
   artifact, and local executor instead of command-string construction.
7. Keep `prompt_and_run(...)` as a compatibility alias around the recipe flow.
8. Update tests for server tool registration, planning behavior, and local spec
   execution.
9. Update README, MCP docs, and capability maturity notes to describe the new
   contract honestly.

## Validation Steps

- Run `python3 -m py_compile` on touched Python files.
- Run `tests/test_planning.py`, `tests/test_server.py`, and
  `tests/test_spec_executor.py`.
- Add focused synthetic tests for the new MCP tools and compatibility alias.
- Confirm the saved artifact round-trip works from `prepare_run_recipe(...)`
  into `run_local_recipe(...)`.

## Blockers or Assumptions

- The first cutover keeps the day-one executable set intentionally small.
- `prompt_and_run(...)` remains available during the migration for compatibility
  while the new recipe tools settle.
- The recipe artifact directory lives under `.runtime/specs/`.
