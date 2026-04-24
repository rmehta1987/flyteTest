# MCP Surface Polish — Submission Prompt

You are implementing the mcp-surface-polish milestone for FLyteTest. This milestone
fixes three architectural gaps in the MCP experiment-loop surface identified by an
HPC bioinformatics usability review. All three were explicitly deferred from the
docs-polish milestone.

Read `docs/2026-04-24-mcp-surface-polish/mcp_surface_polish_plan.md` for full context.
Read `src/flytetest/server.py`, `src/flytetest/bundles.py`, and
`src/flytetest/staging.py` before implementing.

## Execution order

Work through the steps in order:

1. `prompts/step_01_runtime_images_key.md` — rename `"sif_path"` → `"gatk_sif"` in
   both GATK bundles so `load_bundle(**bundle)` wires the SIF correctly
2. `prompts/step_02_slurm_recipe_shared_fs.md` — add `shared_fs_roots` parameter
   to `run_slurm_recipe` and `_run_slurm_recipe_impl` so submission runs the same
   preflight contract as `validate_run_recipe`
3. `prompts/step_03_dry_run_staging_findings.md` — populate `staging_findings` in
   both `run_task` and `run_workflow` dry_run blocks by calling `check_offline_staging`
4. `prompts/step_04_closure.md` — run verification gates, update CHANGELOG, merge

## Hard constraints

- `shared_fs_roots=None` (default) must preserve existing behaviour — staging check
  skipped when not provided
- `staging_findings` in dry_run must be informational only — `supported` stays `True`
  even when findings are non-empty
- Do not change the `DryRunReply` dataclass field names or types
- All 858 existing tests must pass after Step 01 and stay passing through Step 04
- Each step must add tests covering the new behaviour
