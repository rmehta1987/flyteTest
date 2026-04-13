# AGAT Milestone Plan

This plan tracks the next post-EggNOG milestone in FLyteTest.

## Goal

Add an explicit AGAT post-processing boundary after EggNOG functional
annotation, with honest inputs, outputs, and documentation.

## Proposed Scope

- start from the EggNOG-collected annotation bundle
- keep the repeat-filtered GFF3 and EggNOG output bundle available for review
- model AGAT as one or more explicit task boundaries rather than as a generic
  "run AGAT" step
- keep `table2asn` deferred until AGAT is complete

## Current Slice

- cleanup now consumes the AGAT conversion result bundle and writes a cleaned
  GFF3 plus cleanup summary
- keep the statistics, conversion, and cleanup outputs explicit and separate
- keep `table2asn` deferred as a later milestone, not part of AGAT cleanup

## Documentation To Update When Implementation Starts

- `README.md`
- `CHANGELOG.md`
- `docs/refactor_completion_checklist.md`
- `docs/refactor_submission_prompt.md`
- `docs/tool_refs/agat.md`
- `docs/tool_refs/stage_index.md`
- `docs/tutorial_context.md`
- `src/flytetest/registry.py`
- relevant workflow, task, and test modules

## Validation Plan

- add synthetic tests first for command wiring or deterministic transform logic,
  manifest fields, and output naming
- keep the biological boundary explicit in result bundles and registry metadata
- use local fixture-backed validation only if a small deterministic AGAT
  fixture becomes available

## Stop Rule

Do not begin `table2asn` work until the AGAT cleanup implementation has been
validated and the checklist has been updated to say so.
