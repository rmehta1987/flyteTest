# MCP Surface Polish Milestone Plan — 2026-04-24

## Context

The HPC scientist review identified three architectural gaps in the MCP surface
that were explicitly deferred from the docs-polish milestone. All three affect the
scientist-facing experiment loop in ways that reduce trust or create hidden failure
modes:

1. The GATK bundle `runtime_images` key `"sif_path"` doesn't match any workflow/task
   parameter (`gatk_sif`), so `load_bundle(**bundle)` doesn't wire the GATK SIF
   through automatically — the scientist must know to pass `gatk_sif` explicitly.

2. `run_slurm_recipe(artifact_path)` accepts no `shared_fs_roots`, so the offline
   staging preflight (which `validate_run_recipe` runs correctly) is silently skipped
   at actual submission time. Validation and submission use different contracts.

3. `run_workflow(..., dry_run=True)` always returns `staging_findings=()`. The user
   must know to call `validate_run_recipe` separately to run the preflight, defeating
   the purpose of dry_run as an inspect-before-submit tool.

## Pillars

1. **Self-explanatory bundles** — `load_bundle(**bundle)` must wire the GATK SIF
   correctly without additional manual steps
2. **Consistent preflight** — validation and submission use the same staging contract
3. **Honest dry_run** — dry_run runs preflight and surfaces findings in the reply

## Steps

| # | Name | Scope |
|---|---|---|
| 01 | Fix runtime_images key in GATK bundles | `bundles.py` |
| 02 | Add shared_fs_roots to run_slurm_recipe | `server.py` |
| 03 | Populate staging_findings in dry_run | `server.py` (run_task + run_workflow) |
| 04 | Closure | Tests, CHANGELOG |

## Key file locations

- `src/flytetest/bundles.py` — `variant_calling_germline_minimal` and
  `variant_calling_vqsr_chr20` both use `"sif_path"` key (lines ~156, ~220)
- `src/flytetest/server.py`:
  - `run_slurm_recipe` (line ~2853) — takes only `artifact_path`
  - `_run_slurm_recipe_impl` (line ~2788) — calls `.submit()` without `shared_fs_roots`
  - `run_task` dry_run block (line ~1923) — `staging_findings=()`
  - `run_workflow` dry_run block (line ~2203) — `staging_findings=()`
  - `validate_run_recipe` (line ~2861) — correctly accepts and passes `shared_fs_roots`

## Out of scope

- Reply shape normalization across all MCP tools (larger refactor)
- `list_bundles` / `load_bundle` response format changes

## Verification gates

- [ ] `PYTHONPATH=src python -m pytest tests/ -q` — 858 pass, 1 skip
- [ ] `from flytetest.bundles import BUNDLES; BUNDLES["variant_calling_germline_minimal"].runtime_images`
      → keys must include `"gatk_sif"` not `"sif_path"`
- [ ] `run_slurm_recipe` signature includes `shared_fs_roots`
- [ ] `run_workflow(..., dry_run=True)` returns non-empty `staging_findings` when
      a referenced path does not exist
