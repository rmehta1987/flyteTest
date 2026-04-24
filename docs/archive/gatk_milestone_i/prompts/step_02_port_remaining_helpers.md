# Step 02 — Port Remaining 5 Helpers + Adapt Workflows

## Model

**Sonnet 4.6** (`claude-sonnet-4-6`). Five signature changes plus four
workflow rewires; the VQSR tuple return needs careful mapping across
the two-pass pipeline.

## Goal

1. Port `merge_bam_alignment`, `gather_vcfs`, `variant_recalibrator`,
   `apply_vqsr`, `calculate_genotype_posteriors` to
   `@variant_calling_env.task` with `File`/`Dir` I/O.
2. Update the four workflows that call them:
   `preprocess_sample_from_ubam`, `genotype_refinement`,
   `post_genotyping_refinement`, and `scattered_haplotype_caller`
   (the latter is renamed in Step 03, but updated here).
3. Update existing tests.

## Context

- Milestone I plan §3 (signature table) and §4 Step 02.
- Precedent: Step 01 patterns for File I/O + `project_mkdtemp`.
- Branch: `gatkport-i`.

## What to build

### `src/flytetest/tasks/variant_calling.py`

**`merge_bam_alignment`** — new signature:

```python
@variant_calling_env.task
def merge_bam_alignment(
    reference_fasta: File,
    aligned_bam: File,
    ubam: File,
    sample_id: str,
    gatk_sif: str = "",
) -> File:
    """Merge aligned BAM with unmapped BAM via GATK4 MergeBamAlignment."""
```

**`gather_vcfs`** — new signature:

```python
@variant_calling_env.task
def gather_vcfs(
    gvcfs: list[File],
    sample_id: str,
    gatk_sif: str = "",
) -> File:
    """Merge ordered per-interval GVCFs into a single GVCF via GatherVcfs."""
```

**`variant_recalibrator`** — new signature with tuple return:

```python
@variant_calling_env.task
def variant_recalibrator(
    reference_fasta: File,
    cohort_vcf: File,
    known_sites: list[File],
    known_sites_flags: list[dict],
    mode: str,
    cohort_id: str,
    sample_count: int,  # NEW — used in Step 03 for auto-InbreedingCoeff
    annotations: list[str] | None = None,  # NEW — used in Step 03
    gatk_sif: str = "",
) -> tuple[File, File]:
    """Build a VQSR recalibration model; returns (recal_file, tranches_file)."""
```

(`sample_count` and `annotations` are introduced here as parameters but
the auto-`InbreedingCoeff` logic lands in Step 03. For Step 02, keep
the Milestone D annotation defaults unchanged; just plumb the
parameters through.)

**`apply_vqsr`** — new signature:

```python
@variant_calling_env.task
def apply_vqsr(
    reference_fasta: File,
    input_vcf: File,
    recal_file: File,
    tranches_file: File,
    mode: str,
    cohort_id: str,
    truth_sensitivity_filter_level: float = 0.0,
    gatk_sif: str = "",
) -> File:
    """Apply a VQSR recalibration model to a VCF via ApplyVQSR."""
```

**`calculate_genotype_posteriors`** — new signature (drop the unused
`ref_path` that was already flagged in Milestone H Step 04):

```python
@variant_calling_env.task
def calculate_genotype_posteriors(
    input_vcf: File,
    cohort_id: str,
    supporting_callsets: list[File] | None = None,
    gatk_sif: str = "",
) -> File:
    """Refine genotype posteriors via GATK4 CalculateGenotypePosteriors."""
```

### `src/flytetest/workflows/variant_calling.py`

**`preprocess_sample_from_ubam`** — update the inner
`merge_bam_alignment` call and return type. Parallel to how Step 01
updated `preprocess_sample`.

**`genotype_refinement`** — two-pass VQSR, now with `File`/tuple
plumbing:

```python
@variant_calling_env.task
def genotype_refinement(
    reference_fasta: File,
    joint_vcf: File,
    snp_resources: list[File],
    snp_resource_flags: list[dict],
    indel_resources: list[File],
    indel_resource_flags: list[dict],
    cohort_id: str,
    sample_count: int,
    snp_filter_level: float = 0.0,
    indel_filter_level: float = 0.0,
    gatk_sif: str = "",
) -> File:
    snp_recal, snp_tranches = variant_recalibrator(
        reference_fasta=reference_fasta, cohort_vcf=joint_vcf,
        known_sites=snp_resources, known_sites_flags=snp_resource_flags,
        mode="SNP", cohort_id=cohort_id, sample_count=sample_count,
        gatk_sif=gatk_sif,
    )
    snp_vcf = apply_vqsr(
        reference_fasta=reference_fasta, input_vcf=joint_vcf,
        recal_file=snp_recal, tranches_file=snp_tranches,
        mode="SNP", cohort_id=cohort_id,
        truth_sensitivity_filter_level=snp_filter_level, gatk_sif=gatk_sif,
    )
    indel_recal, indel_tranches = variant_recalibrator(
        reference_fasta=reference_fasta, cohort_vcf=snp_vcf,
        known_sites=indel_resources, known_sites_flags=indel_resource_flags,
        mode="INDEL", cohort_id=cohort_id, sample_count=sample_count,
        gatk_sif=gatk_sif,
    )
    return apply_vqsr(
        reference_fasta=reference_fasta, input_vcf=snp_vcf,
        recal_file=indel_recal, tranches_file=indel_tranches,
        mode="INDEL", cohort_id=cohort_id,
        truth_sensitivity_filter_level=indel_filter_level, gatk_sif=gatk_sif,
    )
```

**`post_genotyping_refinement`** — single-task wrapper around
`calculate_genotype_posteriors`:

```python
@variant_calling_env.task
def post_genotyping_refinement(
    input_vcf: File,
    cohort_id: str,
    supporting_callsets: list[File] | None = None,
    gatk_sif: str = "",
) -> File:
    return calculate_genotype_posteriors(
        input_vcf=input_vcf, cohort_id=cohort_id,
        supporting_callsets=supporting_callsets, gatk_sif=gatk_sif,
    )
```

**`scattered_haplotype_caller`** — update inner `gather_vcfs` call +
return `File`. (Rename happens in Step 03.)

Also update `germline_short_variant_discovery` to consume the new
`preprocess_sample` → `File` return chain that landed in Step 01.

### Registry entries

Update the five task entries and four workflow entries:

- `inputs` tuples reflect `File`/`Dir`.
- Drop `results_dir` everywhere.
- Drop `ref_path` from `calculate_genotype_posteriors` and
  `post_genotyping_refinement` (already flagged in H Step 04).
- Add `sample_count` (int) to `variant_recalibrator` and
  `genotype_refinement` `inputs`.
- Add `annotations` (`list[str]`, optional) to `variant_recalibrator`
  `inputs`.
- `produced_planner_types=("VariantCallSet",)` on `apply_vqsr`,
  `gather_vcfs`, `calculate_genotype_posteriors`.

### Tests

Update classes in `test_variant_calling.py` and
`test_variant_calling_workflows.py` for `File`/tuple returns. The
`genotype_refinement` two-pass test needs particular care: assert that
the second `variant_recalibrator` call receives the SNP-filtered VCF
(not the original `joint_vcf`).

Add `test_genotype_refinement_threads_sample_count_through_both_passes`.

## CHANGELOG

```
### GATK Milestone I Step 02 — Port remaining helpers (YYYY-MM-DD)
- [x] YYYY-MM-DD ported merge_bam_alignment, gather_vcfs, variant_recalibrator, apply_vqsr, calculate_genotype_posteriors to @variant_calling_env.task with File I/O.
- [x] YYYY-MM-DD variant_recalibrator gained sample_count (int) and annotations (list[str] | None); wired through genotype_refinement.
- [x] YYYY-MM-DD four workflows updated: preprocess_sample_from_ubam, genotype_refinement, post_genotyping_refinement, scattered_haplotype_caller.
- [x] YYYY-MM-DD tests migrated; 1 new sample_count threading test added.
- [!] Breaking: all five task signatures changed. Registry inputs updated.
- [!] Breaking: genotype_refinement and post_genotyping_refinement now return File instead of dict.
```

## Verification

```bash
VIRTUAL_ENV=.venv PATH=".venv/bin:$PATH" PYTHONPATH=src \
  pytest tests/test_variant_calling.py tests/test_variant_calling_workflows.py tests/test_registry.py tests/test_registry_manifest_contract.py -xvs
rg "^def " src/flytetest/tasks/variant_calling.py
# expected: zero hits — every def must be preceded by @variant_calling_env.task
rg "results_dir" src/flytetest/tasks/variant_calling.py
# expected: zero hits
rg "ref_path" src/flytetest/tasks/variant_calling.py | rg "calculate_genotype"
# expected: zero hits
```

## Commit message

```
variant_calling: port remaining 5 helpers to Flyte task pattern + sample_count threading
```

## Checklist

- [ ] All five remaining tasks decorated with `@variant_calling_env.task`.
- [ ] No `def` at module level in `tasks/variant_calling.py` without the decorator.
- [ ] No `results_dir` parameter anywhere in the module.
- [ ] `variant_recalibrator` accepts `sample_count` and `annotations`.
- [ ] `calculate_genotype_posteriors` no longer accepts `ref_path`.
- [ ] Four workflows updated to the new return types.
- [ ] Registry entries updated.
- [ ] All tests migrated; new threading test passing.
- [ ] CHANGELOG breaking-change notes present.
- [ ] Step 02 marked Complete in checklist.
