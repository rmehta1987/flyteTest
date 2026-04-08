# Realtime Architecture Refactor Checklist

This checklist tracks the incremental refactor required to move FLyteTest
toward the `realtime` architecture described in `DESIGN.md`.

It is intentionally separate from
`docs/refactor_completion_checklist.md`.
That older checklist remains the notes-faithful pipeline milestone gate for the
implemented annotation workflow.
This document tracks platform architecture work only.

Use this file as the canonical shared tracker for the `realtime` refactor.
Future sessions should add new tasks, mark completed tasks, and record partial
progress here until the architecture refactor is complete.

Keep this checklist short and scannable.
It is the quick reference for current status, next unchecked work, compatibility
guardrails, and completion state.
Detailed per-slice implementation plans should live separately under
`docs/realtime_refactor_plans/`.

## Completion Rule

The `realtime` architecture refactor is only complete when:

- current registered workflows still run through `flyte run`
- `flyte_rnaseq_workflow.py` compatibility exports remain intact
- current `run_manifest.json` contracts remain readable and truthful
- the MCP server executes only targets with explicit local handlers and frozen
  recipe artifacts
- docs, registry metadata, planner behavior, and tests stay aligned
- no database-first or storage-first rewrite is introduced as a prerequisite
- dynamic workflow creation remains allowed, but new workflow shapes must be
  represented as typed, reviewable, replayable `WorkflowSpec` / `BindingPlan`
  artifacts or valid registered-stage compositions rather than opaque one-off
  code generation

## Status Labels

- `Not started`
- `In progress`
- `Blocked`
- `Complete`

## Compatibility Guardrails

The refactor must preserve these surfaces throughout:

- `src/flytetest/planning.py`
  Typed recipe planning remains the MCP-facing planning path, while older
  explicit-path helpers stay internal compatibility plumbing for day-one
  targets.
- `src/flytetest/registry.py`
  Current listing helpers stay callable while richer metadata is added.
- `src/flytetest/server.py`
  `prompt_and_run(...)` stays available as a compatibility alias, and recipe
  execution only exposes targets with explicit local handlers.
- `/home/rmeht/Projects/flyteTest/flyte_rnaseq_workflow.py`
  Compatibility exports remain intact.
- Current workflow result bundles and `run_manifest.json` files
  Existing stage contracts remain readable and truthful.

## Current Stop Rule

Do not treat the `realtime` architecture as complete just because new helper
types or modules exist.
Each milestone below must satisfy its acceptance evidence and compatibility
guardrails before later critical-path work can be considered complete.

Short stop-rule note for Milestones 1 through 9:

- do not break the current `plan_request(...)` payload shape or explicit-path
  requirement while richer planning metadata lands
- do not break `list_entries()` / `get_entry()` consumer behavior while the
  registry grows into a compatibility graph
- do not rename the current MCP tools or resource URIs before a deliberate
  migration lands
- do not remove or rename `flyte_rnaseq_workflow.py` exports that current
  `flyte run` usage depends on
- recipe metadata is allowed, but existing result manifests and MCP responses
  must stay readable and truthful
- deterministic execution means reproducible and inspectable plans, not a ban
  on dynamic workflow assembly from prompts

## Plan History Rule

The checklist is the quick-reference source of truth for progress.
When a session creates or materially revises a concrete implementation plan for
one slice or lane:

- keep the checklist concise by recording only status, key tasks, acceptance
  evidence, and risks here
- write the detailed plan as a markdown file under
  `docs/realtime_refactor_plans/`
- move superseded or completed plan revisions into
  `docs/realtime_refactor_plans/archive/`

This keeps the checklist easy to scan while preserving a visible history of how
the refactor plan evolved over time.

## Critical Path

## Milestone 0

Goal: freeze compatibility surfaces and define the refactor stop rules.

Status: Complete

### Done

- [x] `DESIGN.md` now describes the resolver-first, manifest-first,
      compatibility-preserving architecture target.
- [x] The architecture refactor is tracked in a separate checklist rather than
      being merged into the notes-faithful pipeline milestone gate.

### Still required

- [x] Inventory the compatibility-critical interfaces in
      `src/flytetest/planning.py`, `src/flytetest/registry.py`,
      `src/flytetest/server.py`, and `flyte_rnaseq_workflow.py`.
- [x] Record which planner, registry, MCP, and workflow-export behaviors are
      safe to refactor internally versus externally visible and compatibility
      critical.
- [x] Add or confirm acceptance checks for current planner outputs, registry
      listing behavior, server tool names, server resource URIs, and
      compatibility exports.
- [x] Write a short stop-rule note in this checklist for what must not break
      while Milestones 1 through 8 land.
- [x] Establish the plan-history convention by keeping the checklist as the
      quick reference and storing detailed slice plans under
      `docs/realtime_refactor_plans/`.

### Compatibility inventory

- `src/flytetest/planning.py`
  Externally visible:
  `plan_request`, `split_entry_inputs`, `supported_entry_parameters`, the
  current plan payload keys, the explicit-local-path extraction rule, and the
  hard downstream-stage decline behavior used by the MCP showcase.
  Safe internal refactors:
  prompt tokenization, path-matching heuristics, and target-classification
  helpers as long as the current supported-subset behavior and payload contract
  remain intact.
- `src/flytetest/registry.py`
  Externally visible:
  `REGISTRY_ENTRIES`, `list_entries`, `get_entry`, current entry names, and the
  existing `RegistryEntry` / `InterfaceField` metadata fields consumed by docs,
  tests, and the server.
  Safe internal refactors:
  richer metadata, helper utilities, and compatibility-graph internals as long
  as current entry lookup and listing behavior remain unchanged.
- `src/flytetest/server.py`
  Externally visible:
  MCP tool names `list_entries`, `plan_request`, `prompt_and_run`; resource URIs
  under `flytetest://...`; and the additive `result_summary` contract already
  documented in the README and server resources.
  Safe internal refactors:
  command construction helpers, execution plumbing, and additive non-breaking
  response metadata.
- `flyte_rnaseq_workflow.py`
  Externally visible:
  top-level task and workflow exports used by `flyte run`, especially the
  current runnable workflow names and showcase task exports.
  Safe internal refactors:
  import-shim organization, optional-module loading details, and module layout
  changes behind the same export names.

### Acceptance evidence

- Source of truth: `DESIGN.md`
- Compatibility surfaces:
  - `src/flytetest/planning.py`
  - `src/flytetest/registry.py`
  - `src/flytetest/server.py`
  - `flyte_rnaseq_workflow.py`
- Tests:
  - `tests/test_planning.py`
  - `tests/test_registry.py`
  - `tests/test_server.py`
  - `tests/test_compatibility_exports.py`

### Compatibility risks

- Silent drift between current planner output shape and new planning metadata
- Breaking MCP tool names or resource URIs too early
- Breaking `flyte run` by changing compatibility exports indirectly

## Milestone 1

Goal: introduce planner-facing biology types without changing runnable task
signatures.

Status: Complete

### Done

- [x] Define a small stable planner type set:
      `ReferenceGenome`, `ReadSet`, `TranscriptEvidenceSet`,
      `ProteinEvidenceSet`, `AnnotationEvidenceSet`, `ConsensusAnnotation`, and
      `QualityAssessmentTarget`.
- [x] Keep current Flyte `File` and `Dir` task signatures unchanged while the
      planner type layer is introduced.

### Still required

- [x] Decide where the planner-facing biology types live and document how they
      differ from the larger local-path-centric asset catalog.
- [x] Add conversion or adapter rules from current assets and manifests into the
      planner-facing biology types.
- [x] Define explicit criteria for when a new top-level planner type may be
      added.
- [x] Verify the planner-facing types are broad enough to support future
      workflow families, not only the current annotation tools.
- [x] Add synthetic tests that round-trip planner-facing types through
      planning-time serialization or conversion paths.

### Milestone 1 implementation note

- `src/flytetest/planner_types.py`
  Stable planner-facing import surface for the new biology-level dataclasses.
- `src/flytetest/planner_adapters.py`
  Compatibility-safe adapters from current lower-level assets and current
  result-manifest shapes into the planner-facing types.
- `src/flytetest/planning.py`
  The narrow showcase planner remains unchanged in this milestone and is still a
  compatibility subset that works with explicit prompt paths.

### Acceptance evidence

- Type surface lives in a stable import location under `src/flytetest/`
- `tests/test_planning.py` or new type-focused tests cover conversion and
  round-trip behavior
- `README.md` and `DESIGN.md` describe the planner-facing type layer honestly
- Tests:
  - `tests/test_planner_types.py`

### Compatibility risks

- Accidentally replacing runnable task I/O with planner types too early
- Growing a tool-specific type surface instead of a biology-level contract

## Milestone 2

Goal: add normalized architecture specs for planning and replay.

Status: Complete

### Done

- [x] Introduce `TaskSpec`, `WorkflowSpec`, `BindingPlan`,
      `ExecutionProfile`, `ResourceSpec`, `RuntimeImageSpec`, and
      `GeneratedEntityRecord`.

### Still required

- [x] Define a stable module location for the new normalized spec types.
- [x] Keep the new spec types planning-time and metadata-time only for this
      milestone.
- [x] Define serialization expectations for `TaskSpec`, `WorkflowSpec`, and
      `BindingPlan`.
- [x] Verify `WorkflowSpec` can represent:
      registered workflow selection, registered-stage composition, and a saved
      generated workflow artifact.
- [x] Add tests for spec creation and serialization without involving real tool
      execution.

### Milestone 2 implementation note

- `src/flytetest/specs.py`
  Stable normalized spec surface for planning-time and replay-time metadata.
- The spec layer is additive only in this milestone:
  it is not yet persisted as a saved run artifact and it is not yet wired into
  execution.
- `src/flytetest/planning.py`, `src/flytetest/server.py`, and current runnable
  workflows remain unchanged in behavior.

### Acceptance evidence

- New spec module under `src/flytetest/`
- Synthetic tests for serialization and representation
- Design and README language updated only for what is actually implemented
- Tests:
  - `tests/test_specs.py`

### Compatibility risks

- Letting spec definitions imply execution behavior that does not exist yet
- Divergence between spec schema and current registry or planner concepts

## Milestone 3

Goal: add a manifest-backed resolver over explicit bindings and prior outputs.

Status: Complete

### Done

- [x] Define an `AssetResolver` contract that can resolve planner-facing types
      from explicit local inputs, prior `run_manifest.json` files, and
      registered workflow result bundles.

### Still required

- [x] Create a first local manifest-backed resolver implementation.
- [x] Define ambiguity handling and missing-input reporting rules.
- [x] Add adapter logic from current result bundles into resolver outputs.
- [x] Verify the resolver can satisfy at least one current downstream stage from
      a prior result bundle without prompt-contained raw paths.
- [x] Keep database-backed or remote-index-backed resolution explicitly out of
      scope for this milestone.

### Milestone 3 implementation note

- `src/flytetest/resolver.py`
  Defines the `AssetResolver` behavior and the first
  `LocalManifestAssetResolver` implementation.
- Explicit bindings take priority over discovered matches.
- When more than one manifest or result bundle matches, the resolver reports an
  ambiguity instead of guessing.
- Database-backed and remote-backed lookup remain explicitly out of scope.

### Acceptance evidence

- Resolver contract and first implementation under `src/flytetest/`
- Synthetic resolver tests using copied or fake manifests
- At least one resolver test using a real current manifest shape when feasible
- Tests:
  - `tests/test_resolver.py`

### Compatibility risks

- Encoding current manifest quirks as permanent public API
- Mixing storage policy into the resolver contract

## Milestone 4

Goal: evolve the registry into a compatibility graph while preserving current
listing behavior.

Status: Complete

### Done

- [x] Extend registry entries to declare biological stage, accepted planner
      types, produced planner types, reusable stage status, execution defaults,
      and composition constraints.

### Still required

- [x] Preserve current registry listing helpers and current consumer behavior.
- [x] Mark which workflows are reusable reference workflows.
- [x] Backfill richer metadata for the currently implemented workflows.
- [x] Add tests showing current registered workflows can be described in the new
      richer schema without changing executable signatures.
- [x] Keep README and machine-readable registry docs aligned with the real code.

### Milestone 4 implementation note

- `src/flytetest/registry.py`
  Adds `RegistryCompatibilityMetadata` to `RegistryEntry` while preserving
  existing names, categories, inputs, outputs, tags, and listing helpers.
- Current workflow entries are backfilled as reusable reference workflows with
  accepted and produced planner types.
- Task entries keep safe default compatibility metadata unless a later
  milestone needs a specific task as a reusable graph edge.

### Acceptance evidence

- Updated registry schema in `src/flytetest/registry.py`
- Registry tests covering old and new metadata views
- Updated docs that distinguish current static behavior from new compatibility
  metadata where needed
- Tests:
  - `tests/test_registry.py`

### Compatibility risks

- Breaking current `list_entries()` behavior
- Overfitting the compatibility graph to the current annotation pipeline only

## Milestone 5

Goal: upgrade the planner from prompt-path extraction first to typed goal
resolution.

Status: Complete

### Done

- [x] Refactor the planner flow toward:
      prompt -> biological goal -> planner-facing types -> resolver -> registry
      match.

### Still required

- [x] Preserve the current narrow prompt planner behavior as a compatibility
      subset during migration.
- [x] Add planning outcomes for:
      registered workflow, registered-stage composition, saved or generated
      `WorkflowSpec`, and honest decline.
- [x] Add assumption and missing-input reporting at the typed-planning level.
- [x] Verify unsupported biology is rejected rather than invented.
- [x] Add tests covering both the current showcase prompts and new
      typed-planning outcomes.

### Milestone 5 implementation note

- `src/flytetest/planning.py`
  Adds `plan_typed_request(...)` as an additive typed-planning preview while
  leaving the current `plan_request(...)` payload shape unchanged.
- Typed planning now classifies a prompt into a small biology-level goal,
  resolves planner-facing input types through `LocalManifestAssetResolver`,
  matches reviewed registry workflows or stage compositions, and emits
  metadata-only `WorkflowSpec` / `BindingPlan` previews.
- The first typed outcomes cover direct registered workflow selection,
  registered-stage composition, generated `WorkflowSpec` preview, and honest
  decline for unsupported or underspecified biology.
- Generated spec previews are not yet persisted or executed; that remains
  Milestone 6 and Milestone 7 work.

### Acceptance evidence

- Planner tests for both current narrow behavior and richer typed planning
- No regression in current showcase prompt classifications unless intentionally
  documented
- Tests:
  - `tests/test_planning.py`

### Compatibility risks

- Breaking the showcase planner while generalizing it
- Over-coupling prompting to local path extraction again

## Milestone 6

Goal: add saved replayable workflow specs for composed requests.

Status: Complete

### Done

- [x] Define how a composed request becomes a saved `WorkflowSpec` plus
      `BindingPlan`.

### Still required

- [x] Record prompt provenance, assumptions, execution profile, referenced
      registered stages, and replay metadata.
- [x] Keep v1 limited to saved `WorkflowSpec` artifacts rather than general task
      synthesis.
- [x] Add serialization and reload tests for saved specs.
- [x] Verify a composed plan can be reloaded and replayed without re-parsing the
      original prompt.

### Milestone 6 implementation note

- `src/flytetest/spec_artifacts.py`
  Adds the v1 saved artifact format for metadata-only `WorkflowSpec` plus
  `BindingPlan` pairs.
- Successful typed-planning payloads can now be frozen into
  `workflow_spec_artifact.json` and loaded back as typed dataclasses.
- Saved artifacts record prompt provenance, assumptions, runtime requirements,
  referenced registered stages, selected binding metadata, and replay metadata.
- Declined typed plans are not saved as replayable artifacts.
- The artifact layer does not execute workflows and does not generate Python
  task or workflow source.

### Acceptance evidence

- Saved spec artifact format documented in code and docs
- Tests for save, load, and replay metadata
- Tests:
  - `tests/test_spec_artifacts.py`

### Compatibility risks

- Treating transient planner output as if it were replay-safe
- Expanding into code generation prematurely

## Milestone 7

Goal: add a local executor path for saved workflow specs over registered
building blocks.

Status: Complete

### Done

- [x] Implement a local executor path for saved `WorkflowSpec` artifacts over
      current registered tasks and workflows.

### Still required

- [x] Keep direct workflow execution through current entrypoints untouched.
- [x] Ensure execution uses the resolver and binding plan rather than bypassing
      them.
- [x] Verify one composed workflow can run through the new executor path while
      preserving current manifest semantics.
- [x] Add synthetic tests that exercise local spec execution without requiring
      all external binaries.

### Milestone 7 implementation note

- `src/flytetest/spec_executor.py`
  Adds `LocalWorkflowSpecExecutor`, a local saved-spec executor that runs
  registered nodes through explicit handler functions.
- The executor accepts a saved `SavedWorkflowSpecArtifact` or artifact path,
  resolves planner-facing inputs through `LocalManifestAssetResolver` plus the
  saved `BindingPlan`, validates registered node references, and reports final
  outputs and discovered `run_manifest.json` paths.
- Synthetic tests execute a generated repeat-filtering-plus-BUSCO spec with
  fake registered handlers and manifest-bearing result directories.
- The executor does not replace direct Flyte workflow entrypoints, does not
  auto-import every checked-in Flyte workflow, and does not generate Python
  source.

### Acceptance evidence

- Executor module and tests
- Compatibility checks against current workflows and manifests
- Tests:
  - `tests/test_spec_executor.py`

### Compatibility risks

- Introducing a second execution path that diverges from current workflow
  semantics
- Losing manifest truthfulness for composed runs

## Milestone 8

Goal: rework MCP around the new planner and resolver surface without breaking
current clients prematurely.

Status: Complete

### Done

- [x] Keep current tool names and showcase behavior stable until the new
      planner/resolver surface is ready.

### Still required

- [x] Route `plan_request` and `prompt_and_run` through the new planner and
      resolver once those layers are stable.
- [x] Expand MCP responses with typed planning or spec-preview data only when it
      does not break current clients.
- [x] Verify current showcase prompts still behave correctly.
- [x] Add tests showing broader prompt planning can be layered in without
      breaking the narrow showcase contract.

### Milestone 8 implementation note

- `src/flytetest/server.py`
  Keeps the current MCP tool names and old showcase fields while adding
  `typed_planning` preview data to `plan_request(...)` and
  `prompt_and_run(...)` responses.
- `prompt_and_run(...)` still executes only the existing runnable showcase
  targets through the old explicit-path path.
- Broader typed-planning requests can now surface generated `WorkflowSpec`
  previews through MCP without being executed as showcase targets.
- `result_summary` now includes additive `typed_planning_available` metadata.

### Acceptance evidence

- `tests/test_server.py`
- MCP contract and server docs remain aligned
- Current showcase prompt examples still pass or are intentionally versioned

### Compatibility risks

- Breaking external MCP clients by changing tool names or response shape too
  early
- Letting MCP-specific assumptions leak into planner internals

## Milestone 9

Goal: cut the MCP server over to spec-backed execution while keeping the first
execution set intentionally small and reviewable.

Status: Complete

### Done

- [x] Confirm the day-one executable set for the cutover.
- [x] Confirm the frozen recipe artifact location under `.runtime/specs/`.

### Still required

- [x] Replace the prompt-to-CLI path in `src/flytetest/server.py` with
      recipe-backed execution over `LocalWorkflowSpecExecutor`.
- [x] Keep `prompt_and_run(...)` as a compatibility alias while it delegates to
      the recipe flow.
- [x] Add `prepare_run_recipe(...)` and `run_local_recipe(...)` MCP tools.
- [x] Remove the showcase-only downstream blocklist and hardcoded runnable
      target assumptions from the MCP contract.
- [x] Update planning, server, and executor tests for the new recipe-first MCP
      flow.
- [x] Update README, MCP docs, capability maturity, and any related handoff
      docs to describe the cutover honestly.

### Milestone 9 implementation note

- The first cutover should remain limited to
  `ab_initio_annotation_braker3`, `protein_evidence_alignment`, and
  `exonerate_align_chunk` until the recipe path is proven.
- `prompt_and_run(...)` stays available as a compatibility alias so existing
  clients do not need to change their entrypoint immediately.
- Frozen recipe artifacts are stored under `.runtime/specs/` so they are easy to
  inspect and keep out of the repository root.

### Acceptance evidence

- `docs/realtime_refactor_plans/2026-04-07-milestone-9-mcp-spec-cutover.md`
- `tests/test_server.py`
- `tests/test_planning.py`
- `tests/test_spec_executor.py`
- `README.md`, `docs/mcp_showcase.md`, `docs/capability_maturity.md`, and the
  MCP contract stay aligned with the new behavior

### Compatibility risks

- Breaking existing MCP clients by removing `prompt_and_run` too early
- Exposing more runnable targets than the handler map can actually execute
- Losing the current explicit artifact/replay boundary while moving to the new
  recipe flow

## Verification Matrix

| Area | Minimum verification |
| --- | --- |
| Planner compatibility | `tests/test_planning.py` covers current showcase behavior and new typed outcomes when introduced |
| Registry compatibility | `tests/test_registry.py` covers current listing behavior plus richer metadata |
| MCP compatibility | `tests/test_server.py` preserves current tool/resource behavior until intentionally expanded |
| Compatibility exports | import checks or tests confirm `flyte_rnaseq_workflow.py` still exposes current entrypoints |
| Planner-facing types | synthetic round-trip tests through planning/binding structures |
| Resolver | tests cover explicit local bindings, manifest inputs, and registered bundle resolution |
| Saved specs | tests cover `WorkflowSpec` creation, serialization, reload, and replay metadata |
| Local spec executor | synthetic or lightweight integration test for one composed path over registered stages |
| Docs | `README.md`, `DESIGN.md`, checklist docs, and registry descriptions stay aligned with landed work |

Completed parallel lanes were archived in
[docs/realtime_refactor_plans/archive/2026-04-07-completed-realtime-refactor-lanes.md](/home/rmeht/Projects/flyteTest/docs/realtime_refactor_plans/archive/2026-04-07-completed-realtime-refactor-lanes.md).

## Handoff Instructions

When handing this work to another session or a sub-agent:

- read `AGENTS.md`, `DESIGN.md`, this checklist, and the relevant `.codex`
  guides first
- if the work was delegated by role, read the matching guide under
  `.codex/agent/`
- pick the next unchecked item on the critical path unless explicitly assigned a
  parallel lane
- if that item is completed cleanly and the next critical-path item is a small
  safe continuation, keep going in the same session instead of stopping after a
  single checkbox
- stop when blocked, when a compatibility guardrail would be at risk, or when
  the next step would force a larger risky batch that should be split
- if you create or materially revise a detailed implementation plan for the
  slice, store it under `docs/realtime_refactor_plans/` and archive superseded
  revisions under `docs/realtime_refactor_plans/archive/`
- preserve current workflow and MCP compatibility surfaces while landing the
  chosen task
- update docs and tests whenever a checklist item lands
- report back with:
  - checklist item(s) completed
  - files changed
  - validation run
  - current checklist status
  - remaining blockers or assumptions

The companion handoff prompt for this checklist lives in
`docs/realtime_refactor_submission_prompt.md`.
