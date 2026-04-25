# Step 05 — Closure

Run verification gates, update CHANGELOG.md, and prepare for merge.

---

## Verification gates (all must pass)

### Test suite
```bash
PYTHONPATH=src python -m pytest tests/ -q 2>&1 | tail -5
# Expected: 858 passed, 1 skipped
```

### No stale references
```bash
grep -r "build_gatk_local_sif" src/ scripts/ docs/ README.md SCIENTIST_GUIDE.md
# Must return zero matches

grep -r "scattered_haplotype_caller" src/ docs/ README.md SCIENTIST_GUIDE.md \
    scripts/rcc/README.md
# Must return zero matches (archived docs are exempt)
```

### README line count
```bash
wc -l README.md
# Must be ≤ 300 lines
```

### SCIENTIST_GUIDE has GATK runbook
```bash
grep -n "GATK Germline\|prepare_reference\|run_record_path" SCIENTIST_GUIDE.md
# Must show results in the new runbook section
```

### Registry module_loads correct
```bash
PYTHONPATH=src python -c "
from flytetest.registry import get_entry
cases = [
    ('pre_call_coverage_qc',    {'gatk', 'multiqc'}),
    ('post_call_qc_summary',    {'bcftools', 'multiqc'}),
    ('annotate_variants_snpeff',{'snpeff'}),
    ('small_cohort_filter',     {'gatk'}),
]
for name, must_include in cases:
    ml = set(get_entry(name).compatibility.execution_defaults['module_loads'])
    ok = must_include.issubset(ml)
    print(f'{'OK' if ok else 'FAIL'} {name}: {sorted(ml)}')
"
```

---

## CHANGELOG.md entry

Add a dated entry under today's date (2026-04-24) covering:
- Bug fixes: stale `build_gatk_local_sif.sh` reference in bundles.py;
  duplicate step numbering and wrong MCP parameter in `stage_gatk_local.sh`;
  incorrect `module_loads` hints on `pre_call_coverage_qc`, `post_call_qc_summary`,
  and `annotate_variants_snpeff`
- README rewritten from 656 lines to ≤ 300; now a stable landing page with
  audience-first documentation map
- `SCIENTIST_GUIDE.md`: added GATK germline variant calling chr20 runbook
- `scripts/rcc/README.md`: updated with SIF strategy, module_loads guidance,
  Slurm job lifecycle commands

---

## Merge

```bash
git add -p   # review all changes
git commit -m "docs-polish: bug fixes, README rewrite, GATK runbook"
git checkout main
git merge docs-polish
```

Archive this milestone folder:
```bash
git mv docs/2026-04-24-docs-polish docs/archive/2026-04-24-docs-polish
git commit -m "archive: docs-polish milestone"
```
