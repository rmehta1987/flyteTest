# Milestone 7 Local Spec Executor

Date: 2026-04-07

Related checklist milestone:
- `docs/realtime_refactor_checklist.md` Milestone 7

## Current State

- Milestone 6 saved supported typed plans as metadata-only
  `WorkflowSpec` plus `BindingPlan` artifacts.
- Saved artifacts could be reloaded without re-parsing the original prompt.
- There was no executor path that consumed saved artifacts and ran registered
  building blocks.

## Target State

- Add a local executor path for saved workflow-spec artifacts.
- Use the saved `BindingPlan` plus resolver inputs before executing nodes.
- Validate node references against the registry.
- Run registered building blocks through explicit local handlers so tests can
  exercise the path without external bioinformatics tools.
- Preserve manifest-bearing result-directory outputs in execution reporting.

## Implementation Steps

1. Add `src/flytetest/spec_executor.py` with `LocalWorkflowSpecExecutor`.
2. Resolve planner-facing inputs through `LocalManifestAssetResolver`.
3. Build node inputs from `WorkflowSpec` bindings, upstream outputs, and saved
   runtime bindings.
4. Execute registered node references through caller-provided handlers.
5. Report node outputs, final outputs, assumptions, limitations, and discovered
   `run_manifest.json` paths.
6. Add synthetic tests for a composed repeat-filtering-plus-BUSCO saved spec.
7. Update README, capability maturity notes, and the realtime checklist.

## Validation Steps

- Run executor-focused tests.
- Run planner, registry, resolver, spec, artifact, server, and compatibility
  export suites.
- Compile touched Python modules and tests.

## Blockers Or Assumptions

- The executor does not auto-import or directly run all Flyte workflow
  functions; handlers remain explicit so execution stays reviewable.
- The executor does not replace existing direct `flyte run` entrypoints.
- Synthetic tests preserve manifest-shaped outputs, but they do not validate
  real BUSCO, repeat-filtering, or Flyte execution.
