Use this prompt when handing the MCP recipe input-binding and BUSCO enablement
slice off to another Codex session or when starting the next implementation
pass.

This BUSCO slice has now landed in code. Keep this prompt as a reference for
the manifest-source / explicit-binding / runtime-binding pattern, and start the
next follow-on slice from EggNOG or AGAT instead of redoing BUSCO work.

```text
You are continuing the FLyteTest MCP recipe-backed execution work under the rules in:

- /home/rmeht/Projects/flyteTest/AGENTS.md
- /home/rmeht/Projects/flyteTest/DESIGN.md
- /home/rmeht/Projects/flyteTest/mcp_implementation_plan.md
- /home/rmeht/Projects/flyteTest/docs/realtime_refactor_checklist.md
- /home/rmeht/Projects/flyteTest/docs/realtime_refactor_plans/archive/2026-04-07-milestone-10-mcp-recipe-input-binding-busco.md
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

- Milestone 9 completed the day-one MCP cutover to recipe-backed execution.
- The current MCP recipe flow is:
  `plan_typed_request(...)` -> saved artifact under `.runtime/specs/` ->
  `LocalWorkflowSpecExecutor`.
- `prepare_run_recipe(...)`, `run_local_recipe(...)`, and `prompt_and_run(...)`
  are the MCP-facing tools for that flow.
- Day-one MCP execution remains limited to `ab_initio_annotation_braker3`,
  `protein_evidence_alignment`, and `exonerate_align_chunk`.
- Milestone 10 should widen the input-binding contract before it widens the
  runnable handler map.
- `annotation_qc_busco` is the first post-day-one MCP expansion target.
- BUSCO requires a `QualityAssessmentTarget`, usually adapted from an
  `annotation_repeat_filtering` result manifest or supplied explicitly by the
  caller.
- BUSCO runtime choices such as `busco_lineages_text`, optional `busco_sif`, and
  `busco_cpu` must be explicit in the saved recipe.
- EggNOG and AGAT MCP execution are intentionally deferred to Milestone 11,
  which should reuse the BUSCO input-binding pattern.

Task:

1. Read `docs/realtime_refactor_plans/archive/2026-04-07-milestone-10-mcp-recipe-input-binding-busco.md`.
2. Investigate the current implementation state in `server.py`, `planning.py`,
   `resolver.py`, `planner_adapters.py`, `spec_artifacts.py`,
   `spec_executor.py`, `registry.py`, and the relevant tests.
3. Define and implement the smallest JSON-friendly MCP input contract for
   recipe preparation, covering:
   - manifest sources, such as `run_manifest.json` paths or result directories
   - explicit planner bindings, especially serialized `QualityAssessmentTarget`
   - runtime bindings, especially `busco_lineages_text`, `busco_sif`, and
     `busco_cpu`
4. Pass those inputs into typed planning and saved recipe preparation without
   relying on prompt text as a hidden transport for runtime parameters.
5. Enable `annotation_qc_busco` in the MCP local handler map only after
   manifest-source resolution, runtime binding persistence, and synthetic local
   execution are covered by tests.
6. Keep `prompt_and_run(...)` available as a compatibility alias. If you add the
   same optional input context to it, update its docs and tests in the same
   change.
7. Update README, MCP docs, capability maturity notes, MCP contract docs, and
   the refactor checklist so they describe only the behavior that has actually
   landed.
8. Mark completed Milestone 10 checklist items in
   `docs/realtime_refactor_checklist.md` when they land.
9. Stop when blocked, when a compatibility guardrail would be at risk, or when
   the next step would widen into EggNOG, AGAT, Slurm, or database-backed asset
   discovery.

Important constraints:

- Do not expose every registered workflow as MCP-runnable.
- Do not add EggNOG or AGAT MCP handlers in this slice.
- Do not hide BUSCO runtime requirements inside natural-language prompt text.
- Do not guess when multiple manifest sources could satisfy
  `QualityAssessmentTarget`.
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
