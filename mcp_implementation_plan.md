# Phase 3 MCP Maturity: Cut Over MCP to Spec-Backed Execution

This plan replaces the current narrow MCP showcase with the primary
spec-backed orchestration path. The goal is to make the MCP server a real
planner-and-executor surface instead of a fixed three-target demo.

The cutover should keep execution transparent and inspectable:

- prompt interpretation happens before execution
- the chosen plan is frozen into a saved `WorkflowSpec` artifact
- execution consumes the saved artifact, not ad hoc CLI arguments
- result payloads continue to expose clear status, assumptions, and outputs

## Goals

1. Make the MCP server plan supported requests from registered workflows and
   workflow compositions, not from a fixed showcase list.
2. Save every supported plan as a replayable spec artifact before execution.
3. Execute saved recipes through `LocalWorkflowSpecExecutor`.
4. Expose a direct recipe workflow for clients that want to prepare, inspect,
   and then run a frozen artifact.
5. Retire the legacy `subprocess.run` prompt-to-CLI path from the MCP server.

## Day One Scope

The first cutover should preserve a small, regression-testable execution set
while the new recipe path lands:

- `ab_initio_annotation_braker3`
- `protein_evidence_alignment`
- `exonerate_align_chunk`

That keeps the migration safe while still proving the new executor can replace
the old CLI backend. Additional workflows can be enabled later by extending the
handler map and contract metadata once the same recipe flow has been verified.

## Scope

This change is focused on `src/flytetest/server.py`, `src/flytetest/planning.py`,
and the contract/docs/tests that describe the MCP surface.

The plan intentionally does not add remote storage, indexed asset discovery, or
Slurm orchestration in the same change. Those remain separate follow-up steps.

## Proposed Changes

### 1. Remove the Narrow Showcase Boundary

#### [MODIFY] `src/flytetest/mcp_contract.py`
- Remove the showcase-specific downstream blocklist constants and the
  showcase-only runnable target list.
- Replace the narrow surface metadata with registry-backed MCP contract data.
- Keep stable result-code definitions, but make them reflect the new
  recipe-first execution path rather than the old showcase limitations.

#### [MODIFY] `src/flytetest/planning.py`
- Remove the showcase-only downstream decline gate from `plan_request`.
- Stop using the three hardcoded `_extract_*` prompt-path helpers as the primary
  MCP planning surface.
- Keep `plan_request` only if it remains useful as a thin compatibility wrapper;
  otherwise replace it with a typed-plan preparation helper that returns the
  chosen `WorkflowSpec` or a structured decline.
- Keep the typed planner as the source of truth for supported prompt-to-spec
  interpretation.

### 2. Add Recipe-First MCP Tools

#### [MODIFY] `src/flytetest/server.py`
Replace the current prompt-to-command execution path with recipe-backed
execution.

- Import `LocalWorkflowSpecExecutor`, `artifact_from_typed_plan`, and
  `save_workflow_spec_artifact`.
- Add a small, explicit handler map for the registered nodes the MCP server is
  prepared to execute locally.
- Update the prompt execution flow:
  1. call `plan_typed_request(prompt)`
  2. if the plan is supported, convert it into a saved spec artifact
  3. persist the artifact to a stable local path
  4. execute the artifact with `LocalWorkflowSpecExecutor`
  5. map `LocalSpecExecutionResult` back into the MCP response payload
- Register the new MCP tools:
  - `prepare_run_recipe(prompt: str) -> dict`
  - `run_local_recipe(artifact_path: str) -> dict`
- Keep `prompt_and_run(prompt: str) -> dict` as a compatibility alias that
  internally calls the recipe preparation and execution flow.
- Keep the response shape explicit so clients can distinguish:
  - supported plan
  - saved artifact location
  - execution attempt
  - execution limitations
  - final outputs

### 3. Make the Server Registry-Driven

#### [MODIFY] `src/flytetest/mcp_contract.py`
- Derive supported MCP entries from the registry and execution handler map.
- Expose only entries the server can actually execute, starting with the
  original three targets on day one.
- Treat workflow and task availability as a server capability decision, not as
  a hardcoded showcase list.

#### [MODIFY] `src/flytetest/server.py`
- Replace the old `list_entries` and resource payloads with registry-backed
  summaries.
- Ensure the MCP resources describe the new recipe flow, the saved artifact
  format, and the current execution constraints.

### 4. Rework Verification

#### [MODIFY] `tests/test_server.py`
- Update tool registration checks for the new recipe tools.
- Update prompt-to-run tests so they assert spec-backed execution, not CLI
  string construction.
- Add tests for `prepare_run_recipe` and `run_local_recipe`.

#### [MODIFY] `tests/test_planning.py`
- Update planning tests to cover typed-plan preparation and supported declines.
- Remove assertions that depend on the showcase-only downstream blocklist.

#### [MODIFY] `tests/test_spec_executor.py`
- Add or extend coverage for the handler map used by the MCP server.
- Verify the server can execute saved artifacts through the executor with
  synthetic handlers.

#### [MODIFY] Docs
- Update `README.md` so the MCP section describes the new recipe-based flow.
- Update `docs/mcp_showcase.md` or replace it with a new MCP surface document
  that describes the post-showcase contract.
- Update `docs/capability_maturity.md` to mark the MCP cutover complete when
  the new path lands.

## Migration Order

1. Land the recipe preparation and saved-artifact flow.
2. Wire the MCP server to execute saved recipes through local handlers.
3. Update tests and docs to the new contract.
4. Remove the old showcase-specific decline paths and target lists.

## Confirmed Decisions

- Day one execution remains limited to `ab_initio_annotation_braker3`,
  `protein_evidence_alignment`, and `exonerate_align_chunk`.
- `prompt_and_run` stays available as a compatibility alias over the new
  recipe flow.
- Frozen recipe artifacts live under `.runtime/specs/` so they are easy to
  inspect and stay out of the repository root.

## Next Expansion Slice

After the day-one cutover, the next planned MCP slice is Milestone 10:
recipe input binding and BUSCO enablement.

The priority is to widen the recipe-preparation input contract before widening
the runnable handler map. MCP clients should be able to pass:

- prior manifest sources, such as `run_manifest.json` paths or result
  directories
- explicit planner bindings, especially serialized `QualityAssessmentTarget`
  payloads
- explicit runtime bindings, starting with `busco_lineages_text`, optional
  `busco_sif`, and `busco_cpu`

Only after those inputs are explicit and tested should the server add
`annotation_qc_busco` to the local handler map as the first post-day-one
target. EggNOG, AGAT, Slurm, and database-backed asset discovery remain
separate follow-up work.

Detailed plan:

- `docs/realtime_refactor_plans/2026-04-07-milestone-10-mcp-recipe-input-binding-busco.md`

Companion handoff prompt:

- `docs/mcp_recipe_binding_busco_submission_prompt.md`

## Verification Plan

### Automated Tests
- `python3 -m py_compile` on touched Python files.
- Update and run `tests/test_server.py`.
- Update and run `tests/test_planning.py`.
- Update and run `tests/test_spec_executor.py`.

### Manual Verification
- Launch the MCP server locally.
- Prepare a recipe from a supported prompt.
- Inspect the saved artifact path.
- Run the saved artifact through `run_local_recipe`.
- Confirm the response includes `LocalSpecExecutionResult`-derived fields and
  no longer depends on literal prompt-to-CLI translation.
