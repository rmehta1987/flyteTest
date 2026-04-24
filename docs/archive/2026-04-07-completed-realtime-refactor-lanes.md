# Completed Realtime Refactor Lanes

Date: 2026-04-07

This document archives the parallel lane content that used to live in
`docs/realtime_refactor_checklist.md`.

The lanes are complete and no longer active coordination tracks. They are kept
here for historical context only.

## Lane A: Docs And Contracts

Status: Complete

### Tasks

- [x] Keep `README.md`, `DESIGN.md`, `docs/capability_maturity.md`, registry
      descriptions, and handoff prompts aligned with each landed milestone.
- [x] Update scope language only after the corresponding code or schema work is
      real.
- [x] Maintain a short implemented-now versus target-state distinction
      throughout the docs.
- [x] Add links to any new tracking or handoff docs where discoverability is
      useful.

### Lane A implementation note

- `README.md`, `DESIGN.md`, and `docs/capability_maturity.md` now describe the
  landed planner type, resolver, registry compatibility metadata, typed planner,
  saved spec artifact, local spec executor, and MCP typed-planning preview
  layers.
- Scope language distinguishes current additive behavior from deferred remote
  lookup, broad automatic Flyte workflow loading, and general task synthesis.
- README links the realtime checklist, handoff prompt, plan workspace, and
  capability maturity snapshot.

### Acceptance evidence

- Documentation diff stays aligned with the changed code
- No planned behavior is described as already shipped

## Lane B: Test Scaffolding And Fixtures

Status: Complete

### Tasks

- [x] Add planner, registry, resolver, spec, and executor tests as each seam
      lands.
- [x] Preserve current `tests/test_planning.py`, `tests/test_registry.py`, and
      `tests/test_server.py` expectations unless intentionally superseded.
- [x] Add synthetic tests before relying on real tool execution.
- [x] Keep test reporting explicit about what was verified directly,
      synthetically, or not verified due to missing tools.

### Lane B implementation note

- Planner, registry, resolver, spec, saved artifact, local executor, MCP server,
  planner type, and compatibility export tests now cover the realtime layers.
- Synthetic tests cover resolver manifests, saved artifacts, local spec
  execution through fake registered handlers, and MCP response compatibility
  without requiring external bioinformatics tools.

### Acceptance evidence

- New tests land with each milestone
- Test handoffs separate direct, synthetic, and unverified coverage

## Lane C: Reference Workflow Metadata Backfill

Status: Complete

### Tasks

- [x] Mark current implemented workflows as reusable or non-reusable reference
      stages in the richer registry metadata.
- [x] Backfill biological stage, accepted planner types, produced planner types,
      and composition constraints for current workflows.
- [x] Do not alter runnable workflow semantics during metadata backfill.

### Lane C implementation note

- `src/flytetest/registry.py` backfills current workflow entries with
  compatibility metadata while preserving existing entry names, categories,
  inputs, outputs, tags, `list_entries()`, and `get_entry()` behavior.
- `rnaseq_qc_quant` is deliberately marked as reusable but producing no
  genome-annotation planner type because it remains a standalone legacy QC
  branch.

### Acceptance evidence

- Registry metadata for current workflows is richer and consistent
- Existing workflow tests continue to pass
