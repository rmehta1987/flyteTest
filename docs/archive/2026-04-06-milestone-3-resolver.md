# Milestone 3 Resolver

Date: 2026-04-06

Related checklist milestone:
- `docs/realtime_refactor_checklist.md` Milestone 3

## Current State

- The repo already had planner-facing biology types and normalized spec types,
  but no actual resolver layer over explicit bindings, manifests, or result
  bundle objects.
- The prompt planner and MCP showcase still depend on explicit local file paths
  written directly in prompts.

## Target State

- A resolver module exists under `src/flytetest/` with:
  - an `AssetResolver` behavior definition
  - a first `LocalManifestAssetResolver` implementation
- The resolver can read:
  - explicit local bindings
  - local `run_manifest.json` files or result directories
  - current result-bundle objects from registered workflows
- The resolver reports:
  - resolved
  - ambiguous
  - missing
  outcomes without guessing

## Implementation Steps

1. Expose `reference_genome_from_manifest(...)` from the planner adapter layer
   so the resolver can reuse current manifest-to-type conversion logic.
2. Add `src/flytetest/resolver.py` with:
   - source metadata types
   - resolution candidate/result types
   - `AssetResolver`
   - `LocalManifestAssetResolver`
3. Encode simple first-version rules:
   - explicit bindings win
   - one discovered candidate resolves
   - multiple discovered candidates are ambiguous
   - zero discovered candidates are missing
4. Add resolver tests covering explicit bindings, manifest-backed resolution,
   ambiguity, missing cases, bundle-backed resolution, and a downstream QC
   target recovered from a prior repeat-filter manifest.
5. Update README, capability maturity notes, and the realtime checklist.

## Validation Steps

- Run:
  `.venv/bin/python -m unittest tests.test_resolver tests.test_specs tests.test_planner_types tests.test_planning tests.test_registry tests.test_server tests.test_compatibility_exports`
- Run:
  `.venv/bin/python -m py_compile src/flytetest/resolver.py src/flytetest/planner_adapters.py src/flytetest/planner_types.py src/flytetest/specs.py tests/test_resolver.py tests/test_specs.py tests/test_planner_types.py tests/test_planning.py tests/test_registry.py tests/test_server.py tests/test_compatibility_exports.py`

## Blockers Or Assumptions

- This first resolver is intentionally local and file-based only.
- Database-backed or remote-backed lookup is still out of scope.
- The prompt planner does not consume the resolver yet; that remains later
  checklist work.
