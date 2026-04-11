# Milestone 23 Protein Evidence Nested Asset Cleanup

Date: 2026-04-10
Status: Proposed

Related checklist milestone:
- `docs/realtime_refactor_checklist.md` Milestone 23

Implementation note:
- This slice should stay limited to the protein-evidence family.
- The top-level `protein_evidence_result_bundle` contract is already acceptable
  and should remain stable.
- The likely cleanup target is the nested Exonerate-specific naming.

## Current State

- `src/flytetest/tasks/protein_evidence.py` emits a reasonable biology-facing
  top-level bundle name, `protein_evidence_result_bundle`.
- Some nested raw-alignment outputs still expose the implementation tool
  directly, for example `raw_exonerate_chunk_results` and
  `concatenated_raw_exonerate`.
- `src/flytetest/types/assets.py` still uses types such as
  `ExonerateChunkAlignmentResult` that may be too tool-specific if another
  protein-to-genome aligner is later added.

## Target State

- The top-level protein-evidence bundle stays stable.
- Nested asset names are made more biology-facing where a stable meaning
  exists.
- Historical manifests remain replayable and truthful.

## Scope

In scope:

- Audit nested Exonerate-specific keys and type names.
- Decide which nested names are worth genericizing.
- Introduce generic sibling names only where a stable biology-facing meaning
  exists.
- Preserve top-level bundle stability and historical replay.
- Add focused tests and doc updates.

Out of scope:

- Renaming the whole protein-evidence workflow family.
- Replacing the current Exonerate implementation.
- Broad genericization of unrelated task families.

## Implementation Steps

1. Audit `src/flytetest/tasks/protein_evidence.py`,
   `src/flytetest/types/assets.py`, and current tests for nested asset usage.
2. Identify which nested names are too Exonerate-specific for future planner
   or manifest reuse.
3. Introduce generic sibling names for those nested assets while keeping the
   current Exonerate names readable.
4. Update emitters and adapters to prefer the generic nested names where
   appropriate.
5. Preserve historical replay of manifests that only use Exonerate-specific
   nested keys.
6. Add tests for nested generic-name round-tripping, legacy manifest loading,
   and current manifest emission.
7. Update README, capability notes, and the checklist once the behavior lands.

## Validation Steps

- Run `python3 -m py_compile` on touched Python files if code changes land.
- Run focused tests:
  - `python3 -m unittest tests.test_protein_evidence`
  - `python3 -m unittest tests.test_planner_types`
- Run `git diff --check`.
- Expand coverage if planner adapters or manifest loaders change.

## Blockers Or Assumptions

- This milestone assumes the top-level protein-evidence bundle should stay
  stable.
- It assumes generic nested names are only worthwhile if they improve planner
  clarity or future tool interchangeability.
- If a nested Exonerate name remains the clearest truthful description, it may
  be reasonable to leave that part unchanged.
