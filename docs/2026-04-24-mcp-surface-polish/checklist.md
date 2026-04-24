# MCP Surface Polish Checklist

Branch: `mcp-surface-polish`

## Steps

| Step | Name | Status |
|---|---|---|
| 01 | Fix runtime_images key in GATK bundles | [ ] |
| 02 | Add shared_fs_roots to run_slurm_recipe | [ ] |
| 03 | Populate staging_findings in dry_run | [ ] |
| 04 | Closure (tests, CHANGELOG) | [ ] |

## Verification gates (must pass before merge)

- [ ] Full test suite: `PYTHONPATH=src python -m pytest tests/ -q` — 858 pass, 1 skip
- [ ] `BUNDLES["variant_calling_germline_minimal"].runtime_images` has `"gatk_sif"` key
- [ ] `BUNDLES["variant_calling_vqsr_chr20"].runtime_images` has `"gatk_sif"` key
- [ ] `run_slurm_recipe` MCP tool accepts `shared_fs_roots` parameter
- [ ] `run_workflow(..., dry_run=True)` with a missing path returns non-empty `staging_findings`

## Hard constraints

- Do not rename `bwa_sif` — it already matches the task parameter correctly
- `run_slurm_recipe` must remain backwards-compatible: `shared_fs_roots` defaults
  to `None` (staging check skipped if not provided, preserving existing behaviour)
- Do not change `DryRunReply` dataclass shape — only populate `staging_findings`
  from an actual preflight call instead of hardcoding `()`
- New tests must cover each fix
