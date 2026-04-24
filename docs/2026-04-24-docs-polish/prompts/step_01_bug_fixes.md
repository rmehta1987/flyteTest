# Step 01 — Bug Fixes

Fix three concrete bugs found by the HPC scientist review. These are small, targeted
changes. Do not refactor surrounding code.

---

## Bug 1 — bundles.py stale fetch_hint

File: `src/flytetest/bundles.py`

The `variant_calling_germline_minimal` bundle `fetch_hints` tuple references
`bash scripts/rcc/build_gatk_local_sif.sh`, a script that was deleted. The correct
scripts are `pull_gatk_image.sh` (GATK SIF) and `build_bwa_mem2_sif.sh` (bwa-mem2 SIF).

Find the fetch_hints tuple for `variant_calling_germline_minimal` (currently line ~167-171).
Replace:
```python
"Build GATK4+bwa-mem2 SIF:     bash scripts/rcc/build_gatk_local_sif.sh",
```
With:
```python
"Pull GATK4 SIF (~8 GB):        bash scripts/rcc/pull_gatk_image.sh",
"Build bwa-mem2+samtools SIF:   bash scripts/rcc/build_bwa_mem2_sif.sh",
```

Verify with:
```bash
grep -r "build_gatk_local_sif" src/ scripts/ docs/  # must return zero matches
```

---

## Bug 2 — stage_gatk_local.sh: duplicate step 3 + wrong MCP parameter

File: `scripts/rcc/stage_gatk_local.sh`

The summary block at the end of the script has two problems:

**Problem A — duplicate step numbering:** Steps read `1. ... 2. ... 3. ... 3. ...`.
Renumber so they are `1. ... 2. ... 3. ... 4.` (four distinct steps).

**Problem B — stale MCP example:** Step 4 (after renumbering) currently says:
```bash
echo "       # then call run_workflow(target='prepare_reference', dry_run=True, ...)"
```
The MCP parameter is `workflow_name`, not `target`. Remove the entire stale
MCP Python snippet (the `echo "  3. Run a dry-run smoke test via MCP:"` block
through the closing `EOF`) — point scientists to SCIENTIST_GUIDE.md instead:
```bash
echo "  4. Run a dry-run smoke test:"
echo "       See SCIENTIST_GUIDE.md — GATK Germline Variant Calling"
```

---

## Bug 3 — Registry module_loads for three workflow entries

File: `src/flytetest/registry/_variant_calling.py`

A global replace earlier added `"gatk"` to all `module_loads` tuples, including three
workflow entries that do not use GATK tools. Find and fix these three entries:

### pre_call_coverage_qc
Uses `collect_wgs_metrics` (GATK) + `multiqc_summarize` → needs both modules.

Change:
```python
"module_loads": ("python/3.11.9", "apptainer/1.4.1", "gatk"),
```
To:
```python
"module_loads": ("python/3.11.9", "apptainer/1.4.1", "gatk", "multiqc"),
```

### post_call_qc_summary
Uses `bcftools_stats` + `multiqc_summarize` — no GATK tools.

Change:
```python
"module_loads": ("python/3.11.9", "apptainer/1.4.1", "gatk"),
```
To:
```python
"module_loads": ("python/3.11.9", "apptainer/1.4.1", "bcftools", "multiqc"),
```

### annotate_variants_snpeff
Uses `snpeff_annotate` only — no GATK tools.

Change:
```python
"module_loads": ("python/3.11.9", "apptainer/1.4.1", "gatk"),
```
To:
```python
"module_loads": ("python/3.11.9", "apptainer/1.4.1", "snpeff"),
```

Note: `small_cohort_filter` uses `variant_filtration` (GATK) — its `"gatk"` entry
is correct. Do not change it.

---

## Verification

```bash
# Confirm stale script reference is gone
grep -r "build_gatk_local_sif" src/ scripts/ docs/

# Confirm registry module_loads
PYTHONPATH=src python -c "
from flytetest.registry import get_entry
checks = {
    'pre_call_coverage_qc': {'gatk', 'multiqc'},
    'post_call_qc_summary': {'bcftools', 'multiqc'},
    'annotate_variants_snpeff': {'snpeff'},
    'small_cohort_filter': {'gatk'},
}
for name, expected in checks.items():
    ml = set(get_entry(name).compatibility.execution_defaults['module_loads'])
    ok = expected.issubset(ml) and 'gatk' not in ml - {'gatk'} or name == 'small_cohort_filter'
    print(f'{name}: {ml}')
"

# Full test suite
PYTHONPATH=src python -m pytest tests/ -q 2>&1 | tail -5
```
