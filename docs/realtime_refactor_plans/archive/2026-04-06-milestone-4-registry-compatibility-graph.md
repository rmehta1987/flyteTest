# Milestone 4 Registry Compatibility Graph

Date: 2026-04-06

Related checklist milestone:
- `docs/realtime_refactor_checklist.md` Milestone 4

## Current State

- `src/flytetest/registry.py` lists current tasks and workflows with names,
  categories, descriptions, inputs, outputs, and tags.
- Existing callers rely on `list_entries()` and `get_entry()`.
- Planner-facing types, normalized specs, and the first local resolver now exist,
  but the registry does not yet describe planner input/output types or reusable
  workflow status.

## Target State

- Registry entries include additive compatibility metadata:
  - biological stage
  - accepted planner types
  - produced planner types
  - reusable reference workflow status
  - execution defaults
  - supported execution profiles
  - runtime image policy
  - synthesis eligibility
  - composition constraints
- Current listing and lookup helpers keep their existing behavior.
- Current workflow entries are backfilled with richer metadata first.

## Implementation Steps

1. Add small registry metadata dataclasses while preserving `RegistryEntry`.
2. Add default metadata for entries that have not yet been backfilled.
3. Backfill the currently implemented workflow entries with richer metadata.
4. Add tests proving old listing behavior still works and workflow metadata is
   available through the new fields.
5. Update README, capability maturity notes, and the realtime checklist.

## Validation Steps

- Run the registry tests plus the compatibility suites.
- Run `py_compile` on touched Python files and tests.

## Blockers Or Assumptions

- This milestone seeds the compatibility graph; it does not make the planner
  consume the richer metadata yet.
- Task-level metadata can continue using defaults unless a task is needed as a
  reusable compatibility edge in a later milestone.
