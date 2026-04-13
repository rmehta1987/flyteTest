This was the handoff prompt for the Milestone 11 MCP recipe input-binding and
EggNOG/AGAT enablement slice. The implementation has now landed, so keep this
file as historical context for the slice rather than as a fresh start prompt.

```text
You are continuing the FLyteTest MCP recipe-backed execution work under the rules in:

- /home/rmeht/Projects/flyteTest/AGENTS.md
- /home/rmeht/Projects/flyteTest/DESIGN.md
- /home/rmeht/Projects/flyteTest/mcp_implementation_plan.md
- /home/rmeht/Projects/flyteTest/docs/realtime_refactor_checklist.md
- /home/rmeht/Projects/flyteTest/docs/realtime_refactor_plans/archive/2026-04-08-milestone-11-mcp-eggnog-agat.md
- /home/rmeht/Projects/flyteTest/docs/realtime_refactor_plans/README.md
- /home/rmeht/Projects/flyteTest/README.md
- /home/rmeht/Projects/flyteTest/docs/mcp_showcase.md
- /home/rmeht/Projects/flyteTest/docs/capability_maturity.md

Read the relevant repo-local guides under `.codex/` for the area you touch,
especially:

- /home/rmeht/Projects/flyteTest/.codex/documentation.md
- /home/rmeht/Projects/flyteTest/.codex/testing.md
- /home/rmeht/Projects/flyteTest/.codex/workflows.md
- /home/rmeht/Projects/flyteTest/.codex/tasks.md

Context:

- Milestone 9 completed the MCP cutover to recipe-backed execution.
- Milestone 10 proved the explicit recipe input contract with BUSCO:
  `manifest_sources`, `explicit_bindings`, and `runtime_bindings`.
- The current MCP recipe flow is:
  `plan_typed_request(...)` -> saved artifact under `.runtime/specs/` ->
  `LocalWorkflowSpecExecutor`.
- `prepare_run_recipe(...)`, `run_local_recipe(...)`, and `prompt_and_run(...)`
  are the MCP-facing tools for that flow.
- Current MCP local execution is limited to:
  `ab_initio_annotation_braker3`, `protein_evidence_alignment`,
  `exonerate_align_chunk`, and `annotation_qc_busco`.
- EggNOG and AGAT were the next planned MCP recipe targets because their
  biological workflows are already implemented and registered.
- This slice assumes individual targets matching existing `RegistryEntry`
  boundaries, not a composed EggNOG-plus-AGAT pipeline target.

Task:

1. Read `docs/realtime_refactor_plans/archive/2026-04-08-milestone-11-mcp-eggnog-agat.md`.
2. Investigate the current implementation state in `server.py`, `planning.py`,
   `resolver.py`, `planner_adapters.py`, `spec_artifacts.py`,
   `spec_executor.py`, `registry.py`, and the relevant tests.
3. Confirm the current workflow signatures and config constants:
   - `annotation_functional_eggnog`
   - `annotation_postprocess_agat`
   - `annotation_postprocess_agat_conversion`
   - `annotation_postprocess_agat_cleanup`
   - `EGGNOG_WORKFLOW_NAME`
   - `AGAT_WORKFLOW_NAME`
   - `AGAT_CONVERSION_WORKFLOW_NAME`
   - `AGAT_CLEANUP_WORKFLOW_NAME`
4. Extend the MCP target contract and local handler map for those four
   workflows without adding new MCP tool names and without exposing every
   registered workflow.
5. Reuse the Milestone 10 JSON-friendly input contract:
   - `manifest_sources: list[str] = []`
   - `explicit_bindings: dict[str, object] = {}`
   - `runtime_bindings: dict[str, object] = {}`
6. Add or reuse executor and adapter helpers for concrete workflow input
   mapping:
   - EggNOG: resolved repeat-filter or QC target -> `repeat_filter_results`
   - AGAT stats/conversion: EggNOG-derived target -> `eggnog_results`
   - AGAT cleanup: AGAT conversion manifest target -> `agat_conversion_results`
7. Keep runtime bindings explicit and saved in the recipe:
   - EggNOG: `eggnog_data_dir`, `eggnog_sif`, `eggnog_cpu`,
     `eggnog_database`
   - AGAT statistics: `annotation_fasta_path`, `agat_sif`
   - AGAT conversion: `agat_sif`
8. Add synthetic tests for MCP recipe preparation, saved binding persistence,
   local executor routing with fake handlers, result summaries, and structured
   declines for missing or ambiguous compatible targets.
9. Update README, MCP docs, capability maturity notes, MCP contract docs, and
   the refactor checklist so they describe only the behavior that has actually
   landed.
10. Mark completed Milestone 11 checklist items in
    `docs/realtime_refactor_checklist.md` when they land.
11. Stop when blocked, when a compatibility guardrail would be at risk, or when
    the next step would widen into composed pipelines, table2asn, Slurm, or
    database-backed asset discovery.

Important constraints:

- Do not expose every registered workflow as MCP-runnable.
- Do not add a composed EggNOG-plus-AGAT pipeline target in this slice.
- Do not add table2asn or submission-prep MCP execution.
- Do not hide EggNOG or AGAT runtime requirements inside natural-language
  prompt text.
- Do not guess when multiple manifest sources could satisfy the requested
  planner target.
- Do not overwrite unrelated user changes in a dirty worktree.
- Keep README, DESIGN, checklist docs, registry metadata, planner behavior, MCP
  contract, and tests aligned.

Validation:

- Run `python3 -m py_compile` on touched Python files.
- Run `python3 -m unittest tests.test_planning`.
- Run `python3 -m unittest tests.test_server`.
- Run `python3 -m unittest tests.test_spec_executor`.
- Run `python3 -m unittest discover tests` if shared planning/resolver/executor
  behavior changes broadly.
- Run `git diff --check`.

Report back with:

- checklist item(s) completed
- files changed
- validation run
- current checklist status
- new or archived plan documents created
- remaining blockers or assumptions
```
