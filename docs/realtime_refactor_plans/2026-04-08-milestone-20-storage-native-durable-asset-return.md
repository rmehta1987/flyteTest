# Milestone 20 Storage-Native Durable Asset Return

Date: 2026-04-08
Status: Proposed

Related checklist milestone:
- `docs/realtime_refactor_checklist.md` Milestone 20

Implementation note:
- This slice should make workflow outputs durable and reusable as asset
  references without introducing a database-first architecture.
- It should stay manifest-driven and filesystem-backed in its first version.
- Existing replay paths and legacy filesystem outputs should remain valid.

## Current State

- The repo already emits local result bundles and manifests with deterministic
  paths.
- There is no content-addressed object store or metadata-indexed asset layer
  yet.
- Historical manifests still point at filesystem paths, so any durable asset
  reference model has to be additive.

## Target State

- Workflow outputs can be represented as durable asset references with stable
  identifiers.
- Manifests can carry durable references where appropriate while keeping the
  old path-based fields readable.
- Downstream runs can consume prior outputs without depending on fragile local
  paths alone.
- The first implementation remains filesystem-backed and manifest-driven
  rather than database-first.

## Scope

In scope:

- Define a durable asset reference model for outputs.
- Persist or index outputs so they can be reloaded after the local run
  directory is gone.
- Update manifests to carry durable asset references where appropriate.
- Add tests for asset lookup, replay, and downstream reuse.
- Keep legacy manifest paths working during the migration.

Out of scope:

- Database-first storage.
- Breaking current result-bundle replay.
- Changing the biological pipeline itself.
- Generic remote orchestration.

## Implementation Steps

1. Audit `src/flytetest/resolver.py`, `src/flytetest/spec_executor.py`,
   `src/flytetest/spec_artifacts.py`, `src/flytetest/types/assets.py`, and the
   manifest-loading tests to identify the smallest durable asset surface.
2. Define a stable asset-reference model that can live alongside current path
   fields.
3. Update manifest writing so durable references are captured without removing
   legacy path-based compatibility.
4. Add lookup and replay support for durable asset references.
5. Add tests for asset lookup, replay, and downstream reuse.
6. Update docs once the behavior lands.

## Validation Steps

- Run `python3 -m py_compile` on touched Python files if code changes land.
- Run focused tests:
  - `python3 -m unittest tests.test_resolver`
  - `python3 -m unittest tests.test_spec_executor`
  - `python3 -m unittest tests.test_planning`
- Run `git diff --check`.
- Expand coverage if the durable asset work touches shared manifest contracts.

## Blockers or Assumptions

- This milestone assumes legacy filesystem path replay must continue to work.
- It assumes the durable asset layer should start as additive metadata rather
  than a new database-backed platform.
- If a durable reference cannot be resolved, the system should report that
  explicitly rather than inventing a fallback.
