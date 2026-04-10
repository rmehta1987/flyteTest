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

Short stop-rule note for Milestones 1 through 20:

- keep `plan_request(...)` on the typed recipe-planning path, and preserve
  structured unsupported responses when inputs cannot be resolved
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
- compatibility-preserving asset aliases are allowed, but historical manifests
  and planner adapters must keep loading and replaying older asset names
- dynamic composition remains registry-constrained, typed, bounded, and
  reviewable before any executor runs it
- Slurm failure recovery should stay frozen-recipe driven and Slurm-specific,
  not broaden into generic remote orchestration
- execution-capable composed DAGs remain gated on Milestone 19 caching and
  resumability, even if Milestone 15 lands earlier as a composition preview

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

### Completed

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

### Completed

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

- `docs/realtime_refactor_plans/archive/2026-04-07-milestone-9-mcp-spec-cutover.md`
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

## Milestone 10

Goal: add explicit MCP recipe input binding and enable BUSCO as the first
post-day-one recipe target.

Status: Complete

### Done

- [x] Confirm BUSCO is the first post-day-one MCP expansion target.
- [x] Confirm the MCP recipe input contract for prior manifests, explicit
      planner bindings, and runtime bindings.

### Still required

- [x] Extend `prepare_run_recipe(...)` and its internal planning path so MCP
      callers can provide prior `run_manifest.json` paths or result directories
      as manifest sources.
- [x] Extend the recipe preparation contract so callers can provide explicit
      planner bindings when they already have a serialized
      `QualityAssessmentTarget`.
- [x] Extend the recipe preparation contract so callers can provide runtime
      bindings such as `busco_lineages_text`, optional `busco_sif`, and
      `busco_cpu` without relying on prompt text alone.
- [x] Enable `annotation_qc_busco` in the MCP local handler map only after its
      manifest source, runtime binding, and result-summary behavior are covered
      by tests.
- [x] Add or update synthetic MCP recipe tests that prepare and run a BUSCO
      recipe through `LocalWorkflowSpecExecutor` with a fake handler.
- [x] Update README, MCP docs, capability maturity notes, and handoff prompts so
      they describe BUSCO MCP support only after the handler lands.

All Milestone 10 checklist items are complete in this slice.

### Milestone 10 implementation note

- This slice widened the input-binding contract before it widened the runnable
  handler map.
- `annotation_qc_busco` consumes a `QualityAssessmentTarget`, usually adapted
  from an `annotation_repeat_filtering` manifest or supplied explicitly by the
  caller.
- BUSCO runtime choices stay explicit and inspectable in the saved recipe:
  at minimum `busco_lineages_text`, optional `busco_sif`, and `busco_cpu`.
- EggNOG and AGAT remain intentionally deferred until the same binding pattern
  is proven on those later stages.

### Acceptance evidence

- `docs/realtime_refactor_plans/archive/2026-04-07-milestone-10-mcp-recipe-input-binding-busco.md`
- `docs/mcp_recipe_binding_busco_submission_prompt.md`
- `tests/test_server.py`
- `tests/test_planning.py`
- `tests/test_spec_executor.py`
- `README.md`, `docs/mcp_showcase.md`, `docs/capability_maturity.md`, and the
  MCP contract stay aligned with whichever BUSCO behavior has actually landed

### Compatibility risks

- Treating any registry entry as MCP-runnable before it has an explicit local
  handler.
- Hiding runtime requirements inside prompt text instead of freezing them into
  the saved recipe.
- Making manifest/result-bundle resolution ambiguous when more than one prior
  result could satisfy `QualityAssessmentTarget`.
- Accidentally widening the MCP surface to EggNOG or AGAT before each workflow
  has explicit input mapping, runtime binding persistence, and synthetic MCP
  coverage.

## Milestone 11

Goal: extend the recipe-backed MCP execution surface to the remaining completed
functional annotation workflows: EggNOG and AGAT.

Status: Completed

### Completed

- [x] Confirm EggNOG and AGAT are exposed as individual runnable MCP targets
      matching the existing `RegistryEntry` workflow boundaries rather than as
      one composed pipeline target.
- [x] Extend the MCP contract with `ShowcaseTarget` entries for
      `annotation_functional_eggnog`, `annotation_postprocess_agat`,
      `annotation_postprocess_agat_conversion`, and
      `annotation_postprocess_agat_cleanup`.
- [x] Extend `_local_node_handlers()` so the four workflows route through the
      explicit workflow handler only after input mapping tests are in place.
- [x] Add or reuse executor helpers that map resolved planner values or
      manifest-derived saved bindings to concrete workflow inputs:
      `repeat_filter_results`, `eggnog_results`, and
      `agat_conversion_results`.
- [x] Extend manifest adapters only where needed so EggNOG and AGAT manifests
      can be resolved without guessing among multiple compatible sources.
- [x] Keep EggNOG and AGAT runtime choices explicit in saved recipes instead of
      relying on prompt text:
      `eggnog_data_dir`, `eggnog_sif`, `eggnog_cpu`, `eggnog_database`,
      `annotation_fasta_path`, and `agat_sif`.
- [x] Add synthetic MCP recipe tests for preparation, saved binding
      persistence, fake-handler execution through `LocalWorkflowSpecExecutor`,
      result summaries, and missing or ambiguous target declines.
- [x] Update README, MCP docs, capability maturity notes, and handoff prompts
      once the implementation lands.

### Milestone 11 implementation note

- Remote object support, database-backed discovery, and broad storage-native
  asset return remain out of scope.
- This milestone reuses the Milestone 10 JSON-friendly input context:
  `manifest_sources`, `explicit_bindings`, and `runtime_bindings`.
- EggNOG consumes a repeat-filter or QC target and maps it to
  `repeat_filter_results`.
- AGAT statistics and conversion consume an EggNOG manifest boundary and map
  it to `eggnog_results`.
- AGAT cleanup consumes an AGAT conversion manifest boundary and maps it
  to `agat_conversion_results`.
- A composed EggNOG-plus-AGAT pipeline target should be a later milestone if the
  project wants that UX.

### Acceptance evidence

- `docs/realtime_refactor_plans/archive/2026-04-08-milestone-11-mcp-eggnog-agat.md`
- `docs/mcp_recipe_binding_eggnog_agat_submission_prompt.md`
- `tests/test_server.py`
- `tests/test_planning.py`
- `tests/test_spec_executor.py`
- README, MCP docs, capability maturity notes, and MCP contract docs stay
  aligned with whichever EggNOG and AGAT behavior has actually landed

### Compatibility risks

- Exposing EggNOG or AGAT in the MCP target list before the executor can build
  their concrete workflow inputs from saved recipe bindings.
- Treating workflow-layer tests as enough without MCP recipe tests.
- Hiding database directories, CPU counts, container image paths, or FASTA
  paths inside natural-language prompt text.
- Adding table2asn, Slurm, or a composed downstream pipeline in the same slice.

## Milestone 12

Goal: make resource requests and execution profiles first-class in the
recipe-backed MCP planning flow.

Status: Complete

### Still required

- [x] Extend typed planning and recipe preparation so explicit resource
      requests become structured fields instead of prompt text.
- [x] Connect registry compatibility metadata and default execution profile
      names to current runnable MCP targets.
- [x] Persist the selected execution profile and resource bindings into saved
      artifacts and local execution results.
- [x] Add synthetic tests for resource-profile selection, persistence, and
      structured declines for incomplete or contradictory resource requests.
- [x] Update README, `docs/mcp_showcase.md`, `docs/capability_maturity.md`,
      and the handoff prompt after the behavior lands.

### Milestone 12 implementation note

- This slice stayed local-first and declarative.
- It prepares the recipe layer for Slurm later without introducing scheduler
  submission.
- `BindingPlan` now carries `execution_profile`, `ResourceSpec`, and
  `RuntimeImageSpec`; the planner, MCP preparation path, saved artifacts, and
  local executor preserve those fields.

### Acceptance evidence

- `docs/realtime_refactor_plans/2026-04-08-milestone-12-resource-aware-recipe-planning.md`
- `docs/realtime_refactor_milestone_12_submission_prompt.md`
- Tests likely to include `tests/test_specs.py`, `tests/test_planning.py`,
  `tests/test_server.py`, `tests/test_spec_executor.py`, and
  `tests/test_registry.py`
- `README.md`, `docs/mcp_showcase.md`, `docs/capability_maturity.md`, and MCP
  contract docs stay aligned with the landed behavior

### Compatibility risks

- Hiding resource requests inside prompt text instead of freezing them into
  the saved recipe
- Adding Slurm submission before explicit resource policy is in place
- Breaking current runnable targets or manifest contracts while plumbing
  resource metadata

## Milestone 13

Goal: turn frozen recipe artifacts into deterministic Slurm submissions with
durable run records.

Status: Complete

### Still required

- [x] Create `SlurmWorkflowSpecExecutor` as a sibling class to
      `LocalWorkflowSpecExecutor`.
- [x] Implement a deterministic `sbatch` translation layer that converts a
      `WorkflowSpec` and its `ExecutionProfile` into a Bash/Slurm script.
- [x] Dispatch the generated script with
      `subprocess.run(["sbatch", script_path], ...)` and persist the emitted
      Slurm Job ID.
- [x] Capture the submitted run in a run-scoped filesystem record under
      `.runtime/runs/` with the job ID, script path, selected execution
      profile, and stdout / stderr paths.
- [x] Expose `run_slurm_recipe` as an MCP endpoint while preserving local
      recipe execution behavior.
- [x] Add synthetic tests for script determinism, `sbatch` parsing, run-record
      persistence, and MCP wiring.
- [x] Keep an optional live smoke test separate from milestone 13 synthesis;
      it submits a tiny script with explicit `rcc-staff` / `caslake` Slurm
      policy and stays skipped unless `sbatch` is available.
- [x] Update README, `docs/mcp_showcase.md`, `docs/capability_maturity.md`,
      and the handoff prompt after the behavior lands.

### Milestone 13 implementation note

- This slice treats filesystem-backed run records as durable state, not
  in-memory MCP state.
- `SlurmWorkflowSpecExecutor` renders a deterministic `sbatch` script from a
  saved `WorkflowSpec` artifact, explicit `BindingPlan.execution_profile`, and
  frozen `ResourceSpec`, then persists the accepted job ID under
  `.runtime/runs/`.
- The MCP surface now exposes `run_slurm_recipe` as an explicit submission
  endpoint while preserving `run_local_recipe` and `prompt_and_run`.
- Scheduler monitoring, cancellation, retry, and resumability remain later
  milestones and are not hidden inside this submission slice.

### Acceptance evidence

- `docs/realtime_refactor_plans/2026-04-08-milestone-13-slurm-executor-engine.md`
- `docs/realtime_refactor_milestone_13_submission_prompt.md`
- Tests:
  - `tests/test_spec_executor.py`
  - `tests/test_server.py`
  - `tests/test_planning.py`
  - `tests/test_registry.py`
- `README.md`, `docs/mcp_showcase.md`, `docs/capability_maturity.md`, and
  `src/flytetest/mcp_contract.py` stay aligned with the landed behavior

### Compatibility risks

- Losing track of running jobs if the MCP process restarts before the run
  record is written
- Colliding run records if the state file is keyed only by recipe spec ID
- Reintroducing prompt-text-based resource inference instead of using the
  frozen execution profile
- Expanding into scheduler monitoring or cancellation before the submission
  and run-record boundary is proven

## Milestone 14

Goal: decouple the biology-facing asset model from vendor-specific names
without breaking manifest replay or planner compatibility.

Status: Complete

### Still required

- [x] Introduce a `ManifestSerializable` compatibility mixin or interface with
      `to_dict()` and `from_dict()` helpers for asset types that need durable
      round-tripping.
- [x] Add generic asset aliases or sibling types for:
      `Braker3ResultBundle` → `AbInitioResultBundle`,
      `StarAlignmentResult` → `RnaSeqAlignmentResult`, and
      `PasaCleanedTranscriptAsset` → `CleanedTranscriptDataset`.
- [x] Update `planner_adapters.py`, resolver compatibility, and local workflow
      outputs to prefer the generic names while still accepting legacy manifest
      shapes.
- [x] Add typed provenance metadata so tool-specific details remain explicit
      without forcing them into an untyped catch-all dictionary.
- [x] Add compatibility tests that prove older manifests still load and replay
      through the generic asset layer.
- [x] Update README, `docs/capability_maturity.md`, and the handoff prompt
      after the behavior lands.

### Milestone 14 implementation note

- This slice is additive and compatibility-preserving, not a hard cutover that
  deletes legacy names.
- `src/flytetest/types/assets.py` now exposes `ManifestSerializable`,
  `AssetToolProvenance`, `AbInitioResultBundle`, `RnaSeqAlignmentResult`, and
  `CleanedTranscriptDataset`.
- The current BRAKER3, STAR, and PASA manifest emitters write generic asset
  keys alongside legacy keys so older manifest shapes remain readable and newer
  records can prefer generic names.
- Resolver bundle matching accepts generic subclasses without losing legacy
  `Braker3ResultBundle` compatibility.
- Historical run records remain replayable without mass-editing JSON
  manifests.

### Acceptance evidence

- `docs/realtime_refactor_plans/2026-04-08-milestone-14-generic-asset-compatibility.md`
- `docs/realtime_refactor_milestone_14_submission_prompt.md`
- Tests:
  - `tests/test_planner_types.py`
  - `tests/test_resolver.py`
  - `tests/test_spec_executor.py`
- `README.md`, `docs/capability_maturity.md`, and compatibility docs stay
  aligned with the landed behavior

### Compatibility risks

- Breaking replay for existing `run_manifest.json` files by renaming asset
  classes too early
- Losing resolver compatibility with older manifest shapes or serialized
  planner bindings
- Hiding tool provenance inside an untyped catch-all field instead of keeping
  it inspectable
- Rewriting historical manifests instead of teaching the loader to understand
  them

## Milestone 19

Goal: support caching and resumability for frozen recipes so interrupted work
can continue without recomputing completed stages.

Status: Not started

### Still required

- [ ] Define cache keys for frozen `WorkflowSpec` artifacts and resolved
      inputs.
- [ ] Decide what resume means for local saved-spec execution versus Slurm
      execution.
- [ ] Persist stage completion state in run records.
- [ ] Re-run only missing or invalidated stages when a run is resumed.
- [ ] Add synthetic tests for cache hits, cache misses, and interrupted-run
      recovery.
- [ ] Update README, `docs/capability_maturity.md`, and the handoff prompt
      after the behavior lands.

### Milestone 19 implementation note

- This slice should keep caching and resumability explicit and inspectable.
- It should key reuse off the frozen recipe, resolved inputs, and relevant
  runtime bindings rather than hidden mutable state.
- Resume behavior should be compatible with both local saved-spec execution
  and the Slurm path that Milestones 13, 16, and 18 establish.
- It is the prerequisite that makes execution-capable composed DAGs safe to
  expose after Milestone 15 has already defined the composition preview.

### Acceptance evidence

- `docs/realtime_refactor_plans/2026-04-08-milestone-19-caching-resumability.md`
- `docs/realtime_refactor_milestone_19_submission_prompt.md`
- Tests likely to include `tests/test_spec_executor.py`, `tests/test_server.py`,
  and any focused cache / resume coverage
- `README.md`, `docs/capability_maturity.md`, and compatibility docs stay
  aligned with the landed behavior

### Compatibility risks

- Reusing stale results when the frozen spec or resolved inputs no longer
  match
- Making resume behavior ambiguous between local and Slurm execution paths
- Hiding stage-completion state in memory instead of the durable run record
- Turning caching into an implicit behavior instead of an explicit replay rule

## Milestone 18

Goal: add Slurm-specific retry and resubmission policy for failed jobs while
preserving the frozen recipe boundary.

Status: Not started

### Still required

- [ ] Define a Slurm failure-classification model in the run-record layer.
- [ ] Distinguish retryable failures from terminal failures using scheduler
      state and exit information.
- [ ] Add a retry policy with an explicit maximum attempt limit.
- [ ] Resubmit failed jobs by reusing the frozen `WorkflowSpec` and recorded
      execution profile.
- [ ] Preserve the original run record while linking retry attempts back to
      the parent job.
- [ ] Expose retry and resubmission operations through the execution layer or
      MCP in a Slurm-specific way.
- [ ] Add synthetic tests for retry classification, resubmission behavior,
      attempt limits, and stale-record handling.

### Milestone 18 implementation note

- This slice should stay Slurm-specific and frozen-recipe driven.
- It should build on the run-record boundary and scheduler reconciliation work
  rather than inventing generic remote orchestration.
- Every retry attempt should remain explicit and inspectable in the run
  history.

### Acceptance evidence

- `docs/realtime_refactor_plans/2026-04-08-milestone-18-slurm-retry-resubmission-policy.md`
- `docs/realtime_refactor_milestone_18_submission_prompt.md`
- Tests likely to include `tests/test_spec_executor.py`, `tests/test_server.py`,
  and any focused retry / resubmission coverage
- `README.md`, `docs/capability_maturity.md`, and compatibility docs stay
  aligned with the landed behavior

### Compatibility risks

- Masking a real infrastructure or biological failure with broad automatic
  retries
- Losing reproducibility if retries drift away from the frozen spec or bound
  execution profile
- Collapsing retry history into a single run record instead of linking explicit
  attempts
- Letting a retry policy broaden into generic remote execution

## Milestone 15

Goal: compose workflow graphs from biological intent while keeping generated
plans typed, bounded, reviewable, and registry-constrained.

Status: Not started

### Still required

- [ ] Add an intent-based planning route in `planning.py` that can produce a
      supported `WorkflowSpec` preview or a structured decline from biological
      intent.
- [ ] Implement registry-constrained graph composition using
      `RegistryEntry.compatibility` so only biologically valid stage edges are
      considered.
- [ ] Bundle multiple sequential `TaskSpec` nodes into a cohesive multi-node
      `WorkflowSpec` with explicit stage boundaries and frozen inputs and
      outputs.
- [ ] Enforce cycle detection, stage-count limits, and structured decline
      reasons for unsupported or ambiguous compositions.
- [ ] Require explicit user approval for the composed recipe preview, with
      execution gated until Milestone 19 lands.
- [ ] Update README, `docs/capability_maturity.md`, and the handoff prompt
      after the behavior lands.

### Milestone 15 implementation note

- This slice should be registry-driven and compatibility-preserving, not an
  unconstrained autonomous graph search.
- It should keep dynamic workflow creation typed, inspectable, and reviewable
  before execution.
- It should only open the composition and approval path; execution-capable
  composed DAGs stay gated on Milestone 19 caching and resumability.
- The approval boundary should sit on the frozen recipe, not on a specific
  backend such as local or Slurm execution.

### Acceptance evidence

- `docs/realtime_refactor_plans/2026-04-08-milestone-15-registry-driven-dynamic-composition.md`
- `docs/realtime_refactor_milestone_15_submission_prompt.md`
- Tests likely to include `tests/test_planning.py`, `tests/test_registry.py`,
  `tests/test_server.py`, and any focused composition / decline coverage
- `README.md`, `docs/capability_maturity.md`, and compatibility docs stay
  aligned with the landed behavior

### Compatibility risks

- Hallucinated or biologically invalid stage paths if composition is not
  constrained by registry compatibility
- Infinite loops or runaway graph expansion if cycle detection and depth
  limits are missing
- Executing a composed recipe before the user has reviewed the frozen graph
- Breaking current supported-path planning while adding the new intent route

## Milestone 16

Goal: reconcile submitted Slurm runs with durable records and expose job
lifecycle operations.

Status: Complete

### Still required

- [x] Add a filesystem-backed Slurm run-record loader and status model for
      submitted jobs.
- [x] Poll scheduler state with `squeue`, `scontrol show job`, and `sacct`
      to reconcile pending, running, completed, failed, and cancelled jobs.
- [x] Record stdout and stderr paths, exit code, and final scheduler state in
      the durable Slurm run record.
- [x] Expose MCP status and cancellation operations for submitted Slurm runs
      while preserving the submission path.
- [x] Add synthetic tests for scheduler reconciliation, cancellation, and
      stale or missing run-record handling.
- [x] Update README, `docs/mcp_showcase.md`, `docs/capability_maturity.md`,
      and the handoff prompt after the behavior lands.

### Milestone 16 implementation note

- This slice builds on the submission and run-record boundary from Milestone 13
  rather than reworking submission itself.
- `SlurmWorkflowSpecExecutor` now loads durable run records, reconciles live or
  accounting state with `squeue`, `scontrol show job`, and `sacct`, and writes
  observed scheduler state, stdout/stderr paths, exit code, and terminal state
  back to the record when available.
- The MCP surface now exposes `monitor_slurm_job` and `cancel_slurm_job`.
- Cancellation records an explicit `scancel` request and leaves final cancelled
  state to later reconciliation rather than inventing scheduler state.

### Acceptance evidence

- `docs/realtime_refactor_plans/2026-04-08-milestone-16-slurm-job-lifecycle-observability.md`
- `docs/realtime_refactor_milestone_16_submission_prompt.md`
- Tests:
  - `tests/test_spec_executor.py`
  - `tests/test_server.py`
- `README.md`, `docs/mcp_showcase.md`, `docs/capability_maturity.md`, and MCP
  contract docs stay aligned with the landed behavior

### Compatibility risks

- Losing consistency between the filesystem run record and live scheduler
  state after MCP restarts
- Missing final stdout, stderr, or exit-state details when a job transitions
  quickly through terminal states
- Surfacing cancellation or monitoring behavior without the durable run record
  being authoritative
- Breaking the submission path while adding lifecycle plumbing

## Milestone 17

Goal: make generic biology-facing asset names the preferred internal surface
while retaining legacy aliases for replay and compatibility.

Status: Not started

### Still required

- [ ] Update planner adapters to emit the generic asset names by default
      wherever the workflow semantics are already known.
- [ ] Update local workflow outputs and manifest-producing helpers to prefer
      the generic asset types while keeping legacy aliases available.
- [ ] Ensure resolver and replay paths still accept historical legacy asset
      names without rewriting manifests.
- [ ] Expand tests to cover both legacy alias loading and generic-name
      round-tripping through planner adapters and workflow outputs.
- [ ] Update README, `docs/capability_maturity.md`, and the handoff prompt
      after the behavior lands.

### Milestone 17 implementation note

- This slice should be a migration and adoption phase, not a compatibility
  break.
- It should build on the aliases and loaders from Milestone 14 instead of
  replacing them.
- Legacy names should stay available for replay, but new internal outputs
  should prefer the generic asset vocabulary.

### Acceptance evidence

- `docs/realtime_refactor_plans/2026-04-08-milestone-17-generic-asset-adoption.md`
- `docs/realtime_refactor_milestone_17_submission_prompt.md`
- Tests likely to include `tests/test_planner_adapters.py`, `tests/test_resolver.py`,
  `tests/test_spec_executor.py`, and any workflow-output coverage that proves
  the generic names are now preferred
- `README.md`, `docs/capability_maturity.md`, and compatibility docs stay
  aligned with the landed behavior

### Compatibility risks

- Breaking manifest replay if legacy aliases are removed too early
- Mixing generic and legacy asset names inconsistently across adapters and
  local workflow outputs
- Losing the ability to load historical run records after the migration
- Updating only the type names without changing the actual emitted internal
  surface

## Milestone 20

Goal: make workflow outputs durable and reusable as asset references without
introducing a database-first architecture.

Status: Not started

### Still required

- [ ] Define a durable asset reference model for workflow outputs.
- [ ] Persist or index outputs so they can be reloaded after the local run
      directory is gone.
- [ ] Update manifests to carry durable asset references where appropriate.
- [ ] Add tests for asset lookup, replay, and downstream reuse.
- [ ] Keep legacy manifest paths working during the migration.
- [ ] Update README, `docs/capability_maturity.md`, and the handoff prompt
      after the behavior lands.

### Milestone 20 implementation note

- This slice should stay manifest-driven and filesystem-backed in its first
  form.
- It should make outputs durable and reusable without becoming a database-first
  asset platform.
- Legacy paths and replay behavior should stay intact while durable references
  are introduced.

### Acceptance evidence

- `docs/realtime_refactor_plans/2026-04-08-milestone-20-storage-native-durable-asset-return.md`
- `docs/realtime_refactor_milestone_20_submission_prompt.md`
- Tests likely to include `tests/test_resolver.py`, `tests/test_spec_executor.py`,
  and any focused asset-reference or replay coverage
- `README.md`, `docs/capability_maturity.md`, and compatibility docs stay
  aligned with the landed behavior

### Compatibility risks

- Breaking replay for older manifests by replacing path-based outputs too
  abruptly
- Turning the first durable asset model into a database-first architecture
- Losing compatibility with current filesystem-backed result bundles
- Making asset references opaque instead of inspectable through manifests

## Milestone 21

Goal: support bounded ad hoc task execution through MCP and local execution
without weakening the recipe-first workflow model.

Status: Not started

### Still required

- [ ] Define which registered tasks are eligible for user-facing ad hoc
      execution and which helper tasks must remain internal-only.
- [ ] Add an explicit task-execution contract that keeps ad hoc task runs
      distinct from saved workflow recipe execution.
- [ ] Support explicit task input binding for scalar values plus local
      `File` / `Dir` and collection-shaped task inputs when those shapes are
      part of the registered task signature.
- [ ] Preserve structured result summaries, explicit assumptions, and stable
      manifest or output-path reporting for ad hoc task runs.
- [ ] Add tests for task eligibility, task input coercion, structured
      declines, and successful direct task execution.
- [ ] Update README, `docs/mcp_showcase.md`, `docs/capability_maturity.md`,
      and the handoff prompt after the behavior lands.

### Milestone 21 implementation note

- This slice should broaden the current narrow task surface deliberately, not
  expose every registered task automatically.
- Ad hoc task execution is for bounded experimentation and stage debugging; it
  does not replace the saved-recipe workflow path for reproducible multi-stage
  runs.
- Eligible tasks should have a clear biological or stage boundary, explicit
  input and output contracts, and result reporting that stays machine-readable.
- Input binding rules should stay explicit and inspectable rather than
  reintroducing hidden shell glue or prompt-only inference.

### Acceptance evidence

- `docs/realtime_refactor_plans/2026-04-10-milestone-21-ad-hoc-task-execution-surface.md`
- `docs/realtime_refactor_milestone_21_submission_prompt.md`
- Tests likely to include `tests/test_server.py`, `tests/test_planning.py`,
  `tests/test_registry.py`, and any focused ad hoc task execution coverage
- `README.md`, `docs/mcp_showcase.md`, `docs/capability_maturity.md`, and MCP
  contract docs stay aligned with the landed behavior

### Compatibility risks

- Exposing internal helper tasks as user-facing execution targets without a
  clear biological boundary
- Letting ad hoc task execution drift into a shadow workflow engine that
  bypasses saved recipe provenance
- Making task input binding inconsistent across scalar, local-path, and
  collection-shaped Flyte I/O inputs
- Reintroducing hidden ad hoc shell behavior instead of explicit direct task
  execution policy

## Verification Matrix

| Area | Minimum verification |
| --- | --- |
| Planner compatibility | `tests/test_planning.py` covers current typed recipe outcomes, structured declines, and any newly introduced resolver inputs |
| Registry compatibility | `tests/test_registry.py` covers current listing behavior plus richer metadata |
| MCP compatibility | `tests/test_server.py` preserves the recipe-backed tool/resource behavior until intentionally expanded |
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
