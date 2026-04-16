# Milestone 22 TransDecoder Generic Asset Follow-Up

Date: 2026-04-10
Status: Proposed

Related checklist milestone:
- `docs/realtime_refactor_checklist.md` Milestone 22

Implementation note:
- This slice should stay limited to the current TransDecoder-backed coding
  prediction family.
- It should not rename unrelated PASA, protein-evidence, or consensus assets.
- It should preserve historical replay while deciding on a stable
  biology-facing concept for this boundary.

## Current State

- `src/flytetest/tasks/transdecoder.py` still emits tool-branded asset keys
  such as `transdecoder_prediction` and `source_pasa_alignment_assembly`.
- `src/flytetest/types/assets.py` exposes `TransDecoderPredictionResult`, but
  there is not yet a generic sibling type for a broader biology-facing coding
  prediction boundary.
- Planner and manifest work can still function today, but the TransDecoder
  family is a likely future cleanup target if the repo wants planner-facing
  names that are less tool-specific.

## Target State

- The TransDecoder family has an explicit decision for what biology-facing
  concept should represent this stage boundary.
- If a stable biology-facing concept exists, generic sibling types and manifest
  keys are introduced while keeping the TransDecoder-branded names readable.
- Historical manifests remain replayable without in-place rewriting.

## Scope

In scope:

- Audit the current TransDecoder manifest keys, asset types, and adapter usage.
- Decide whether a generic sibling type should be introduced now.
- If yes, add the generic sibling type and prefer it in new manifest emitters.
- Preserve replay compatibility with current TransDecoder-branded manifests.
- Add focused tests and doc updates.

Out of scope:

- Broad renaming of PASA, protein-evidence, or consensus assets.
- Changing the biological stage boundary itself.
- Rewriting historical manifests in place.

## Implementation Steps

1. Audit `src/flytetest/tasks/transdecoder.py`,
   `src/flytetest/types/assets.py`, planner adapters, resolver behavior, and
   current tests for TransDecoder result usage.
2. Decide what biology-facing concept should name this stage boundary:
   coding prediction, ORF prediction, or transcript-derived coding evidence.
3. If a generic sibling type is justified, add it in `types/assets.py` while
   keeping `TransDecoderPredictionResult` readable.
4. Update manifest emitters and adapters to prefer the new generic key while
   still accepting legacy TransDecoder-only keys.
5. Add tests for generic-name round-tripping, legacy manifest loading, and
   current manifest emission.
6. Update README, capability notes, and the checklist once the behavior lands.

## Validation Steps

- Run `python3 -m py_compile` on touched Python files if code changes land.
- Run focused tests:
  - `python3 -m unittest tests.test_transdecoder`
  - `python3 -m unittest tests.test_planner_types`
- Run `git diff --check`.
- Expand coverage if planner adapters or manifest loaders change.

## Blockers Or Assumptions

- This milestone assumes historical manifests must remain replayable.
- It assumes genericization is only worthwhile if the biology-facing concept
  is stable enough to survive future tool variation.
- If that concept is not ready yet, the milestone may land as an explicit
  “not yet” boundary decision plus documentation tightening rather than a code
  rename.
