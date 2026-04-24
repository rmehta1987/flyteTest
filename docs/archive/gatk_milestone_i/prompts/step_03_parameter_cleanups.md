# Step 03 — VQSR Parameterization + Honest Scatter Rename

## Model

**Sonnet 4.6** (`claude-sonnet-4-6`). The rename touches many files
(registry, workflows, tests, docs); careful sed-like work with a review
pass.

## Goal

1. Land the VQSR annotation parameterization logic in
   `variant_recalibrator` (parameters were plumbed in Step 02; the
   auto-`InbreedingCoeff` behavior ships here).
2. Rename `scattered_haplotype_caller` to
   `sequential_interval_haplotype_caller` across the repo and document
   its synchronous execution honestly in the manifest.

## Context

- Milestone I plan §4 Step 03 — VQSR semantics and rename rationale.
- GATK Best Practices: `InbreedingCoeff` required for VQSR training
  when the cohort has ≥10 unrelated samples; optional otherwise.
- Branch: `gatkport-i`.

## What to build

### VQSR annotation logic (`src/flytetest/tasks/variant_calling.py`)

In `variant_recalibrator` (ported in Step 02), replace the hardcoded
annotation list with the parameter + auto-add logic:

```python
_DEFAULT_SNP_ANNOTATIONS = ("QD", "MQ", "MQRankSum", "ReadPosRankSum", "FS", "SOR")
_DEFAULT_INDEL_ANNOTATIONS = ("QD", "FS", "SOR")
_INBREEDING_COEFF_MIN_SAMPLES = 10


def _resolve_vqsr_annotations(
    mode: str,
    sample_count: int,
    annotations: list[str] | None,
) -> list[str]:
    """Return the effective `-an` list for VariantRecalibrator."""
    if annotations is not None:
        return list(annotations)
    if mode == "SNP":
        base = list(_DEFAULT_SNP_ANNOTATIONS)
    elif mode == "INDEL":
        base = list(_DEFAULT_INDEL_ANNOTATIONS)
    else:
        raise ValueError(f"mode must be 'SNP' or 'INDEL', got {mode!r}")
    if mode == "SNP" and sample_count >= _INBREEDING_COEFF_MIN_SAMPLES:
        if "InbreedingCoeff" not in base:
            base.append("InbreedingCoeff")
    return base
```

Inside `variant_recalibrator`, call
`_resolve_vqsr_annotations(mode, sample_count, annotations)` and use
the result for the `-an` flags. Record the effective list in the
manifest:

```python
manifest = build_manifest_envelope(
    stage="variant_recalibrator",
    assumptions=[
        "InbreedingCoeff is auto-added to SNP-mode annotations when sample_count >= 10 (GATK Best Practices).",
        "Override via the `annotations` parameter when non-default sets are needed.",
        ...
    ],
    inputs={..., "effective_annotations": effective},
    ...
)
```

### Honest scatter rename

**Rename `scattered_haplotype_caller` → `sequential_interval_haplotype_caller`.**

Files to update (grep the repo):

```bash
rg -l "scattered_haplotype_caller" src/ tests/ docs/
```

Expected list (adjust to actual hits):

- `src/flytetest/workflows/variant_calling.py` — rename `def`, update
  manifest `stage=`, update any local references.
- `src/flytetest/registry/_variant_calling.py` — rename registry entry
  `name=`; keep `pipeline_stage_order=6`; update `biological_stage=`.
- `tests/test_variant_calling_workflows.py` — rename test class
  (`ScatteredHaplotypeCallerTests` →
  `SequentialIntervalHaplotypeCallerTests`), update test method names,
  update string assertions.
- `tests/test_registry.py` / `tests/test_registry_manifest_contract.py`
  — any string literal.
- `docs/gatk_pipeline_overview.md` — DAG diagram + workflow inventory
  table.
- `docs/tool_refs/gatk4.md` — if cited.
- `docs/gatk_milestone_f/` — DO NOT touch archive docs; leave historical
  references intact.
- `CHANGELOG.md` — DO NOT rewrite history; leave prior entries as-is
  and document the rename in the Step 03 entry.

**Manifest assumption update** in the renamed workflow:

```python
manifest = build_manifest_envelope(
    stage="sequential_interval_haplotype_caller",
    assumptions=[
        "Intervals must be non-empty and in genomic order for GatherVcfs.",
        "Execution is synchronous — all intervals run serially inside one task "
        "invocation. True scheduler-level scatter (job arrays or per-interval "
        "sbatch fan-out) is Milestone K HPC work.",
        "BAM must be BQSR-recalibrated (preprocess_sample or preprocess_sample_from_ubam must have run first).",
    ],
    ...
)
```

Remove the pre-existing `"Scatter is synchronous (Python for loop); no job arrays."`
line — it's now the dedicated second assumption.

### Tests

Add `VariantRecalibratorAnnotationTests` in
`tests/test_variant_calling.py`:

- `test_snp_defaults_below_threshold` — `sample_count=5`, `mode="SNP"`,
  `annotations=None` → effective list equals
  `["QD","MQ","MQRankSum","ReadPosRankSum","FS","SOR"]`.
- `test_snp_auto_adds_inbreeding_coeff_at_threshold` —
  `sample_count=10`, `mode="SNP"` → `"InbreedingCoeff"` appended.
- `test_snp_auto_adds_inbreeding_coeff_above_threshold` —
  `sample_count=50` → same result as above.
- `test_indel_never_auto_adds_inbreeding_coeff` — `sample_count=50`,
  `mode="INDEL"` → defaults unchanged.
- `test_explicit_annotations_override_defaults_and_auto_add` —
  `annotations=["QD","DP"]`, `sample_count=50`, `mode="SNP"` →
  exactly `["QD","DP"]`.
- `test_effective_annotations_recorded_in_manifest` — assert the
  manifest input dict contains `effective_annotations`.

Update existing `SequentialIntervalHaplotypeCaller` tests to consume
the renamed symbol.

## CHANGELOG

```
### GATK Milestone I Step 03 — VQSR parameterization + honest scatter rename (YYYY-MM-DD)
- [x] YYYY-MM-DD variant_recalibrator: annotations override + auto-add InbreedingCoeff when mode==SNP and sample_count>=10.
- [x] YYYY-MM-DD effective annotation list recorded in manifest inputs.
- [x] YYYY-MM-DD renamed scattered_haplotype_caller → sequential_interval_haplotype_caller everywhere (src, tests, docs).
- [x] YYYY-MM-DD manifest assumptions updated to describe synchronous-serial execution explicitly.
- [x] YYYY-MM-DD added 6 VariantRecalibratorAnnotationTests.
- [!] Breaking: scattered_haplotype_caller no longer exists; use sequential_interval_haplotype_caller.
- Deferred: real scheduler-level scatter (job arrays / per-interval sbatch) is Milestone K.
```

## Verification

```bash
VIRTUAL_ENV=.venv PATH=".venv/bin:$PATH" PYTHONPATH=src \
  pytest tests/test_variant_calling.py tests/test_variant_calling_workflows.py tests/test_registry.py -xvs
rg "scattered_haplotype_caller" src/ tests/ docs/ --glob '!docs/gatk_milestone_*/' --glob '!CHANGELOG.md'
# expected: zero hits (archives and CHANGELOG may retain historical mentions)
rg "InbreedingCoeff" src/flytetest/tasks/variant_calling.py
# expected: at least one match inside _resolve_vqsr_annotations
```

## Commit message

```
variant_calling: parameterize VQSR annotations (auto InbreedingCoeff ≥10 samples); rename scattered→sequential_interval_haplotype_caller
```

## Checklist

- [ ] `_resolve_vqsr_annotations` helper covers SNP/INDEL modes.
- [ ] `InbreedingCoeff` auto-added only when `mode="SNP"` and
      `sample_count >= 10` and `annotations is None`.
- [ ] Effective annotation list recorded in manifest.
- [ ] `scattered_haplotype_caller` removed from all live code paths.
- [ ] Archive docs (`docs/gatk_milestone_f/`) and CHANGELOG entries
      untouched; rename documented only in the new Step 03 CHANGELOG
      entry.
- [ ] Manifest assumption explicitly calls out synchronous-serial
      execution and names Milestone K.
- [ ] 6 new annotation tests passing; renamed workflow tests passing.
- [ ] Step 03 marked Complete in checklist.
