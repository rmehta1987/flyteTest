# Milestone 18c Standard Manifest Envelope

Date: 2026-04-10
Status: Proposed

Related checklist milestone:
- `docs/realtime_refactor_checklist.md` Milestone 18c

Implementation note:
- This slice standardizes the common manifest envelope while keeping task-
  specific fields intact.
- It should stay separate from consensus-asset naming decisions.

## Current State

- Task modules build their manifest dictionaries manually.
- Most manifests share the same conceptual fields:
  - `stage`
  - `assumptions`
  - `inputs`
  - `outputs`
- Some modules also want a stable code-reference or tool-reference pointer in
  the manifest record.

## Target State

- A small helper produces the common manifest envelope.
- Task modules can still add their own fields after the envelope is built.
- The helper does not force a global schema rewrite.

## Scope

In scope:

- Standardize the common manifest shape.
- Decide whether `code_reference` or `tool_ref` should be included.
- Keep task-specific manifest additions possible.
- Preserve current output paths and replay behavior.

Out of scope:

- Changing biological task behavior.
- Renaming consensus assets.
- Forcing every manifest to become identical.

## Implementation Steps

1. Add a thin manifest-envelope helper.
2. Migrate a small representative set of task modules.
3. Preserve current task-specific fields and output paths.
4. Add tests that exercise the common envelope and task-specific extensions.
5. Update docs if the envelope fields become part of the repo contract.

## Validation Steps

- Run `python3 -m py_compile` on touched Python files if code changes land.
- Run focused manifest-shape tests for the migrated modules.
- Run `git diff --check`.

## Blockers Or Assumptions

- This slice assumes the common envelope can remain thin and additive.
- It assumes code-reference metadata can be optional if it would otherwise
  complicate migration.
