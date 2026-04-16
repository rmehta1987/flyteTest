# Milestone 26 Consensus Asset Generalization Boundary

Date: 2026-04-10
Status: Proposed

Related checklist milestone:
- `docs/realtime_refactor_checklist.md` Milestone 25

Implementation note:
- This slice is also partly a design-decision milestone.
- It should decide whether the EVM-prefixed consensus asset family needs a
  generic sibling layer now or should remain explicitly EVM-backed.
- It should not proceed as a casual rename.

## Current State

- `src/flytetest/tasks/consensus.py` emits a structurally consistent EVM-backed
  asset family, including:
  - `evm_transcript_input_bundle`
  - `evm_protein_input_bundle`
  - `evm_prediction_input_bundle`
  - `evm_input_preparation_bundle`
  - `evm_execution_input_bundle`
  - `evm_partition_bundle`
  - `evm_command_set`
  - `evm_consensus_result_bundle`
- `src/flytetest/types/assets.py` exposes matching EVM-prefixed types.
- The current names are truthful and consistent, but they may be too tool-bound
  if the repo later wants a generic consensus-annotation layer.

## Target State

- The repo has an explicit answer for whether it currently needs a generic
  consensus-annotation asset layer.
- If yes, generic sibling names are introduced compatibly and EVM replay stays
  intact.
- If no, the decision is documented clearly so future sessions do not restart
  the same abstraction debate without new justification.

## Scope

In scope:

- Audit the current EVM asset family for planner and manifest usage.
- Decide whether a generic consensus layer is justified now.
- If yes, introduce generic sibling names compatibly.
- Preserve historical EVM manifest replay.
- Add focused tests and doc updates.

Out of scope:

- Changing the implemented EVM workflow behavior itself.
- Pretending the repo already supports a second consensus engine.
- Genericizing the family solely for naming aesthetics.

## Implementation Steps

1. Audit `src/flytetest/tasks/consensus.py`, `src/flytetest/types/assets.py`,
   and current tests for consensus asset usage.
2. Decide whether planner pressure or a future second-engine path justifies a
   generic consensus layer now.
3. If yes, add generic sibling types and manifest keys while keeping current
   EVM names available for replay.
4. Update emitters and adapters to prefer the generic names only when the
   broader stage meaning is explicit enough.
5. Preserve replay of historical EVM manifests and result bundles.
6. Add tests for generic-name round-tripping, legacy manifest loading, and
   current manifest emission when the generic layer is adopted.
7. Update README, capability notes, and the checklist once the behavior lands.

## Validation Steps

- Run `python3 -m py_compile` on touched Python files if code changes land.
- Run focused tests:
  - `python3 -m unittest tests.test_consensus`
  - `python3 -m unittest tests.test_planner_types`
- Run `git diff --check`.
- Expand coverage if planner adapters or manifest loaders change.

## Blockers Or Assumptions

- This milestone assumes the current EVM names are still the truthful source of
  implementation detail today.
- It assumes a generic consensus layer should only be introduced when there is
  concrete value for planning, manifest reuse, or future tool interchange.
- It treats an explicit “not yet” decision as a valid milestone outcome if no
  real generalization pressure exists.
