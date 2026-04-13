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
- the currently planned sequencing is `18 -> 18a -> 18b -> 18c -> 15 -> 19`
- Milestone 15 is the composition-preview milestone; Milestone 19 is the later
  caching/resumability milestone that makes execution-capable composed DAGs
  safe to expose

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

Status: Not started; split into core resumability phases plus a separate async
monitoring follow-on

### Core Phase A: Cache Identity And Durable Local Run Records

- [x] 2026-04-12 defined `LOCAL_RUN_RECORD_SCHEMA_VERSION = "local-run-record-v1"`
  as the schema version constant that identifies the initial Phase A record
  shape; schema version is validated on load and rejected when mismatched.
- [x] 2026-04-12 introduced `LocalRunRecord(SpecSerializable)` in
  `src/flytetest/spec_executor.py` as the durable local run-record shape;
  stage state is no longer implicit or in-memory only.
- [x] 2026-04-12 persisted per-node completion state (`node_completion_state`
  dict), output references (`node_results`, `final_outputs`), timestamps
  (`created_at`, `completed_at`), and assumptions in every durable record.
- [x] 2026-04-12 added `save_local_run_record()` and `load_local_run_record()`
  helpers with atomic temp-file writes (same pattern as Slurm M16/18);
  `LocalWorkflowSpecExecutor` writes a record when `run_root` is set.
- [x] 2026-04-12 Define deterministic cache-key inputs from frozen `WorkflowSpec`,
  `BindingPlan`, resolved inputs, runtime bindings, execution profile, and
  runtime-image or resource policy that should invalidate reuse of a prior
  record.  Implemented as `cache_identity_key()` in `spec_executor.py` using
  SHA-256 over normalized JSON; `HANDLER_SCHEMA_VERSION` invalidates stale
  handler outputs; repo-root prefix is stripped for path normalization.
  `cache_identity_key` field added to both `LocalRunRecord` and
  `SlurmRunRecord`; `_validate_resume_identity()` uses the key as the
  authoritative content-level gate for resume acceptance.

### Core Phase B: Local Resume Semantics

- [x] 2026-04-12 Implement resume-from-record for local saved-spec execution using the
  frozen recipe and recorded bindings as the only authority.
  `LocalWorkflowSpecExecutor.execute()` accepts `resume_from: Path | None`;
  prior record is loaded, identity-validated (workflow name + artifact path),
  and used to skip nodes whose `node_completion_state` entry is `True`.
- [x] 2026-04-12 Skip completed nodes and rerun only missing or invalidated stages when
  resuming a local run.  Completed nodes reuse their prior outputs as
  `upstream_outputs` without calling the handler.
- [x] 2026-04-12 Record why a node was reused, rerun, or invalidated so resume behavior
  stays inspectable in the durable run record.  `LocalRunRecord.node_skip_reasons`
  dict records a human-readable reason for each skipped node.
- [x] 2026-04-12 Add focused tests for local cache hits, local cache misses, interrupted
  local runs, and explicit invalidation when the frozen identity changes.
  Six new tests in `LocalResumeTests`: full-skip resume, skip-reason recording,
  workflow-name mismatch rejection, artifact-path mismatch rejection,
  partial-completion re-execution, and node_skip_reasons round-trip.

### Core Phase C: Slurm Parity And Safe Composed Execution

- [x] 2026-04-12 Align the local run-record model with the existing Slurm run-record layer
  so both paths can honor the same explicit replay and resume rules.
  Both `LocalRunRecord` and `SlurmRunRecord` remain separate dataclasses.
  `SlurmRunRecord` gained `local_resume_node_state` and `local_resume_run_id`
  fields.  Both paths share `_validate_resume_identity()` for identity checking.
- [x] 2026-04-12 Extend resumability to Slurm-backed execution without weakening the
  durable run-record boundary from Milestones 13, 16, and 18.
  `SlurmWorkflowSpecExecutor.submit()` accepts `resume_from_local_record: Path | None`;
  when identity-matched, prior local node completion state is recorded in the
  new `SlurmRunRecord`.
- [x] 2026-04-12 Add an explicit approval-acceptance path for composed recipes before
  enabling execution-capable composed DAGs.
  `RecipeApprovalRecord(SpecSerializable)` in `spec_artifacts.py` with
  `save_recipe_approval()`, `load_recipe_approval()`, `check_recipe_approval()`.
  `approve_composed_recipe` MCP tool in `server.py` writes the approval record.
  `run_local_recipe` and `run_slurm_recipe` check approval before executing
  composed (`generated_workflow`) recipes.  `APPROVE_COMPOSED_RECIPE_TOOL_NAME`
  added to `MCP_TOOL_NAMES` in `mcp_contract.py`.
- [x] 2026-04-12 Add tests covering resume behavior across local and Slurm execution,
  plus guardrails that prevent stale or mismatched reuse.
  3 tests in `SlurmResumeFromLocalRecordTests` (Slurm resume with local record,
  identity mismatch rejection, round-trip of new fields).
  10 tests in `tests/test_recipe_approval.py` covering approval round-trip,
  schema validation, missing/approved/rejected/expired checks, MCP tool
  behavior, and run_local_recipe approval gate (block and allow).
- [x] 2026-04-12 Update README, `docs/capability_maturity.md`, and the handoff prompt
  after the core behavior lands.

### Milestone 19 Part B: Async Monitoring Follow-On

- [x] 2026-04-12 created `src/flytetest/slurm_monitor.py` with
  `SlurmPollingConfig`, `batch_query_slurm_job_states()`,
  `discover_active_slurm_run_dirs()`, `reconcile_active_slurm_jobs()`,
  `save_slurm_run_record_locked()`, `load_slurm_run_record_locked()`, and
  `slurm_poll_loop()`; the async loop batches all active job queries into a
  single `squeue`/`sacct` call per cycle rather than one call per job.
- [x] 2026-04-12 introduced `fcntl.flock`-based exclusive file locking via
  companion `.lock` files to guard concurrent writes between the background
  async updater and synchronous MCP handlers that read or update durable run
  records.
- [x] 2026-04-12 attached the background `slurm_poll_loop` to the main MCP
  server event loop inside `_run_stdio_server_async()` using an `anyio`
  task group; the loop is cancelled cleanly when the MCP server shuts down.
- [x] 2026-04-12 configured `SlurmPollingConfig` with a 30-second default
  poll interval, 300-second backoff cap, factor-of-2 exponential backoff, and
  a 30-second per-command timeout; a single scheduler error backs off rather
  than crashing the server.
- [x] 2026-04-12 added `tests/test_slurm_async_monitor.py` with 28 tests
  covering batch squeue/sacct parsing, mocked batch queries, run-directory
  discovery, reconciliation end-to-end, locked round-trips, and async loop
  lifecycle (starts, survives errors, cancels cleanly).
- [x] 2026-04-12 updated `docs/capability_maturity.md` to mark async Slurm
  monitoring as `Current`; removed it from the future-optimization note.
- [x] 2026-04-12 kept continuous async Slurm monitoring separate from the
  core cache and resume work; the module is observational only and does not
  alter submission or retry semantics.

### Milestone 19 implementation note

- This slice should keep caching and resumability explicit and inspectable.
- It should key reuse off the frozen recipe, resolved inputs, and relevant
  runtime bindings rather than hidden mutable state.
- The safest implementation order is: generic local run record first, local
  resume second, Slurm parity third, and async monitoring after that.
- Resume behavior should be compatible with both local saved-spec execution
  and the Slurm path that Milestones 13, 16, and 18 establish, but the first
  implementation pass should not try to solve cross-run reuse, local resume,
  Slurm parity, and async monitoring in one risky batch.
- It follows Milestone 15 rather than preceding it: Milestone 15 defines the
  composition preview and approval boundary first, while Milestone 19 later
  adds the caching and resumability needed to make execution-capable composed
  DAGs safe to expose.

### Open blockers and design questions

- ~~There is not yet a generic durable local run-record model comparable to the
  Slurm run-record layer.~~
  - resolved: Phase A added `LocalRunRecord(SpecSerializable)` (2026-04-12)
- ~~Cache-key normalization still needs an explicit decision for manifest-backed
  inputs, local paths, runtime-image data, and resource-policy overrides.~~
  - resolved: Phase D added `cache_identity_key()` with path normalization, repo-root
    prefix stripping, and frozen JSON hashing (2026-04-12)
- ~~Cache invalidation needs a versioned rule so handler or schema changes do not
  silently reuse stale outputs.~~
  - resolved: Phase D added `HANDLER_SCHEMA_VERSION` constant included in the cache key;
    bumping the version invalidates all prior records (2026-04-12)
- The current composition work added approval gating, but there is still no
  explicit approval-acceptance path for executing a composed recipe.
- Local and Slurm resumability should probably share a common run-state model
  before broader cache reuse is attempted.

### Suggested implementation order

- [ ] Audit `src/flytetest/spec_executor.py`, `src/flytetest/spec_artifacts.py`,
  and `src/flytetest/server.py` for the smallest durable local run-record
  insertion point.
- [ ] Land the local run-record and cache-identity model before adding reuse.
- [ ] Land local resume behavior before extending the same rules to Slurm.
- [ ] Add approval acceptance only after the executor can resume deterministically.
- [ ] Defer async polling until the core resume semantics are stable.

### Acceptance evidence

- `docs/realtime_refactor_plans/2026-04-08-milestone-19-caching-resumability.md`
- `docs/realtime_refactor_plans/2026-04-10-milestone-19-part-b-async-slurm-monitoring.md`
- `docs/realtime_refactor_milestone_19_submission_prompt.md`
- Tests likely to include `tests/test_spec_executor.py`, `tests/test_server.py`,
  and any focused cache / resume coverage
- `README.md`, `docs/capability_maturity.md`, and compatibility docs stay
  aligned with the landed behavior

### Compatibility risks

- Reusing stale results when the frozen spec or resolved inputs no longer
  match
- Making resume behavior ambiguous between local and Slurm execution paths or
  trying to force both paths into one first-pass implementation batch
- Hiding stage-completion state in memory instead of the durable run record
- Turning caching into an implicit behavior instead of an explicit replay rule
- Treating async Slurm monitoring as a prerequisite for the first resumability
  pass instead of a follow-on optimization

## Milestone 18

Goal: add Slurm-specific retry and resubmission policy for failed jobs while
preserving the frozen recipe boundary.

Status: Complete

### Still required

- [x] Define a Slurm failure-classification model in the run-record layer.
- [x] Distinguish retryable failures from terminal failures using scheduler
      state and exit information.
- [x] Add a retry policy with an explicit maximum attempt limit.
- [x] Resubmit failed jobs by reusing the frozen `WorkflowSpec` and recorded
      execution profile.
- [x] Preserve the original run record while linking retry attempts back to
      the parent job.
- [x] Expose retry and resubmission operations through the execution layer or
      MCP in a Slurm-specific way.
- [x] Add synthetic tests for retry classification, resubmission behavior,
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

## Milestone 18a

Goal: extract shared manifest and file-operation helpers so task modules stop
duplicating the same JSON and copy logic.

Status: Complete

### Done

- [x] Add a shared manifest helper module for JSON-compatible conversion,
      read/write, and deterministic file-copy helpers used by task modules.
- [x] Migrate the most duplicated task modules to the shared helpers without
      changing manifest behavior or result-bundle paths.
- [x] Keep current `run_manifest.json` shapes readable and truthful during the
      transition.
- [x] Add focused tests for the shared helpers and one or two migrated call
      sites.
- [x] Update the 18a handoff prompt and this checklist after the behavior
      landed.

### Milestone 18a implementation note

- This slice should stay purely mechanical.
- It should reduce duplication across the task modules without changing any
  biological boundary or manifest semantics.
- If a helper would need consensus-specific naming knowledge, it belongs in a
  later milestone instead of this one.

### Acceptance evidence

- `docs/realtime_refactor_plans/2026-04-10-milestone-18a-shared-manifest-io-utilities.md`
- `docs/realtime_refactor_milestone_18a_submission_prompt.md`
- Tests likely to include `tests/test_spec_executor.py`, `tests/test_server.py`,
  and focused helper-unit coverage
- `README.md`, `docs/capability_maturity.md`, and compatibility docs stay
  aligned with the landed behavior

### Compatibility risks

- Accidentally changing manifest serialization or copied output paths
- Introducing a helper API that is too broad for the current refactor lane
- Mixing non-mechanical naming changes into a pure utility extraction

## Milestone 18b

Goal: centralize GFF3 attribute parsing, formatting, escaping, and common
filtering helpers used by EggNOG and repeat filtering.

Status: Complete

### Done

- [x] Add a shared `gff3` utility module with ordered attribute parsing and
      formatting helpers.
- [x] Centralize escaping and ID / Parent filtering helpers needed by EggNOG
      propagation and repeat-filter cleanup.
- [x] Migrate the current EggNOG and repeat-filter callers while preserving
      exact GFF3 output ordering and behavior.
- [x] Add focused tests that prove the shared helpers preserve the current
      file outputs.
- [x] Update the 18b handoff prompt and this checklist after the behavior
      landed.

### Milestone 18b implementation note

- This slice should stay focused on deterministic GFF3 mechanics.
- It should not change the biological meaning of the current EggNOG or repeat-
  filtering stages.
- The helper representation should be chosen to preserve attribute ordering
  and existing output fidelity.

### Acceptance evidence

- `docs/realtime_refactor_plans/2026-04-10-milestone-18b-shared-gff3-utilities.md`
- `docs/realtime_refactor_milestone_18b_submission_prompt.md`
- Tests likely to include `tests/test_eggnog.py`, `tests/test_repeat_filtering.py`,
  and focused helper-unit coverage
- `README.md`, `docs/capability_maturity.md`, and compatibility docs stay
  aligned with the landed behavior

### Compatibility risks

- Reordering attributes or changing GFF3 escaping semantics
- Creating a helper that silently changes cleanup or annotation propagation
- Conflating generic GFF3 utilities with tool-specific biological policy

## Milestone 18c

Goal: standardize the common manifest envelope so task modules record
assumptions, inputs, outputs, and code references consistently.

Status: Complete

### Done

- [x] Add a small manifest-envelope helper that standardizes the common
      `stage` / `assumptions` / `inputs` / `outputs` shape.
- [x] Decide that `code_reference` and `tool_ref` remain optional in the
      shared envelope so task-specific manifests can opt in without a schema
      rewrite.
- [x] Update task modules to use the helper while preserving their task-
      specific fields and current result-bundle paths.
- [x] Add focused tests that check the standardized envelope without forcing a
      global manifest schema rewrite.
- [x] Update the 18c handoff prompt, this checklist, and the capability
      snapshot after the behavior landed.

### Milestone 18c implementation note

- This slice should remain manifest-shape focused.
- It may be implemented after 18a and 18b if those helpers make the call sites
  easier to standardize.
- If the envelope would need consensus asset naming decisions, defer that
  specific part until the later abstraction milestone.

### Acceptance evidence

- `docs/realtime_refactor_plans/2026-04-10-milestone-18c-standard-manifest-envelope.md`
- `docs/realtime_refactor_milestone_18c_submission_prompt.md`
- Tests likely to include `tests/test_spec_executor.py`, `tests/test_server.py`,
  and manifest-shape coverage from the migrated task modules
- `README.md`, `docs/capability_maturity.md`, and compatibility docs stay
  aligned with the landed behavior

### Compatibility risks

- Forcing a schema rewrite instead of a thin common envelope helper
- Losing task-specific manifest details while standardizing the envelope
- Mixing the manifest-shape work with naming decisions that belong in later
  milestones

## Milestone 15

Goal: compose workflow graphs from biological intent while keeping generated
plans typed, bounded, reviewable, and registry-constrained.

Status: Complete through Phase 2 (composition preview and approval gating landed)

### Phase 1: Registry-Constrained Composition Algorithm (Complete)

- [x] Create `src/flytetest/composition.py` with registry-constrained graph traversal
- [x] Implement `compose_workflow_path()` for greedy forward-chaining composition
- [x] Implement `_find_compatible_successors()` using registry compatibility metadata
- [x] Implement `_detect_cycles()` to prevent self-loops and cycles
- [x] Implement `bundle_composition_into_workflow_spec()` to freeze paths into specs
- [x] Add comprehensive test suite with 18 passing tests
- [x] Validate against current registry (all 20+ workflows synthesis-eligible)

### Phase 2: Planning Integration & User Approval (Complete)

- [x] Extend `_planning_goal_for_typed_request()` to use composition algorithm for
      broader biological intents that don't match hardcoded patterns
- [x] Add intent-based planning route that can produce either supported
      `WorkflowSpec` preview or structured decline from biological intent
- [x] Require explicit user approval for composed recipe preview via MCP
- [x] Gate execution of composed DAGs until Milestone 19 lands (caching/resumability)
- [x] Update README, `docs/capability_maturity.md`, and handoff prompt
- [x] Validate no regression in existing hardcoded compositions (EVM, repeat+BUSCO, AGAT)
- [x] Keep fallback conservative so unrelated prompts and known day-one missing
      input declines do not get reinterpreted as composed workflows

### Milestone 15 implementation note

- This slice is registry-driven and compatibility-preserving, not an
  unconstrained autonomous graph search.
- It followed Milestone 17 generic asset adoption, Milestone 18 Slurm
  retry/resubmission, and the 18a/18b/18c utility cleanup lane.
- It keeps dynamic workflow creation typed, inspectable, and reviewable
  before execution.
- It only opens the composition and approval path; execution-capable
  composed DAGs stay gated on Milestone 19 caching and resumability.
- The approval boundary sits on the frozen recipe, not on a specific
  backend such as local or Slurm execution.

### Acceptance evidence

- `docs/realtime_refactor_plans/2026-04-08-milestone-15-registry-driven-dynamic-composition.md`
- `docs/realtime_refactor_milestone_15_submission_prompt.md`
- `docs/realtime_refactor_milestone_15_phase_1_summary.md`
- `docs/realtime_refactor_milestone_15_phase_2_summary.md`
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
- The authenticated-access follow-up now makes the supported Slurm topology
  explicit: the MCP/server process runs inside an already-authenticated
  scheduler-capable environment, and unsupported environments return explicit
  limitations instead of generic subprocess failures.

### Acceptance evidence

- `docs/realtime_refactor_plans/2026-04-08-milestone-16-slurm-job-lifecycle-observability.md`
- `docs/realtime_refactor_plans/2026-04-09-milestone-16-part-2-authenticated-slurm-access-boundary.md`
- `docs/realtime_refactor_milestone_16_submission_prompt.md`
- `docs/realtime_refactor_milestone_16_part_2_submission_prompt.md`
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

Status: Complete

### Completed

- [x] Update planner adapters to emit the generic asset names by default
      wherever the workflow semantics are already known.
- [x] Update local workflow outputs and manifest-producing helpers to prefer
      the generic asset types while keeping legacy aliases available.
- [x] Ensure resolver and replay paths still accept historical legacy asset
      names without rewriting manifests.
- [x] Expand tests to cover both legacy alias loading and generic-name
      round-tripping through planner adapters and workflow outputs.
- [x] Update README, `docs/capability_maturity.md`, and the handoff prompt
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
- Tests include `tests/test_planner_adapters.py`, `tests/test_planner_types.py`,
  `tests/test_transcript_contract.py`, and `tests/test_annotation.py`
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

## Asset Cleanup Follow-On Lane

These milestones are the narrow follow-up cleanup lane after Milestone 17.
They are intentionally family-scoped and should be done one family at a time
instead of as a repo-wide rename.

They do not replace the mainline sequencing of `18 -> 15 -> 19`.
They exist so tool-branded asset cleanup can continue in bounded slices when it
materially helps planner clarity, manifest reuse, or future tool interchange.

## Milestone 22

Goal: define and adopt a biology-facing generic asset surface for the current
TransDecoder-backed coding-prediction boundary while retaining legacy replay.

Status: Not started

### Still required

- [ ] Define the biology-facing concept that should replace the current
      TransDecoder-only naming at this stage boundary.
- [ ] Introduce generic sibling asset names or types for the TransDecoder
      output family while keeping the current tool-branded names readable.
- [ ] Update manifest-producing helpers and adapters to prefer the generic
      naming where the biological meaning is already known.
- [ ] Preserve replay of historical manifests that only use the current
      TransDecoder-branded asset names.
- [ ] Add tests for generic-name round-tripping, legacy manifest loading, and
      current manifest emission.
- [ ] Update README, `docs/capability_maturity.md`, and the handoff prompt
      after the behavior lands.

### Milestone 22 implementation note

- This slice should stay limited to the TransDecoder family.
- It should not rename unrelated PASA, protein-evidence, or consensus assets.
- It should only introduce a generic sibling layer once the biology-facing
  concept is named clearly enough to survive future tool variation.

### Acceptance evidence

- `docs/realtime_refactor_plans/2026-04-10-milestone-22-transdecoder-generic-asset-follow-up.md`
- `docs/realtime_refactor_milestone_22_submission_prompt.md`
- Tests likely to include `tests/test_transdecoder.py`,
  `tests/test_planner_types.py`, and any focused adapter or manifest-shape
  coverage
- `README.md`, `docs/capability_maturity.md`, and compatibility docs stay
  aligned with the landed behavior

### Compatibility risks

- Renaming TransDecoder outputs before the biological boundary is named clearly
- Breaking historical PASA-to-TransDecoder manifest replay
- Mixing new generic keys and old tool-branded keys inconsistently across
  emitters and adapters
- Generalizing the TransDecoder family before another implementation path
  actually exists

## Milestone 23

Goal: make the nested protein-evidence alignment assets less Exonerate-specific
while preserving the current top-level protein-evidence bundle contract.

Status: Not started

### Still required

- [ ] Audit which nested protein-evidence assets are too Exonerate-branded for
      future planner or manifest reuse.
- [ ] Define generic sibling names for the nested raw-alignment and converted
      evidence assets where a stable biology-facing meaning exists.
- [ ] Keep the current top-level `protein_evidence_result_bundle` contract
      intact while adding generic nested names.
- [ ] Preserve replay of manifests that still carry the current
      Exonerate-specific nested asset names.
- [ ] Add tests for nested generic-name round-tripping, legacy manifest
      loading, and current manifest emission.
- [ ] Update README, `docs/capability_maturity.md`, and the handoff prompt
      after the behavior lands.

### Milestone 23 implementation note

- This slice should stay limited to the protein-evidence family.
- The top-level bundle name is already acceptable and should not be broadened
  casually.
- The main target is the nested Exonerate-specific naming, not a rewrite of
  the whole protein-evidence workflow.

### Acceptance evidence

- `docs/realtime_refactor_plans/2026-04-10-milestone-23-protein-evidence-nested-asset-cleanup.md`
- `docs/realtime_refactor_milestone_23_submission_prompt.md`
- Tests likely to include `tests/test_protein_evidence.py`,
  `tests/test_planner_types.py`, and any focused adapter or manifest-shape
  coverage
- `README.md`, `docs/capability_maturity.md`, and compatibility docs stay
  aligned with the landed behavior

### Compatibility risks

- Accidentally changing the top-level protein-evidence result-bundle contract
- Breaking manifest replay for current Exonerate-backed results
- Introducing generic nested names that hide useful current-tool truth
- Renaming nested assets without clear downstream planner or reuse benefit

## Milestone 24

Goal: define whether PASA post-EVM refinement should grow a generic annotation-
refinement asset layer, and adopt it only if that abstraction is genuinely
useful.

Status: Not started

### Still required

- [ ] Decide whether the PASA post-EVM refinement boundary needs a generic
      annotation-refinement asset layer at all.
- [ ] If yes, define generic sibling names for the PASA refinement input,
      round, and result-bundle assets while keeping current PASA names
      available.
- [ ] Update manifest emitters and adapters to prefer the generic names only
      if the biological boundary is now explicit enough.
- [ ] Preserve replay of historical PASA refinement manifests.
- [ ] Add tests for generic-name round-tripping, legacy manifest loading, and
      current manifest emission when the generic layer is adopted.
- [ ] Update README, `docs/capability_maturity.md`, and the handoff prompt
      after the behavior lands.

### Milestone 24 implementation note

- This slice may legitimately decide not to introduce a generic sibling layer
  yet if PASA remains the only clear truthful boundary.
- The milestone is about making that decision explicit, not forcing a rename.
- If the answer is “not yet”, the landed result should still improve the docs
  and clarify the boundary.

### Acceptance evidence

- `docs/realtime_refactor_plans/2026-04-10-milestone-24-pasa-refinement-asset-generalization-boundary.md`
- `docs/realtime_refactor_milestone_24_submission_prompt.md`
- Tests likely to include `tests/test_pasa_update.py`, `tests/test_planner_types.py`,
  and any focused adapter or manifest-shape coverage
- `README.md`, `docs/capability_maturity.md`, and compatibility docs stay
  aligned with the landed behavior

### Compatibility risks

- Introducing a generic refinement layer before the repo has a stable
  biology-facing meaning for it
- Breaking PASA update manifest replay while trying to generalize too early
- Hiding that the current implementation is still explicitly PASA-backed
- Forcing rename churn that does not materially help planner or composition
  work

## Milestone 25

Goal: define whether the EVM-prefixed consensus assets need a generic
consensus-annotation layer, and adopt it only when another implementation path
or real planner pressure justifies it.

Status: Not started

### Still required

- [ ] Decide whether the repo currently needs a generic consensus-annotation
      asset layer or should keep the explicit EVM-prefixed names for now.
- [ ] If yes, define generic sibling names for the consensus input,
      preparation, execution, partition, command, and result assets while
      keeping current EVM names available.
- [ ] Update manifest emitters and adapters to prefer the generic names only
      if the broader stage meaning is now explicit enough.
- [ ] Preserve replay of historical EVM manifests and result bundles.
- [ ] Add tests for generic-name round-tripping, legacy manifest loading, and
      current manifest emission when the generic layer is adopted.
- [ ] Update README, `docs/capability_maturity.md`, and the handoff prompt
      after the behavior lands.

### Milestone 25 implementation note

- This slice should not proceed as a casual rename.
- It should only introduce a generic consensus layer if the repo has a real
  need for that abstraction, such as planner pressure or a second
  consensus-engine path.
- If the answer is “not yet”, the milestone can still land as a clarified
  boundary decision and documentation improvement.

### Acceptance evidence

- `docs/realtime_refactor_plans/2026-04-10-milestone-25-consensus-asset-generalization-boundary.md`
- `docs/realtime_refactor_milestone_25_submission_prompt.md`
- Tests likely to include `tests/test_consensus.py`, `tests/test_planner_types.py`,
  and any focused adapter or manifest-shape coverage
- `README.md`, `docs/capability_maturity.md`, and compatibility docs stay
  aligned with the landed behavior

### Compatibility risks

- Renaming EVM assets before the repo has a concrete non-EVM reason for a
  generic consensus layer
- Breaking replay of current pre-EVM, EVM, or consensus result manifests
- Blurring the current truth that the implemented consensus path is EVM-backed
- Broadening the abstraction without any actual execution or planner benefit

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
