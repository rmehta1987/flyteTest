# Milestone 10 MCP Recipe Input Binding and BUSCO Enablement

Date: 2026-04-07

Related checklist milestone:
- `docs/realtime_refactor_checklist.md` Milestone 10

## Current State

- The MCP server now uses the recipe-backed flow from Milestone 9.
- `prepare_run_recipe(...)` freezes a supported typed plan into a saved artifact
  under `.runtime/specs/`.
- `run_local_recipe(...)` executes a saved artifact through
  `LocalWorkflowSpecExecutor`.
- `prompt_and_run(...)` remains available as a compatibility alias over
  prepare-then-run.
- Day-one execution remains limited to:
  - `ab_initio_annotation_braker3`
  - `protein_evidence_alignment`
  - `exonerate_align_chunk`
- Typed planning already recognizes `annotation_qc_busco` and requires a
  `QualityAssessmentTarget`.
- `LocalManifestAssetResolver` can resolve planner-facing values from explicit
  bindings, manifest sources, and result bundles, but the MCP recipe tools do
  not yet expose that resolver input contract to clients.

## Target State

- MCP recipe preparation accepts explicit input context in addition to the
  natural-language prompt.
- MCP callers can provide prior manifest paths or result directories so the
  resolver can adapt a repeat-filtering result into a `QualityAssessmentTarget`.
- MCP callers can provide serialized planner bindings directly when they already
  have a `QualityAssessmentTarget`.
- MCP callers can provide runtime bindings that must be frozen into the saved
  recipe, starting with BUSCO choices such as:
  - `busco_lineages_text`
  - `busco_sif`
  - `busco_cpu`
- `annotation_qc_busco` becomes the first post-day-one MCP recipe target only
  after its local handler, saved artifact shape, and result summary behavior are
  covered by tests.
- EggNOG and AGAT remain deferred until the same input-binding pattern is proven
  on BUSCO.

## Scope

This milestone is focused on the MCP recipe input contract and the first
post-day-one handler expansion.

In scope:

- MCP tool argument shape for manifest sources, explicit planner bindings, and
  runtime bindings.
- Planning/server plumbing that passes those inputs into `plan_typed_request`.
- Saved artifact behavior that records resolved planner inputs and explicit
  runtime bindings.
- Local handler wiring for `annotation_qc_busco`.
- Synthetic tests with fake BUSCO execution to avoid requiring the BUSCO binary
  in the default suite.
- Documentation updates that clearly distinguish planned behavior from landed
  behavior until the code is implemented.

Out of scope:

- Enabling every registered workflow as an MCP target.
- EggNOG or AGAT MCP execution.
- Slurm submission or scheduler monitoring.
- Database-backed or remote asset discovery.
- Automatic selection among multiple ambiguous prior manifests.

## Implementation Steps

1. Inspect the current signatures and payloads for:
   - `plan_typed_request(...)`
   - `prepare_run_recipe(...)`
   - `_prepare_run_recipe_impl(...)`
   - `_prompt_and_run_impl(...)`
   - `LocalWorkflowSpecExecutor`
   - `annotation_qc_busco`
2. Define the MCP recipe-preparation input contract. The initial shape should
   stay explicit and JSON-friendly, for example:
   - `manifest_sources: list[str] = []`
   - `explicit_bindings: dict[str, object] = {}`
   - `runtime_bindings: dict[str, object] = {}`
3. Validate manifest source paths before planning:
   - accept a `run_manifest.json` path
   - accept a result directory containing `run_manifest.json`
   - report missing or unreadable sources as structured unsupported input
     rather than throwing an opaque error to the client
4. Pass manifest sources and explicit planner bindings through to
   `plan_typed_request(...)` so BUSCO can resolve `QualityAssessmentTarget`.
5. Merge explicit runtime bindings into the saved binding plan without hiding
   them in prompt text.
6. Add or reuse a helper that maps a resolved `QualityAssessmentTarget` to the
   concrete `annotation_qc_busco` workflow inputs:
   - `repeat_filter_results`
   - `busco_lineages_text`
   - `busco_sif`
   - `busco_cpu`
7. Add `annotation_qc_busco` to the MCP local handler map only after the input
   mapping is covered by tests.
8. Keep `prompt_and_run(...)` as a compatibility alias, and decide whether it
   accepts the same optional input context in this milestone or remains a
   prompt-only convenience wrapper.
9. Update tests for:
   - manifest-source resolution from a repeat-filtering `run_manifest.json`
   - explicit serialized `QualityAssessmentTarget` binding
   - BUSCO runtime bindings persisted in the saved recipe
   - synthetic BUSCO recipe execution through `LocalWorkflowSpecExecutor`
   - structured decline for missing/ambiguous `QualityAssessmentTarget`
10. Update README, MCP docs, capability maturity notes, and the handoff prompt
    once behavior lands.

## Validation Steps

- Run `python3 -m py_compile` on touched Python files.
- Run focused tests:
  - `python3 -m unittest tests.test_planning`
  - `python3 -m unittest tests.test_server`
  - `python3 -m unittest tests.test_spec_executor`
- Run broader discovery if the implementation touches shared planning,
  resolver, or spec-executor behavior:
  - `python3 -m unittest discover tests`
- Run `git diff --check`.

## Blockers or Assumptions

- `annotation_qc_busco` is the first post-day-one MCP target.
- A repeat-filtering result manifest is the preferred source for
  `QualityAssessmentTarget` because BUSCO consumes the repeat-filtered protein
  FASTA boundary.
- The default test path should use synthetic handlers and fixture manifests; it
  should not require a local BUSCO installation.
- The resolver must keep refusing ambiguous discovered inputs instead of
  guessing among multiple manifests.
- EggNOG and AGAT MCP enablement should wait for a follow-up milestone.
