# Milestone 24 PASA Refinement Asset Generalization Boundary

Date: 2026-04-10
Status: Proposed

Related checklist milestone:
- `docs/realtime_refactor_checklist.md` Milestone 24

Implementation note:
- This slice is partly a design decision milestone.
- It should decide whether PASA post-EVM refinement needs a generic
  annotation-refinement asset layer at all.
- It should not force a rename if the generic biology-facing boundary is still
  too vague.

## Current State

- `src/flytetest/tasks/pasa.py` emits PASA-specific refinement assets such as:
  - `pasa_gene_model_update_inputs`
  - `pasa_gene_model_update_round`
  - `pasa_gene_model_update_bundle`
- `src/flytetest/types/assets.py` exposes matching PASA-specific types.
- The current implementation is explicitly PASA-backed and truthful, but the
  naming may become too narrow if the planner later wants a broader
  annotation-refinement stage.

## Target State

- The repo has an explicit answer for whether PASA refinement should stay
  PASA-branded or gain a generic annotation-refinement sibling layer.
- If a generic layer is justified, it is introduced compatibly and historical
  manifests remain replayable.
- If a generic layer is not justified yet, the docs and boundary description
  still become explicit and reviewable.

## Scope

In scope:

- Audit the current PASA post-EVM refinement asset surface.
- Decide whether a generic annotation-refinement asset layer is warranted now.
- If yes, introduce generic sibling names compatibly.
- Preserve historical PASA manifest replay.
- Add focused tests and doc updates.

Out of scope:

- Changing the PASA-backed biological workflow itself.
- Broad genericization of unrelated PASA align/assemble assets.
- Renaming for aesthetics alone without a clear planner or boundary benefit.

## Implementation Steps

1. Audit `src/flytetest/tasks/pasa.py`, `src/flytetest/types/assets.py`, and
   current tests for the PASA refinement result family.
2. Decide whether a stable biology-facing “annotation refinement” concept
   exists strongly enough to justify generic sibling names now.
3. If yes, add generic sibling types and keys while keeping the PASA names
   available for replay.
4. Update emitters and adapters to prefer the generic names only when the
   boundary meaning is explicit enough.
5. Preserve replay of historical PASA refinement manifests.
6. Add tests for generic-name round-tripping, legacy manifest loading, and
   current manifest emission when the generic layer is adopted.
7. Update README, capability notes, and the checklist once the behavior lands.

## Validation Steps

- Run `python3 -m py_compile` on touched Python files if code changes land.
- Run focused tests:
  - `python3 -m unittest tests.test_pasa_update`
  - `python3 -m unittest tests.test_planner_types`
- Run `git diff --check`.
- Expand coverage if planner adapters or manifest loaders change.

## Blockers Or Assumptions

- This milestone assumes historical manifests must remain replayable.
- It assumes “annotation refinement” may or may not be a useful generic layer
  yet, and that a “not yet” decision is an acceptable milestone outcome.
- It assumes the project should not hide the current truth that the
  implementation is still explicitly PASA-backed.
