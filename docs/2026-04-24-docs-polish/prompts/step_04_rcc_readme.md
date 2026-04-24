# Step 04 — scripts/rcc/README.md: HPC Operator Reference

Read the current `scripts/rcc/README.md` (621 lines) before starting. Assess what
is still accurate and what has drifted, then update it to be the definitive HPC
operator reference for FLyteTest.

The audience is a cluster operator or HPC-savvy bioinformatician setting up
FLyteTest on a Slurm cluster for the first time, or returning after a long break.

---

## Required sections (add or update as needed)

### Container images (SIFs)

Explain the per-tool SIF strategy: one SIF per tool family, never bundle unrelated
tools. Document which scripts provide which SIFs and the module-first priority.

Table format:

| Tool | Script | Size | When to use instead of module |
|---|---|---|---|
| GATK 4.x | `pull_gatk_image.sh` | ~8 GB | cluster has no `gatk` module |
| bwa-mem2 + samtools | `build_bwa_mem2_sif.sh` | ~300 MB | always (not a standard module) |
| bcftools | `pull_bcftools_sif.sh` | ~200 MB | cluster has no `bcftools` module |
| MultiQC | `pull_multiqc_sif.sh` | ~400 MB | cluster has no `multiqc` module |
| SnpEff | `pull_snpeff_sif.sh` | ~600 MB | always (not a standard module) |

Include the priority rule: prefer `module load <tool>/<version>` when the module is
available; SIFs are the fallback.

### module_loads

Explain the full-replacement semantics: `module_loads` in `resource_request` replaces
`DEFAULT_SLURM_MODULE_LOADS` entirely — it does not merge.

Show the escape hatch for extending defaults:
```python
from flytetest.spec_executor import DEFAULT_SLURM_MODULE_LOADS
resource_request = {
    "queue": "...",
    "account": "...",
    "module_loads": [*DEFAULT_SLURM_MODULE_LOADS, "gatk/4.5.0"],
}
```

Note that `DEFAULT_SLURM_MODULE_LOADS` is the authoritative source — do not
hardcode the version list in docs.

### GATK data staging sequence

Document the end-to-end staging sequence for the chr20 smoke test:

```bash
# 1. Stage reference data + synthetic reads
bash scripts/rcc/stage_gatk_local.sh

# 2. Pull/build container images
bash scripts/rcc/pull_gatk_image.sh        # or use HPC module
bash scripts/rcc/build_bwa_mem2_sif.sh

# 3. (optional) Pull tool SIFs if modules unavailable
bash scripts/rcc/pull_bcftools_sif.sh
bash scripts/rcc/pull_multiqc_sif.sh
bash scripts/rcc/pull_snpeff_sif.sh

# 4. Download SnpEff database if using annotation
bash scripts/rcc/download_snpeff_db.sh GRCh38.105

# 5. Verify all required files
bash scripts/rcc/check_gatk_fixtures.sh
```

### Slurm job lifecycle commands

Document the distinction between `scontrol` (running jobs) and `sacct` (all jobs):

```bash
# While job is running:
squeue -j <job_id>
scontrol show job <job_id>     # only works for active jobs

# After job completes or fails:
sacct -j <job_id> --format=JobID,State,ExitCode,Elapsed,MaxRSS
```

Note that `scontrol` returns nothing for completed jobs — always use `sacct`
for postmortem investigation.

---

## What to preserve from the current README

Keep sections that are still accurate (check each carefully):
- General intro and purpose
- Prerequisites (Python version, virtualenv setup)
- Any sections covering annotation pipeline scripts (braker3, PASA, etc.) that
  are still correct — these predate GATK and should not be removed

## What to remove or update

- Any reference to `build_gatk_local_sif.sh` (deleted) → replace with
  `pull_gatk_image.sh` + `build_bwa_mem2_sif.sh`
- Any hardcoded module version lists → point to `DEFAULT_SLURM_MODULE_LOADS`
- Any stale workflow or task names (e.g. `scattered_haplotype_caller` →
  `sequential_interval_haplotype_caller`)

---

## Verification

```bash
grep "build_gatk_local_sif\|scattered_haplotype_caller" scripts/rcc/README.md
# must return nothing

grep "scontrol\|sacct" scripts/rcc/README.md
# must show the lifecycle distinction is documented
```
