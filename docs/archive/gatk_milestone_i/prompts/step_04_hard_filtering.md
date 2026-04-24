# Step 04 — Hard-Filtering Fallback for Small Cohorts

## Model

**Sonnet 4.6** (`claude-sonnet-4-6`). The filter expressions and
two-pass workflow need accurate transcription from GATK Best
Practices; Haiku has higher risk of paraphrasing thresholds.

## Goal

1. Add `variant_filtration` task wrapping GATK `VariantFiltration`.
2. Add `small_cohort_filter` workflow composing a SNP pass and an
   INDEL pass with the Best Practices default expressions.
3. Registry entries, planner-type wiring, tests, docs.

## Context

- Milestone I plan §4 Step 04 — filter expressions and workflow
  composition.
- GATK docs:
  - `VariantFiltration` tool reference.
  - Best Practices article: `Hard-filtering germline short variants`.
- Use-case: cohorts with <30k SNPs or <2k indels where VQSR training
  fails. The `variant_calling_germline_minimal` fixture is the obvious
  first caller.
- Branch: `gatkport-i`.

## What to build

### `src/flytetest/tasks/variant_calling.py`

Append `variant_filtration` after `calculate_genotype_posteriors`:

```python
# GATK Best Practices hard-filtering defaults.
# Source: https://gatk.broadinstitute.org/hc/en-us/articles/360035531112
_DEFAULT_SNP_FILTER_EXPRESSIONS: tuple[tuple[str, str], ...] = (
    ("QD2", "QD < 2.0"),
    ("FS60", "FS > 60.0"),
    ("MQ40", "MQ < 40.0"),
    ("MQRankSum-12.5", "MQRankSum < -12.5"),
    ("ReadPosRankSum-8", "ReadPosRankSum < -8.0"),
    ("SOR3", "SOR > 3.0"),
)
_DEFAULT_INDEL_FILTER_EXPRESSIONS: tuple[tuple[str, str], ...] = (
    ("QD2", "QD < 2.0"),
    ("FS200", "FS > 200.0"),
    ("ReadPosRankSum-20", "ReadPosRankSum < -20.0"),
    ("SOR10", "SOR > 10.0"),
)


@variant_calling_env.task
def variant_filtration(
    reference_fasta: File,
    input_vcf: File,
    mode: str,
    cohort_id: str,
    filter_expressions: list[tuple[str, str]] | None = None,
    gatk_sif: str = "",
) -> File:
    """Apply GATK VariantFiltration with Best Practices defaults.

    ``mode``: 'SNP' or 'INDEL' — selects default filter expressions when
    ``filter_expressions`` is None.
    ``filter_expressions``: parallel list of (filter_name, expression)
    tuples. Overrides defaults when provided.
    """
    if mode not in ("SNP", "INDEL"):
        raise ValueError(f"mode must be 'SNP' or 'INDEL', got {mode!r}")

    effective = list(filter_expressions) if filter_expressions is not None else (
        list(_DEFAULT_SNP_FILTER_EXPRESSIONS) if mode == "SNP"
        else list(_DEFAULT_INDEL_FILTER_EXPRESSIONS)
    )

    ref = require_path(Path(reference_fasta.download_sync()), "Reference FASTA")
    vcf = require_path(Path(input_vcf.download_sync()), f"VCF for {mode} filtration")

    out_dir = project_mkdtemp(f"gatk_filt_{mode.lower()}_")
    out_vcf = out_dir / f"{cohort_id}_{mode.lower()}_filtered.vcf.gz"

    cmd = ["gatk", "VariantFiltration",
           "-R", str(ref),
           "-V", str(vcf),
           "-O", str(out_vcf)]
    for name, expression in effective:
        cmd.extend(["--filter-name", name, "--filter-expression", expression])

    run_tool(cmd, gatk_sif or "data/images/gatk4.sif",
             [ref.parent, vcf.parent, out_dir])

    require_path(out_vcf, "VariantFiltration output VCF")
    tbi = Path(str(out_vcf) + ".tbi")

    manifest = build_manifest_envelope(
        stage="variant_filtration",
        assumptions=[
            "Filter expressions default to GATK Best Practices hard-filtering thresholds.",
            "Input VCF should be joint-called; filtration marks records rather than removing them.",
            "--create-output-variant-index is implied by .vcf.gz output.",
        ],
        inputs={
            "reference_fasta": str(ref),
            "input_vcf": str(vcf),
            "mode": mode,
            "cohort_id": cohort_id,
            "effective_filter_expressions": effective,
        },
        outputs={
            "filtered_vcf": str(out_vcf),
            "filtered_vcf_index": str(tbi) if tbi.exists() else "",
        },
    )
    _write_json(out_dir / "run_manifest_variant_filtration.json", manifest)
    return File(path=str(out_vcf))
```

Extend `MANIFEST_OUTPUT_KEYS` with `"filtered_vcf"`.

### `src/flytetest/workflows/variant_calling.py`

Add `small_cohort_filter` workflow after `post_genotyping_refinement`:

```python
@variant_calling_env.task
def small_cohort_filter(
    reference_fasta: File,
    joint_vcf: File,
    cohort_id: str,
    snp_filter_expressions: list[tuple[str, str]] | None = None,
    indel_filter_expressions: list[tuple[str, str]] | None = None,
    gatk_sif: str = "",
) -> File:
    """Hard-filter a joint-called VCF with separate SNP and INDEL passes.

    Intended for cohorts too small for VQSR (<30k SNPs / <2k indels).
    Mirrors the two-pass structure of `genotype_refinement`:
      Pass 1 — SNP filtration on joint_vcf.
      Pass 2 — INDEL filtration on the SNP-filtered VCF.
    """
    snp_filtered = variant_filtration(
        reference_fasta=reference_fasta,
        input_vcf=joint_vcf,
        mode="SNP",
        cohort_id=cohort_id,
        filter_expressions=snp_filter_expressions,
        gatk_sif=gatk_sif,
    )
    final_vcf = variant_filtration(
        reference_fasta=reference_fasta,
        input_vcf=snp_filtered,
        mode="INDEL",
        cohort_id=cohort_id,
        filter_expressions=indel_filter_expressions,
        gatk_sif=gatk_sif,
    )
    # Workflow-level manifest with assumptions + both-pass visibility.
    ...
    return final_vcf
```

Extend workflow-module `MANIFEST_OUTPUT_KEYS` with
`"small_cohort_filtered_vcf"`.

### Registry entries

- `variant_filtration`: task, `pipeline_stage_order=17`,
  `accepted_planner_types=("ReferenceGenome","VariantCallSet")`,
  `produced_planner_types=("VariantCallSet",)`,
  `showcase_module="flytetest.tasks.variant_calling"`,
  `description` cites the Best Practices article URL.
- `small_cohort_filter`: workflow, `pipeline_stage_order=8`,
  `accepted_planner_types=("ReferenceGenome","VariantCallSet")`,
  `produced_planner_types=("VariantCallSet",)`,
  `showcase_module="flytetest.workflows.variant_calling"`.

Set `slurm_resource_hints` to `{"cpu": "2", "memory": "8Gi", "walltime": "01:00:00"}`
(filtration is CPU-light).

### `docs/tool_refs/gatk4.md`

Append a `## variant_filtration` section: FLyteTest path, command
shape, Best Practices citation, key argument rationale for
`--filter-name` / `--filter-expression` pairing, composable-after-
joint_call_gvcfs note.

### Tests (`tests/test_variant_calling.py`)

Add `VariantFiltrationTests`:

- `test_default_snp_expressions_applied` — `mode="SNP"`,
  `filter_expressions=None` → cmd contains each of the six default
  name/expression pairs in order.
- `test_default_indel_expressions_applied` — `mode="INDEL"` →
  four default pairs.
- `test_override_filter_expressions` — custom tuple list passes
  through as-is; defaults not present.
- `test_invalid_mode_raises` — `mode="CNV"` raises `ValueError`.
- `test_missing_output_raises` — mock `run_tool` to succeed but
  output file absent → `FileNotFoundError`.
- `test_effective_expressions_recorded_in_manifest` — manifest inputs
  include `effective_filter_expressions`.

Add `SmallCohortFilterWorkflowTests` in
`tests/test_variant_calling_workflows.py`:

- `test_two_passes_chain_snp_into_indel` — assert the second
  `variant_filtration` call's `input_vcf` is the SNP-filtered output,
  not the original `joint_vcf`.
- `test_workflow_accepts_expression_overrides` — custom expressions
  threaded through both passes.
- `test_manifest_tracks_final_filtered_vcf` — workflow manifest
  outputs include `small_cohort_filtered_vcf`.

Add entries for `variant_filtration` to
`tests/test_registry_manifest_contract.py`.

## CHANGELOG

```
### GATK Milestone I Step 04 — Hard-filtering fallback (YYYY-MM-DD)
- [x] YYYY-MM-DD added variant_filtration task (stage 17) wrapping GATK VariantFiltration.
- [x] YYYY-MM-DD added small_cohort_filter workflow (stage 8) — two-pass SNP→INDEL mirroring genotype_refinement.
- [x] YYYY-MM-DD hard-filter defaults sourced verbatim from GATK Best Practices (SNP: QD<2, FS>60, MQ<40, MQRankSum<-12.5, ReadPosRankSum<-8, SOR>3 | INDEL: QD<2, FS>200, ReadPosRankSum<-20, SOR>10).
- [x] YYYY-MM-DD registry entries wired; showcase_module set on both.
- [x] YYYY-MM-DD added 6 VariantFiltrationTests + 3 SmallCohortFilterWorkflowTests.
- [x] YYYY-MM-DD docs/tool_refs/gatk4.md updated.
- Fills the small-cohort gap from the 2026-04-23 review (variant_calling_germline_minimal chr20 fixture now has a valid filtering path without VQSR).
```

## Verification

```bash
VIRTUAL_ENV=.venv PATH=".venv/bin:$PATH" PYTHONPATH=src \
  pytest tests/test_variant_calling.py tests/test_variant_calling_workflows.py tests/test_registry.py tests/test_registry_manifest_contract.py -xvs
rg "variant_filtration" src/flytetest/registry/_variant_calling.py
# expected: registry entry present with pipeline_stage_order=17
rg "small_cohort_filter" src/flytetest/
# expected: registry + workflow + tests
grep -q "variant_filtration" docs/tool_refs/gatk4.md && echo "tool ref updated"
```

## Commit message

```
variant_calling: add variant_filtration + small_cohort_filter (Best Practices hard-filtering)
```

## Checklist

- [ ] `variant_filtration` task implemented with GATK-exact default expressions.
- [ ] Filter expressions cited with the Best Practices URL in docstring or registry description.
- [ ] `small_cohort_filter` workflow runs SNP then INDEL passes.
- [ ] `MANIFEST_OUTPUT_KEYS` extended on both modules.
- [ ] Registry entries include `showcase_module`.
- [ ] 9 new tests passing.
- [ ] `docs/tool_refs/gatk4.md` updated.
- [ ] Step 04 marked Complete in checklist.
