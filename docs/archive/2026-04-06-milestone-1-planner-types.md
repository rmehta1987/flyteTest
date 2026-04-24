# Milestone 1 Planner Types

Date: 2026-04-06

Related checklist milestone:
- `docs/realtime_refactor_checklist.md` Milestone 1

## Current State

- `src/flytetest/types/assets.py` already provides many local-path-centric
  dataclasses for manifests, collectors, and stage-boundary provenance.
- The repo does not yet have a clearly separated planner-facing biology type
  surface with the stable top-level names described in `DESIGN.md`.
- The narrow MCP showcase planner still works with explicit prompt paths and
  should remain unchanged during this milestone.

## Target State

- A stable planner-facing import surface exists under `src/flytetest/` with:
  `ReferenceGenome`, `ReadSet`, `TranscriptEvidenceSet`,
  `ProteinEvidenceSet`, `AnnotationEvidenceSet`, `ConsensusAnnotation`, and
  `QualityAssessmentTarget`.
- Those types serialize and round-trip cleanly for planning-time use.
- Explicit adapters exist from the current lower-level asset layer and from the
  current manifest/result-bundle shapes into the new planner-facing types.
- Current Flyte `File` and `Dir` task signatures remain unchanged.

## Implementation Steps

1. Add a new planner-facing module separate from `src/flytetest/types/` so the
   public planner layer is not conflated with the existing path-centric asset
   catalog.
2. Implement planner-facing dataclasses and planning-time serialization helpers.
3. Add adapter helpers for:
   - current asset dataclasses
   - transcript-evidence manifests
   - protein-evidence manifests and bundles
   - BRAKER3 or pre-EVM evidence manifests/bundles
   - consensus/repeat-filter manifests for downstream QC targets
4. Add synthetic tests that cover conversion and round-trip behavior.
5. Update README and the realtime checklist to describe the layering honestly.

## Validation Steps

- Run focused unit tests for the new planner types and existing planning tests.
- Run `py_compile` on the touched Python files.

## Blockers Or Assumptions

- The milestone should not change `src/flytetest/planning.py` behavior yet.
- The existing `src/flytetest/types/assets.py` dataclasses remain valid as the
  lower-level provenance layer even after the new planner-facing module lands.
