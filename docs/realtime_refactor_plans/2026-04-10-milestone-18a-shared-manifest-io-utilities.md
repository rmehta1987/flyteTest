# Milestone 18a Shared Manifest IO Utilities

Date: 2026-04-10
Status: Proposed

Related checklist milestone:
- `docs/realtime_refactor_checklist.md` Milestone 18a

Implementation note:
- This slice is intentionally mechanical.
- It should extract the repeated manifest JSON and deterministic file-copy
  helpers used across task modules without changing manifest semantics.

## Current State

- Many task modules currently duplicate the same private helpers:
  - `_as_json_compatible`
  - `_write_json` / `_read_json`
  - `_copy_file` / `_copy_tree`
- The repeated code appears in modules such as:
  - `src/flytetest/tasks/eggnog.py`
  - `src/flytetest/tasks/functional.py`
  - `src/flytetest/tasks/pasa.py`
  - `src/flytetest/tasks/filtering.py`

## Target State

- A shared manifest helper module exists and is used by the most duplicated
  task modules.
- Current `run_manifest.json` contracts remain readable and truthful.
- The refactor does not change task behavior, output paths, or manifest keys.

## Scope

In scope:

- Extract JSON-compatible conversion and manifest read/write helpers.
- Extract deterministic copy helpers used by task modules.
- Migrate a small first set of task modules.
- Preserve current manifest semantics.

Out of scope:

- Changing biological task behavior.
- Introducing consensus-specific naming decisions.
- Standardizing every manifest field in one pass.

## Implementation Steps

1. Create a shared manifest utility module.
2. Migrate one or two representative task modules.
3. Keep all manifest shapes and output paths unchanged.
4. Add focused unit tests for the helpers.
5. Update docs and handoff prompts if the helper module changes visible behavior.

## Validation Steps

- Run `python3 -m py_compile` on touched Python files if code changes land.
- Run focused helper tests and any migrated module tests.
- Run `git diff --check`.

## Blockers Or Assumptions

- This slice assumes the shared helper module can stay generic.
- It assumes task-module manifests can keep their current task-specific fields.
