# Docs Polish Milestone — Submission Prompt

You are implementing the docs-polish milestone for FLyteTest. This milestone has
two tracks: concrete bug fixes found by a bioinformatics HPC usability review, and
a documentation restructure to make the platform legible to first-time users.

Read `docs/2026-04-24-docs-polish/docs_polish_plan.md` for full context.
Read `docs/readme_replacement_outline.md` for the README rewrite design rationale.
Read `SCIENTIST_GUIDE.md`, `README.md`, and `scripts/rcc/README.md` before editing them.

## Execution order

Work through the steps in order. Each step has a prompt in `prompts/`:

1. `prompts/step_01_bug_fixes.md` — fix bundles.py fetch_hint, stage_gatk_local.sh,
   and registry module_loads on three workflow entries
2. `prompts/step_02_readme_rewrite.md` — rewrite README.md from 656 → ≤300 lines
3. `prompts/step_03_scientist_guide_gatk.md` — add GATK chr20 runbook to SCIENTIST_GUIDE.md
4. `prompts/step_04_rcc_readme.md` — update scripts/rcc/README.md with HPC operator guidance
5. `prompts/step_05_closure.md` — run all verification gates, update CHANGELOG, prepare merge

## Hard constraints

- All 858 tests must pass after Step 01 and remain passing through Step 05
- README must be ≤ 300 lines after Step 02
- Do not remove `docs/gatk_pipeline_overview.md` — it is the detailed inventory that
  the slimmed README links to
- Use actual MCP parameter names: `workflow_name` (not `target`),
  `run_record_path` (not `job_id`) for monitor/retry tools
- The scontrol/sacct distinction (running vs completed jobs) must appear in both
  SCIENTIST_GUIDE.md and scripts/rcc/README.md

## Do not fix in this milestone

- `runtime_images` key mismatch (`"sif_path"` vs `"gatk_sif"` in planning layer)
- `run_slurm_recipe` missing `shared_fs_roots`
- `dry_run` returning empty `staging_findings`

These are architectural and tracked for a separate milestone.
