# Milestone 11 MCP EggNOG and AGAT Recipe Enablement

Date: 2026-04-08
Status: Implemented

Related checklist milestone:
- `docs/realtime_refactor_checklist.md` Milestone 11

Archived implementation note:
- The individual EggNOG and AGAT MCP recipe targets landed with explicit
  manifest-source, serialized-binding, and runtime-binding coverage. A composed
  EggNOG-plus-AGAT target, `table2asn`, Slurm, and database-backed discovery
  remain out of scope.

## Current State

- Remote object support is out of scope for the current MCP maturity track.
- Milestone 9 cut the MCP server over to recipe-backed execution.
- Milestone 10 proved explicit recipe input binding with BUSCO:
  - `manifest_sources`
  - `explicit_bindings`
  - `runtime_bindings`
- Current MCP local execution is limited to:
  - `ab_initio_annotation_braker3`
  - `protein_evidence_alignment`
  - `exonerate_align_chunk`
  - `annotation_qc_busco`
- Typed planning already recognizes:
  - `annotation_functional_eggnog`
  - `annotation_postprocess_agat`
  - `annotation_postprocess_agat_conversion`
  - `annotation_postprocess_agat_cleanup`
- EggNOG and AGAT workflows are implemented and registered, and they are
  exposed as runnable MCP recipe targets.

## Target State

- EggNOG and AGAT become runnable MCP recipe targets only after their explicit
  input-binding and local execution behavior is covered by tests.
- The MCP target expansion remains registry-aligned and individual:
  - `annotation_functional_eggnog`
  - `annotation_postprocess_agat`
  - `annotation_postprocess_agat_conversion`
  - `annotation_postprocess_agat_cleanup`
- EggNOG consumes a resolved `QualityAssessmentTarget` from a repeat-filtering
  or compatible QC boundary and maps it to `repeat_filter_results`.
- AGAT statistics and conversion consume a resolved `QualityAssessmentTarget`
  from an EggNOG manifest boundary and map it to `eggnog_results`.
- AGAT cleanup consumes an AGAT conversion manifest boundary and maps it to
  `agat_conversion_results`.
- Runtime choices remain explicit and inspectable in saved recipes:
  - EggNOG: `eggnog_data_dir`, `eggnog_sif`, `eggnog_cpu`, `eggnog_database`
  - AGAT statistics: `annotation_fasta_path`, `agat_sif`
  - AGAT conversion: `agat_sif`
  - AGAT cleanup: no new runtime option beyond the conversion result input
- No composed EggNOG-plus-AGAT pipeline target is added in this slice.

## Scope

In scope:

- MCP contract expansion for the four individual workflow targets listed above.
- Server handler-map expansion for those workflows.
- Executor input mapping from resolved planner values or manifest-derived saved
  bindings into concrete workflow inputs.
- Planner adapter support for any manifest boundary that cannot currently be
  adapted into the needed planner value.
- Synthetic MCP/server and executor tests using fake handlers.
- Documentation updates that describe only the behavior that actually lands.

Out of scope:

- A composed EggNOG-to-AGAT pipeline target.
- Table2asn or submission-prep enablement.
- Slurm submission, scheduling, monitoring, or cancellation.
- Remote object storage or database-backed asset discovery.
- Exposing every registered workflow as MCP-runnable.
- Automatically choosing among multiple candidate manifests.

## Implementation Steps

1. Recheck the current signatures and registry entries for:
   - `annotation_functional_eggnog`
   - `annotation_postprocess_agat`
   - `annotation_postprocess_agat_conversion`
   - `annotation_postprocess_agat_cleanup`
2. Confirm the config constants are the existing names:
   - `EGGNOG_WORKFLOW_NAME`
   - `AGAT_WORKFLOW_NAME`
   - `AGAT_CONVERSION_WORKFLOW_NAME`
   - `AGAT_CLEANUP_WORKFLOW_NAME`
3. Extend `src/flytetest/mcp_contract.py` with `ShowcaseTarget` entries for
   the four workflows without adding a new MCP tool name.
4. Extend `src/flytetest/server.py` so `_local_node_handlers()` maps those
   workflows to the existing workflow handler.
5. Add or reuse executor helpers in `src/flytetest/spec_executor.py` that map:
   - `QualityAssessmentTarget.source_result_dir` or
     `QualityAssessmentTarget.source_manifest_path` to `repeat_filter_results`
     for EggNOG
   - an EggNOG-derived `QualityAssessmentTarget` source to `eggnog_results`
     for AGAT statistics and conversion
   - an AGAT conversion manifest source to `agat_conversion_results` for AGAT
     cleanup
6. Extend `src/flytetest/planner_adapters.py` only where needed so the resolver
   can adapt landed manifest shapes without guessing.
7. Keep `prepare_run_recipe(...)` and `prompt_and_run(...)` on the Milestone 10
   explicit input contract instead of hiding runtime values in prompt text.
8. Add tests for:
   - EggNOG recipe preparation from an explicit manifest source or serialized
     `QualityAssessmentTarget`
   - EggNOG runtime bindings persisted in the saved recipe
   - AGAT statistics and conversion recipe preparation from an EggNOG manifest
   - AGAT cleanup recipe preparation from an AGAT conversion manifest
   - synthetic execution through `LocalWorkflowSpecExecutor`
   - structured decline for missing or ambiguous compatible targets
9. Update README, MCP docs, capability maturity notes, and the checklist only
   after the implementation lands.

## Validation Steps

- Run `python3 -m py_compile` on touched Python files.
- Run focused tests:
  - `python3 -m unittest tests.test_planning`
  - `python3 -m unittest tests.test_server`
  - `python3 -m unittest tests.test_spec_executor`
- Run broader discovery if shared planner, resolver, adapter, executor, or MCP
  contract behavior changes:
  - `python3 -m unittest discover tests`
- Run `git diff --check`.

## Blockers or Assumptions

- This plan assumed individual runnable MCP targets matching the existing
  `RegistryEntry` workflow boundaries. A composed EggNOG-plus-AGAT target
  should be a later milestone if users want that experience.
- Synthetic tests were required; workflow-layer tests alone were not sufficient
  because they do not verify MCP recipe preparation, saved binding replay,
  handler-map exposure, or result summaries.
- EggNOG and AGAT runtime requirements had to stay explicit in the saved
  recipe.
- The resolver kept refusing ambiguous manifest matches instead of selecting
  among multiple compatible prior results.
