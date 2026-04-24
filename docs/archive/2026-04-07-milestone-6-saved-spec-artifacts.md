# Milestone 6 Saved Spec Artifacts

Date: 2026-04-07

Related checklist milestone:
- `docs/realtime_refactor_checklist.md` Milestone 6

## Current State

- `src/flytetest/specs.py` defines `WorkflowSpec`, `BindingPlan`, and related
  metadata dataclasses.
- `src/flytetest/planning.py` can return typed planning previews with
  metadata-only `WorkflowSpec` and `BindingPlan` payloads.
- Those payloads were still transient and were not saved as replayable
  artifacts.

## Target State

- Add a v1 saved artifact format for supported typed planning results.
- Save `WorkflowSpec` plus `BindingPlan` together with prompt provenance,
  assumptions, runtime requirements, referenced registered stages, and replay
  metadata.
- Reload the saved artifact into typed dataclasses without re-parsing the
  original prompt.
- Keep the artifact metadata-only and avoid adding any executor or generated
  Python code.

## Implementation Steps

1. Add `src/flytetest/spec_artifacts.py` with the saved artifact dataclass and
   save/load helpers.
2. Convert successful typed-planning payloads into saved
   `SavedWorkflowSpecArtifact` records.
3. Write artifacts as stable JSON named `workflow_spec_artifact.json`.
4. Add reload and replay-pair tests.
5. Update README, capability maturity notes, and the realtime checklist.

## Validation Steps

- Run artifact-focused tests.
- Run planner, registry, resolver, spec, server, and compatibility export
  suites.
- Compile touched Python modules and tests.

## Blockers Or Assumptions

- Declined typed plans are not replayable artifacts and are rejected by the
  artifact helper.
- The artifact layer does not execute saved specs; local execution remains
  Milestone 7 work.
- The artifact layer does not synthesize Flyte task or workflow source code.
