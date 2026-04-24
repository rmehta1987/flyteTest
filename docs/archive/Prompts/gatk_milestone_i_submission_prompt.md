# GATK Milestone I Submission Prompt

**TL;DR:** Phase 3 scientific completeness. All 9 previously plain-Python GATK helpers
are now `@variant_calling_env.task`-decorated with `File`/`Dir` I/O (Milestones D-G pattern,
applied backward). Hard-filter fallback, QC bookends, and SnpEff annotation fill the
P2/P3 biology gaps from the 2026-04-23 review.

## What Was Built

| Scope | Item |
|---|---|
| **9 ported tasks** | bwa_mem2_index, bwa_mem2_mem, sort_sam, mark_duplicates, merge_bam_alignment, gather_vcfs, variant_recalibrator, apply_vqsr, calculate_genotype_posteriors |
| **5 new tasks** | variant_filtration (stage 17), collect_wgs_metrics (18), bcftools_stats (19), multiqc_summarize (20), snpeff_annotate (21) |
| **1 renamed workflow** | scattered_haplotype_caller → sequential_interval_haplotype_caller |
| **4 new workflows** | small_cohort_filter (8), pre_call_coverage_qc (9), post_call_qc_summary (10), annotate_variants_snpeff (11) |
| **VQSR enhancement** | InbreedingCoeff auto-added for SNP mode ≥10 samples (GATK Best Practices) |
| **RG parameterization** | library_id + platform on bwa_mem2_mem |
| **MCP surface** | 14 new TASK_PARAMETERS entries; planning intent extended |
| **Docs** | gatk_pipeline_overview.md refreshed; 4 new tool refs |

## Key Files

| File | Change |
|---|---|
| `src/flytetest/tasks/variant_calling.py` | All 9 helpers ported; 5 new tasks added; MANIFEST_OUTPUT_KEYS extended |
| `src/flytetest/workflows/variant_calling.py` | All workflows consume File returns; 4 new workflows + rename |
| `src/flytetest/registry/_variant_calling.py` | All 14 new/ported entries updated with File I/O and showcase_module |
| `src/flytetest/server.py` | TASK_PARAMETERS entries for 14 new/ported tasks |
| `src/flytetest/planning.py` | _VARIANT_CALLING_KEYWORDS + _VARIANT_CALLING_TARGET_MAP extended |
| `tests/test_variant_calling.py` | All 9 ported task tests migrated to File API; 3 RG + 6 annotation + 6 filtration + 8 QC + 4 snpeff tests added |
| `tests/test_variant_calling_workflows.py` | All 7 workflow tests migrated; 12 new Step 04-06 workflow tests |
| `docs/gatk_pipeline_overview.md` | 21-task + 11-workflow DAG; deferred items updated |
| `docs/tool_refs/picard_wgs_metrics.md` | New |
| `docs/tool_refs/bcftools.md` | New |
| `docs/tool_refs/multiqc.md` | New |
| `docs/tool_refs/snpeff.md` | New |
| `scripts/rcc/download_snpeff_db.sh` | New SnpEff database fetch helper |

## Verification

```bash
# Full test suite
PYTHONPATH=src python -m pytest
# Expected: 858 passed, 1 skipped

# No plain defs at module level in tasks
rg "^def " src/flytetest/tasks/variant_calling.py
# Expected: zero hits

# No results_dir in tasks
rg "results_dir" src/flytetest/tasks/variant_calling.py
# Expected: zero hits

# No scattered_haplotype_caller in live code
rg "scattered_haplotype_caller" src/ tests/ docs/ \
  --glob '!docs/gatk_milestone_f/**' --glob '!CHANGELOG.md'
# Expected: only test assertion lines

# showcase_module count (≥20)
rg "showcase_module" src/flytetest/registry/_variant_calling.py | grep -v '""' | wc -l
# Expected: 32
```

## Scope Boundaries

| Deferred | Milestone |
|---|---|
| Real scheduler-level scatter (job arrays / per-interval sbatch) | K |
| VEP variant annotation | K |
| MultiQC config customization | K |
| Somatic variant calling (Mutect2) | Out of scope |
| CNV / structural variant calling | Out of scope |

## Phase 3 Status

**Complete.** End-to-end germline variant calling from preprocessing through
calling → hard-filter or VQSR → CGP → QC → SnpEff annotation. All 21 task stages
and 11 workflow stages are implemented, decorated, and MCP-reachable.
