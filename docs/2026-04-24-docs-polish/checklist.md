# Docs Polish Milestone Checklist

Branch: `docs-polish`

## Steps

| Step | Name | Status |
|---|---|---|
| 01 | Bug fixes (bundles, stage script, registry module_loads) | [ ] |
| 02 | README rewrite (656 → ≤300 lines) | [ ] |
| 03 | SCIENTIST_GUIDE.md: GATK chr20 runbook | [ ] |
| 04 | scripts/rcc/README.md: HPC operator reference | [ ] |
| 05 | Closure (tests, CHANGELOG, merge) | [ ] |

## Verification gates (must pass before merge)

- [ ] `PYTHONPATH=src python -m pytest tests/ -q` — 858 pass, 1 skip
- [ ] `wc -l README.md` ≤ 300
- [ ] `grep "prepare_reference" SCIENTIST_GUIDE.md` — GATK runbook present
- [ ] `grep -r "build_gatk_local_sif" src/ scripts/ docs/` — no matches
- [ ] Registry: `pre_call_coverage_qc` module_loads includes `"multiqc"` not `"gatk"` alone
- [ ] Registry: `post_call_qc_summary` module_loads has `"bcftools"` and `"multiqc"`
- [ ] Registry: `annotate_variants_snpeff` module_loads has `"snpeff"` not `"gatk"`

## Hard constraints

- Do not delete `docs/gatk_pipeline_overview.md` — README links to it
- Do not shorten step prompts below what a fresh agent needs to execute correctly
- README must remain a landing page — no enumerating every task or workflow name
- SCIENTIST_GUIDE runbook must use the actual MCP parameter names (`workflow_name`,
  not `target`; `run_record_path`, not `job_id` for monitor/retry)
