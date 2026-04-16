# Milestone 14 Generic Asset Compatibility

Date: 2026-04-08
Status: Complete

Related checklist milestone:
- `docs/realtime_refactor_checklist.md` Milestone 14

Implementation note:
- This slice should introduce generic biology-facing asset names and
  compatibility loaders without breaking replay of older manifests.
- It should prefer additive aliases, adapters, and structured provenance over
  a hard class rename or a manifest rewrite.
- Historical run records should remain readable and truthful.

## Current State

- The current local asset layer still uses vendor-specific or tool-specific
  names in `src/flytetest/types/assets.py`.
- `src/flytetest/planner_adapters.py` and `src/flytetest/resolver.py` already
  understand the current manifest shapes and the planner-facing types they feed
  today.
- Existing `run_manifest.json` files and saved recipes depend on the current
  compatibility names, so a direct rename would be disruptive.
- The roadmap should treat this as a tech-debt cleanup that preserves current
  behavior, not as a format migration that invalidates old records.

## Target State

- Generic biology-facing asset names are available alongside the legacy names.
- Legacy class names remain available as aliases or thin wrappers for backward
  compatibility.
- A `ManifestSerializable` helper or mixin provides consistent `to_dict()` and
  `from_dict()` behavior for asset types that need durable round-tripping.
- Planner adapters and resolver compatibility prefer the generic asset names
  while still accepting older manifest shapes and serialized bindings.
- Tool provenance remains explicit and typed enough to inspect without forcing
  unrelated fields into a loose catch-all structure.

## Scope

In scope:

- Introduce generic asset aliases or sibling types for the current
  vendor-specific biology objects.
- Add compatibility helpers for manifest serialization and deserialization.
- Update planner adapters and resolver compatibility to prefer generic names
  while preserving legacy inputs.
- Add tests that prove old and new asset shapes both load correctly.
- Update docs so the asset-model evolution is described honestly.

Out of scope:

- Rewriting historical manifests in place.
- Breaking current `run_manifest.json` replay behavior.
- Renaming exported compatibility symbols without aliases.
- Broad biological pipeline changes unrelated to the asset model itself.

## Implementation Steps

1. Audit `src/flytetest/types/assets.py`, `src/flytetest/__init__.py`,
   `src/flytetest/planner_adapters.py`, `src/flytetest/resolver.py`, and the
   manifest-loading tests to map the current asset compatibility surface.
2. Add a compatibility helper or mixin for serialization and deserialization
   of asset dataclasses that need to round-trip through manifests.
3. Introduce generic asset aliases or sibling types, keeping the legacy names
   available for existing callers and manifests.
4. Update planner adapters and resolver compatibility to prefer the generic
   names while still accepting legacy manifest payloads.
5. Add typed provenance metadata where it helps preserve inspectability without
   collapsing everything into an untyped dictionary.
6. Add compatibility tests for legacy manifest replay and generic-name
   round-tripping.
7. Update README, capability maturity notes, and any asset-model references
   once the behavior lands.

## Validation Steps

- Run `python3 -m py_compile` on touched Python files if code changes land.
- Run focused tests:
  - `python3 -m unittest tests.test_resolver`
  - `python3 -m unittest tests.test_planner_adapters`
  - `python3 -m unittest tests.test_spec_executor`
- Run `git diff --check`.
- Expand coverage if the asset model touches shared planner or manifest
  contracts.

## Blockers or Assumptions

- This milestone assumes historical manifests must remain replayable.
- It assumes the existing asset classes can be layered with aliases or
  compatibility wrappers rather than being renamed in place.
- If a generic name conflicts with current exports, the legacy symbol should
  remain as an alias until callers are migrated deliberately.
